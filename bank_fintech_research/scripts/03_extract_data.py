#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
从PDF年报中提取财务数据并生成Markdown
同时从已有Markdown的正文中重新提取正确的财务数据
输出: annual_reports/analysis/panel_data_raw.json
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Optional, Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 金融科技关键词库（与pdf_to_markdown.py保持一致，并做扩展）
FINTECH_KEYWORDS = [
    '人工智能', 'AI', '机器学习', '大数据', '风控模型', '算法',
    '数字金融', '智能信贷', '金融科技', 'Fintech', 'fintech',
    '云计算', '区块链', '人脸识别', '智能风控', '开放银行',
    '数字化转型', '数字转型', '线上化', '智能化', '科技赋能',
    '科技输出', '移动互联', '物联网', '5G',
    '智能营销', '智能客服', '智能投顾', '智能网点',
    '无纸化', '电子化', '网络金融', '直销银行',
]

# 18家银行配置
BANKS = {
    # 6家国有大型银行
    '工商银行': 'state_owned',
    '建设银行': 'state_owned',
    '农业银行': 'state_owned',
    '中国银行': 'state_owned',
    '交通银行': 'state_owned',
    '邮储银行': 'state_owned',
    # 10家全国性股份制商业银行
    '平安银行': 'joint_stock',
    '光大银行': 'joint_stock',
    '民生银行': 'joint_stock',
    '招商银行': 'joint_stock',
    '兴业银行': 'joint_stock',
    '中信银行': 'joint_stock',
    '华夏银行': 'joint_stock',
    '浦发银行': 'joint_stock',
    '浙商银行': 'joint_stock',
    '渤海银行': 'joint_stock',
    # 2家非上市银行（单独处理）
    '广发银行': 'joint_stock',
    '恒丰银行': 'joint_stock',
}


def extract_npl_from_text(text: str) -> Optional[float]:
    """从文本中提取不良贷款率"""
    patterns = [
        # 格式1: "不良贷款率（注1） 1.36%" 或 "不良贷款率 1.36"
        r'不良贷款率[^0-9\n]*?(\d+\.\d+)\s*%',
        r'不良貸款率[^0-9\n]*?(\d+\.\d+)\s*%',
        # 格式2: 表格中 "不良贷款率（%）\n1.36"
        r'不良贷款率[（(（][^）)）\n]*[）)）]\s*\n?\s*(\d+\.\d+)',
        r'不良贷款率[^0-9\n]{0,30}(\d+\.\d+)',
        r'不良貸款率[^0-9\n]{0,30}(\d+\.\d+)',
        # 格式3: "NPL ratio 1.36%"
        r'NPL\s+ratio\s*[:\s]+(\d+\.\d+)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            val = float(m)
            if 0.1 <= val <= 8.0:  # 合理的NPL范围
                return val
    return None


def extract_roe_from_text(text: str) -> Optional[float]:
    """从文本中提取加权平均净资产收益率(ROE)"""
    patterns = [
        r'加权平均净资产收益率[^0-9\n]*?(\d+\.\d+)\s*%',
        r'加权平均净資產收益率[^0-9\n]*?(\d+\.\d+)\s*%',
        r'加权平均净资产收益率[（(][^）)\n]*[）)]\s*\n?\s*(\d+\.\d+)',
        r'加权平均净资产收益率[^0-9\n]{0,30}(\d+\.\d+)',
        r'ROAE[^0-9\n]{0,10}(\d+\.\d+)\s*%',
        r'ROAE\s*为\s*(\d+\.\d+)\s*%',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            val = float(m)
            if 2.0 <= val <= 30.0:  # 合理的ROE范围
                return val
    return None


def extract_roa_from_text(text: str) -> Optional[float]:
    """从文本中提取平均总资产回报率(ROA)"""
    patterns = [
        r'平均总资产回报率[^0-9\n]*?(\d+\.\d+)\s*%',
        r'平均總資產回報率[^0-9\n]*?(\d+\.\d+)\s*%',
        r'平均总资产回报率[^0-9\n]{0,30}(\d+\.\d+)',
        r'ROAA[^0-9\n]{0,10}(\d+\.\d+)\s*%',
        r'ROAA\s*为\s*(\d+\.\d+)\s*%',
        r'平均资产回报率[^0-9\n]*?(\d+\.\d+)\s*%',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            val = float(m)
            if 0.1 <= val <= 3.0:  # 合理的ROA范围
                return val
    return None


def extract_total_assets_from_text(text: str) -> Optional[float]:
    """从文本中提取总资产（亿元）"""
    patterns = [
        # "总资产 461,286.68亿元"
        r'总资产[^0-9\n]{0,10}([\d,]+\.?\d*)\s*亿元',
        r'資產總額[^0-9\n]{0,10}([\d,]+\.?\d*)\s*億元',
        r'总资产[^0-9\n]{0,10}([\d,]+\.?\d*)\s*亿',
        # "资产总额17,327.34亿元"
        r'资产总额[^0-9\n]{0,10}([\d,]+\.?\d*)\s*亿元',
        r'资产总额[^0-9\n]{0,10}([\d,]+\.?\d*)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for m in matches:
            val_str = m.replace(',', '')
            try:
                val = float(val_str)
                if val > 1000:  # 至少1000亿才合理
                    return val
            except:
                pass
    return None


def count_fintech_keywords(text: str) -> Tuple[Dict[str, int], int]:
    """统计金融科技关键词频率"""
    text_lower = text.lower()
    counts = {}
    for kw in FINTECH_KEYWORDS:
        kw_lower = kw.lower()
        count = text_lower.count(kw_lower)
        if count > 0:
            counts[kw] = count
    total = sum(counts.values())
    # 字符数（中文）
    char_count = len(re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text))
    return counts, total, char_count


def process_pdf_to_markdown(pdf_path: Path, md_dir: Path) -> Optional[Dict]:
    """处理单个PDF，生成Markdown并提取数据"""
    try:
        import pdfplumber
    except ImportError:
        logger.error("请先安装 pdfplumber: pip install pdfplumber")
        return None

    logger.info(f"处理PDF: {pdf_path.name}")
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"  总页数: {len(pdf.pages)}")
            for i, page in enumerate(pdf.pages):
                t = page.extract_text()
                if t:
                    text += t + "\n"
    except Exception as e:
        logger.error(f"  提取失败: {e}")
        return None

    logger.info(f"  提取字符: {len(text)}")

    # 提取财务数据
    npl = extract_npl_from_text(text)
    roe = extract_roe_from_text(text)
    roa = extract_roa_from_text(text)
    total_assets = extract_total_assets_from_text(text)

    logger.info(f"  NPL={npl}%, ROE={roe}%, ROA={roa}%, 总资产={total_assets}亿")

    # 统计关键词
    kw_counts, kw_total, char_count = count_fintech_keywords(text)
    logger.info(f"  金融科技词频: {kw_total}次")

    # 生成Markdown
    parts = pdf_path.stem.split('_')
    bank_name = parts[0]
    year_match = re.search(r'(\d{4})', pdf_path.stem)
    year = int(year_match.group(1)) if year_match else None

    md_lines = [
        f"# {pdf_path.stem}\n",
        "## 基本信息\n",
        f"- 文件: {pdf_path.name}\n",
        f"- 字符数: {len(text)}\n",
        "\n## 财务指标\n",
        "| 指标 | 数值 |\n",
        "|------|------|\n",
    ]
    if npl is not None:
        md_lines.append(f"| 不良贷款率(%) | {npl} |\n")
    if roe is not None:
        md_lines.append(f"| 加权平均净资产收益率(%) | {roe} |\n")
    if roa is not None:
        md_lines.append(f"| 平均总资产回报率(%) | {roa} |\n")
    if total_assets is not None:
        md_lines.append(f"| 总资产(亿元) | {total_assets:,.0f} |\n")

    md_lines += [
        "\n## 金融科技关键词词频\n",
        "| 关键词 | 出现次数 |\n",
        "|--------|----------|\n",
    ]
    for kw, cnt in sorted(kw_counts.items(), key=lambda x: -x[1]):
        md_lines.append(f"| {kw} | {cnt} |\n")
    md_lines.append(f"\n**合计: {kw_total} 次**\n")

    md_lines += [
        "\n## 正文内容（节选）\n",
        "```\n",
        text[:5000],
        "\n```\n",
    ]

    md_content = "".join(md_lines)
    md_path = md_dir / f"{pdf_path.stem}.md"
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    logger.info(f"  Markdown已保存: {md_path.name}")

    return {
        'bank': bank_name,
        'year': year,
        'npl': npl,
        'roe': roe,
        'roa': roa,
        'total_assets': total_assets,
        'fintech_total': kw_total,
        'fintech_keywords': kw_counts,
        'char_count': char_count,
        'raw_char_count': len(text),
        'source': 'pdf',
    }


def process_existing_markdown(md_path: Path) -> Optional[Dict]:
    """从已有的Markdown文件中重新提取财务数据"""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析文件名
    bank_name = md_path.stem.split('_')[0]
    year_match = re.search(r'(\d{4})', md_path.stem)
    year = int(year_match.group(1)) if year_match else None

    # 获取正文部分（``` 块内）
    body_match = re.search(r'```\n(.*?)```', content, re.DOTALL)
    body_text = body_match.group(1) if body_match else content

    # 从正文提取财务数据（更准确）
    npl = extract_npl_from_text(body_text)
    roe = extract_roe_from_text(body_text)
    roa = extract_roa_from_text(body_text)
    total_assets = extract_total_assets_from_text(body_text)

    # 从Markdown的关键词表格中提取词频
    kw_section = re.search(r'## 金融科技关键词词频\n(.*?)\n\*\*合计', content, re.DOTALL)
    kw_counts = {}
    kw_total = 0
    if kw_section:
        kw_text = kw_section.group(1)
        for line in kw_text.split('\n'):
            match = re.match(r'\|\s*(.+?)\s*\|\s*(\d+)\s*\|', line)
            if match and match.group(1) not in ('关键词', '---'):
                kw_counts[match.group(1)] = int(match.group(2))
        kw_total = sum(kw_counts.values())

    # 如果从正文提取失败，尝试从表格中获取
    if npl is None:
        # 从已有的财务指标表格中提取
        npl_match = re.search(r'不良贷款率\(%\)\s*\|\s*([\d.]+)', content)
        if npl_match:
            val = float(npl_match.group(1))
            if 0.1 <= val <= 8.0:
                npl = val

    if roe is None:
        roe_match = re.search(r'加权平均净资产收益率\(%\)\s*\|\s*([\d.]+)', content)
        if roe_match:
            val = float(roe_match.group(1))
            if 2.0 <= val <= 30.0:
                roe = val

    # 字符数
    char_count_match = re.search(r'字符数:\s*(\d+)', content)
    raw_char_count = int(char_count_match.group(1)) if char_count_match else 0
    char_count = raw_char_count  # markdown中已经是全文字符数

    return {
        'bank': bank_name,
        'year': year,
        'npl': npl,
        'roe': roe,
        'roa': roa,
        'total_assets': total_assets,
        'fintech_total': kw_total,
        'fintech_keywords': kw_counts,
        'char_count': char_count,
        'raw_char_count': raw_char_count,
        'source': 'markdown',
    }


def main():
    base_dir = Path("../data")
    md_dir = base_dir / "markdown"
    pdf_dir = base_dir / "pdf"
    analysis_dir = base_dir / "analysis"
    analysis_dir.mkdir(exist_ok=True)
    md_dir.mkdir(exist_ok=True)

    results = []

    # 所有18家银行：优先从PDF提取（重新生成Markdown），PDF不存在则从已有Markdown提取
    for bank in BANKS.keys():
        for year in [2023, 2024, 2025]:
            pdf_name = f"{bank}_{year}年度报告.pdf"
            pdf_path = pdf_dir / pdf_name
            md_name = f"{bank}_{year}年度报告.md"
            md_path = md_dir / md_name

            if pdf_path.exists():
                logger.info(f"从PDF提取: {bank} {year}")
                result = process_pdf_to_markdown(pdf_path, md_dir)
                if result:
                    results.append(result)
                    logger.info(f"  {bank} {year}: NPL={result['npl']}%, ROE={result['roe']}%")
            elif md_path.exists():
                logger.warning(f"无PDF，从Markdown提取: {bank} {year}")
                result = process_existing_markdown(md_path)
                if result:
                    results.append(result)
            else:
                logger.error(f"PDF和Markdown均不存在: {bank} {year}")

    # 3. 保存原始数据
    output_path = analysis_dir / "panel_data_raw.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"\n原始数据已保存: {output_path}")
    logger.info(f"总计: {len(results)} 条记录")

    # 4. 统计缺失情况
    print("\n=== 数据完整性检查 ===")
    for bank in BANKS.keys():
        for year in [2023, 2024, 2025]:
            rec = next((r for r in results if r['bank'] == bank and r['year'] == year), None)
            if rec:
                npl_str = f"{rec['npl']:.2f}%" if rec['npl'] else "缺失"
                roe_str = f"{rec['roe']:.2f}%" if rec['roe'] else "缺失"
                kw_str = f"{rec['fintech_total']}次"
                print(f"  {bank} {year}: NPL={npl_str}, ROE={roe_str}, 词频={kw_str}")
            else:
                print(f"  {bank} {year}: ⚠️ 记录缺失")

    return results


if __name__ == '__main__':
    main()
