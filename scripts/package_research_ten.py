#!/usr/bin/env python3
"""Package the reviewed essays as a self-contained reading file and local bundle."""
import base64
import html
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTENT = ROOT / "content/research-ten-topics"
OUTPUT = ROOT / "output/research-ten-topics"


def embed_asset(name):
    asset = OUTPUT / html.unescape(name)
    if asset.parent != OUTPUT or not asset.is_file():
        raise ValueError(f"Invalid local asset: {name}")
    mime = "image/svg+xml" if asset.suffix == ".svg" else "text/markdown;charset=utf-8"
    return f"data:{mime};base64," + base64.b64encode(asset.read_bytes()).decode("ascii")


def main():
    articles = [json.loads(p.read_text()) for p in sorted(CONTENT.glob("[0-9][0-9]-*.json"))]
    if len(articles) != 10:
        raise ValueError(f"Expected ten complete articles, found {len(articles)}")
    parts, entries = [], []
    for article in articles:
        n = int(article["number"])
        prefix = f"a{n:02d}-"
        stem = f"{n:02d}-{article['slug']}"
        rendered = (OUTPUT / f"{stem}.html").read_text()
        body = rendered.split('<main class="wrap">', 1)[1].split("</main>", 1)[0]
        body = re.sub(r'id="([^"]+)"', lambda m: f'id="{prefix}{m[1]}"', body)
        body = re.sub(r'href="#([^"]+)"', lambda m: f'href="#{prefix}{m[1]}"', body)
        body = body.replace('href="index.html"', 'href="#contents"')
        for other in articles:
            other_stem = f"{int(other['number']):02d}-{other['slug']}"
            body = body.replace(f'href="{other_stem}.html"', f'href="#article-{int(other["number"]):02d}"')
        body = re.sub(r'(src|srcset)="([^"]+\.svg)"', lambda m: f'{m[1]}="{embed_asset(m[2])}"', body)
        body = re.sub(r'<a download href="([^"]+\.svg)">',
                      lambda m: f'<a download="{m[1]}" href="{embed_asset(m[1])}">', body)
        body = body.replace(f'href="{stem}.md"', f'download="{stem}.md" href="{embed_asset(stem + ".md")}"')
        body = body.replace("查看 / 编辑 Markdown 原稿", "下载本文文字稿")
        parts.append(f'<section class="collection-item" id="article-{n:02d}">{body}</section>')
        entries.append(f'<li><a href="#article-{n:02d}">{n:02d} · {html.escape(article["title"])}</a>'
                       f'<p>{html.escape(article["summary"])}</p></li>')
    chinese = sum(len(re.findall(r"[\u3400-\u9fff]", b.get("text", "")))
                  for a in articles for b in a["blocks"] if b["type"] in ("p", "quote", "h2", "h3"))
    figures = sum(b["type"] == "figure" for a in articles for b in a["blocks"])
    sources = sum(len(a["sources"]) for a in articles)
    stats = {"articles": len(articles), "chinese_body_characters": chinese,
             "explanatory_figures": figures, "responsive_svg_files": figures * 2,
             "source_locations": sources}
    css = (OUTPUT / "research.css").read_text()
    css += "\n.collection-item{margin-top:76px;padding-top:25px;border-top:2px solid var(--line)}"
    css += "\n.collection-contents li{padding:14px 0;border-bottom:1px solid var(--line)}.collection-contents p{margin:5px 0 0;color:var(--muted);font-size:15px}"
    css += "\n.collection-contents ol{list-style:none;padding-left:0}"
    css += "\n:target{scroll-margin-top:20px}.sources :target{background:#edf2e9;outline:2px solid #91a59b;outline-offset:5px}"
    document = '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    document += '<title>通鉴专题研究 · 十篇完整图文</title><style>' + css + '</style></head><body>'
    document += '<header class="site-header"><a href="#contents">通鉴专题研究 · 十篇完整图文</a></header><main class="wrap">'
    document += '<section id="contents"><h1>十个问题，十种判断</h1><p class="subtitle">从具体史事出发，理解人物的选择、代价与经验的边界。</p>'
    document += f'<p class="summary">十篇完整文章，{figures}张解释图。正文与图注附原文定位；全部图形已内嵌，保存这个文件即可离线阅读。</p>'
    document += '<nav class="toc collection-contents" aria-label="十篇文章目录"><ol>' + ''.join(entries) + '</ol></nav></section>'
    document += ''.join(parts) + '</main></body></html>'
    (OUTPUT / "collection.html").write_text(document)
    readme = "# 通鉴专题研究：十篇图文文集\n\n"
    readme += "直接打开 `collection.html` 阅读全部十篇；图形和样式已经内嵌，这个文件可以单独保存。也可打开 `index.html` 逐篇阅读。\n\n"
    readme += f"正文共 {chinese:,} 个汉字，含 {figures} 张解释图、{sources} 处原文定位。每张图另有桌面与手机版 SVG，可下载、放大与后续编辑。\n\n"
    readme += "各篇 `.md` 是可编辑文字稿，引用采用脚注，图形采用同目录 SVG。`source/` 保存结构化成稿，便于继续修订文字、图形与出处。\n\n"
    readme += "文章依据本项目胡三省注本《资治通鉴》的正文、注释与史家评论分别写作；事实、作者解释和经验适用边界在正文及图注中交代。原书阅读链接定位到卷、年、段落，点击后需要联网。\n\n"
    readme += "本次仅完成本地图文稿，未向网站发布。\n\n"
    readme += "## 目录\n\n" + "\n".join(f'{a["number"]}. {a["title"]}' for a in articles) + "\n"
    (OUTPUT / "README.md").write_text(readme)
    (ROOT / "reports/research-ten-topics/delivery-stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n")
    archive = ROOT / "output/tongjian-research-ten-topics.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(OUTPUT.iterdir()):
            if path.is_file() and path.suffix in (".html", ".css", ".svg", ".md"):
                bundle.write(path, f"tongjian-research-ten-topics/{path.name}")
        for path in sorted(CONTENT.glob("[0-9][0-9]-*.json")):
            bundle.write(path, f"tongjian-research-ten-topics/source/{path.name}")
    print(json.dumps({**stats, "portable": str(OUTPUT / "collection.html"), "archive": str(archive)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
