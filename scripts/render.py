#!/usr/bin/env python3
"""
pmc-q1-weekly 渲染器:把 {meta, articles}(已由 Agent 回填 zh_title/zh_abstract/emoji)
渲染为飞书文档 XML(grid 卡片式)。

注意:direct(对话内)模式的图标卡片由 Agent 手写,不走脚本——故本文件只负责 doc 模式。

用法:
  python3 render.py --in pmc_result.json --out body.xml
"""
import json, argparse, html
from collections import OrderedDict


def esc(s):
    return html.escape(s or "", quote=False)


def load(inp):
    data = json.load(open(inp))
    if isinstance(data, list):  # 向后兼容旧结构
        return {"articles": data, "meta": {"count": len(data), "note": "", "widened": False, "window_days": 7}}
    return data


def group_by_journal(recs):
    g = OrderedDict()
    for r in recs:
        g.setdefault(r["jname"], []).append(r)
    return OrderedDict(sorted(g.items(), key=lambda kv: -len(kv[1])))


def render_doc(data):
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="pmc_result.json")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    text = render_doc(load(args.inp))
    if args.out:
        open(args.out, "w").write(text)
        print(f"written -> {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
