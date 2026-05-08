#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
PDF转Markdown脚本
提取文本并保留表格结构，输出Markdown格式
"""

import os
import pdfplumber
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class FinancialData:
    """财务指标数据"""
    bank: str = None
    year: int = None
    npl: float = None        # 不良贷款率
    roe: float = None       # 加权平均净资产收益率
    roa: float = None        # 平均总资产回报率
    total_assets: float = None  # 总资产(亿元)
    loan_to_deposit: float = None  # 存贷比


class PDFAnalyzer:
    """PDF分析器"""

    # 金融科技关键词库
    FINTECH_KEYWORDS = [
        '人工智能', 'AI', '机器学习', '大数据', '风控模型', '算法',
        '数字金融', '智能信贷', '金融科技', 'Fintech', ' fintech',
        '云计算', '区块链', '人脸识别', '智能风控', '开放银行',
        '数字化转型', '数字转型', '线上化', '智能化', '科技赋能',
        '科技输出', '金融科技', '移动互联', '物联网', '5G',
        '智能风控', '智能营销', '智能客服', '智能投顾', '智能网点',
        '无纸化', '电子化', '网络金融', '直销银行', '民营银行'
    ]

    def __init__(self, pdf_path: Path):
        self.pdf_path = pdf_path
        self.text = ""
        self.tables = []
        self.pages_text = []

    def extract_text(self) -> str:
        """提取PDF全文"""
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        self.pages_text.append(text)
                        self.text += text + "\n"
            return self.text
        except Exception as e:
            logger.error(f"提取文本失败 {self.pdf_path.name}: {e}")
            return ""

    def extract_tables(self) -> List:
        """提取表格"""
        try:
            with pdfplumber.open(self.pdf_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    if tables:
                        self.tables.extend(tables)
            return self.tables
        except Exception as e:
            logger.error(f"提取表格失败 {self.pdf_path.name}: {e}")
            return []

    def extract_financial_data(self) -> FinancialData:
        """提取财务指标"""
        data = FinancialData()

        # 从文件名解析
        parts = self.pdf_path.stem.split('_')
        data.bank = parts[0]
        year_match = re.search(r'(\d{4})', parts[1])
        if year_match:
            data.year = int(year_match.group(1))

        # 在文本中搜索财务指标
        for page_text in self.pages_text:
            # 不良贷款率 - 格式: "不良贷款率（7） 1.36 1.38 1.38 1.42" 取第一个数
            if data.npl is None:
                npl_match = re.search(r'不良贷款率[（(][^\)]+\）\）?\s*([\d.]+)', page_text)
                if npl_match:
                    val = float(npl_match.group(1))
                    # 合理的NPL范围是0.5-3%
                    if 0.1 <= val <= 5:
                        data.npl = val
                    else:
                        # 尝试找多个数字，取第一个合理的
                        npl_all = re.findall(r'不良贷款率[（(][^\)]+\）\）?\s*([\d.]+)', page_text)
                        for npl_val in npl_all:
                            if 0.1 <= float(npl_val) <= 5:
                                data.npl = float(npl_val)
                                break

            # ROE - 加权平均净资产收益率 - 格式: "加权平均净资产收益率（2） 10.66 11.43 11.45 12.15" 取第一个数
            if data.roe is None:
                roe_match = re.search(r'加权平均净资产收益率[（(][^\)]+\）\）?\s*([\d.]+)', page_text)
                if roe_match:
                    val = float(roe_match.group(1))
                    # 合理的ROE范围是5-20%
                    if 3 <= val <= 25:
                        data.roe = val

            # ROA - 平均总资产回报率
            if data.roa is None:
                roa_match = re.search(r'平均总资产回报率[（(][^\)]+\）\）?\s*([\d.]+)', page_text)
                if roa_match:
                    val = float(roa_match.group(1))
                    if 0.1 <= val <= 3:
                        data.roa = val

            # 总资产
            if data.total_assets is None:
                assets_match = re.search(r'总资产[^\d]*([\d,]+)\s*亿元', page_text)
                if assets_match:
                    assets_str = assets_match.group(1).replace(',', '')
                    data.total_assets = float(assets_str)

        return data

    def count_fintech_keywords(self) -> Dict[str, int]:
        """统计金融科技关键词出现次数"""
        counts = {}
        text_lower = self.text.lower()

        for keyword in self.FINTECH_KEYWORDS:
            keyword_lower = keyword.lower()
            count = text_lower.count(keyword_lower)
            if count > 0:
                counts[keyword] = count

        return counts

    def to_markdown(self) -> str:
        """转换为Markdown格式"""
        md = []

        # 添加标题
        md.append(f"# {self.pdf_path.stem}\n")

        # 添加基本信息
        md.append("## 基本信息\n")
        md.append(f"- 文件: {self.pdf_path.name}\n")
        md.append(f"- 字符数: {len(self.text)}\n")

        # 添加财务指标
        fin_data = self.extract_financial_data()
        md.append("\n## 财务指标\n")
        md.append(f"| 指标 | 数值 |\n")
        md.append(f"|------|------|\n")
        if fin_data.npl:
            md.append(f"| 不良贷款率(%) | {fin_data.npl} |\n")
        if fin_data.roe:
            md.append(f"| 加权平均净资产收益率(%) | {fin_data.roe} |\n")
        if fin_data.roa:
            md.append(f"| 平均总资产回报率(%) | {fin_data.roa} |\n")
        if fin_data.total_assets:
            md.append(f"| 总资产(亿元) | {fin_data.total_assets:,.0f} |\n")

        # 添加金融科技关键词统计
        fintech_counts = self.count_fintech_keywords()
        md.append("\n## 金融科技关键词词频\n")
        if fintech_counts:
            md.append("| 关键词 | 出现次数 |\n")
            md.append("|--------|----------|\n")
            sorted_counts = sorted(fintech_counts.items(), key=lambda x: x[1], reverse=True)
            for keyword, count in sorted_counts:
                md.append(f"| {keyword} | {count} |\n")
            md.append(f"\n**合计: {sum(fintech_counts.values())} 次**\n")
        else:
            md.append("未找到金融科技关键词\n")

        # 添加正文内容（简化版）
        md.append("\n## 正文内容（节选）\n")
        md.append("```\n")
        md.append(self.text[:5000])  # 只显示前5000字
        md.append("\n```\n")

        return "".join(md)


def process_all_pdfs(pdf_dir: Path, output_dir: Path):
    """批量处理PDF"""
    output_dir.mkdir(parents=True, exist_ok=True)
    md_dir = output_dir / "markdown"
    data_dir = output_dir / "data"
    md_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(pdf_dir.glob("*.pdf"))
    logger.info(f"找到 {len(pdf_files)} 个PDF文件")

    all_financial_data = []
    all_fintech_data = []

    for pdf_path in sorted(pdf_files):
        logger.info(f"处理: {pdf_path.name}")

        try:
            analyzer = PDFAnalyzer(pdf_path)

            # 提取文本
            text = analyzer.extract_text()
            logger.info(f"  提取文本: {len(text)} 字符")

            # 提取财务数据
            fin_data = analyzer.extract_financial_data()
            logger.info(f"  财务数据: NPL={fin_data.npl}%, ROE={fin_data.roe}%")

            # 统计关键词
            fintech_counts = analyzer.count_fintech_keywords()
            total_keywords = sum(fintech_counts.values())
            logger.info(f"  金融科技关键词: {total_keywords} 次")

            # 保存Markdown
            md_content = analyzer.to_markdown()
            md_path = md_dir / f"{pdf_path.stem}.md"
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            logger.info(f"  保存Markdown: {md_path.name}")

            # 记录数据
            all_financial_data.append({
                'bank': fin_data.bank,
                'year': fin_data.year,
                'npl': fin_data.npl,
                'roe': fin_data.roe,
                'roa': fin_data.roa,
                'total_assets': fin_data.total_assets,
                'pdf_file': pdf_path.name,
                'md_file': md_path.name
            })

            all_fintech_data.append({
                'bank': fin_data.bank,
                'year': fin_data.year,
                'total_keywords': total_keywords,
                'keywords': fintech_counts,
                'total_chars': len(text)
            })

        except Exception as e:
            logger.error(f"  处理失败: {e}")

    # 保存数据
    with open(data_dir / 'financial_data.json', 'w', encoding='utf-8') as f:
        json.dump(all_financial_data, f, ensure_ascii=False, indent=2)

    with open(data_dir / 'fintech_keywords.json', 'w', encoding='utf-8') as f:
        json.dump(all_fintech_data, f, ensure_ascii=False, indent=2)

    logger.info(f"\n处理完成!")
    logger.info(f"  成功处理: {len(all_financial_data)} 份")
    logger.info(f"  Markdown目录: {md_dir}")
    logger.info(f"  数据目录: {data_dir}")

    return all_financial_data, all_fintech_data


if __name__ == '__main__':
    base_dir = Path("../data")
    pdf_dir = base_dir / "pdf"
    output_dir = base_dir

    logger.info("=" * 60)
    logger.info("开始PDF处理")
    logger.info("=" * 60)

    process_all_pdfs(pdf_dir, output_dir)
