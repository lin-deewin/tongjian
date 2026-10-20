# 逐年独立地址（2026-10-16）

在已存在的294个静态卷页上增加1362个逐年正文页和逐年目录。

- `year/`：完整逐年目录。
- `year/bce-403/`：公元前403年；`year/ce-1/`：公元1年。没有0年。
- 初始HTML包含原文、胡注、所据白话、缺译和版本差异说明；启用JavaScript时复用 `reader.html` 的左右对照、主题、字号、注释、摘记及选区高亮；禁用时显示完整静态正文。
- 每年声明自身canonical，进入站点地图；首页、静态卷页和阅读器连接逐年页。
- 同年跨卷内容按卷序合并，段落锚点带卷号，保留本年续篇；前后年导航跨公元前后。
- 既有静态卷页继续作为完整卷章节，原阅读器hash链接继续工作，阅读器正文提供独立年份页入口。

生成：`python scripts/build_seo.py`。仅同步年度阅读界面：`python scripts/year_reader.py`（从当前卷数据重建年度静态正文，并共用阅读器模板）。
校验：`python scripts/check_seo.py`、`node scripts/check_reader.cjs`、`python scripts/check_year_pages_browser.py`。
浏览器校验包含1440px、390px禁用JavaScript阅读、跨卷年份、阅读器到独立页、阅读模式。

本次共用阅读器的样式修改仅在本地，尚未发布。

此前的静态样式版本于2026-10-16按用户要求发布工作区dist，完成增量同步和caddy读取ACL。公网抽查14个资源摘要与本地一致，旧路径308跳转正确；1440px、390px真实浏览器禁用JavaScript阅读、跨卷年份、阅读器到年份页和阅读工具均通过。证据见artifacts/seo/year-pages/deployment.json和live-browser.json。

可在Search Console抽查新网址、测试Google渲染与实际收录；公网可访问不代表已被Google收录。

## 既有配图的正文位置

全书1148张译本原书插图保留原图文件与图题，统一由 `dist/illustrations/volume*.json` 管理。
1131张按图题、月份、来源上下文及对应事件放在正文对照组之后；17张所属年份在胡注本无单列正文，保留为年度背景参考图。
同年跨卷的图随对应记事归卷。两张原无外部图题的图，按图内文字标注武氏世系和十二时辰。

重新计算：`python scripts/place_reader_illustrations.py --epub /path/to/zztj2.epub`；
仅输出候选报告：增加 `--report-only`。人工核对的138处位置保存在 `scripts/illustration-placements.json`，
绑定原文段落摘要，原文变化会中止处理，避免静默错位。放置报告见 `artifacts/illustration-placement/placement-report.json`。
运行后执行 `python scripts/build_seo.py`，同步卷页和年度页。导入译本后也需重新执行以上步骤。
动态阅读器与静态正文均使用这些位置，包括尚未可靠对齐的原文段落；原文与白话文本不因配图调整而改写。

配图逐张校验：`python scripts/check_reader_illustrations.py`（文件存在、年度归属、无重复、正文对照组后的准确位置）。
