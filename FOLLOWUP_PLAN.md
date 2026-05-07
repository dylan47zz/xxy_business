# 后续计划 - Fintech采纳指数研究

## 项目概述
研究金融科技采纳是否改善了商业银行信用风险治理，基于16家上市银行年报文本挖掘分析。

## 当前进度

### 已完成
- [x] 年报数据抓取：16家银行 × 3年 = 48份PDF
- [x] 文本提取：PDF → Markdown格式
- [x] 关键词词频统计：初步金融科技关键词统计
- [x] 财务数据提取：NPL、ROE、ROA（需人工校正）

### 数据文件位置
```
annual_reports/
├── pdf/                    # 原始年报PDF (本地,未上传)
│   ├── 工商银行_2023年度报告.pdf
│   └── ...
├── markdown/              # Markdown格式文本
│   ├── 工商银行_2023年度报告.md
│   └── ...
└── data/                  # 结构化数据
    ├── financial_data.json
    └── fintech_keywords.json
```

## 待办事项

### P0 - 核心分析
1. **财务数据校正**
   - 检查并校正NPL/ROE提取结果
   - 补充渤海银行财务数据（手动查找）
   - 提取总资产(Size)数据

2. **Fintech采纳指数构建**
   - 优化关键词词频统计
   - 计算指数 = 关键词词频 / 年报总词数
   - 生成标准化指数表

3. **词云图生成**
   - 为每份年报生成词云图
   - 保存至 `annual_reports/wordcloud/`

### P1 - 数据分析
4. **描述性统计**
   - 各银行Fintech采纳指数分布
   - NPL时间趋势
   - 相关性分析

5. **回归分析**
   - 面板数据固定效应模型
   - 检验Fintech指数对NPL的影响
   - 稳健性检验

### P2 - 论文撰写
6. **论文草稿**
   - Introduction (500字)
   - Literature & Hypothesis (500字)
   - Data & Methodology (600字)
   - Empirical Results (700字)
   - Risk Governance Implications (400字)
   - Conclusion (300字)

## 技术栈
- 数据抓取：Python + requests
- PDF处理：pdfplumber
- 文本分析：正则表达式、词频统计
- 词云图：wordcloud
- 回归分析：statsmodels / Stata

## 注意事项
- 渤海银行年报API无法直接抓取，已手动下载
- 部分财务数据提取需人工校验
- PDF文件过大，未上传至GitHub

## 下一步行动
1. 人工检查并校正financial_data.json中的NPL/ROE数据
2. 运行词云图生成脚本
3. 执行描述性统计分析
