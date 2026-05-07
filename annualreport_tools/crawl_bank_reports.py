#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
年报数据抓取脚本
目标：15家A股上市银行 2023-2025年年报
数据源：巨潮资讯 cninfo.com.cn
"""

import os
import time
import random
import requests
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Optional
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BankConfig:
    """银行配置"""
    name: str
    search_keyword: str  # 搜索关键词


# 15家目标银行配置
BANKS = [
    BankConfig("工商银行", "工商银行"),
    BankConfig("建设银行", "建设银行"),
    BankConfig("农业银行", "农业银行"),
    BankConfig("中国银行", "中国银行"),
    BankConfig("交通银行", "交通银行"),
    BankConfig("邮储银行", "邮储银行"),
    BankConfig("平安银行", "平安银行"),
    BankConfig("光大银行", "光大银行"),
    BankConfig("民生银行", "民生银行"),
    BankConfig("招商银行", "招商银行"),
    BankConfig("兴业银行", "兴业银行"),
    BankConfig("中信银行", "中信银行"),
    BankConfig("华夏银行", "华夏银行"),
    BankConfig("浦发银行", "浦发银行"),
    BankConfig("浙商银行", "浙商银行"),
]

# 目标年份
YEARS = [2023, 2024, 2025]


@dataclass
class AnnualReport:
    """年报信息"""
    bank_name: str
    year: int
    title: str
    url: str
    sec_code: str
    announcement_id: str


class CNINFOClient:
    """巨潮资讯API客户端"""

    BASE_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
    DOWNLOAD_BASE = "https://static.cninfo.com.cn"

    SEARCH_HEADERS = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Host": "www.cninfo.com.cn",
        "Origin": "https://www.cninfo.com.cn",
        "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "X-Requested-With": "XMLHttpRequest"
    }

    DOWNLOAD_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.cninfo.com.cn/"
    }

    def __init__(self):
        self.search_session = requests.Session()
        self.search_session.headers.update(self.SEARCH_HEADERS)

    def search_reports(self, keyword: str, year: int) -> List[AnnualReport]:
        """搜索某银行某年的年报"""
        reports = []

        # 年报通常在次年3-5月发布
        search_start = f"{year + 1}-03-01"
        search_end = f"{year + 1}-06-30"

        data = {
            "pageNum": 1,
            "pageSize": 30,
            "column": "szse",
            "tabName": "fulltext",
            "plate": "sz;sh",
            "searchkey": keyword,
            "category": "category_ndbg_szsh",
            "seDate": f"{search_start}~{search_end}"
        }

        try:
            resp = self.search_session.post(self.BASE_URL, data=data, timeout=30)
            result = resp.json()

            for item in (result.get('announcements') or []):
                title = item.get('announcementTitle', '')

                # 过滤完整年报（不含摘要、英文版、H股版）
                if not self._is_valid_annual_report(title, year):
                    continue

                # 检查是否已是A股年报（排除H股）
                if 'H股' in title or '(H股' in title or 'H股' in title:
                    continue

                report = AnnualReport(
                    bank_name=item.get('secName', keyword),
                    year=year,
                    title=title,
                    url=f"{self.DOWNLOAD_BASE}/{item.get('adjunctUrl', '')}",
                    sec_code=item.get('secCode', ''),
                    announcement_id=item.get('announcementId', '')
                )
                reports.append(report)

        except Exception as e:
            logger.error(f"搜索失败 [{keyword} {year}年]: {e}")

        return reports

    def _is_valid_annual_report(self, title: str, year: int) -> bool:
        """判断是否是有效的年度报告"""
        # 必须包含年份和"年度报告"
        if str(year) not in title:
            return False
        if '年度报告' not in title:
            return False

        # 排除项
        exclude_keywords = ['摘要', '英文', '已取消', '修订', '更正', '补充']
        for kw in exclude_keywords:
            if kw in title:
                return False

        return True

    def download_pdf(self, report: AnnualReport, output_dir: Path) -> Optional[Path]:
        """下载年报PDF"""
        try:
            # 使用 stream=True 下载大文件
            resp = requests.get(report.url, timeout=60, stream=True, headers=self.DOWNLOAD_HEADERS)

            if resp.status_code != 200:
                logger.warning(f"下载失败 [{report.bank_name} {report.year}年]: HTTP {resp.status_code}")
                return None

            # 直接保存文件（cninfo的PDF通常是有效的）
            filename = f"{report.bank_name}_{report.year}年度报告.pdf"
            filepath = output_dir / filename

            file_size = 0
            with open(filepath, 'wb') as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    file_size += len(chunk)

            logger.info(f"下载成功: {filename} ({file_size/1024:.1f} KB)")
            return filepath

        except Exception as e:
            logger.error(f"下载异常 [{report.bank_name} {report.year}年]: {e}")
            return None


def crawl_annual_reports():
    """执行年报抓取"""
    # 创建输出目录
    output_dir = Path("annual_reports")
    output_dir.mkdir(exist_ok=True)

    # 创建子目录
    pdf_dir = output_dir / "pdf"
    pdf_dir.mkdir(exist_ok=True)

    client = CNINFOClient()

    all_reports = []  # 记录所有找到的年报
    successful_downloads = []  # 成功下载的年报

    logger.info("=" * 60)
    logger.info("开始抓取15家银行2023-2025年年报")
    logger.info("=" * 60)

    for bank in BANKS:
        logger.info(f"\n>>> 正在处理: {bank.name}")

        for year in YEARS:
            # 搜索年报
            reports = client.search_reports(bank.search_keyword, year)
            logger.info(f"  {year}年: 找到 {len(reports)} 份年报")

            for report in reports:
                all_reports.append(report)

                # 下载PDF
                filepath = client.download_pdf(report, pdf_dir)
                if filepath:
                    successful_downloads.append({
                        'bank': report.bank_name,
                        'year': report.year,
                        'title': report.title,
                        'path': str(filepath)
                    })

                # 随机延时，避免限流
                time.sleep(random.uniform(1.0, 2.0))

    # 保存下载记录
    log_path = output_dir / "download_log.txt"
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write("年报下载记录\n")
        f.write("=" * 80 + "\n\n")
        for item in successful_downloads:
            f.write(f"{item['bank']} | {item['year']}年 | {item['title']}\n")
            f.write(f"  路径: {item['path']}\n\n")

    # 打印统计
    logger.info("\n" + "=" * 60)
    logger.info("抓取完成!")
    logger.info(f"  找到年报: {len(all_reports)} 份")
    logger.info(f"  成功下载: {len(successful_downloads)} 份")
    logger.info(f"  保存目录: {output_dir.absolute()}")
    logger.info("=" * 60)

    return successful_downloads


if __name__ == '__main__':
    crawl_annual_reports()
