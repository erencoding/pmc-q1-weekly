#!/usr/bin/env python3
"""
pmc-q1-weekly: 抓取本周入库、全文可读、Q1 期刊论文。

用法:
  python3 fetch_pmc.py --field psychiatry --days 7 \
      [--max-per-journal 60] [--require-fulltext] [--dynamic-if] [--out pmc_result.json]

特性:
  1 日期多格式兼容(年/年月/年月日)        2 全文可读校验(<body>)
  3 空结果自动放宽时间窗(7→14→30)       4 期刊 OR 批量检索(请求数 N→1~2)
  5 OpenAlex 动态近似 IF(--dynamic-if)   6 DOI 跨刊去重
  7 网络全失败 → 退出码 2
"""
import urllib.request, urllib.parse, json, time, re, argparse, os, sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
OPENALEX = "https://api.openalex.org"
API_KEY = os.environ.get("NCBI_API_KEY", "")
EXCLUDE = re.compile(r"(error in|correction|erratum|visual abstract|retraction|^reply|table of contents|masthead|author response)", re.I)
SLEEP = 0.12 if API_KEY else 0.4  # 有 key 可提速


class AllFailed(Exception):
    pass


def http_get(url, timeout=60):
    last = None
    for _ in range(3):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            last = e
            time.sleep(1.5)
    raise last


def resolve_figure_url(pmcid, filename, html=None):
    """PMC JATS XML 里的 graphic href 是裸文件名,真 URL 在 HTML 渲染后注入。

    策略:抓(已缓存)文章 HTML 页面 → 在 HTML 里 findall 所有 'cdn.ncbi.nlm.nih.gov/pmc/blobs/...' →
    按 filename 末尾匹配(CDN 路径含 /{prefix}/{pmcid}/{hash}/{filename})。
    失败兜底:走 bin 路径(老格式,部分文章可能仍可用)。

    Args:
        pmcid: 纯数字 PMCID
        filename: JATS 里 graphic 的 href(裸文件名如 '41398_2026_4140_Fig1_HTML.jpg')
        html: 已抓的 HTML 文本(可选,加速批量调用)

    Returns:
        完整 URL(str),失败返回 bin 路径(让 docx 链接仍可点)
    """
    if not filename or not pmcid:
        return ""
    if filename.startswith("http"):
        return filename
    fallback = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/bin/{filename}"
    try:
        if html is None:
            html = get_html_page(pmcid)
        if not html:
            return fallback
        # 在 HTML 里 findall 所有 CDN blob URL
        all_cdn = re.findall(r'https://cdn\.ncbi\.nlm\.nih\.gov/pmc/blobs/[^"\s]+', html)
        # 按 filename 末尾匹配
        for cdn_url in all_cdn:
            if cdn_url.endswith(filename) or cdn_url.split("/")[-1] == filename:
                return cdn_url
        return fallback
    except Exception:
        return fallback


def eutils(endpoint, params):
    if API_KEY:
        params = dict(params, api_key=API_KEY)
    return http_get(f"{BASE}/{endpoint}?" + urllib.parse.urlencode(params))


def load_field(field):
    here = os.path.dirname(os.path.abspath(__file__))
    data = json.load(open(os.path.join(here, "journals.json")))
    if field not in data:
        sys.exit(f"未知学科 field={field}，可选: {[k for k in data if k != '_emoji_rules']}")
    return data[field]["journals"], data.get("_emoji_rules", {})


# ---------- 多格式日期解析 ----------
def parse_date(s):
    if not s:
        return None
    s = s.split()[0] if "/" in s else s
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y %b %d", "%Y %b", "%Y/%m", "%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except Exception:
            continue
    # "2026 Jun" 这类
    try:
        return datetime.strptime(" ".join(s.split()[:2]), "%Y %b")
    except Exception:
        return None


# ---------- OR 批量检索 ----------
def search_ids_batch(journals, start, end, retmax):
    # 期刊用 OR 合并;db=pmc 默认即免费全文库
    jclause = " OR ".join(f'"{j}"[Journal]' for j in journals)
    term = f'({jclause}) AND ("{start}"[PDAT] : "{end}"[PDAT])'
    ids, retstart, got_any = [], 0, False
    while True:
        res = json.loads(eutils("esearch.fcgi", {
            "db": "pmc", "term": term, "retmax": str(retmax),
            "retstart": str(retstart), "retmode": "json"}))
        er = res.get("esearchresult", {})
        batch = er.get("idlist", [])
        got_any = True
        ids.extend(batch)
        total = int(er.get("count", "0"))
        retstart += len(batch)
        if retstart >= total or not batch or retstart >= retmax * len(journals):
            break
        time.sleep(SLEEP)
    return ids, got_any


def fetch_summaries(ids):
    recs = {}
    for i in range(0, len(ids), 30):
        batch = ids[i:i+30]
        res = json.loads(eutils("esummary.fcgi", {"db": "pmc", "id": ",".join(batch), "retmode": "json"}))
        result = res.get("result", {})
        for uid in result.get("uids", []):
            d = result[uid]
            recs[uid] = {
                "uid": uid,
                "title": (d.get("title") or "").strip(),
                "source": d.get("fulljournalname") or d.get("source", ""),
                "sortdate": d.get("sortdate") or d.get("epubdate") or d.get("pubdate", ""),
                "doi": next((aid.get("value") for aid in d.get("articleids", [])
                             if aid.get("idtype") == "doi"), ""),
            }
        time.sleep(SLEEP)
    return recs


# ---------- 全文可读校验 + body 段落 + 图片 URL ----------
# HTML 页面缓存(每 PMC id 只抓一次,避免 6 张图 × 1 次重复抓)
_HTML_CACHE: dict = {}


def get_html_page(pmcid):
    """抓 PMC 文章 HTML 页面(per-pmcid 缓存)。返回 str,失败返 ''。"""
    if pmcid in _HTML_CACHE:
        return _HTML_CACHE[pmcid]
    try:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmcid}/"
        html = http_get(url, timeout=20)
        _HTML_CACHE[pmcid] = html
        time.sleep(0.3)
        return html
    except Exception:
        _HTML_CACHE[pmcid] = ""
        return ""


def fetch_fulltext(ids):
    """对 PMC id 取 abstract + 是否有 body + authors + body 段 + 图片 URL。

    输出 schema:
      abstract: str                    # 摘要纯文本
      has_fulltext: bool               # 是否有 body
      authors: str                     # 前 3 作者 + et al.
      body_sections: list[str]         # body 段落(英文,过滤短段)
      body_text: str                   # body 全文拼接(限定 8000 字符防 docx 爆)
      figures: list[dict]              # [{label, caption, url}],label=F1/F2/...
    """
    out = {}
    for i in range(0, len(ids), 20):
        batch = [b for b in ids[i:i+20] if b]
        if not batch:
            continue
        xml = eutils("efetch.fcgi", {"db": "pmc", "id": ",".join(batch), "retmode": "xml"})
        try:
            root = ET.fromstring(xml)
        except Exception:
            continue
        for art in root.iter("article"):
            numid = None
            for aid in art.iter("article-id"):
                if aid.get("pub-id-type") == "pmcaid":
                    numid = aid.text
            if not numid:
                for aid in art.iter("article-id"):
                    if aid.get("pub-id-type") == "pmcid":
                        numid = (aid.text or "").replace("PMC", "")
            abs_txt = ""
            for ab in art.iter("abstract"):
                abs_txt = " ".join("".join(p.itertext()) for p in ab.iter("p"))
                if abs_txt.strip():
                    break
            body = next(art.iter("body"), None)
            has_body = body is not None and any(len("".join(p.itertext())) > 60 for p in body.iter("p"))
            if not abs_txt.strip() and has_body:
                ps = [" ".join("".join(p.itertext()).split()) for p in body.iter("p")]
                ps = [p for p in ps if len(p) > 40]
                abs_txt = "[正文摘录] " + " ".join(ps[:2]) if ps else ""

            # body 段落(英文原文,过滤 <40 字符的短段)
            body_sections = []
            body_text_full = ""
            if has_body:
                for p in body.iter("p"):
                    txt = " ".join("".join(p.itertext()).split())
                    if len(txt) >= 40:
                        body_sections.append(txt)
                body_text_full = "\n\n".join(body_sections)
                # 限 12000 字符防 docx 爆(原 8000,2026-06-17 v4 放宽到 12000 含全文主体)
                if len(body_text_full) > 12000:
                    body_text_full = body_text_full[:12000] + "..."

            # 一次性抓 HTML 页面(供所有 fig 共享)
            html_page = get_html_page(numid)

            # 图片(label + caption + URL)
            figures = []
            for fig in art.iter("fig"):
                label_el = fig.find("label")
                caption_els = fig.findall("caption")
                caption = " ".join(
                    "".join(p.itertext()) for c in caption_els for p in c.iter("p")
                ).strip()
                if caption and len(caption) > 300:
                    caption = caption[:300] + "..."
                # 找 graphic 拿 filename
                filenames = []
                for g in fig.iter("graphic"):
                    href = g.get("{http://www.w3.org/1999/xlink}href") or g.get("href")
                    if not href or href.startswith("data:"):
                        continue
                    if href.startswith("http"):
                        # 已是完整 URL,直接用
                        filenames.append(href)
                    else:
                        # 裸文件名 / 相对路径
                        filenames.append(href)
                figures.append({
                    "label": (label_el.text or "").strip() if label_el is not None else "",
                    "caption": caption,
                    "url": "",  # 第一轮不解析 URL(见下)
                    "filename": filenames[0] if filenames else "",
                })
            # 批量解析图 URL(用一次性抓的 html_page)
            for fig in figures:
                if fig["filename"]:
                    fig["url"] = resolve_figure_url(numid, fig["filename"], html=html_page)

            names = []
            for c in art.iter("contrib"):
                if c.get("contrib-type") == "author":
                    sn = c.find(".//surname"); gn = c.find(".//given-names")
                    if sn is not None:
                        names.append(((gn.text + " ") if gn is not None else "") + sn.text)
            if numid:
                out[numid] = {
                    "abstract": abs_txt.strip(),
                    "has_fulltext": bool(has_body),
                    "authors": "; ".join(names[:3]) + (" et al." if len(names) > 3 else ""),
                    "body_sections": body_sections,
                    "body_text": body_text_full,
                    "figures": figures,
                }
        time.sleep(SLEEP)
    return out


# ---------- OpenAlex 动态近似 IF ----------
def openalex_if(issn):
    if not issn:
        return None
    try:
        data = json.loads(http_get(f"{OPENALEX}/sources/issn:{issn}", timeout=20))
        v = data.get("summary_stats", {}).get("2yr_mean_citedness")
        return round(v, 1) if v else None
    except Exception:
        return None


# ---------- 研究类型 → emoji ----------
def pick_emoji(title, abstract, rules):
    text = (title + " " + abstract).lower()
    for kw, emo in rules.items():
        if re.search(kw, text):
            return emo
    return "📄"


def collect(args, days):
    journals, emoji_rules = load_field(args.field)
    jnames = [j["name"] for j in journals]
    jmeta = {j["name"]: j for j in journals}
    today = datetime.now()
    start_dt = today - timedelta(days=days)
    start, end = start_dt.strftime("%Y/%m/%d"), today.strftime("%Y/%m/%d")

    print(f"[1/4] PMC OR-批量检索 {len(jnames)} 刊，窗口 {start}~{end}", file=sys.stderr)
    ids, ok = search_ids_batch(jnames, start, end, args.max_per_journal)
    if not ok:
        raise AllFailed("所有检索请求失败（疑似网络问题）")
    ids = list(dict.fromkeys(ids))
    print(f"      命中 {len(ids)} 条", file=sys.stderr)

    print(f"[2/4] 取元数据", file=sys.stderr)
    summ = fetch_summaries(ids)

    print(f"[3/4] 取全文/摘要并校验", file=sys.stderr)
    ft = fetch_fulltext(list(summ.keys()))

    # 动态 IF 缓存
    if_cache = {}
    if args.dynamic_if:
        print(f"[3.5] OpenAlex 拉取近似 IF", file=sys.stderr)
        for j in journals:
            v = openalex_if(j.get("issn", ""))
            if v:
                if_cache[j["name"]] = str(v)
            time.sleep(SLEEP)

    def match_journal(src):
        s = (src or "").lower()
        for name, meta in jmeta.items():
            if name.lower() in s or s in name.lower():
                return name, meta
        return src, {"if": "-", "zone": "Q1 (近似)"}

    print(f"[4/4] 过滤 + 去重", file=sys.stderr)
    recs, seen_doi = [], set()
    for uid, d in summ.items():
        dt = parse_date(d.get("sortdate", ""))
        if not (dt and dt >= start_dt):
            continue
        if EXCLUDE.search(d["title"]):
            continue
        info = ft.get(uid, {})
        # --require-fulltext 时必须 has_fulltext;否则至少要有 abstract
        if args.require_fulltext and not info.get("has_fulltext"):
            continue
        if not info.get("abstract"):
            continue
        # DOI 去重
        doi = (d.get("doi") or "").lower()
        if doi and doi in seen_doi:
            continue
        if doi:
            seen_doi.add(doi)
        jname, meta = match_journal(d["source"])
        if_val = if_cache.get(jname, meta.get("if", "-"))
        recs.append({
            "pmcid": uid,
            "doi": doi,
            "title": d["title"],
            "journal": d["source"],
            "jname": jname,
            "if_": if_val,
            "if_source": "OpenAlex 近似" if jname in if_cache else "JCR 近似",
            "zone": meta.get("zone", "Q1 (近似)"),
            "has_fulltext": bool(info.get("has_fulltext")),
            "date": dt.strftime("%Y-%m-%d"),
            "authors": info.get("authors", ""),
            "abstract": info["abstract"],
            "url": f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{uid}/",
            "emoji": pick_emoji(d["title"], info["abstract"], emoji_rules),
            "zh_title": "",
            "zh_abstract": "",
            "body_text": info.get("body_text", ""),
            "figures": info.get("figures", []),
        })
    recs.sort(key=lambda x: (x["date"], -(float(x["if_"]) if x["if_"] not in ("-", "") else 0)), reverse=True)
    return recs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--field", default="psychiatry")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--max-per-journal", type=int, default=60)
    ap.add_argument("--require-fulltext", action="store_true", default=True)
    ap.add_argument("--no-require-fulltext", dest="require_fulltext", action="store_false")
    ap.add_argument("--dynamic-if", action="store_true")
    ap.add_argument("--out", default="pmc_result.json")
    args = ap.parse_args()

    # 空结果自动放宽时间窗
    windows = sorted({args.days, 14, 30})
    windows = [w for w in windows if w >= args.days] or [args.days]
    recs, used = [], args.days
    try:
        for w in windows:
            recs = collect(args, w)
            used = w
            if recs:
                break
            print(f"  ⚠ 窗口 {w} 天无结果，放宽重试…", file=sys.stderr)
    except AllFailed as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(2)

    payload = {
        "meta": {
            "field": args.field,
            "window_days": used, "requested_days": args.days,
            "count": len(recs),
            "note": "IF/分区为近似值（JCR 或 OpenAlex），精确分区以 Web of Science 官方为准。",
            "widened": used != args.days,
        },
        "articles": recs,
    }
    json.dump(payload, open(args.out, "w"), ensure_ascii=False, indent=2)
    tip = f"（已放宽至 {used} 天）" if used != args.days else ""
    print(f"✅ 有效文章 {len(recs)} 篇{tip} → {args.out}", file=sys.stderr)
    print(payload["meta"]["note"], file=sys.stderr)


if __name__ == "__main__":
    main()
