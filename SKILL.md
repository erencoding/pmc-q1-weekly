---
name: pmc-q1-weekly
description: 从 PubMed Central (PMC) 抓取本周入库、全文可读、SCI 一区(JCR Q1)期刊的论文，翻译为中文，默认直接在对话里以图标卡片形式返回（每篇含中文标题、中文摘要、超链接源链接）。触发词：PMC 一区文献、PMC 周报、本周 Q1 论文、心理精神科最新文献、抓取 PMC 文献、PMC weekly、最新 SCI 一区论文。支持参数：output_mode(direct/doc)、field(学科)、time_window_days(默认7)、journals(自定义期刊)。
---

# pmc-q1-weekly · PMC 一区周报

从 **PubMed Central (PMC)** 抓取本周入库、全文可读、SCI 一区(JCR Q1)期刊的论文，翻译为中文，按图标卡片方式输出。

## 定位

| 维度 | 说明 |
|---|---|
| 数据来源 | PubMed Central (PMC)，经 NCBI E-utilities API（免费、免登录） |
| 全文可读 | 仅保留能取到 abstract / body 的文章 |
| SCI 一区 | 内置可配置 Q1 期刊白名单（人工核定，IF 标 JCR 近似值） |
| 时间范围 | 默认本周（今天往前 7 天） |
| 语言 | 标题 + 摘要翻译为中文（运行时 Agent 学术化意译） |
| 输出 | 默认「直接提供」——对话内图标卡片清单；可选飞书文档 |

## 参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `output_mode` | `direct` | `direct`=对话内直接返回（默认，由 Agent 手写图标卡片）；`doc`=生成飞书文档 |
| `field` | `psychiatry` | 学科领域，决定用哪份期刊白名单（见 scripts/journals.json） |
| `time_window_days` | `7` | 时间窗（天），默认本周 |
| `journals` | 白名单 | 可覆盖：传入自定义期刊名列表 |
| `max_per_journal` | `40` | 每刊最大抓取数 |

## 工作流（4 步）

### Step 1 — 检索
运行 `scripts/fetch_pmc.py --field <学科> --days <天数>`，内部对 Q1 白名单中每个期刊执行 esearch（`db=pmc`，`"期刊名"[Journal] AND (近 N 天 [PubDate])`），收集 PMCID。

### Step 2 — 取数 + 校验
脚本继续用 esummary 拿元数据、efetch 拿摘要/全文：
- 用 `sortdate` 二次精确过滤（≥ 时间窗起点），剔除回填旧文
- 校验能取到 abstract 或 body，无全文的剔除
- 去重；用正则剔除勘误/通知类（correction / erratum / visual abstract / retraction 等）
- 统一用 `pmcaid`（纯数字 PMCID）做主键
- 结果落地为 JSON：`pmc_result.json`

### Step 3 — 翻译 + 配图标
**由 Agent（你）完成，不调用外部翻译 API**：
- 读 `pmc_result.json`，对每篇英文标题+摘要做**学术化中文意译**（非逐字直译）
- 把中文标题、中文摘要、emoji 回填进 JSON（写 `zh_title` / `zh_abstract` / `emoji` 字段）

**翻译规范（必须遵守）**：
1. **术语准确**：精神科/统计学术语用规范译名（如 randomized controlled trial→随机对照试验、odds ratio→比值比、polygenic risk score→多基因风险评分）。
2. **保留缩写**：RCT、CHR（临床高危）、MDD、PTSD、EEG、fMRI、GWAS、SNP、AI/LLM 等通用缩写保留英文原文，可在首次出现处括注中文。
3. **摘要长度**：中文摘要控制在 **80–120 字**，提炼「研究目的 + 方法 + 主要发现/结论」，不堆砌冗余背景。
4. **忠于原文**：**严禁编造数据、样本量、效应值或结论**；原文没有的数字不要补。原文摘要缺失时，`zh_abstract` 基于 `[正文摘录]` 内容如实概括并保留该标注。
5. **标题**：意译为通顺的中文短句，避免直译腔；保留关键专业名词。

**emoji 配图**：脚本已用 `journals.json` 的 `_emoji_rules`（正则关键词→emoji）自动预填 `emoji` 字段，Agent 可按实际内容微调。规则映射：

| emoji | 触发关键词（研究类型） |
|---|---|
| 📊 | meta-analysis / systematic review / pooled（荟萃分析） |
| 💊 | randomized / RCT / placebo / double-blind / clinical trial（药物/临床试验） |
| 🧠 | eeg / mri / fmri / neuroimaging / cortex / white matter（神经影像） |
| 🧬 | polygenic / genome / genetic / gwas / snp（遗传） |
| 👶 | child / adolescent / youth / paediatric（儿少） |
| 🍽️ | diet / nutrition / microbiota / gut / fatty acid（营养/肠道） |
| 📈 | cohort / register / longitudinal / prospective（队列/纵向） |
| 🏥 | care / service / guideline / management / real-world（临床照护/指南） |
| 🧪 | biomarker / plasma / blood / serum / csf（生物标志物） |
| ⚠️ | mortality / suicide / death / survival（死亡/自杀） |
| 🤖 | language model / chatbot / AI / machine learning（AI） |
| 📄 | 默认（无匹配） |

### Step 4 — 输出（按 output_mode 分支）
- **`direct`（默认）**：Agent 直接在对话里以**纯文本图标卡片**返回（样式见下），**不生成飞书文档**，响应快。卡片由 Agent 读 `pmc_result.json` 手写，灵活可控。
- **`doc`**：运行 `scripts/render.py --in pmc_result.json --out body.xml` 生成 grid 卡片式 XML → 切 `lark-doc` skill 创建飞书文档 → 返回链接。

## 「直接提供」输出样式（纯文本 + 图标）

**硬性要求**：direct 模式输出**只用纯文本 + emoji 图标**，**禁止任何 Markdown 语法**——不得出现 `**加粗**`、`#标题`、`>引用`、`|表格|`、`[文字](链接)`、反引号代码块等。URL 一律裸链直出。用 emoji、缩进/空行、全角分隔符（如 │ ／ ·）来组织层次。

每篇渲染为纯文本图标卡片，建议格式：

```
🧠 1. [中文标题]
   📝 摘要：[中文意译摘要]
   📰 期刊：World Psychiatry（IF 73.3 · Q1 近似）　📅 2026-06-XX　📖 全文可读
   🔗 https://www.ncbi.nlm.nih.gov/pmc/articles/PMCxxxx/
```

开头给一段纯文本概览（不用表格），例如：

```
📚 PMC 一区周报 · 近 7 天收录 N 篇
ℹ️ 来源 PubMed Central（PMC）免费全文。IF/分区为近似值，精确分区以 Web of Science 官方为准。
📊 期刊概览：World Psychiatry（IF 73.3 · 1 篇）／JAMA Psychiatry（IF 25.8 · 2 篇）…
```

## 关键工程要点（踩坑经验）

1. **日期双重过滤**：esearch 的 `[PubDate]` 会混入回填旧文，必须用 esummary 的 `sortdate` 二次卡 ≥ 时间窗起点。
2. **PMCID 匹配键统一**：efetch 返回 `PMC13237144`、esummary 返回纯数字，统一用 `pmcaid`（纯数字）做主键，避免摘要匹配丢失。
3. **翻译交运行时 Agent**：不写死翻译 API（避免直连模型违规），由 Agent 产出学术化中文。
4. **SCI 一区分区数据非免费**：JCR/Web of Science 收费，无法实时合法免费调用。Skill 用内置人工核定白名单（主）+ Scimago SJR / OpenAlex 免费近似（兜底）。**所有 IF/分区必须标注"JCR 近似值，精确分区以 Web of Science 官方为准"**。
5. **NCBI 频率**：请求间加 0.3~0.5s 间隔；可选用 `NCBI_API_KEY` 提速（环境变量）。
6. **多格式日期解析**：PMC 的 `sortdate` 可能是 `2026 Jun`、`2026/06`、`2026` 等，`parse_date()` 逐格式兜底，避免 World Psychiatry 这类只标年月的期刊被误丢。
7. **全文可读校验**：efetch 取 `<body>` 且段落正文 >60 字才算全文可读（`has_fulltext`）；摘要缺失但有正文时用 `[正文摘录]` 兜底。
8. **空结果自动放宽**：本周（默认 7 天）无新文时，自动放宽窗口 7→14→30，并在输出标注 `widened`。
9. **OR 批量检索**：所有期刊用 `OR` 合并为一次 esearch，请求数从 N 降到 1~2，显著提速。
10. **网络全失败分级**：所有检索请求均失败时抛 `AllFailed`，退出码 2，便于上层区分「无结果」与「网络故障」。

## 高级参数（脚本）

| 参数 | 说明 |
|---|---|
| `--dynamic-if` | 用 OpenAlex `2yr_mean_citedness` 拉取近似 IF（兜底白名单） |
| `--require-fulltext` / `--no-require-fulltext` | 是否强制全文可读（默认强制） |
| `--max-per-journal` | 每刊最大抓取数（默认 60） |

## 扩展学科

编辑 `scripts/journals.json`，按 `field` 增加学科分组（期刊名 + ISSN + 近似 IF + 分区标注）。初始内置 `psychiatry`（精神病学/心理学）。
