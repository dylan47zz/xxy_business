#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
PDF转TXT脚本
批量将年报PDF转换为TXT文本
"""

import os
import pdfplumber
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PDFReport:
    """PDF年报信息"""
    bank_name: str
    year: int
    pdf_path: Path


def extract_text_from_pdf(pdf_path: Path) -> Optional[str]:
    """从PDF提取文本"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    all_text.append(text)
            return '\n'.join(all_text)
    except Exception as e:
        logger.error(f"提取文本失败 {pdf_path.name}: {e}")
        return None


def extract_financial_data(pdf_path: Path) -> dict:
    """从PDF提取关键财务数据"""
    data = {
        'npl': None,      # 不良贷款率
        'roe': None,      # 净资产收益率
        'roa': None,      # 总资产收益率
        'total_assets': None,  # 总资产
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if not text:
                    continue

                # 提取不良贷款率
                if data['npl'] is None:
                    import re
                    # 匹配"不良贷款率"或"不良率"后面的数字
                    npl_match = re.search(r'不良贷款率[^\d]*([\d.]+)', text)
                    if npl_match:
                        data['npl'] = float(npl_match.group(1))

                # 提取加权平均净资产收益率 (ROE)
                if data['roe'] is None:
                    roe_match = re.search(r'加权平均净资产收益率[^\d]*([\d.]+)', text)
                    if roe_match:
                        data['roe'] = float(roe_match.group(1))

                # 提取平均总资产回报率 (ROA)
                if data['roa'] is None:
                    roa_match = re.search(r'平均总资产回报率[^\d]*([\d.]+)', text)
                    if roa_match:
                        data['roa'] = float(roa_match.group(1))

                # 提取总资产
                if data['total_assets'] is None:
                    assets_match = re.search(r'总资产[^\d]*([\d,]+)亿元', text)
                    if assets_match:
                        assets_str = assets_match.group(1).replace(',', '')
                        data['total_assets'] = float(assets_str)

    except Exception as e:
        logger.warning(f"提取财务数据失败 {pdf_path.name}: {e}")

    return data


def convert_pdfs_to_txt(pdf_dir: Path, txt_dir: Path, data_dir: Path):
    """批量转换PDF为TXT并提取财务数据"""
    txt_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = list(pdf_dir.glob("*.pdf"))
    logger.info(f"找到 {len(pdf_files)} 个PDF文件")

    results = []
    financial_data = []

    for pdf_path in sorted(pdf_files):
        logger.info(f"处理: {pdf_path.name}")

        # 提取文本
        text = extract_text_from_pdf(pdf_path)
        if text:
            # 保存TXT
            txt_name = pdf_path.stem + '.txt'  # 去掉.pdf
            txt_path = txt_dir / txt_name
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(text)
            logger.info(f"  TXT保存成功: {len(text)} 字符")

            # 提取财务数据
            fin_data = extract_financial_data(pdf_path)
            # 从文件名解析银行名和年份
            parts = pdf_path.stem.split('_')
            fin_data['bank'] = parts[0]
            # 提取年份（如 "2023年度报告" -> "2023"）
            import re
            year_match = re.search(r'(\d{4})', parts[1])
            if year_match:
                fin_data['year'] = int(year_match.group(1))
            else:
                fin_data['year'] = None
            fin_data['pdf_file'] = pdf_path.name
            financial_data.append(fin_data)

            logger.info(f"  财务数据: NPL={fin_data['npl']}%, ROE={fin_data['roe']}%")

            results.append({
                'bank': fin_data['bank'],
                'year': fin_data['year'],
                'txt_file': txt_name,
                'chars': len(text)
            })
        else:
            logger.error(f"  文本提取失败!")

    # 保存财务数据
    import json
    data_file = data_dir / 'financial_data.json'
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(financial_data, f, ensure_ascii=False, indent=2)
    logger.info(f"财务数据已保存: {data_file}")

    return results, financial_data


if __name__ == '__main__':
    # 目录设置
    base_dir = Path("annual_reports")
    pdf_dir = base_dir / "pdf"
    txt_dir = base_dir / "txt"
    data_dir = base_dir / "data"

    logger.info("=" * 60)
    logger.info("开始PDF转TXT处理")
    logger.info("=" * 60)

    results, financial_data = convert_pdfs_to_txt(pdf_dir, txt_dir, data_dir)

    logger.info("\n" + "=" * 60)
    logger.info("处理完成!")
    logger.info(f"  成功转换: {len(results)} 份")
    logger.info(f"  TXT目录: {txt_dir}")
    logger.info(f"  数据目录: {data_dir}")
    logger.info("=" * 60)
