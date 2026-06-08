# 📚 pmc-q1-weekly

> Hermes Agent skill · PubMed Central (PMC) SCI 一区期刊周报（中文版）

从 [PubMed Central](https://www.ncbi.nlm.nih.gov/pmc/) 抓取最近 7 天入库、全文可读、SCI 一区（JCR Q1）期刊的论文，整理成图标美化的中文卡片清单。每篇含**中文标题、中文摘要、源链接**。

## 触发场景

- 「PMC 一区文献」「PMC 周报」「本周 Q1 论文」
- 「心理精神科最新文献」「抓取 PMC 文献」
- 「PMC weekly」「最新 SCI 一区论文」

## 定位

| 维度 | 说明 |
|---|---|
| 数据来源 | PubMed Central (PMC) · NCBI E-utilities API（免费、免登录） |
| 全文可读 | 仅保留能取到 abstract / body 的文章 |
| SCI 一区 | 内置可配置 Q1 期刊白名单（人工核定，IF 标 JCR 近似值） |
| 时间范围 | 默认本周（今天往前 7 天） |
| 语言 | 标题 + 摘要由 Agent 学术化意译为中文 |
| 输出 | 默认对话内直接返回（图标卡片）；可选飞书文档 |

## 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `output_mode` | `direct` | `direct`=对话内图标卡片（默认）；`doc`=生成飞书文档 |
| `field` | `psychiatry` | 学科领域，决定期刊白名单（见 `scripts/journals.json`） |
| `time_window_days` | `7` | 时间窗（天），本周 |
| `journals` | 白名单 | 可传入自定义期刊名列表 |
| `max_per_journal` | `40` | 每刊最大抓取数 |

## 仓库结构

```
pmc-q1-weekly/
├── README.md
├── SKILL.md                  # Hermes skill 描述 + LLM 渲染指令
└── scripts/
    ├── fetch_pmc.py          # 抓取 + 解析 + JSON 输出
    ├── journals.json         # Q1 期刊白名单 + emoji 规则
    └── render.py             # 飞书文档 grid 卡片 XML 渲染
```

## 用法

### 命令行

```bash
# 默认：psychiatry 学科，7 天
python3 scripts/fetch_pmc.py

# 自定义
python3 scripts/fetch_pmc.py --field psychiatry --days 14 --max-per-journal 60
python3 scripts/fetch_pmc.py --dynamic-if                 # 用 OpenAlex 近似 IF
python3 scripts/fetch_pmc.py --no-require-fulltext       # 允许无全文
```

### 渲染飞书文档（可选）

```bash
python3 scripts/render.py --in pmc_result.json --out body.xml
```

### 在 Hermes Agent 中

把仓库 raw URL 加进 Hermes skill 索引，或直接放到 `~/.hermes/skills/pmc-q1-weekly/`。LLM 会按 `SKILL.md` frontmatter 的触发词自动加载。

## 卡片输出样式（默认 direct 模式）

每篇论文一张图标卡片：

```
🧠 1. [中文标题]
   📝 摘要：[中文意译摘要 80–120 字]
   📰 期刊：World Psychiatry（IF 73.3 · Q1 近似）　📅 2026-06-XX　📖 全文可读
   🔗 https://www.ncbi.nlm.nih.gov/pmc/articles/PMCxxxx/
```

emoji 配图规则（来自 `journals.json._emoji_rules`）：

| emoji | 触发关键词 |
|---|---|
| 📊 | meta-analysis / systematic review / pooled |
| 💊 | randomized / RCT / placebo / double-blind / clinical trial |
| 🧠 | eeg / mri / fmri / neuroimaging / cortex / white matter |
| 🧬 | polygenic / genome / genetic / GWAS / SNP |
| 👶 | child / adolescent / youth / paediatric |
| 🍽️ | diet / nutrition / microbiota / gut / fatty acid |
| 📈 | cohort / register / longitudinal / prospective |
| 🏥 | care / service / guideline / management / real-world |
| 🧪 | biomarker / plasma / blood / serum / csf |
| ⚠️ | mortality / suicide / death / survival |
| 🤖 | language model / chatbot / AI / machine learning |
| 📄 | 默认（无匹配） |

## 关键工程要点（踩坑沉淀）

1. **日期双重过滤**：esearch 的 `[PubDate]` 会混入回填旧文，必须用 esummary 的 `sortdate` 二次卡 ≥ 时间窗起点。
2. **PMCID 匹配键统一**：efetch 返回 `PMC13237144`、esummary 返回纯数字，统一用 `pmcaid`（纯数字）做主键。
3. **翻译交运行时 Agent**：不写死翻译 API（避免直连模型违规），由 Agent 产出学术化中文。
4. **SCI 一区分区数据非免费**：JCR / Web of Science 收费。Skill 用内置人工核定白名单（主）+ Scimago SJR / OpenAlex 免费近似（兜底）。**所有 IF / 分区必须标注"JCR 近似值，精确分区以 Web of Science 官方为准"。**
5. **NCBI 频率**：请求间加 0.3–0.5s 间隔；可选 `NCBI_API_KEY` 环境变量提速。
6. **多格式日期解析**：`sortdate` 可能是 `2026 Jun` / `2026/06` / `2026` 等，逐格式兜底，避免 `World Psychiatry` 这类只标年月的期刊被误丢。
7. **全文可读校验**：efetch 取 `<body>` 且段落正文 > 60 字才算 `has_fulltext`；摘要缺失但有正文时用 `[正文摘录]` 兜底。
8. **空结果自动放宽**：本周 0 条 → 自动放宽窗口 7 → 14 → 30 天，输出标注 `widened`。
9. **OR 批量检索**：所有期刊用 `OR` 合并为一次 esearch，请求数从 N 降到 1–2。
10. **网络全失败分级**：所有检索请求均失败时抛 `AllFailed`，退出码 2，便于上层区分"无结果"与"网络故障"。

## 翻译规范（Agent 必须遵守）

1. **术语准确**：randomized controlled trial → 随机对照试验；odds ratio → 比值比；polygenic risk score → 多基因风险评分。
2. **保留缩写**：RCT、CHR（临床高危）、MDD、PTSD、EEG、fMRI、GWAS、SNP、AI / LLM 等通用缩写保留英文原文。
3. **摘要长度**：**80–120 字**，提炼"研究目的 + 方法 + 主要发现 / 结论"。
4. **严禁编造数据**：原文没有的样本量、效应值不要补。摘要缺失时 `zh_abstract` 基于 `[正文摘录]` 内容如实概括并保留标注。
5. **标题意译**：避免直译腔；保留关键专业名词。

## 维护提示

- 期刊白名单：`scripts/journals.json` → 新增学科 = 新增 field 分组（期刊名 + ISSN + 近似 IF + 分区标注）。初始内置 `psychiatry`。
- 解析器：PMC 改版（如新版 OA API）需更新 `fetch_pmc.py` 的 efetch 解析段。
- 翻译规范：见上文"翻译规范"。

## 许可

MIT
