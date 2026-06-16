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


# ---------- 单篇双语(2026-06-16 新增, 与 psych-news-digest 对齐; 2026-06-16 v2 扩 body+figs) ----------
def render_single(data, index=0, title_prefix="", max_body_chars=10000, max_figures=10):
    """
    单篇双语 docx body(每篇 1 docx, 与 psych-news-digest 一致):
      <title>{title_prefix}中文标题 · {eng_title}</title>
      ## 中文意译标题
      ## 🇨🇳 中文摘要
      ## 🇬🇧 English Abstract
      ## 📑 元信息 (IF / DOI / PMCID / PMID / 链接 / Authors)
      ## 📖 原文主体 / Full Text Body (新)  — body 段落(英文, 限 max_body_chars)
      ## 🖼️ 图片 / Figures (新)        — 前 max_figures 张图(飞书自动嵌入)
      ## 📚 元信息 / Links
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
    authors = r.get("authors", "")
    body_text = r.get("body_text", "")
    figures = r.get("figures", [])
    # v5 新增:body 各段的中文意译 + figures caption 中文意译
    #   zh_body_sections: list[str],与 body_text 按段顺序一一对应(空字符串 = 该段没翻译,显示英文原文)
    #   zh_figure_captions: dict[str, str] 形如 {"Fig. 1": "图 1 译文"}
    zh_body_sections = r.get("zh_body_sections", []) or []
    zh_figure_captions = r.get("zh_figure_captions", {}) or {}

    p = []
    # 标题:v2 markdown 必带 <title> XML 标签(lark-cli 坑)
    p.append(f'<title>{esc(title_prefix + zh_title + " · " + en_title)}</title>')
    p.append(f'<h1>{esc(zh_title)}</h1>')
    p.append(f'<p><span text-color="gray">🇬🇧 {esc(en_title)}</span></p>')

    # 元信息横幅
    meta_lines = [
        f'📰 期刊:{esc(journal)}(IF {esc(if_val)},{esc(zone)})',
        f'📅 日期:{esc(date)}',
        f'{"📖 全文可读" if has_fulltext else "📃 仅摘要"}',
    ]
    if authors:
        meta_lines.append(f'👥 作者:{esc(authors)}')
    if pmid:
        meta_lines.append(f'🔢 PMID:{esc(pmid)}')
    if pmcid:
        meta_lines.append(f'🔢 PMCID:PMC{esc(pmcid)}')
    if doi:
        meta_lines.append(f'🔗 DOI:{esc(doi)}')
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

    # 原文主体(v2/v4;v5 2026-06-17 加中文意译)— 中英对照(中文在上,英文在下)
    if body_text and body_text.strip():
        p.append('<h2>📖 原文主体(中英对照)/ Full Text Body (Bilingual)</h2>')
        p.append('<p><span text-color="gray">以下为 PMC 全文前若干段(中英双语对照,中文为意译;长段拆成多个块避免 docx 单块超限)。如需完整正文,请点击下方 PMC 全文链接。</span></p>')
        body_to_show = body_text
        if len(body_to_show) > max_body_chars:
            body_to_show = body_to_show[:max_body_chars] + "..."
        en_paras = [para for para in body_to_show.split("\n\n") if para.strip()]
        for i, en_para in enumerate(en_paras):
            # 取对应中文段(若无翻译则空,跳过中文块)
            zh_para = zh_body_sections[i] if i < len(zh_body_sections) else ""
            # 中文段(若存在)
            if zh_para.strip():
                # 长段拆
                if len(zh_para) > 3000:
                    for j in range(0, len(zh_para), 3000):
                        chunk = zh_para[j:j+3000]
                        p.append(f'<p><b>🇨🇳 {esc(chunk)}</b></p>')
                else:
                    p.append(f'<p><b>🇨🇳 {esc(zh_para)}</b></p>')
            # 英文段
            if len(en_para) > 3000:
                for j in range(0, len(en_para), 3000):
                    chunk = en_para[j:j+3000]
                    p.append(f'<p><span text-color="gray">🇬🇧 {esc(chunk)}</span></p>')
            else:
                p.append(f'<p><span text-color="gray">🇬🇧 {esc(en_para)}</span></p>')

    # 图片(v2 新增;v5 加中文 caption)— 飞书 <img href="..."/> 自动下载嵌入
    if figures:
        figs_to_show = figures[:max_figures]
        p.append(f'<h2>🖼️ 图片 / Figures({len(figs_to_show)}/{len(figures)})</h2>')
        for f in figs_to_show:
            if not f.get("url"):
                continue
            label = f.get("label", "")
            caption = f.get("caption", "")
            url_fig = f["url"]
            # 取中文 caption(若存在)
            zh_caption = ""
            if label and label in zh_figure_captions:
                zh_caption = zh_figure_captions[label]
            # 飞书 <img> 标签,自动下载嵌入(原 caption 在属性里)
            full_caption = label + (" " + caption if caption else "")
            if zh_caption:
                full_caption += f" | 🇨🇳 {zh_caption}"
            img_attrs = f'caption="{esc(full_caption)}"' if full_caption else ''
            p.append(f'<img href="{esc(url_fig)}" {img_attrs}/>')
            # caption 说明(若原文)
            if caption and len(caption) > 0:
                p.append(f'<p><span text-color="gray">{esc(label + " — " + caption) if label else esc(caption)}</span></p>')
            # 中文 caption(独立段,加粗方便读)
            if zh_caption:
                p.append(f'<p><b>🇨🇳 {esc(label + " — " + zh_caption) if label else esc(zh_caption)}</b></p>')
        if len(figures) > max_figures:
            p.append(f'<p><span text-color="gray">…另有 {len(figures) - max_figures} 张图未展示,详见 PMC 全文链接。</span></p>')

    # 元数据尾
    if url:
        p.append('<h2>📚 元信息 / Links</h2>')
        p.append(f'<p>🔗 <a type="url-preview" href="{esc(url)}">PMC 全文链接(PMC{esc(pmcid)})</a></p>')
    # IF 近似值声明(铁律,见 SKILL.md 关键工程要点 4)
    p.append('<p><span text-color="gray">⚠️ IF/分区为近似值(JCR 或 OpenAlex),精确分区以 Web of Science 官方为准。</span></p>')
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
