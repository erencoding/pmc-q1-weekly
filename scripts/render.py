#!/usr/bin/env python3
"""
pmc-q1-weekly 渲染器:把 {meta, articles}(已由 Agent 回填 zh_title/zh_abstract/emoji)
渲染为飞书文档 body。

两种模式(2026-06-16 实战分叉):
  --mode grid   多篇分组表格(原行为,大批量用)
  --mode single 1 篇 1 docx 双语结构(中小批量用, 与 psych-news-digest 双语模板一致)

用法:
  # 多篇 grid(原行为)
  python3 render.py --in pmc_result.json --out body.xml --mode grid

  # 单篇双语(中小批量用, 默认走 zh_title / zh_abstract)
  python3 render.py --in pmc_result.json --out body.xml --mode single --index 0
  python3 render.py --in pmc_result.json --out body.xml --mode single --index 0 --title-prefix "2026-06-12_"
"""
import json, argparse, html
from collections import OrderedDict


def esc(s):
    return html.escape(s or "", quote=False)


def load(inp):
    data = json.load(open(inp))
    if isinstance(data, list):  # 兼容旧结构
        return {"articles": data, "meta": {"count": len(data), "note": "", "widened": False, "window_days": 7}}
    return data


def group_by_journal(recs):
    g = OrderedDict()
    for r in recs:
        g.setdefault(r["jname"], []).append(r)
    return OrderedDict(sorted(g.items(), key=lambda kv: -len(kv[1])))


# ---------- 多篇 grid(原行为) ----------
def render_grid(data):
    meta, recs = data["meta"], data["articles"]
    p = []
    p.append('<title>PMC 一区周报 · 文献速递</title>')
    cb = ('<callout emoji="📌" background-color="light-blue" border-color="blue">'
          '<p><b>数据来源</b>：PubMed Central (PMC) 免费全文，经 NCBI E-utilities API 抓取。</p>'
          f'<p><b>共收录</b>：{len(recs)} 篇（窗口 {meta.get("window_days",7)} 天）。{esc(meta.get("note",""))}</p>')
    if meta.get("widened"):
        cb += f'<p>⚠️ 本周无新文，已放宽至近 {meta["window_days"]} 天。</p>'
    cb += '</callout>'
    p.append(cb)
    g = group_by_journal(recs)
    p.append('<h1>📊 期刊概览</h1>')
    p.append('<table><colgroup><col width="220"/><col width="120"/><col width="160"/><col width="70"/></colgroup>'
             '<thead><tr><th background-color="light-blue">期刊</th><th background-color="light-blue">IF</th>'
             '<th background-color="light-blue">分区</th><th background-color="light-blue">篇数</th></tr></thead><tbody>')
    for j, items in g.items():
        m = items[0]
        p.append(f'<tr><td>{esc(j)}</td><td>{esc(m["if_"])}（{esc(m.get("if_source","近似"))}）</td>'
                 f'<td>{esc(m["zone"])}</td><td>{len(items)}</td></tr>')
    p.append('</tbody></table>')
    idx = 0
    for j, items in g.items():
        p.append(f'<h1>{esc(j)}（IF {esc(items[0]["if_"])}，{esc(items[0]["zone"])}）</h1>')
        for r in items:
            idx += 1
            emo = r.get("emoji") or "📄"
            title = r.get("zh_title") or r["title"]
            ab = r.get("zh_abstract") or r["abstract"]
            ft = "📖 全文可读" if r.get("has_fulltext") else "📃 仅摘要"
            p.append(f'<callout emoji="{esc(emo)}" background-color="light-gray" border-color="gray">')
            p.append(f'<p><b>{idx}. {esc(title)}</b></p>')
            p.append(f'<p>📝 {esc(ab)}</p>')
            p.append(f'<p><span text-color="gray">📰 {esc(r["jname"])}（IF {esc(r["if_"])}，{esc(r["zone"])}）　'
                     f'📅 {esc(r.get("date",""))}　{ft}</span></p>')
            p.append(f'<p>🔗 <a type="url-preview" href="{esc(r["url"])}">PMC 全文链接（PMC{esc(r["pmcid"])}）</a></p>')
            p.append('</callout>')
        p.append('<hr/>')
    return "\n".join(p)


# ---------- 单篇双语(2026-06-16 新增, 与 psych-news-digest 对齐) ----------
def render_single(data, index=0, title_prefix=""):
    """
    单篇双语 docx body(每篇 1 docx, 与 psych-news-digest 一致):
      <title>{title_prefix}中文标题 · {eng_title}</title>
      ## 中文意译标题
      ## 🇨🇳 中文摘要
      ## 🇬🇧 English Abstract
      ## 📑 元信息 (IF / DOI / PMCID / PMID / 日期 / 链接)
    """
    recs = data["articles"]
    if index >= len(recs):
        raise ValueError(f"--index {index} 越界 (共 {len(recs)} 篇)")
    r = recs[index]
    meta = data.get("meta", {})

    zh_title = (r.get("zh_title") or r["title"]).strip()
    en_title = r["title"].strip()
    zh_abstract = (r.get("zh_abstract") or "").strip()
    en_abstract = r.get("abstract", "").strip()
    emo = r.get("emoji") or "📄"
    journal = r["jname"]
    if_val = r.get("if_", "")
    zone = r.get("zone", "")
    pmid = r.get("pmid", "")
    pmcid = r.get("pmcid", "")
    doi = r.get("doi", "")
    date = r.get("date", "")
    url = r.get("url", "")
    has_fulltext = r.get("has_fulltext", False)

    p = []
    # 标题:v2 markdown 必带 <title> XML 标签(lark-cli 坑)
    p.append(f'<title>{esc(title_prefix + zh_title + " · " + en_title)}</title>')
    p.append(f'<h1>{esc(zh_title)}</h1>')
    p.append(f'<p><span text-color="gray">🇬🇧 {esc(en_title)}</span></p>')

    # 元信息横幅
    meta_lines = [
        f'📰 期刊：{esc(journal)}（IF {esc(if_val)}，{esc(zone)}）',
        f'📅 日期：{esc(date)}',
        f'{"📖 全文可读" if has_fulltext else "📃 仅摘要"}',
    ]
    if pmid:
        meta_lines.append(f'🔢 PMID：{esc(pmid)}')
    if pmcid:
        meta_lines.append(f'🔢 PMCID：PMC{esc(pmcid)}')
    if doi:
        meta_lines.append(f'🔗 DOI：{esc(doi)}')
    p.append('<callout emoji="' + esc(emo) + '" background-color="light-blue" border-color="blue">')
    for line in meta_lines:
        p.append(f'<p>{line}</p>')
    p.append('</callout>')

    # 中文摘要
    if zh_abstract:
        p.append('<h2>📝 中文摘要</h2>')
        for para in zh_abstract.split("\n\n"):
            p.append(f'<p>{esc(para)}</p>')

    # 英文摘要
    if en_abstract:
        p.append('<h2>🇬🇧 English Abstract</h2>')
        for para in en_abstract.split("\n\n"):
            p.append(f'<p>{esc(para)}</p>')

    # 元数据尾
    if url:
        p.append('<h2>📚 元信息 / Links</h2>')
        p.append(f'<p>🔗 <a type="url-preview" href="{esc(url)}">PMC 全文链接（PMC{esc(pmcid)}）</a></p>')
    # IF 近似值声明(铁律,见 SKILL.md 关键工程要点 4)
    p.append('<p><span text-color="gray">⚠️ IF/分区为近似值（JCR 或 OpenAlex），精确分区以 Web of Science 官方为准。</span></p>')
    if meta.get("note"):
        p.append(f'<p><span text-color="gray">📝 {esc(meta["note"])}</span></p>')

    return "\n".join(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="pmc_result.json")
    ap.add_argument("--out", default="")
    ap.add_argument("--mode", choices=["grid", "single"], default="grid",
                    help="grid=多篇分组表格(原), single=1 篇 1 docx 双语(2026-06-16 新增)")
    ap.add_argument("--index", type=int, default=0, help="single 模式:选第 N 篇 (从 0 开始)")
    ap.add_argument("--title-prefix", default="", help="single 模式:docx 标题前缀,如 '2026-06-12_'")
    args = ap.parse_args()
    data = load(args.inp)
    if args.mode == "single":
        text = render_single(data, index=args.index, title_prefix=args.title_prefix)
    else:
        text = render_grid(data)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"written -> {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
