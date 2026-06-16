# PMC Q1 → 飞书云文档 端到端 workflow(2026-06-16 实战手册)

> 把 pmc-q1-weekly 的 `pmc_result.json` 渲染成**飞书云文档**的完整 step-by-step。
>
> 与兄弟 `psych-news-digest/references/lark-cli-pitfalls.md` 互补 — 本文件专讲 PMC 周报,
> lark-cli 通用坑(切 user / 索引延迟 / `--content @<file>` 相对路径)看兄弟文件。
>
> **适用版本**:pmc-q1-weekly v1.x · lark-cli v1.0.53+ · Feishu user OAuth ready

## 0. 前置

| 组件 | 用途 | 验证 |
|---|---|---|
| `lark-cli` v1.0.53+ | 写飞书云文档 | `lark-cli --version` ≥ 1.0.53 |
| Feishu user OAuth | 写到**自己**云盘 | `lark-cli auth status` 看到 openId + 已授权 |
| 目标云盘 folder | 归档 weekly docx | 默认「心理精神科新闻日志」(沿用 psych-news-digest) |
| `pmc-q1-weekly` 脚本 | 抓数据 | `python3 scripts/fetch_pmc.py --field psychiatry --days 7` |
| `scripts/render.py` | JSON → XML body | 见下 step 2 |

**降级矩阵**:

| 环境 | 能做 | 不能做 |
|---|---|---|
| 全功能 | 抓 + 翻译 + 写云文档 + 推消息 | — |
| 无 lark-cli | 抓 + 翻译 | 不能写云文档;走 `output_mode=direct` 对话内卡片 |
| 有 lark-cli 但 user 未授权 | 抓 + 翻译 | 只能写 bot 云盘(user 需手动加协作者) |

## 1. 抓数据

```bash
cd /home/admin/.hermes/skills/pmc-q1-weekly
python3 scripts/fetch_pmc.py --field psychiatry --days 7 --out /tmp/pmc_result.json
# → JSON: {meta, articles[]}
```

- `meta.window_days` = 实际窗宽(7/14/30 自动放宽)
- `meta.widened` = `true` 表示已放宽
- `articles[i]` 字段:`pmcid` / `pmcaid` / `pmid` / `doi` / `jname` / `if_` / `zone` /
  `title` / `abstract` / `date` / `has_fulltext` / `emoji`(脚本预填)

**反编造铁律**(本 skill 已硬编码):无 abstract / 无 body / 命中 EXCLUDE 正则(勘误/更正/visual abstract/retraction/letter/editorial/perspective)的一律剔除。**严禁**为凑数瞎补。

## 2. 翻译回填(由 Agent 完成,非脚本)

读 `/tmp/pmc_result.json`,对每篇 `title` + `abstract` 做**学术化中文意译**(80-120 字),
回填 `zh_title` / `zh_abstract` 字段。emoji 字段用 `journals.json` 的 `_emoji_rules` 预填
的即可,Agent 按内容微调。

**翻译规范**:

1. 术语准确(RCT / CHR / MDD / PTSD / polygenic risk score → 多基因风险评分 等)
2. 通用缩写保留英文(RCT / CHR / EEG / fMRI / GWAS / AI)
3. 摘要 80-120 字,「研究目的 + 方法 + 主要发现/结论」
4. **不编造数据**;原文摘要缺失则 zh_abstract 基于 `[正文摘录]` 概括并保留标注
5. 标题意译为通顺中文短句

参考 PMC 中文速览示例见 `pmc-jats-pitfalls.md` §7。

## 3. 渲染为飞书 docx body(两种模式)

### 3a. grid 模式(原,大批量 ≥ 10 篇)

```bash
python3 scripts/render.py --in /tmp/pmc_result.json --out /tmp/pmc-body.xml --mode grid
```

输出:1 份大 docx,按期刊分组的 grid 卡片表格。适合周报/月报大批量。

### 3b. single 模式(2026-06-16 新增,中小批量 1-5 篇)

```bash
# 第 0 篇(默认),docx 标题前缀 = "2026-06-12_"
python3 scripts/render.py --in /tmp/pmc_result.json --out /tmp/pmc-body.xml \
    --mode single --index 0 --title-prefix "2026-06-12_"
```

输出:1 篇 1 docx 的双语结构(每篇 1 docx,与 psych-news-digest 一致)。
**结构**:
- `<title>` XML 标签 = 标题前缀 + 中文标题 + 英文标题
- `<h1>` = 中文标题
- 🇬🇧 英文原标题
- 元信息 callout(emoji + 期刊 + IF + 分区 + 日期 + PMCID + PMID + DOI)
- `<h2>📝 中文摘要</h2>` — zh_abstract
- `<h2>🇬🇧 English Abstract</h2>` — 原文 abstract
- `<h2>📚 元信息 / Links</h2>` — PMC URL + IF 近似值声明

**适用场景**:
- 5 命中 / 1 有效(本周典型)→ 1 份 docx 1 篇
- 用户需要"1 篇 1 文件"便于分享单篇
- 双语结构让英文受限的读者直接看中文,英文好的看原文

### 3c. 批量 single(2-5 篇,每篇 1 docx)

循环跑:
```python
import subprocess, os
n = len(json.load(open("/tmp/pmc_result.json"))["articles"])
for i in range(n):
    prefix = f"{date_str}_"  # 如 "2026-06-12_"
    subprocess.run([
        "python3", "scripts/render.py",
        "--in", "/tmp/pmc_result.json",
        "--out", f"/tmp/pmc-body-{i}.xml",
        "--mode", "single", "--index", str(i),
        "--title-prefix", prefix
    ], cwd="/home/admin/.hermes/skills/pmc-q1-weekly")
```

## 4. 写飞书云文档(关键 lark-cli 坑)

### 4a. `--content @<file>` 必须 cwd 相对路径

lark-cli v1.0.53 校验 file path,绝对路径报 "unsafe path"。

```python
# ✅ 正确:把临时文件放在 cwd 下
import os, subprocess
os.chdir("/tmp")
subprocess.run([
    "lark-cli", "docs", "+create", "--as", "user",
    "--doc-format", "markdown",
    "--content", "@/tmp/pmc-body-0.xml",   # ✗ 这样错
])
# 实际:先把 xml mv 到 cwd 下,或 cwd 切到 /tmp
```

**正确姿势**:
```python
import os, subprocess
xml_path = "/tmp/pmc-body-0.xml"
tmp_name = os.path.basename(xml_path)   # "pmc-body-0.xml"
# xml_path 已经在 /tmp 下,只需 cwd=/tmp
subprocess.run([
    "lark-cli", "docs", "+create", "--as", "user",
    "--parent-token", folder_token,     # 一步到位,见 §4b
    "--doc-format", "markdown",
    "--content", f"@{tmp_name}",
], cwd="/tmp", capture_output=True, text=True)
```

### 4b. `--parent-token <folder>` 一次到位

```bash
# ✅ 1 步:直接建到目标 folder
lark-cli docs +create --as user \
  --parent-token "$FOLDER_TOKEN" \
  --doc-format markdown \
  --content "@pmc-body-0.xml"

# ❌ 2 步(多余):先建 root,再 drive +move
lark-cli docs +create --as user --content "..."   # 在 root
lark-cli drive +move --as user --file-token "$DOC_ID" --folder-token "$FOLDER_TOKEN" --type docx
```

### 4c. `<title>` XML 标签必带

lark-cli v2 markdown 格式下:
- `--title` flag **已废止**
- `# 标题` 也不被识别为 title(实测变 "Untitled")
- 必须用 `<title>...</title>` XML 标签,在 `--content` 字符串最前

`render.py --mode single` 已自动输出 `<title>` 在最前。

### 4d. 不要写 `# 标题`(与 `<title>` 重复)

lark-cli v2 markdown 模式下,`<title>` 是 docx 页头标题,正文里再写 `# 标题` 会双标题。
**正确**:`render.py` 的 single 模式用 `<h1>` 而不是 `#` — 兼容飞书 v2 渲染。

## 5. 飞书消息汇总(本 skill 配套 send_message)

docx 创建后,推一条汇总消息到当前 chat(沿用 psych-news-digest 模式):

```
🧠 PMC 一区周报 · 近 7 天收录 N 篇
   (附 N 份 docx 链接列表 + 期刊概览)
```

- 走 `send_message` 工具(直连飞书网关,绕过 lark-cli user 身份 scope 限制)
- docx 链接以 emoji 行 `📄 {title}:{url}` 列出
- 末尾注:⚠️ N 条命中 / 0 条存档失败(如有则具体列出,见 §6 兜底)

## 6. 失败兜底

| 失败 | 兜底 |
|---|---|
| `lark-cli docs +create` 返错 | 该篇不渲染 `📄 飞书文档:` 行,消息末尾汇总 `⚠️ N 条存档失败:<title>` |
| folder_token 不存在 | 走 `lark-cli drive +create-folder` 建一次,缓存到 vault |
| 抓取 `{"error": ...}` | 整周不写 docx,消息只发"本周 PMC 抓取失败" + 错误详情 |
| 0 命中 | 消息发"本周(7 天)PMC Q1 入库 0 篇;如需回顾,跑 `--days 30`" + 跑 30 天 fallback |

**反编造铁律**(再强调):docx 失败**绝不伪造** doc_url,失败就是失败。

## 7. cron 跑会无限堆积 docx(已知铁律)

每次 cron 跑:
- `fetch_pmc.py` 抓到 N 篇
- 渲染阶段:每篇调 `docs +create` → **新 docx**(folder 永不清)

**结果**:1 篇文跑 30 天 = 30 份完全相同的 docx 在 folder 堆。

**修法**(参考 psych-news-digest 同样问题,3 选 1):
- **A. 按 slug 跳创建**:创前 `drive +search` 已有 docx,url slug 匹配则 skip
- **B. 覆盖式 update**:`drive +update --file-token <id>` 全量覆盖
- **C. 每天全删重建**:`drive +delete --file-token <each>` 全清 + 重建

**推荐 A**(简单稳);本 skill **当前 v1 未实现任何去重**,新建 cron 时务必在 prompt
里显式指定策略。

## 8. 验证 checklist

跑完一遍后人工 / 自动校验:

- [ ] `pmc_result.json` 存在且 N > 0
- [ ] 翻译字段 zh_title / zh_abstract **没有空字符串**(空 = agent 漏翻)
- [ ] `lark-cli auth status` 仍是当前 user openId
- [ ] folder_token 仍是当前 user 云盘的「心理精神科新闻日志」
- [ ] 创建的 N 份 docx 都在该 folder 下(用 `drive +search --folder-tokens <folder> --doc-types docx`,
  **注意索引延迟 5-10 分钟**,别因少 1 条误判)
- [ ] 飞书消息已发,`📄` 行的 docx URL 都能点开

## 9. 已知铁律(2026-06-16 实战补)

1. **`drive +search` 索引延迟 5-10 分钟** — 创建返回的 `document_id` + URL 才是权威凭据
2. **`docs +fetch` 命令可能不存在** — 验证用 `docs +update` 看 revision_id 或信任 URL
3. **`lark-cli auth login --recommend` 不给 `search:docs:read`** — 要单独补一次 scope
4. **`--api-version v1` 已废止** — 直接省略
5. **`docs +delete` 必须 `--yes`** — 实际走 `drive +delete --file-token --type docx --yes`
6. **认证弹窗的 bot 名 = 当前 lark-cli appId** — 不是 user 也不一定是你常用的 bot

详细 lark-cli 通用 pitfall 见 `psych-news-digest/references/lark-cli-pitfalls.md`。
JATS / EUtils 抓取 pitfall 见 `references/pmc-jats-pitfalls.md`。

---

**版本**:v1.0 (2026-06-16 实战首版)
**作者**:Judy (朱迪) · 用户 086674 协助验证
**验证状态**:2026-06-16 实测 pmc-q1-weekly 1 篇 / 1 docx / 双语结构 ✔
