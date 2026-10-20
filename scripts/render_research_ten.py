#!/usr/bin/env python3
"""Render the ten research essays as dependency-free local reading pages.

The renderer deliberately knows only the editorial JSON contract.  It is safe to
run while authors are still writing: malformed or incomplete files are reported
and skipped unless --check is requested.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "content" / "research-ten-topics"
OUTPUT = ROOT / "output" / "research-ten-topics"
BASE_READER = "https://deewins.top/reader.html"

CSS = r'''
:root{--ink:#285342;--paper:#fffef9;--ground:#f4f2ec;--line:#dfdfd3;--muted:#647069;--serif:Georgia,"Noto Serif CJK SC","Songti SC",serif;--sans:system-ui,-apple-system,"Noto Sans CJK SC","Microsoft YaHei",sans-serif}
*{box-sizing:border-box}html{background:var(--ground);color:#26342e}body{margin:0;font-family:var(--serif);line-height:1.88;font-size:17px}a{color:var(--ink);text-underline-offset:3px}.site-header{padding:18px max(20px,calc((100vw - 1080px)/2));border-bottom:1px solid var(--line);font-family:var(--sans);background:var(--paper)}.site-header a{text-decoration:none;font-weight:700}.wrap{max-width:1080px;margin:0 auto;padding:34px 24px 70px}.back{font-family:var(--sans);font-size:14px;color:var(--muted)}h1{color:var(--ink);font-size:clamp(30px,5vw,46px);line-height:1.25;margin:16px 0 8px}h2{color:var(--ink);font-size:26px;line-height:1.4;margin:42px 0 12px;border-left:4px solid var(--ink);padding-left:12px}h3{color:var(--ink);font-size:21px;margin-top:30px}.subtitle{font-size:20px;color:#53635c;margin:0 0 18px}.summary{font-family:var(--sans);font-size:16px;background:#f0f0e8;border-left:3px solid var(--ink);padding:14px 18px;margin:20px 0}.question{font-family:var(--sans);font-weight:600;color:var(--ink);margin:24px 0}.toc{background:var(--paper);border:1px solid var(--line);padding:16px 22px;font-family:var(--sans);font-size:15px}.toc ol{margin:6px 0 0;padding-left:24px}.article{background:var(--paper);padding:28px clamp(20px,5vw,64px);box-shadow:0 1px 4px #c8c6bd55}.article p{margin:0 0 1.2em}.article em,.article strong{font-family:var(--sans);font-size:.94em}.quote{border-left:3px solid #91a59b;margin:26px 0;padding:10px 22px;color:#3d5148;background:#f5f5ee}.quote p{margin:0}.quote cite{display:block;font-family:var(--sans);font-size:13px;color:var(--muted);margin-top:8px;font-style:normal}.figure{margin:34px 0;padding:18px 0;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}.figure h3{font-family:var(--sans);font-size:19px;margin:0 0 10px}.figure picture{display:block}.figure img{display:block;width:100%;height:auto;background:#fffef9}.figure-tools{display:flex;gap:12px;margin-top:9px;font:13px var(--sans)}figcaption{font:14px/1.65 var(--sans);color:#53635c;margin-top:10px}.sources{margin-top:46px;border-top:2px solid var(--ink);padding-top:14px}.sources h2{border:0;padding:0;margin:0 0 12px;font-size:22px}.sources li{margin:0 0 14px;font:14px/1.7 var(--sans)}.sources .claim{color:#33443c}.sources .limit{color:#69766f}.pager{display:flex;justify-content:space-between;gap:16px;margin:30px 0;font:14px var(--sans)}.pager a{border:1px solid var(--line);padding:9px 13px;background:var(--paper);text-decoration:none}.md-link{font:14px var(--sans);margin-top:12px}@media(max-width:600px){body{font-size:16px;line-height:1.8}.wrap{padding:24px 12px 50px}.article{padding:20px 15px}h2{font-size:23px;margin-top:32px}.subtitle{font-size:17px}.figure{margin-left:-4px;margin-right:-4px}.figure-tools{font-size:12px}.sources li{font-size:13px}.pager{gap:7px}.pager a{padding:7px 8px}}

/* Let long horizontal navigation titles take whole rows on narrow screens. */
.pager,.figure-tools{flex-wrap:wrap}.pager a{flex:1 1 260px;min-width:0;line-height:1.8;word-break:normal;overflow-wrap:normal}
h1,h2,h3,.article p{word-break:normal;overflow-wrap:normal;writing-mode:horizontal-tb}
'''

def esc(v: object) -> str:
    return html.escape(str(v or ""), quote=True)

def plain(v: object) -> str:
    return re.sub(r"<[^>]+>", "", str(v or ""))

def inline(text: str) -> str:
    # Authors may use only em/strong; escape everything else, then restore them.
    token = re.compile(r"<(em|strong)>(.*?)</\1>", re.S)
    out, pos = [], 0
    for m in token.finditer(text):
        out.append(esc(text[pos:m.start()]))
        out.append(f"<{m.group(1)}>{esc(m.group(2))}</{m.group(1)}>")
        pos = m.end()
    out.append(esc(text[pos:]))
    # Keep [[s1]] intact until the page renderer can turn it into a source link.
    return "".join(out)

def citation(text: str) -> str:
    # [[s1]] becomes a source link; unknown ids remain visible and are caught by --check.
    return text

def wrap(text: str, width: int) -> list[str]:
    text = plain(text).strip()
    lines: list[str] = []
    for para in text.splitlines() or [""]:
        if not para: lines.append(""); continue
        cur = ""
        for ch in para:
            cur += ch
            if len(cur) >= width:
                lines.append(cur); cur = ""
        if cur: lines.append(cur)
    return lines or [""]

def svg_text(lines: Iterable[str], x: int, y: int, size: int, color: str = "#26342e", gap: int | None = None, field: str = "text") -> str:
    """Emit one text node per visual line so browser bbox checks stay meaningful."""
    gap = gap or round(size * 1.45)
    return "".join(f'<text data-field="{esc(field)}" x="{x}" y="{y+i*gap}" font-size="{size}px" fill="{color}">{esc(line)}</text>' for i, line in enumerate(lines))

def svg_header(title: str, desc: str, width: int, height: int) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="title desc" viewBox="0 0 {width} {height}" width="{width}" height="{height}"><title id="title">{esc(title)}</title><desc id="desc">{esc(desc)}</desc><rect width="100%" height="100%" fill="#fffef9"/><style>text{{font-family:"Noto Sans CJK SC","Microsoft YaHei",sans-serif}} .ink{{fill:#285342}} .line{{stroke:#285342;stroke-width:2;fill:none}} .box{{fill:#f4f2ec;stroke:#bfc9c1;stroke-width:1.5}}</style>'

def svg_footer() -> str: return "</svg>"

def render_figure(fig: dict, stem: str) -> tuple[str, str, str]:
    kind = fig.get("kind")
    title, desc = fig.get("title", "图形"), fig.get("caption", "")
    def make(mobile: bool) -> str:
        W = 320 if mobile else 880
        pad = 16 if mobile else 30
        fs = 17 if mobile else 17
        gap = 28 if mobile else 23
        body = ""
        def lines(text: object, boxw: int, size: int = fs) -> list[str]:
            # CJK characters occupy approximately one em; leave a little breathing room.
            return wrap(str(text), max(1, int((boxw - 20) / (size * .98))))
        if kind == "flow":
            steps = fig.get("steps", []); n = len(steps)
            cols = 1 if mobile else n; gapx = 18
            bw = (W - pad*2 - gapx*(cols-1)) // cols
            cards=[]
            links = fig.get("links") or []
            for i,s in enumerate(steps):
                ls=lines(s.get("label", ""),bw,fs); ds=lines(s.get("detail", ""),bw,fs if mobile else fs-1)
                note=lines(links[i],bw-20,fs if mobile else 13) if i < len(steps)-1 and i < len(links) else []
                note_gap=gap if mobile else 18
                cards.append((ls,ds,note,max(94,27+len(ls)*gap+8+len(ds)*gap+(10+len(note)*note_gap if note else 0)+14)))
            if mobile:
                y=24; positions=[]
                for ls,ds,note,h in cards:
                    positions.append((pad,y,bw,h)); body+=f'<rect class="box" data-field="card" x="{pad}" y="{y}" rx="8" width="{bw}" height="{h}"/>'+svg_text(ls,pad+10,y+27,fs,"#285342",gap,"label")+svg_text(ds,pad+10,y+27+len(ls)*gap+8,fs,"#26342e",gap,"detail")+svg_text(note,pad+10,y+h-14-(len(note)-1)*gap,fs,"#647069",gap,"link-note"); y+=h+34
                for i in range(len(positions)-1):
                    x=pad+bw//2; y1=positions[i][1]+positions[i][3]; y2=positions[i+1][1]
                    body+=f'<path class="line" d="M{x} {y1}V{y2-9}"/><path d="m{x-5} {y2-11} 5 8 5-8" fill="none" stroke="#285342" stroke-width="2"/>'
                height=y+4
            else:
                y=24; positions=[]; row_h=max(h for _,_,_,h in cards)
                for i,(ls,ds,note,h) in enumerate(cards):
                    x=pad+i*(bw+gapx); positions.append((x,y,bw,row_h)); body+=f'<rect class="box" data-field="card" x="{x}" y="{y}" rx="8" width="{bw}" height="{row_h}"/>'+svg_text(ls,x+10,y+27,fs,"#285342",gap,"label")+svg_text(ds,x+10,y+27+len(ls)*gap+8,fs-1,"#26342e",gap,"detail")+svg_text(note,x+10,y+row_h-8-(len(note)-1)*18,13,"#647069",18,"link-note")
                for i in range(len(positions)-1):
                    x1=positions[i][0]+bw; x2=positions[i+1][0]; cy=y+row_h//2
                    body+=f'<path class="line" d="M{x1+3} {cy}H{x2-10}"/><path d="m{x2-12} {cy-5} 9 5-9 5z" fill="#285342"/>'
                height=row_h+48
        elif kind == "comparison":
            cols=fig.get("columns",[]); rows=fig.get("rows",[])
            if mobile:
                y=22; bw=W-pad*2
                for r in rows:
                    label=lines(r.get("label",""),bw,fs); cells=r.get("cells",[]); prepared=[]
                    h=18+len(label)*gap+10
                    for c,t in zip(cols,cells):
                        dl=lines(c,bw-20,fs if mobile else 14); vl=lines(t,bw-20,fs if mobile else fs-1); prepared.append((dl,vl)); h+=len(dl)*gap+4+len(vl)*gap+8
                    body+=f'<rect class="box" data-field="case-card" x="{pad}" y="{y}" rx="8" width="{bw}" height="{h}"/>'+svg_text(label,pad+10,y+26,fs,"#285342",gap,"case")
                    cy=y+26+len(label)*gap+8
                    for dl,vl in prepared:
                        body+=svg_text(dl,pad+10,cy,fs if mobile else 14,"#285342",gap,"dimension"); cy+=len(dl)*gap+4; body+=svg_text(vl,pad+10,cy,fs if mobile else fs-1,"#26342e",gap,"value"); cy+=len(vl)*gap+8
                    y+=h+14
                height=y+12
            else:
                first=150; gapx=0; cw=(W-pad*2-first)//max(1,len(cols)); y=22
                head=["案例"]+cols; hs=max(48,max(len(lines(t,first if j==0 else cw,fs)) for j,t in enumerate(head))*gap+18)
                for j,t in enumerate(head):
                    x=pad+(0 if j==0 else first+(j-1)*cw); w=first if j==0 else cw; body+=f'<rect class="box" data-field="header" x="{x}" y="{y}" width="{w}" height="{hs}"/>'+svg_text(lines(t,w,fs),x+10,y+25,fs,"#285342",gap,"header")
                y+=hs
                for r in rows:
                    vals=[r.get("label","")]+r.get("cells",[]); wrapped=[lines(t,first if j==0 else cw,fs-1) for j,t in enumerate(vals)]; rh=max(66,max(len(q) for q in wrapped)*gap+22)
                    for j,q in enumerate(wrapped):
                        x=pad+(0 if j==0 else first+(j-1)*cw); w=first if j==0 else cw; body+=f'<rect class="box" data-field="cell" x="{x}" y="{y}" width="{w}" height="{rh}"/>'+svg_text(q,x+10,y+25,fs-1,"#26342e",gap,"cell")
                    y+=rh
                height=y+22
        elif kind == "timeline":
            ev=fig.get("events",[]); x=pad+35; y=30; item=[]
            for e in ev:
                head=lines(f'{e.get("date", "")} · {e.get("label", "")}',W-x-pad-8,fs); detail=lines(e.get("detail", ""),W-x-pad-8,fs if mobile else fs-1); h=max(76,16+len(head)*gap+8+len(detail)*gap); item.append((head,detail,h))
            total=sum(q[2]+20 for q in item); body+=f'<path class="line" d="M{x} {y+7}V{y+total-20}"/>'
            cy=y
            for head,detail,h in item:
                body+=f'<circle data-field="event" cx="{x}" cy="{cy+7}" r="8" fill="#285342"/>'+svg_text(head,x+18,cy+12,fs,"#285342",gap,"event-label")+svg_text(detail,x+18,cy+12+len(head)*gap+8,fs if mobile else fs-1,"#26342e",gap,"detail"); cy+=h+20
            height=cy+4
        elif kind == "branches":
            prompt=lines(fig.get("prompt", ""),W-pad*2,fs); y=24; body+=svg_text(prompt,pad,y,fs,"#285342",gap,"prompt"); y+=len(prompt)*gap+18
            opts=fig.get("options",[]); n=len(opts); cols=n if not mobile else 1; gapx=14; bw=(W-pad*2-gapx*(cols-1))//cols; cards=[]
            for o in opts:
                label=lines(o.get("label", ""),bw,fs); blocks=[]
                for prefix,key in (("成立条件：","condition"),("代价：","cost"),("限度：","limit")): blocks.append((prefix,lines(o.get(key,""),bw,fs if mobile else fs-1)))
                h=48+len(label)*gap+sum(gap+len(q)*gap+8 for _,q in blocks); cards.append((label,blocks,h))
            for i,(label,blocks,h) in enumerate(cards):
                x=pad+i*(bw+gapx) if not mobile else pad; body+=f'<rect class="box" data-field="branch" x="{x}" y="{y}" rx="8" width="{bw}" height="{h}"/>'+svg_text(label,x+10,y+27,fs,"#285342",gap,"option")
                cy=y+27+len(label)*gap+6
                for prefix,q in blocks: body+=svg_text([prefix],x+10,cy,fs if mobile else 14,"#285342",gap,"field-label"); cy+=gap; body+=svg_text(q,x+10,cy,fs if mobile else fs-1,"#26342e",gap,"field-value"); cy+=len(q)*gap+5
                if mobile: y += h + 16
            if not mobile: y+=max(h for _,_,h in cards)
            height=y+14
        else: raise ValueError(f"unknown figure kind: {kind}")
        return svg_header(title, desc, W, height)+body+svg_footer()
    desktop, mobile = make(False), make(True)
    dname=f"{stem}-{fig.get('id','figure')}-desktop.svg"; mname=f"{stem}-{fig.get('id','figure')}-mobile.svg"
    return desktop, mobile, (dname, mname)

def reader_url(s: dict) -> str:
    return f"{BASE_READER}#volume-{int(s['volume'])}-year-{int(s['year'])}-para-{int(s['paragraph'])}"

def year_label(year: int) -> str:
    year = int(year)
    return f"公元前{year}年" if year > 0 else f"公元{abs(year)}年"

def kind_label(kind: str) -> str:
    return {"text":"正文", "note":"胡三省注", "comment":"史家评论"}.get(kind, "来源")

def render_markdown(data: dict, stem: str) -> str:
    def md_refs(text: str) -> str:
        return re.sub(r'\[\[(s\d+)\]\]', lambda m: '[^'+m.group(1)+']', str(text or ''))
    out=[f"# {data['title']}", f"\n> {data.get('subtitle','')}", f"\n{data.get('summary','')}\n"]
    for b in data.get("blocks",[]):
        t=b.get("type")
        if t=='h2': out.append(f"\n## {b.get('text','')}\n")
        elif t=='h3': out.append(f"\n### {b.get('text','')}\n")
        elif t=='p': out.append(f"\n{md_refs(b.get('text',''))}\n")
        elif t=='quote': out.append(f"\n> {md_refs(b.get('text',''))}\n> — {b.get('attribution','')} [^{b.get('source','')}]\n")
        elif t=='figure':
            fid=b.get('id','figure'); out.append(f"\n### 图：{b.get('title','')}\n\n![{b.get('title','')}（桌面）]({stem}-{fid}-desktop.svg)\n\n![{b.get('title','')}（手机）]({stem}-{fid}-mobile.svg)\n\n{md_refs(b.get('caption',''))}\n")
    out.append("\n## 来源与原书阅读\n")
    for s in data.get('sources',[]):
        sid=s.get('id'); out.append(f"\n[^{sid}]: 卷{s.get('volume')}，{year_label(s.get('year'))}条，本年段落{int(s.get('paragraph',0))+1}（{kind_label(s.get('kind'))}）：{s.get('quote','')}。{s.get('claim','')} 原书：{reader_url(s)}")
    return "\n".join(out)+"\n"

def validate(data: dict) -> list[str]:
    errors=[]
    for k in ('number','slug','title','subtitle','summary','question','blocks','sources'):
        if k not in data: errors.append(f"缺少顶层字段 {k}")
    ids={s.get('id') for s in data.get('sources',[]) if isinstance(s,dict)}
    for i,b in enumerate(data.get('blocks',[])):
        if b.get('type') not in {'p','h2','h3','quote','figure'}: errors.append(f"block {i}: 未知 type")
        if b.get('type')=='figure' and b.get('kind') not in {'flow','comparison','timeline','branches'}: errors.append(f"block {i}: 未知 figure kind")
        text=json.dumps(b,ensure_ascii=False)
        for ref in re.findall(r'\[\[(s\d+)\]\]',text):
            if ref not in ids: errors.append(f"block {i}: 来源 {ref} 不存在")
    for i,s in enumerate(data.get('sources',[])):
        for k in ('id','volume','year','paragraph','quote','kind','claim','limitation','context_checked'):
            if k not in s: errors.append(f"source {i}: 缺少 {k}")
        if s.get('kind') not in {'text','note','comment'}: errors.append(f"source {i}: kind 无效")
        if not isinstance(s.get('paragraph'),int) or s.get('paragraph',-1)<0: errors.append(f"source {i}: paragraph 无效")
    return errors

def render_html(data: dict, all_data: list[dict], out: Path) -> None:
    stem=f"{int(data['number']):02d}-{data['slug']}"; fig_html=[]; toc=[]
    source_map={s['id']:s for s in data.get('sources',[])}
    source_order=[]
    for block in data.get('blocks', []):
        references=re.findall(r'\[\[(s\d+)\]\]', json.dumps(block, ensure_ascii=False))
        if block.get('type') == 'quote': references.append(block.get('source'))
        for sid in references:
            if sid in source_map and sid not in source_order: source_order.append(sid)
    source_order.extend(sid for sid in source_map if sid not in source_order)
    source_numbers={sid: number+1 for number, sid in enumerate(source_order)}
    def ptext(text: str) -> str:
        def sub(m):
            s=source_map.get(m.group(1)); return f'<sup class="source-ref"><a href="#{esc(m.group(1))}">[{source_numbers[m.group(1)]}]</a></sup>' if s else f'<sup>[{esc(m.group(1))}]</sup>'
        return re.sub(r'\[\[(s\d+)\]\]',sub,inline(text))
    chunks=[]
    for b in data.get('blocks',[]):
        t=b.get('type')
        if t in ('h2','h3'):
            tag=t; bid=b.get('id') or re.sub(r'\W+','-',b.get('text','').lower()).strip('-'); toc.append(f'<li><a href="#{esc(bid)}">{esc(b.get("text"))}</a></li>'); chunks.append(f'<{tag} id="{esc(bid)}">{esc(b.get("text"))}</{tag}>')
        elif t=='p': chunks.append(f'<p>{ptext(b.get("text",""))}</p>')
        elif t=='quote': chunks.append(f'<blockquote class="quote"><p>{ptext(b.get("text",""))}</p><cite>{esc(b.get("attribution",""))} · <a href="#{esc(b.get("source",""))}">[{source_numbers.get(b.get("source"), "?")}]</a></cite></blockquote>')
        elif t=='figure':
            dsvg,msvg,names=render_figure(b,stem); (out/names[0]).write_text(dsvg,encoding='utf-8'); (out/names[1]).write_text(msvg,encoding='utf-8')
            dw,dh=re.search(r'viewBox="0 0 (\d+) (\d+)"', dsvg).groups()
            mw,mh=re.search(r'viewBox="0 0 (\d+) (\d+)"', msvg).groups()
            fig_html.append(b.get('id')); srcs=' '.join(re.findall(r'\[\[(s\d+)\]\]',b.get('caption','')))
            cap=ptext(b.get('caption',''))
            chunks.append(f'<figure class="figure" id="{esc(b.get("id"))}"><h3>{esc(b.get("title"))}</h3><picture><source media="(max-width:600px)" srcset="{esc(names[1])}" width="{mw}" height="{mh}"><img src="{esc(names[0])}" width="{dw}" height="{dh}" alt="{esc(plain(b.get("title")))}" loading="lazy"></picture><div class="figure-tools"><a download href="{esc(names[0])}">下载桌面 SVG</a><a download href="{esc(names[1])}">下载手机 SVG</a></div><figcaption>{cap}</figcaption></figure>')
    src_html=[]
    for sid in source_order:
        s=source_map[sid]
        src_html.append(f'<li id="{esc(s["id"])}"><a href="{esc(reader_url(s))}" target="_blank" rel="noreferrer">卷{s["volume"]} · {esc(year_label(s["year"]))}条 · 本年段落{int(s["paragraph"])+1}（{kind_label(s.get("kind"))} · 阅读原文）</a><br><span>{esc(s["quote"])}</span><br><span class="claim">支持：{esc(s["claim"])}</span>{("<br><span class=\"limit\">限制："+esc(s.get("limitation"))+"</span>") if s.get('limitation') else ""}</li>')
    ordered=sorted(all_data,key=lambda x:int(x['number'])); idx=ordered.index(data); prev=ordered[idx-1] if idx else None; nxt=ordered[idx+1] if idx+1<len(ordered) else None
    pager=(f'<a href="{int(prev["number"]):02d}-{prev["slug"]}.html">← {esc(prev["title"])}</a>' if prev else '<span></span>')+(f'<a href="{int(nxt["number"]):02d}-{nxt["slug"]}.html">{esc(nxt["title"])} →</a>' if nxt else '')
    html_doc=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(data['title'])} · 通鉴专题</title><link rel="stylesheet" href="research.css"></head><body><header class="site-header"><a href="index.html">通鉴专题研究 · 十篇文集</a></header><main class="wrap"><a class="back" href="index.html">← 返回专题目录</a><h1>{esc(data['title'])}</h1><p class="subtitle">{esc(data.get('subtitle',''))}</p><p class="summary">{esc(data.get('summary',''))}</p><p class="question">核心问题：{esc(data.get('question',''))}</p><p class="md-link"><a href="{stem}.md">查看 / 编辑 Markdown 原稿</a></p><nav class="toc"><strong>本文目录</strong><ol>{''.join(toc)}</ol></nav><article class="article">{''.join(chunks)}<section class="sources"><h2>来源与证据范围</h2><ol>{''.join(src_html)}</ol></section></article><nav class="pager">{pager}</nav></main></body></html>'''
    html_doc=html_doc.replace(f'<p class="question">核心问题：{esc(data.get("question", ""))}</p>', '')
    (out/f'{stem}.html').write_text(html_doc,encoding='utf-8'); (out/f'{stem}.md').write_text(render_markdown(data, stem),encoding='utf-8')

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument('--input',type=Path,default=INPUT); ap.add_argument('--output',type=Path,default=OUTPUT); ap.add_argument('--subset',nargs='*',help='numbers or slugs'); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    files=sorted(args.input.glob('[0-9][0-9]-*.json')); data=[]; errors=[]
    for f in files:
        try: d=json.loads(f.read_text(encoding='utf-8')); errs=validate(d)
        except Exception as e: errors.append(f'{f.name}: {e}'); continue
        if errs: errors.extend(f'{f.name}: {e}' for e in errs)
        if args.subset and not (str(d.get('number')) in args.subset or d.get('slug') in args.subset): continue
        if not errs: data.append(d)
    if args.check:
        if errors:
            print('\n'.join(errors),file=sys.stderr); return 1
        print(f'OK: {len(data)} article schemas checked'); return 0
    args.output.mkdir(parents=True,exist_ok=True)
    # Keep repeated renders deterministic: output contains renderer-owned files only.
    for old in args.output.iterdir():
        if old.name in {'index.html','research.css'} or re.match(r'^\d\d-.*\.(html|md|svg)$', old.name):
            old.unlink()
    (args.output/'research.css').write_text(CSS,encoding='utf-8')
    for d in data: render_html(d,data,args.output)
    cards=''.join(f'<li style="margin-bottom:14px"><a href="{int(d["number"]):02d}-{d["slug"]}.html"><strong>{int(d["number"]):02d} · {esc(d["title"])}</strong><br><span>{esc(d.get("summary",""))}</span></a></li>' for d in sorted(data,key=lambda x:int(x['number'])))
    index=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>通鉴专题研究 · 十篇文集</title><link rel="stylesheet" href="research.css"></head><body><header class="site-header"><a href="index.html">通鉴专题研究 · 十篇文集</a></header><main class="wrap"><h1>十个问题，十种判断</h1><p class="subtitle">从《资治通鉴》的具体困境出发，读人物如何在信息、约束与后果之间作出选择。</p><article class="article"><ol class="toc">{cards}</ol></article></main></body></html>'''; (args.output/'index.html').write_text(index,encoding='utf-8'); print(f'Rendered {len(data)} articles to {args.output}')
    (args.output/'index.html').write_text(index.replace('<ol class="toc">', '<ol class="toc" style="list-style:none">'), encoding='utf-8')
    if errors: print('Skipped invalid inputs:\n'+'\n'.join(errors),file=sys.stderr)
    return 0
if __name__=='__main__': raise SystemExit(main())
