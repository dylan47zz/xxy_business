#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
"""
金融科技采纳与信用风险治理 - 完整统计分析脚本
输出:
  - analysis_results.xlsx  (描述性统计 + 相关性矩阵 + 回归结果)
  - wordcloud.png           (金融科技词云)
  - fai_trend.png           (FAI时序趋势)
  - npl_trend.png           (NPL时序趋势)
  - scatter_fai_npl.png     (FAI vs NPL散点图)
"""

import os
import re
import json
import math
import warnings
import logging
from pathlib import Path
from collections import Counter
from typing import Dict, List, Optional

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # 无头模式
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import FancyBboxPatch
import scipy.stats as stats
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from wordcloud import WordCloud

warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── 字体配置（macOS）─────────────────────────────────────────────
def setup_chinese_font():
    """设置中文字体"""
    font_candidates = [
        '/System/Library/Fonts/STHeiti Light.ttc',
        '/System/Library/Fonts/STHeiti Medium.ttc',
        '/Library/Fonts/Songti.ttc',
        '/System/Library/Fonts/PingFang.ttc',
        '/System/Library/Fonts/Hiragino Sans GB.ttc',
    ]
    for font_path in font_candidates:
        if os.path.exists(font_path):
            return font_path
    # fallback
    return None

FONT_PATH = setup_chinese_font()
if FONT_PATH:
    fm.fontManager.addfont(FONT_PATH)
    plt.rcParams['font.family'] = fm.FontProperties(fname=FONT_PATH).get_name()
    plt.rcParams['axes.unicode_minus'] = False
else:
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False


# ── 数据读取 ──────────────────────────────────────────────────────
def load_panel_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    df['year'] = df['year'].astype(int)
    df['bank_type_label'] = df['bank_type'].map({'state_owned': '国有银行', 'joint_stock': '股份制银行'})
    logger.info(f"加载数据: {len(df)} 条记录, {df['bank'].nunique()} 家银行")
    return df


# ── 描述性统计 ────────────────────────────────────────────────────
def descriptive_stats(df: pd.DataFrame) -> pd.DataFrame:
    cols = ['npl', 'roe', 'roa', 'fai', 'fintech_total', 'total_assets']
    labels = {
        'npl': '不良贷款率(NPL, %)',
        'roe': '净资产收益率(ROE, %)',
        'roa': '总资产回报率(ROA, %)',
        'fai': 'Fintech采纳指数(FAI, ‱)',
        'fintech_total': 'Fintech关键词总次数',
        'total_assets': '总资产(亿元)',
    }
    stats_list = []
    for col in cols:
        s = df[col].dropna()
        stats_list.append({
            '变量': labels[col],
            '观测值': len(s),
            '均值': round(s.mean(), 4),
            '标准差': round(s.std(), 4),
            '最小值': round(s.min(), 4),
            '25%分位': round(s.quantile(0.25), 4),
            '中位数': round(s.median(), 4),
            '75%分位': round(s.quantile(0.75), 4),
            '最大值': round(s.max(), 4),
        })
    return pd.DataFrame(stats_list)


# ── 相关性矩阵 ────────────────────────────────────────────────────
def correlation_matrix(df: pd.DataFrame) -> pd.DataFrame:
    cols = ['npl', 'roe', 'roa', 'fai', 'size']
    labels = ['NPL', 'ROE', 'ROA', 'FAI', 'Size(ln)']
    sub = df[cols].dropna()
    corr = sub.corr(method='pearson').round(4)
    corr.index = labels
    corr.columns = labels
    return corr


# ── 面板回归 ──────────────────────────────────────────────────────
def panel_regression(df: pd.DataFrame) -> dict:
    """
    模型: NPL_it = β0 + β1*FAI_it + β2*ROE_it + β3*Size_it + ε_it
    使用 OLS + 银行固定效应虚拟变量（LSDV）
    """
    try:
        import statsmodels.api as sm
        from statsmodels.regression.linear_model import OLS

        sub = df[['bank', 'year', 'npl', 'fai', 'roe', 'size']].dropna()

        # 模型1: 简单OLS (FAI only)
        X1 = sm.add_constant(sub[['fai']])
        m1 = OLS(sub['npl'], X1).fit(cov_type='HC1')

        # 模型2: OLS + controls
        X2 = sm.add_constant(sub[['fai', 'roe', 'size']])
        m2 = OLS(sub['npl'], X2).fit(cov_type='HC1')

        # 模型3: LSDV 固定效应
        dummies = pd.get_dummies(sub['bank'], drop_first=True, prefix='bank').astype(float)
        X3 = sm.add_constant(pd.concat([sub[['fai', 'roe', 'size']], dummies], axis=1))
        m3 = OLS(sub['npl'], X3).fit(cov_type='HC1')

        # 整理回归结果
        results = []
        for i, (model, name) in enumerate([(m1, 'OLS (FAI only)'), (m2, 'OLS + Controls'), (m3, 'Fixed Effects')]):
            for var in ['const', 'fai', 'roe', 'size']:
                if var in model.params.index:
                    coef = model.params[var]
                    se = model.bse[var]
                    t = model.tvalues[var]
                    p = model.pvalues[var]
                    sig = '***' if p < 0.01 else '**' if p < 0.05 else '*' if p < 0.1 else ''
                    results.append({
                        '模型': name,
                        '变量': {'const': '截距', 'fai': 'FAI(Fintech采纳指数)', 'roe': 'ROE(净资产收益率)', 'size': 'Size(ln总资产)'}[var],
                        '系数': round(coef, 5),
                        '标准误': round(se, 5),
                        't统计量': round(t, 3),
                        'p值': round(p, 4),
                        '显著性': sig,
                    })
            results.append({
                '模型': name,
                '变量': '--- 模型统计 ---',
                '系数': '',
                '标准误': '',
                't统计量': '',
                'p值': '',
                '显著性': '',
            })
            results.append({'模型': name, '变量': 'R²', '系数': round(model.rsquared, 4), '标准误': '', 't统计量': '', 'p值': '', '显著性': ''})
            results.append({'模型': name, '变量': 'Adj. R²', '系数': round(model.rsquared_adj, 4), '标准误': '', 't统计量': '', 'p值': '', '显著性': ''})
            results.append({'模型': name, '变量': '观测值N', '系数': int(model.nobs), '标准误': '', 't统计量': '', 'p值': '', '显著性': ''})

        return {
            'results_df': pd.DataFrame(results),
            'model1': m1,
            'model2': m2,
            'model3': m3,
            'n_obs': len(sub),
        }
    except Exception as e:
        logger.error(f"回归分析失败: {e}")
        return {'results_df': pd.DataFrame(), 'model1': None, 'model2': None, 'model3': None, 'n_obs': 0}


# ── 词云图 ────────────────────────────────────────────────────────
def generate_wordcloud(md_dir: Path, output_path: Path):
    """从所有年报Markdown生成词云"""
    word_freq = Counter()
    fintech_kws = [
        '人工智能', 'AI', '机器学习', '大数据', '风控模型', '算法',
        '数字金融', '智能信贷', '金融科技', 'Fintech',
        '云计算', '区块链', '人脸识别', '智能风控', '开放银行',
        '数字化转型', '线上化', '智能化', '科技赋能',
        '移动互联', '物联网', '5G', '智能客服', '智能营销',
        '无纸化', '电子化', '网络金融', '区块链技术',
        '数字化', '数字技术', '数字经济', '数字转型',
    ]

    for md_file in md_dir.glob("*.md"):
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        # 从词频表中提取
        for kw in fintech_kws:
            count_match = re.search(rf'\|\s*{re.escape(kw)}\s*\|\s*(\d+)\s*\|', content)
            if count_match:
                word_freq[kw] += int(count_match.group(1))

    if not word_freq:
        logger.warning("词频数据为空，无法生成词云")
        return

    logger.info(f"词云词频: {len(word_freq)} 个词，总计 {sum(word_freq.values())} 次")

    # 生成词云
    wc_kwargs = {
        'background_color': 'white',
        'max_words': 50,
        'width': 1200,
        'height': 700,
        'collocations': False,
        'colormap': 'Blues',
        'min_font_size': 12,
        'max_font_size': 150,
    }
    if FONT_PATH:
        wc_kwargs['font_path'] = FONT_PATH

    try:
        wc = WordCloud(**wc_kwargs)
        wc.generate_from_frequencies(word_freq)
        wc.to_file(str(output_path))
        logger.info(f"词云已保存: {output_path}")
    except Exception as e:
        logger.error(f"词云生成失败: {e}")
        # 简化版
        try:
            wc = WordCloud(background_color='white', max_words=30, width=800, height=500)
            # 转换为英文替代
            eng_freq = {f"Fintech{i}": v for i, (k, v) in enumerate(word_freq.most_common(20))}
            eng_freq.update({'AI': word_freq.get('AI', 0), 'BigData': word_freq.get('大数据', 0)})
            wc.generate_from_frequencies(eng_freq)
            wc.to_file(str(output_path))
        except Exception as e2:
            logger.error(f"词云简化版也失败: {e2}")


# ── 趋势图 ────────────────────────────────────────────────────────
def plot_fai_trend(df: pd.DataFrame, output_path: Path):
    """FAI时序趋势图"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 左图: 分组平均FAI趋势
    ax = axes[0]
    for btype, label, color in [('state_owned', '国有银行', '#1f77b4'), ('joint_stock', '股份制银行', '#ff7f0e')]:
        sub = df[df['bank_type'] == btype].groupby('year')['fai'].mean()
        ax.plot(sub.index, sub.values, marker='o', linewidth=2, color=color, label=label, markersize=8)
    ax.set_title('金融科技采纳指数(FAI)年度趋势', fontsize=13, fontweight='bold', pad=10)
    ax.set_xlabel('年份', fontsize=11)
    ax.set_ylabel('FAI (‱)', fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    ax.set_xticks([2023, 2024, 2025])

    # 右图: 各银行2023-2025 FAI热力图
    ax2 = axes[1]
    pivot = df.pivot_table(index='bank', columns='year', values='fai').round(2)
    im = ax2.imshow(pivot.values, cmap='YlOrRd', aspect='auto')
    ax2.set_xticks(range(len(pivot.columns)))
    ax2.set_xticklabels(pivot.columns, fontsize=10)
    ax2.set_yticks(range(len(pivot.index)))
    ax2.set_yticklabels(pivot.index, fontsize=9)
    ax2.set_title('各银行FAI热力图 (2023-2025)', fontsize=13, fontweight='bold', pad=10)
    plt.colorbar(im, ax=ax2, label='FAI (‱)')
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            ax2.text(j, i, f'{val:.1f}', ha='center', va='center', fontsize=7.5,
                     color='black' if val < 5 else 'white')

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"FAI趋势图已保存: {output_path}")


def plot_npl_trend(df: pd.DataFrame, output_path: Path):
    """NPL时序趋势图"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 左图: 分组平均NPL趋势
    ax = axes[0]
    for btype, label, color in [('state_owned', '国有银行', '#2ca02c'), ('joint_stock', '股份制银行', '#d62728')]:
        sub = df[df['bank_type'] == btype].groupby('year')['npl'].mean()
        ax.plot(sub.index, sub.values, marker='s', linewidth=2, color=color, label=label, markersize=8)
    ax.set_title('不良贷款率(NPL)年度趋势', fontsize=13, fontweight='bold', pad=10)
    ax.set_xlabel('年份', fontsize=11)
    ax.set_ylabel('NPL (%)', fontsize=11)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.3)
    ax.set_xticks([2023, 2024, 2025])

    # 右图: 2025年各银行NPL对比条形图
    ax2 = axes[1]
    df25 = df[df['year'] == 2025].sort_values('npl', ascending=True)
    colors = ['#1f77b4' if t == 'state_owned' else '#ff7f0e' for t in df25['bank_type']]
    bars = ax2.barh(df25['bank'], df25['npl'], color=colors, edgecolor='white', linewidth=0.5)
    ax2.set_xlabel('NPL (%)', fontsize=11)
    ax2.set_title('2025年各银行不良贷款率对比', fontsize=13, fontweight='bold', pad=10)
    for bar, val in zip(bars, df25['npl']):
        ax2.text(val + 0.01, bar.get_y() + bar.get_height()/2,
                f'{val:.2f}%', va='center', fontsize=8)
    ax2.grid(axis='x', alpha=0.3)
    # 添加图例
    from matplotlib.patches import Patch
    legend_elements = [Patch(facecolor='#1f77b4', label='国有银行'),
                      Patch(facecolor='#ff7f0e', label='股份制银行')]
    ax2.legend(handles=legend_elements, loc='lower right', fontsize=9)

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"NPL趋势图已保存: {output_path}")


def plot_scatter_fai_npl(df: pd.DataFrame, output_path: Path):
    """FAI vs NPL散点图"""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # 左图: 全样本散点 + 回归线
    ax = axes[0]
    sub = df[['fai', 'npl', 'bank_type']].dropna()
    colors_map = {'state_owned': '#1f77b4', 'joint_stock': '#ff7f0e'}
    for btype, label in [('state_owned', '国有银行'), ('joint_stock', '股份制银行')]:
        s = sub[sub['bank_type'] == btype]
        ax.scatter(s['fai'], s['npl'], c=colors_map[btype], label=label, alpha=0.7, s=60, edgecolors='white')

    # 添加回归线
    x = sub['fai'].values
    y = sub['npl'].values
    slope, intercept, r, p, se = stats.linregress(x, y)
    x_line = np.linspace(x.min(), x.max(), 100)
    ax.plot(x_line, slope * x_line + intercept, 'r--', linewidth=1.5,
            label=f'回归线 (β={slope:.4f}, p={p:.3f})')
    ax.set_xlabel('Fintech采纳指数(FAI, ‱)', fontsize=11)
    ax.set_ylabel('不良贷款率(NPL, %)', fontsize=11)
    ax.set_title('FAI与NPL散点图（全样本）', fontsize=13, fontweight='bold', pad=10)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)
    ax.text(0.05, 0.95, f'n={len(sub)}, r={r:.3f}', transform=ax.transAxes,
            fontsize=10, verticalalignment='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # 右图: 按年份分面散点
    ax2 = axes[1]
    for year, marker, color in [(2023, 'o', '#aec7e8'), (2024, 's', '#ffbb78'), (2025, '^', '#98df8a')]:
        s = sub[df['year'] == year]
        ax2.scatter(s['fai'], df.loc[s.index, 'npl'], c=color, marker=marker, label=str(year),
                   alpha=0.8, s=70, edgecolors='gray', linewidth=0.5)
    ax2.set_xlabel('Fintech采纳指数(FAI, ‱)', fontsize=11)
    ax2.set_ylabel('不良贷款率(NPL, %)', fontsize=11)
    ax2.set_title('FAI与NPL散点图（按年份）', fontsize=13, fontweight='bold', pad=10)
    ax2.legend(fontsize=10)
    ax2.grid(alpha=0.3)

    plt.tight_layout()
    plt.savefig(str(output_path), dpi=150, bbox_inches='tight')
    plt.close()
    logger.info(f"散点图已保存: {output_path}")


# ── 生成Excel报告 ─────────────────────────────────────────────────
def save_excel_report(df: pd.DataFrame, desc_stats: pd.DataFrame, corr: pd.DataFrame,
                      reg_results: dict, output_path: Path):
    """生成分析结果Excel"""
    wb = openpyxl.Workbook()

    # 辅助函数
    def style_header(cell, bg='366092', fg='FFFFFF', bold=True):
        cell.fill = PatternFill(fill_type='solid', fgColor=bg)
        cell.font = Font(color=fg, bold=bold)
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    def style_data(ws, start_row, start_col, df_data, header_bg='4472C4'):
        """写入DataFrame并添加样式"""
        # 写表头
        for j, col in enumerate(df_data.columns):
            cell = ws.cell(row=start_row, column=start_col + j, value=col)
            style_header(cell, bg=header_bg)
        # 写数据
        for i, row in enumerate(df_data.itertuples(index=False)):
            for j, val in enumerate(row):
                cell = ws.cell(row=start_row + 1 + i, column=start_col + j, value=val)
                cell.alignment = Alignment(horizontal='center' if j > 0 else 'left')
                if (i % 2) == 0:
                    cell.fill = PatternFill(fill_type='solid', fgColor='EBF1F8')

    # ── Sheet 1: 面板数据 ──
    ws1 = wb.active
    ws1.title = '面板数据'
    style_data(ws1, 1, 1, df[['bank', 'year', 'bank_type_label', 'npl', 'roe', 'roa',
                               'total_assets', 'fintech_total', 'fai']])
    # 列宽
    for col in ['A', 'B', 'C']:
        ws1.column_dimensions[col].width = 12
    for col in ['D', 'E', 'F', 'G', 'H', 'I']:
        ws1.column_dimensions[col].width = 14

    # ── Sheet 2: 描述性统计 ──
    ws2 = wb.create_sheet('描述性统计')
    ws2.merge_cells('A1:I1')
    ws2['A1'] = 'Table 1: 主要变量描述性统计'
    style_header(ws2['A1'], bg='1F4E79')
    ws2['A1'].font = Font(color='FFFFFF', bold=True, size=12)
    ws2.row_dimensions[1].height = 25
    style_data(ws2, 2, 1, desc_stats, header_bg='2E75B6')
    for i in range(1, 10):
        ws2.column_dimensions[chr(64 + i)].width = 16 if i == 1 else 12

    # ── Sheet 3: 相关性矩阵 ──
    ws3 = wb.create_sheet('相关性矩阵')
    ws3.merge_cells('A1:F1')
    ws3['A1'] = 'Table 2: Pearson相关系数矩阵'
    style_header(ws3['A1'], bg='1F4E79')
    ws3['A1'].font = Font(color='FFFFFF', bold=True, size=12)
    ws3.row_dimensions[1].height = 25
    corr_with_idx = corr.reset_index()
    corr_with_idx.columns = ['变量'] + list(corr.columns)
    style_data(ws3, 2, 1, corr_with_idx, header_bg='2E75B6')
    for i in range(1, 8):
        ws3.column_dimensions[chr(64 + i)].width = 12

    # ── Sheet 4: 回归结果 ──
    ws4 = wb.create_sheet('回归结果')
    ws4.merge_cells('A1:G1')
    ws4['A1'] = 'Table 3: 面板数据回归结果（因变量: 不良贷款率NPL）'
    style_header(ws4['A1'], bg='1F4E79')
    ws4['A1'].font = Font(color='FFFFFF', bold=True, size=12)
    ws4.row_dimensions[1].height = 25
    if not reg_results['results_df'].empty:
        style_data(ws4, 2, 1, reg_results['results_df'], header_bg='2E75B6')
    note_row = ws4.max_row + 2
    ws4.cell(row=note_row, column=1, value='注: *** p<0.01, ** p<0.05, * p<0.1；括号内为异方差稳健标准误')
    ws4.cell(row=note_row, column=1).font = Font(italic=True, size=9)
    for col in ['A', 'B', 'C', 'D', 'E', 'F', 'G']:
        ws4.column_dimensions[col].width = 22 if col in ['A', 'B'] else 12

    wb.save(str(output_path))
    logger.info(f"Excel报告已保存: {output_path}")


# ── 主函数 ────────────────────────────────────────────────────────
def main():
    base_dir = Path("../data")
    analysis_dir = base_dir / "analysis"
    md_dir = base_dir / "markdown"
    analysis_dir.mkdir(exist_ok=True)

    # 读取数据
    csv_path = analysis_dir / "panel_data.csv"
    if not csv_path.exists():
        logger.error(f"面板数据不存在: {csv_path}")
        logger.error("请先运行 build_panel_data.py")
        return

    df = load_panel_data(csv_path)

    # 1. 描述性统计
    logger.info("计算描述性统计...")
    desc = descriptive_stats(df)
    print("\n=== 描述性统计 ===")
    print(desc.to_string(index=False))

    # 2. 相关性矩阵
    logger.info("计算相关性矩阵...")
    corr = correlation_matrix(df)
    print("\n=== 相关性矩阵 ===")
    print(corr)

    # 3. 回归分析
    logger.info("执行面板数据回归...")
    reg = panel_regression(df)
    print("\n=== 回归结果 ===")
    if not reg['results_df'].empty:
        print(reg['results_df'].to_string(index=False))

    # 4. 词云图
    logger.info("生成词云图...")
    wc_path = analysis_dir / "wordcloud.png"
    generate_wordcloud(md_dir, wc_path)

    # 5. 趋势图
    logger.info("生成趋势图...")
    plot_fai_trend(df, analysis_dir / "fai_trend.png")
    plot_npl_trend(df, analysis_dir / "npl_trend.png")
    plot_scatter_fai_npl(df, analysis_dir / "scatter_fai_npl.png")

    # 6. Excel报告
    logger.info("生成Excel报告...")
    save_excel_report(df, desc, corr, reg, analysis_dir / "analysis_results.xlsx")

    logger.info("\n=== 分析完成 ===")
    logger.info(f"输出目录: {analysis_dir.absolute()}")
    for f in analysis_dir.iterdir():
        logger.info(f"  {f.name} ({f.stat().st_size // 1024}KB)")


if __name__ == '__main__':
    main()
