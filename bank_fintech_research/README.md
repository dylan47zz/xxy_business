# Does Fintech Adoption Improve Credit Risk Governance?
### Evidence from Text Mining of Chinese Bank Annual Reports

> 金融科技采纳是否改善了信用风险治理？—— 来自银行年报文本挖掘的证据

---

## 研究概述

本项目通过对 **18家中国商业银行**（6家国有大型银行 + 10家全国性股份制银行 + 广发银行 + 恒丰银行）**2023-2025年年报**进行NLP文本挖掘，构建"金融科技采纳指数（FAI）"，并实证检验其与不良贷款率（NPL）之间的关系。

**核心发现：** FAI 与 NPL 显著负相关（r = -0.508），OLS+控制变量回归系数 β = -0.057（p < 0.001）。

---

## 目录结构

```
bank_fintech_research/
├── requirements.txt          # Python 依赖
├── scripts/                  # 按流程编号的脚本
│   ├── 01_crawl_reports.py   # Step 1: 抓取年报PDF（巨潮资讯API）
│   ├── 02_pdf_to_markdown.py # Step 2: PDF → Markdown 转换
│   ├── 03_extract_data.py    # Step 3: 提取财务指标 + 词频
│   ├── 04_build_panel.py     # Step 4: 构建面板数据集
│   ├── 05_analysis.py        # Step 5: 统计分析（回归+图表）
│   └── 06_generate_paper.py  # Step 6: 生成英文论文草稿
└── data/
    ├── markdown/             # 54份年报 Markdown（18家 × 3年）
    ├── pdf/                  # 广发+恒丰6份PDF（其余16家本地保存）
    └── analysis/             # 分析输出
        ├── panel_data.csv        # 面板数据（54条）
        ├── panel_data_raw.json   # 自动提取原始数据
        ├── analysis_results.xlsx # 描述统计/相关矩阵/回归结果
        ├── wordcloud.png         # 金融科技词云图
        ├── fai_trend.png         # FAI年度趋势图
        ├── npl_trend.png         # NPL年度趋势图
        ├── scatter_fai_npl.png   # FAI vs NPL 散点图
        └── research_paper.md     # 3000字英文论文草稿
```

---

## 快速开始

```bash
cd bank_fintech_research

# 安装依赖
pip install -r requirements.txt

# Step 1: 抓取16家上市银行年报PDF（广发/恒丰需从官网手动下载）
python scripts/01_crawl_reports.py

# Step 2: PDF → Markdown
python scripts/02_pdf_to_markdown.py

# Step 3: 提取财务数据
python scripts/03_extract_data.py

# Step 4: 构建面板数据
python scripts/04_build_panel.py

# Step 5: 统计分析
python scripts/05_analysis.py

# Step 6: 生成论文
python scripts/06_generate_paper.py
```

> **注意：** 广发银行年报下载地址 `https://www.cgbchina.com.cn/Channel/19772772`
> 恒丰银行年报下载地址 `https://www.hfbank.com.cn/dzzgj/gcgg/djgg/index.shtml`
> 将PDF放入 `data/pdf/` 目录后再运行 Step 2。

---

## 样本说明

| 类别 | 银行 | 数量 |
|------|------|------|
| 国有大型银行 | 工商、建设、农业、中国、交通、邮储 | 6家 |
| 全国性股份制银行 | 平安、光大、民生、招商、兴业、中信、华夏、浦发、浙商、渤海 | 10家 |
| 非上市股份制银行 | 广发、恒丰 | 2家 |
| **合计** | | **18家 × 3年 = 54观测值** |

---

## 关键变量

| 变量 | 说明 | 来源 |
|------|------|------|
| NPL | 不良贷款率（%） | 各行年报 |
| ROE | 加权平均净资产收益率（%） | 各行年报 |
| ROA | 平均总资产回报率（%） | 各行年报 |
| FAI | 金融科技采纳指数 = 关键词词频/字符数×10000（‱） | NLP提取 |
| Size | ln（总资产，亿元） | 各行年报 |

---

## 主要结果

```
模型              变量          系数      p值    显著性
OLS (FAI only)   FAI         -0.0774   0.0     ***
OLS + Controls   FAI         -0.0554   0.0     ***
                 ROE         -0.0362   0.0     ***
Fixed Effects    FAI         -0.0161   0.304   n.s.
                 ROE         -0.0226   0.097   *
                 Size(ln)    -0.6001   0.001   ***

Pearson相关: FAI × NPL = -0.596 (p<0.01)
```
