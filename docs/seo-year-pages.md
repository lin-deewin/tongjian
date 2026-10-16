# 逐年独立地址（2026-10-16）

在已存在的294个静态卷页上增加1362个逐年正文页和逐年目录。

- `year/`：完整逐年目录。
- `year/bce-403/`：公元前403年；`year/ce-1/`：公元1年。没有0年。
- 初始HTML包含原文、胡注、所据白话、缺译和版本差异说明；JavaScript仅增强阅读工具。
- 每年声明自身canonical，进入站点地图；首页、静态卷页和阅读器连接逐年页。
- 同年跨卷内容按卷序合并，段落锚点带卷号，保留本年续篇；前后年导航跨公元前后。
- 既有静态卷页继续作为完整卷章节，原阅读器hash链接继续工作，阅读器正文提供独立年份页入口。

生成：`python scripts/build_seo.py`。
校验：`python scripts/check_seo.py`、`node scripts/check_reader.cjs`、`python scripts/check_year_pages_browser.py`。
浏览器校验包含1440px、390px禁用JavaScript阅读、跨卷年份、阅读器到独立页、阅读模式。

已于2026-10-16按用户要求发布当前工作区dist，完成增量同步和caddy读取ACL。公网抽查14个资源摘要与本地一致，旧路径308跳转正确；1440px、390px真实浏览器禁用JavaScript阅读、跨卷年份、阅读器到年份页和阅读工具均通过。证据见artifacts/seo/year-pages/deployment.json和live-browser.json。

可在Search Console抽查新网址、测试Google渲染与实际收录；公网可访问不代表已被Google收录。
