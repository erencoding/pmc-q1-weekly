---
name: pmc-q1-weekly
description: 从 PubMed Central (PMC) 抓取本周入库、全文可读、SCI 一区(JCR Q1)期刊的论文，翻译为中文，默认写入飞书云文档（1 篇 1 docx 双语结构，含中英标题/中英摘要/元信息/原文主体段落/原图 inline 嵌入/IF 声明，推到用户本人云盘「心理精神科论文」folder）。备选 output_mode=direct 在对话内以图标卡片形式返回。当用户问"截图原文 / 真版式 / 完整 PDF"时也触发（告知当前免费方案的天花板 = 6 张原图 + 主体段落，要 100% 原版式需走付费 2Captcha / EUtils bulk download）。触发词：PMC 一区文献、PMC 周报、本周 Q1 论文、心理精神科最新文献、抓取 PMC 文献、PMC weekly、最新 SCI 一区论文、PMC 飞书文档、PMC 截图、原文截图。支持参数：output_mode(direct/doc)、field(学科)、time_window_days(默认7)、journals(自定义期刊)。
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
- **v5 新增**:对每篇的**正文主体各段**(`body_text` 按 `\n\n` 切分)做中文意译,回填 `zh_body_sections` 列表(按段顺序一一对应,空字符串表示该段未翻译)
- **v5 新增**:对每张图 caption 做中文意译,回填 `zh_figure_captions` 字典(形如 `{"Fig. 1": "图 1 译文"}`,key 用原文 fig label)

**翻译规范（必须遵守）**：
1. **术语准确**：精神科/统计学术语用规范译名（如 randomized controlled trial→随机对照试验、odds ratio→比值比、polygenic risk score→多基因风险评分）。
2. **保留缩写**：RCT、CHR（临床高危）、MDD、PTSD、EEG、fMRI、GWAS、SNP、AI/LLM 等通用缩写保留英文原文，可在首次出现处括注中文。
3. **摘要长度**：中文摘要控制在 **80–120 字**，提炼「研究目的 + 方法 + 主要发现/结论」，不堆砌冗余背景。
4. **忠于原文**：**严禁编造数据、样本量、效应值或结论**；原文没有的数字不要补。原文摘要缺失时，`zh_abstract` 基于 `[正文摘录]` 内容如实概括并保留该标注。
5. **标题**：意译为通顺的中文短句，避免直译腔；保留关键专业名词。
6. **正文主体翻译**(v5):每段中文意译控制在**原文 60-80% 长度**(避免冗余),按 `body_text` 段顺序生成 `zh_body_sections` 列表
7. **图 caption 翻译**(v5):简洁(50-150 字),保留关键术语英文括注;`zh_figure_captions` 字典的 key 必须严格匹配 `figures[i].label`("Fig. 1" / "Fig. 2" 等)

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
- **`doc`**：运行 `scripts/render.py --mode {grid,single}` 生成飞书 docx body XML → `lark-cli docs +create --parent-token <folder> --content @<file>` 写云文档(一步到位)。两种 sub-mode:
  - **`grid`(默认,大批量 ≥10 篇)**:多篇分组表格,1 份大 docx。`python3 scripts/render.py --in pmc_result.json --out body.xml --mode grid`
  - **`single`(2026-06-16 新增,中小批量 1-5 篇)**:1 篇 1 docx 双语结构。`python3 scripts/render.py --in pmc_result.json --out body.xml --mode single --index 0 --title-prefix "2026-06-12_"`
  - 完整 workflow + lark-cli 坑(`--content @<file>` 相对路径 / `<title>` XML 必带 / `--parent-token` 一步到位 / 索引延迟)见 `references/feishu-doc-workflow.md`
  - 跨 skill 通用 lark-cli 坑(切 user / bot / scope 补 `search:docs:read` / `docs +fetch` 不存在)见兄弟 `psych-news-digest/references/lark-cli-pitfalls.md`

### single 模式 v2 增强(2026-06-16 实测,含原文主体 + 原图)

为响应用户"docx 缺主体 / 图"反馈,`fetch_pmc.py` + `render.py` v2 扩了 3 个字段:
- `body_text`(每篇文章,英文,`fetch_pmc.py` 抓 JATS `<body>` 段落,过滤 <40 字符短段,**v3 限 8000 字符,v4 限 12000 字符**防 docx 爆)
- `figures`(JATS `<fig>` 解析:`label` + `caption` + `url`)

`render.py --mode single` 把这俩字段渲染成两个新章节:
- `## 📖 原文主体 / Full Text Body` — body 段落,英文原文(**v3 限 `max_body_chars=4000` 默认,v4 改 `max_body_chars=10000`**)
- `## 🖼️ 图片 / Figures(3/6)` — 前 `max_figures` 张图 inline 嵌入(飞书 `<img href="..."/>` 自动下载), caption 跟在图后;超出部分提示"详见 PMC 全文链接"
  - **v3 默认 `max_figures=3`**,**v4 改 `max_figures=10` (全 inline)**
- **v4 长段拆块**:`render.py` 主体渲染时,长段 >3000 字符**拆多个 `<p>` 块**(飞书 docx 单 block 上限 ~4000 字符,长段不拆会触发"block 超限"错误)

**v4 升级触发**(2026-06-17 用户明示"飞书文档应该包含原文全部内容"):
- body 字符: 4000 → 10000(渲染) / 8000 → 12000(抓取)
- 图 inline: 3/6 → 6/6 全展示
- 主体单段拆 3000 字符(防 docx 单 block 超限)
- docx 体积: 11 KB → 19 KB(飞书 docx 1 个 50 MB 上限, 完全够)

**JATS graphic href 是裸文件名**(如 `41398_2026_4140_Fig1_HTML.jpg`),**真 URL 在 HTML 渲染后注入到 `cdn.ncbi.nlm.nih.gov/pmc/blobs/.../filename`**,所以 `fetch_pmc.py` 必须抓文章 HTML 页面 `findall` 所有 CDN URL 后按 filename 末尾匹配。HTML 页面缓存复用(`_HTML_CACHE`,per-pmcid 一次抓取,6 张图共享)。**旧版 bin 路径**(`/pmc/articles/PMCxxx/bin/filename`)对现代 PMC 文章 404,只能当兜底。详细实现见 `scripts/fetch_pmc.py` `resolve_figure_url()` 函数。

## 📤 输出方式(飞书 · 默认云文档,2026-06-16 实战对齐 psych-news-digest v3.4)

与兄弟 `psych-news-digest` 保持一致(用户 2026-06-16 多次明示"给我飞书文档"/"参考 psych-news-digest 输出飞书文档"):

- **默认**:`output_mode=doc` + single 模式(1 篇 1 docx 双语),推到用户本人飞书账号(`lark-cli auth status` 验证 openId)「心理精神科论文」folder
- **备选**:`output_mode=direct`(对话内图标卡片, 不生成 docx)
- **触发判断**(用户明示优先):
  - 明示"飞书文档/云文档/docx/参考 psych-news-digest"→ **云文档**(2026-06-16 偏好)
  - 明示"对话/消息/卡片"→ direct
  - **未明示 → 默认走云文档**(用户当前偏好; 与 psych-news-digest v3.4 对齐)
  - cron 自动任务走云文档(产物留底,方便回顾)
- **docx 失败兜底**:该篇不渲染 `📄 飞书文档:` 行 + 末尾汇总 `⚠️ N 条存档失败:<title>`,**不**伪造 doc_url
- **folder 命名**:用户飞书云盘有 2 个 folder — 「心理精神科新闻日志」`SfYDf4AxYlYCz4dKBLYcpmqgnuh`(psych-news-digest / APA 新闻用)和「心理精神科论文」`A2GFf6ssRlVCFudELgTchIuVn7u`(PMC 论文用,2026-06-16 新建)。**PMC 论文写后者**,APA 新闻写前者,不要混。lark-cli 没暴露 `+rename`,**folder 改名/迁移 = 新建 + `drive +move` 迁 docx + 保留旧 folder(若有共享 docx)**;不要直接删旧 folder(里面可能还有别的 skill 的 docx)。
- **反编造铁律**(再强调):翻译字段不能空字符串(空 = agent 漏翻),IF 近似值声明必带(`render.py` single 模式已硬编码)

## ⚠️ "原文截图"路径走不通(2026-06-16 实测,不要重试)

用户问"能不能直接截图原文放飞书文档" — 实测 4 条路全被反爬挡:

| 方案 | 失败原因 |
|---|---|
| playwright 截 HTML 整页 | Cloudflare reCAPTCHA / "Checking your browser..." 拦截,headless chromium 触发风控,需付费 CAPTCHA solver |
| playwright 截关键段 | 同上,Cloudflare 不分 viewport/整页 |
| curl/wget 直接抓 PMC PDF | NCBI PoW(JS 反爬)返 1.8 KB HTML "Preparing to download...",没 JS 拿不到真 PDF |
| Europe PMC fullTextXML | 只对 OA 文章开放,本篇不在 OA 列表,空响应 |

**当前 v3 最佳折中**:`single` 模式 docx = 中英双语 + 原文主体段落(英文)+ 6 张原图 inline 嵌入(飞书自动下载)+ 末尾 PMC 全文链接。要"版式还原"(表格 / 公式 / 双栏 PDF)只能花钱走 2Captcha 或 EUtils `pmc-oa` 批量(成本高)。

**完整调研 + 强力浏览器分级(L1/L2/L3) + 决策树** 见 `references/screenshot-pitfalls.md`。

**新功能引入守则**(2026-06-16 用户明示):"先试试,不改 skill 文件" — 用一次性脚本验证效果确认值了再固化进 `fetch_pmc.py` / `render.py`。

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
11. **`article-id` 属性顺序**：`pub-id-type="pmcid"` / `pub-id-type="pmcaid"` / `pub-id-type="pmid"`，**属性在前**，不是 `pmcid="..."`。用 ET 的 `.get('pub-id-type')` 或写正则时一定按 `pub-id-type=` 开头。详见 `references/pmc-jats-pitfalls.md` 陷阱 1。
12. **窗宽 vs 反编造铁律**：单刊近 30 天可能 < 5 篇（Lancet Psych / Am J Psych / Biol Psych 常见），**严禁凑数**——放宽到 6 月窗 + 在 output 顶部**显式声明**窗宽与实际命中。详见 `references/pmc-jats-pitfalls.md` 陷阱 4。
13. **JATS graphic href → 真 CDN URL**(2026-06-16 实测):JATS `<graphic xlink:href="...">` 是**裸文件名**(如 `41398_2026_4140_Fig1_HTML.jpg`),**不是完整 URL**。真 URL 模式是 `https://cdn.ncbi.nlm.nih.gov/pmc/blobs/{prefix}/{pmcid}/{hash}/{filename}`,由前端 JS 渲染 HTML 时注入。**正确做法**:抓文章 HTML 页面 → `findall(r'https://cdn\.ncbi\.nlm\.nih\.gov/pmc/blobs/[^"]+', html)` → 按 filename 末尾匹配。**老 bin 路径**(`/pmc/articles/PMCxxx/bin/filename`)对现代文章 404,只当兜底(用户点开虽 404 但不影响其他字段)。详见 § "single 模式 v2 增强"。
14. **NCBI 反爬三件套**(2026-06-16 实测) — 任何想抓 PMC 真 PDF / HTML 截图的尝试都会被这 3 道关挡:(a) Cloudflare reCAPTCHA(IUAM 5s 跳转 + JS 挑战) (b) PoW JS 反爬(PDF "Preparing to download..." 占位 HTML) (c) Europe PMC 镜像只对 OA 文章开 fullTextXML。**实测唯一可行免费方案**:playwright + stealth 脚本 + 2-3 retry + 30s 长等,过 95% Cloudflare。**L1 硬刚工具**:Browserless / ScrapingBee / 2Captcha(付费)/ FlareSolverr(开源,2024 后退化)。详见 `references/screenshot-pitfalls.md` § 三-四。
15. **⚠️ 铁律 · 每次跑 +1 份 docx**(2026-06-17 实测 3 次确认):当前 `render.py` + `lark-cli docs +create` 流程**不做任何去重 / 不删过往**。每次执行 PMC 跑(手动或 cron)→ 1 篇 = +1 份 docx。**修复前**手动维护 folder(每跑完用 `drive +search` 找旧的删);**修复方向**:slug 去重 / 覆盖式 update / 跑前全删 folder,参考 `references/feishu-doc-workflow.md` §7。**新 session 跑前必读**:"folder 心理精神科论文 当前有 N 份 docx" — 评估是否要清理,避免长期堆积。

## 关联文件

- `scripts/fetch_pmc.py` — 主抓取脚本（已含 1-10 + 13 全部工程要点）
- `scripts/render.py` — output_mode=doc 模式的飞书文档生成器
- `scripts/journals.json` — 期刊白名单 + emoji 规则
- **`references/pmc-jats-pitfalls.md`** — 2026-06-11 实测补遗:4 个边角陷阱(`article-id` 属性顺序 / EUtils `db=pmc` 裸数字 vs PMC 前缀 / 反编造铁律下的窗宽放宽 / 11 篇无摘要的体裁识别)+ sci-psychiatry-digest vs pmc-q1-weekly 重叠建议(给 curator 看)
- **`references/feishu-doc-workflow.md`** — 2026-06-16 端到端实战手册:Step 0 前置 / Step 1-3 抓+翻译+渲染(grid + single 双模式)/ Step 4 lark-cli 写云文档(`--content @<file>` 相对路径 / `<title>` XML 必带 / `--parent-token` 一步到位 / 索引延迟)/ Step 5 飞书消息汇总 / Step 6 失败兜底 / Step 7 cron 堆积铁律 / Step 8 验证 checklist / Step 9 已知铁律。供其他 AI 一次跑通。
- **`references/screenshots-ceiling.md`** — 🆕 2026-06-16 "原文截图"调研结论:免费方案天花板 = 6 张原图 + 主体段落(v3);真·整页截图需付费(2Captcha / Browserless 等),小批量不划算;含反检测脚本模板 + 拼图模板 + 升级到 v4 的触发条件。
- **`references/screenshot-pitfalls.md`** — 🆕 2026-06-16 截图/真版式调研实战:NCBI/PMC 反爬三件套 + 强力浏览器分级(L1/L2/L3)+ playwright + stealth 实战代码 + 决策树(给图/整页/关键段/PDF 选型)+ v3 现状 90% 覆盖率评估。**任何"抓学术 PDF / 截图"的 skill 先看这个**。

## 高级参数（脚本）

| 参数 | 说明 |
|---|---|
| `--dynamic-if` | 用 OpenAlex `2yr_mean_citedness` 拉取近似 IF（兜底白名单） |
| `--require-fulltext` / `--no-require-fulltext` | 是否强制全文可读（默认强制） |
| `--max-per-journal` | 每刊最大抓取数（默认 60） |

## 扩展学科

编辑 `scripts/journals.json`，按 `field` 增加学科分组（期刊名 + ISSN + 近似 IF + 分区标注）。初始内置 `psychiatry`（精神病学/心理学）。
