#!/usr/bin/env python3
"""Render the ten reviewed essays into the existing local site's topic directory."""
import hashlib
import html
import json
import re
from pathlib import Path

from render_research_ten import CSS, render_html, validate

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CONTENT = ROOT / "content/research-ten-topics"
START = "<!-- research-ten-topics:start -->"
END = "<!-- research-ten-topics:end -->"
SITE_CSS = """
.site-header{padding:0}.site-header .header-inner{max-width:1080px;margin:auto;padding:18px 28px;display:flex;justify-content:space-between;align-items:center;gap:20px}
.site-header .brand{display:flex;align-items:center;gap:12px;font:23px 'Songti SC','SimSun',serif;letter-spacing:3px;color:#27372f;white-space:nowrap;font-weight:400}
.site-header .seal{display:grid;place-items:center;width:34px;height:38px;background:#9d513d;color:#fffef9;font-size:23px;letter-spacing:0}
.site-header nav{display:flex;gap:20px;font-size:13px;flex-wrap:wrap}.site-header nav a{font-weight:400;white-space:nowrap;min-height:44px;display:inline-flex;align-items:center}.site-header .header-inner{flex-wrap:wrap}
:target{scroll-margin-top:20px}.sources li:target{background:#edf2e9;outline:2px solid #91a59b;outline-offset:5px}
@media(max-width:600px){.site-header .header-inner{padding:15px 18px;flex-direction:column;align-items:flex-start;gap:10px}.site-header nav{gap:16px}}
"""
DIRECTORY_CSS = """<style id="research-ten-topics-style">
.research-series{display:grid;gap:18px;margin:32px 0 42px}.research-series>h2{font-size:26px;margin:0}.research-series>.intro{margin:0}.research-series .entry h3{font-size:24px;line-height:1.5}@media(max-width:600px){.research-series .entry h3{font-size:22px}}
</style>"""


def esc(value):
    return html.escape(str(value), quote=True)


def main():
    articles = [json.loads(p.read_text()) for p in sorted(CONTENT.glob("[0-9][0-9]-*.json"))]
    if len(articles) != 10:
        raise ValueError("All ten complete articles are required")
    for article in articles:
        errors = validate(article)
        if errors:
            raise ValueError(f"{article['number']}: {errors}")
    directory_path = DIST / "research.html"
    directory = directory_path.read_text()
    header = re.search(r"<header>.*?</header>", directory, re.S).group()
    header = header.replace("<header>", '<header class="site-header">', 1)
    header = re.sub(r'href="(?!https?://|#)([^"]+)"',
                    lambda m: f'href="../{m[1].removeprefix("./")}"', header)
    target = DIST / "research"
    target.mkdir(exist_ok=True)
    css = CSS + SITE_CSS
    version = hashlib.sha256(css.encode()).hexdigest()[:12]
    (target / "research.css").write_text(css)
    for article in articles:
        render_html(article, articles, target)
        filename = f"{article['number']:02d}-{article['slug']}.html"
        path = target / filename
        page = path.read_text()
        page = re.sub(r'<header class="site-header">.*?</header>', lambda _: header, page, count=1, flags=re.S)
        page = page.replace('href="index.html"', 'href="../research.html"')
        page = page.replace('https://deewins.top/reader.html#', '../reader.html#')
        page = page.replace('href="research.css"', f'href="research.css?v={version}"')
        page = re.sub(r'<p class="md-link">.*?</p>', '', page, flags=re.S)
        page = re.sub(r'(<div class="figure-tools"><a download href="[^"]+">).*?</div>',
                      lambda m: m[1] + '下载此图</a></div>', page, flags=re.S)
        canonical = f"https://deewins.top/research/{filename}"
        metadata = f'<meta name="description" content="{esc(article["summary"])}"><link rel="canonical" href="{canonical}">'
        metadata += f'<meta property="og:type" content="article"><meta property="og:title" content="{esc(article["title"])}"><meta property="og:description" content="{esc(article["summary"])}"><meta property="og:url" content="{canonical}">'
        schema = {"@context": "https://schema.org", "@type": "Article", "headline": article["title"],
                  "description": article["summary"], "inLanguage": "zh-CN", "mainEntityOfPage": canonical,
                  "isAccessibleForFree": True}
        metadata += '<script type="application/ld+json">' + json.dumps(schema, ensure_ascii=False).replace('<', '\\u003c') + '</script>'
        # Keep the same login and registration interaction as the main directory.
        for asset in re.findall(r'<link rel="stylesheet" href="(?:commerce|account-dialog)\.css[^>]+>', directory):
            metadata += asset.replace('href="', 'href="../', 1)
        page = page.replace('</head>', metadata + '</head>', 1)
        for asset in re.findall(r'<script src="commerce\.js[^>]*></script>', directory):
            page = page.replace('</body>', asset.replace('src="', 'src="../', 1) + '</body>', 1)
        path.write_text(page)
    entries = []
    for article in articles:
        href = f'research/{article["number"]:02d}-{article["slug"]}.html'
        figures = sum(b['type'] == 'figure' for b in article['blocks'])
        entries.append(f'<a class="entry" href="{href}"><h3>{esc(article["title"])}</h3>'
                       f'<p>{esc(article["subtitle"])}</p><p class="meta">{figures}张解释图 · 附原文出处与跨案比较</p>'
                       '<span class="go">阅读图文专题 →</span></a>')
    section = START + '\n<section class="research-series" id="newResearch" aria-labelledby="newResearchTitle">'
    section += '<h2 id="newResearchTitle">十个问题，十种判断</h2><p class="intro">从识人、进谏到改革、继承与乱世安身，十篇图文专题回到人物的具体处境，分析选择、代价与经验的边界。</p>'
    section += '\n'.join(entries) + '</section>\n' + END
    if START in directory:
        directory = re.sub(re.escape(START) + r'.*?' + re.escape(END), lambda _: section, directory, flags=re.S)
    else:
        anchor = '<a class="entry" href="ruler-deaths.html">'
        if anchor not in directory:
            raise ValueError('Cannot locate existing topic directory insertion point')
        directory = directory.replace(anchor, section + '\n' + anchor, 1)
    if 'id="research-ten-topics-style"' not in directory:
        directory = directory.replace('</head>', DIRECTORY_CSS + '\n</head>', 1)
    description = '从识人、进谏、改革、继承到财政与乱世安身，结合原文和图形细读人物的处境、选择与代价；另有孤立、判断真伪、关系与权力等专题。'
    directory = re.sub(r'(<meta (?:name="description"|property="og:description") content=")[^"]*',
                       lambda m: m[1] + esc(description), directory)
    schema_match = re.search(r'(<script type="application/ld\+json" id="seoSchema">)(.*?)(</script>)', directory, re.S)
    if schema_match:
        schema = json.loads(schema_match[2])
        for node in schema.get('@graph', []):
            if node.get('@type') == 'WebPage':
                node['description'] = description
        directory = directory[:schema_match.start(2)] + json.dumps(schema, ensure_ascii=False) + directory[schema_match.end(2):]
    directory_path.write_text(directory)
    print(f'Integrated {len(articles)} essays and 27 responsive figures into dist/research/ and dist/research.html')


if __name__ == '__main__':
    main()
