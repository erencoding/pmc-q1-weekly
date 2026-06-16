# PMC JATS / EUtils 实战陷阱(2026-06-11 实测补遗)

> 跟主 SKILL 的「关键工程要点(踩坑经验)」互补。`fetch_pmc.py` 已覆盖 90% 的坑,
> 本文件记录**本 session 实地再跑发现的 4 个边角**——下次手动跑或写新 skill 时不再踩。

## 1. `article-id` 属性顺序陷阱(P0,极易踩)

JATS XML 里 `<article-id>` 的属性顺序是 **`pub-id-type` 在前**,**不是** 类型名在前。

### 错误正则(0 命中)

```python
# ❌ 错:把 type 当 attribute 写
m = re.search(r'<article-id pmid="(\d+)">(\d+)</article-id>', xml)
# 或
m = re.search(r'<article-id pmc="(PMC\d+)">', xml)
```

### 正确 XPath(直接用 ET 拿 attribute)

```python
# ✅ 对:用 ET 的 .get('pub-id-type') 而不是写死正则
for aid in art.iter("article-id"):
    if aid.get("pub-id-type") == "pmcid":
        pmcid = aid.text                # "PMC13235725"
    elif aid.get("pub-id-type") == "pmcaid":
        numid = aid.text                # "13235725"(纯数字,推荐做主键)
    elif aid.get("pub-id-type") == "pmid":
        pmid = aid.text
    elif aid.get("pub-id-type") == "doi":
        doi = aid.text
```

> **历史踩坑**:2026-06-11 跑 sci-psychiatry-digest 复盘,首次写 `<article-id[^>]*pub-id-type="pmcid"[^>]*>(PMC\d+)</article-id>` 错把 `pmc=` 当 attribute 写在最前,导致 0/48 篇拿到 PMCID。修正后 48/48 命中。

## 2. EUtils `db=pmc` 返回的 ID 是裸数字,**不是** `PMC12345`

esearch PMC 库时 `idlist` 里是 `["13235725","13176872"]`,**没有 PMC 前缀**。
但 efetch 的 XML 里 `article-id pub-id-type="pmc"` 又**带 PMC 前缀**。

```python
# ❌ 错:以为都是带 PMC 前缀的
url = f"https://pmc.ncbi.nlm.nih.gov/articles/{pmid}/"  # → 404

# ✅ 对:统一用 pmcaid(纯数字)做主键,构造链接时手动加前缀
pmcaid = "13235725"
url = f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{pmcaid}/"
```

`fetch_pmc.py` 已用 `pmcaid` 做主键,直接继承即可。

## 3. EUtils `sort=pub_date` + 时间窗双过滤(已用,可省事)

`fetch_pmc.py` 是 OR-批量 + esummary sortdate 二次过滤。
**单刊模式**(如 sci-psychiatry-digest 每刊固定 5 篇)可用更简单姿势:

```python
# 单刊 5 篇,直接 esearch + sort=pub_date
term = f'"World Psychiatry"[Journal] AND 2026/01:2026/06[dp]'
url = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
       f"?db=pmc&term={urllib.parse.quote(term)}&retmax=5&retmode=json&sort=pub_date")
ids = json.loads(urllib.request.urlopen(url).read())["esearchresult"]["idlist"]
# ids = ['13176872','13176878','13176870',...]  ← 纯数字
```

实测 10 个 Q1 刊 × retmax=5 = 48 个 unique id(部分刊近 30 天 < 5,需放宽到 6 个月窗)。

## 4. 时间窗过窄时**显式标注**,绝不凑数(sci-psychiatry-digest 反编造铁律)

某些 Q1 刊近 30 天只发 1-4 篇(Lancet Psychiatry / Am J Psych / Biol Psych / Schizo Bull),
按 SKILL v3.1 **反编造铁律**严禁"为了凑 5 篇"瞎补。

**正确做法**:放宽到 6 个月窗(2026 H1),在 SKILL output 顶部**显式声明**窗宽 + 实际命中数:

```
📅 检索窗口:2026-01-01 ~ 2026-06-11(近半年)
⚠️ 5 篇固定/刊:近 30 天 Lancet Psych 仅 4 条,按反编造铁律
   不凑数,放宽到 6 月窗;每刊"取 5"对 Lancet 是 4 条
```

**严禁**的两种偷懒:
- ❌ 用其他期刊文章"补"缺口
- ❌ 把 Lancet 4 篇编成"5 篇"凑数

## 5. PMC URL HEAD 批量预验证(便宜可信)

写到正式输出前,1 个循环验证 50 个 PMC URL,几十秒搞定:

```python
import urllib.request
for art in articles:
    url = f"https://pmc.ncbi.nlm.nih.gov/articles/PMC{art['pmcaid']}/"
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            art['pmc_ok'] = (r.status == 200)
    except Exception:
        art['pmc_ok'] = False
```

实测 48/48 = 200 OK(2026-06-11),50 个 URL 总耗时 ~30s。
**写到 output 顶部**:`✅ 48/48 PMC 链接 200 OK 验证` —— 跟 sibling openFDA `check_openfda.py` 同等价值。

## 6. 11 篇无摘要的体裁识别(EXCLUDE regex 已覆盖)

PMC 库里**没有 abstract** 的文章,通常体裁是:

| 标题关键词 | 体裁 | 处理 |
|---|---|---|
| `Error in Visual Abstract` | 勘误(Erratum) | 排除 |
| `Correction: ...` | 更正(Correction) | 排除 |
| `Editorial` / `Viewpoint` / `Perspective` | 社论/观点 | 排除(可保留作背景) |
| 无关键词但无 abstract | Letter / Commentary | 视情况 |

`fetch_pmc.py` 的 `EXCLUDE` 正则已包含 `error in|correction|erratum|visual abstract|retraction`,
**新增建议**:`EXCLUDE` 加 `editorial` / `perspective` / `viewpoint` / `letter to`。
**手动写代码的 skill**(比如 sci-psychiatry-digest)需手工打 genre 标签,逻辑见下:

```python
title = a["title"].lower()
if "correction" in title or "erratum" in title:
    a["genre"] = "更正"
elif "error in" in title and "abstract" in title:
    a["genre"] = "勘误"
elif a.get("abstract"):
    a["genre"] = "原创研究"
else:
    a["genre"] = "社论/观点"
```

## 7. SKILL 重叠说明(sci-psychiatry-digest vs pmc-q1-weekly)

`sci-psychiatry-digest`(月报)与 `pmc-q1-weekly`(周报)任务形态高度重叠:

| 维度 | sci-psychiatry-digest | pmc-q1-weekly |
|---|---|---|
| 频率 | 月 | 周 |
| 窗宽 | 6 个月(本期反编造需要) | 7/14/30 天 |
| 刊数 | 10 个固定 Q1 刊 | 配置式白名单 |
| 摘要 | efetch XML 解析 JATS | efetch + ET 解析 |
| 翻译 | SKILL 留给 agent 跑 | 留给 agent 跑 |
| 脚本 | 无,agent 手抓 | `fetch_pmc.py` 完整 pipeline |

**复用建议**:`sci-psychiatry-digest` 月报可直接 `subprocess` 调 `pmc-q1-weekly/scripts/fetch_pmc.py` 拿 JSON,
**不必重写** PMC 抓取逻辑;只做①窗宽参数 ②期刊白名单 ③中文简介 + 主题 emoji 三件事。

**留给 curator 的话**:这两个 skill 合并为单一 `psychiatry-pmc-digest`(配置频率 daily/weekly/monthly)会更紧凑,本 session 不动。

---

**版本**:v1.0 (2026-06-11)
**作者**:Judy (朱迪)
**验证状态**:2026-06-11 沙箱实测 sci-psychiatry-digest 48 篇 / 48 PMC 200 OK
**来源 session**:2026-06-11 双 Skill 飞书输出(drug-weekly + sci-digest)
