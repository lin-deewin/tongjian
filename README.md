# 通鉴年鉴：全书294卷

静态网站，保持原有纸色、墨绿、朴素年表和独立阅读页。桌面原文与白话左右对照，手机按组上下排列。

已载入用户提供的胡三省注版全部294卷，覆盖前403年至959年、1362个连续年份。原书部分年份分属相邻卷，网站有1419个年卷条目，并提供本年续篇链接。原文逐段按源顺序重建，与 EPUB 完全相同。第二百、二百零一卷在原 EPUB 中文件顺序颠倒，依卷题及内容归位。

目前30584段原文正文中28572段有上传译文对应，2012段缺译或待核对。上传的白话 EPUB 第28、113、200卷只有古文；第189、214—218、223卷等处有重复章节造成的白话缺失。其余文字差异、排版粘连、遗漏与未可靠对齐段落另行标注。不要将全书原文已收录说成全书每段白话已完成人工校对。没有生成译文冒充上传版白话。

## 运行

```sh
python -m http.server 8000 --directory dist
```

打开 `http://localhost:8000`。无前端构建或第三方依赖。原文正文按卷加载，正文缓存最多五卷。全书搜索在 Web Worker 内以四个请求并发读取分卷索引，显示检索进度并分页展示结果。

## 数据与定位

- `dist/catalog.json`：294卷、起止年份及同年所在卷索引。
- `dist/volume1.json` 至 `dist/volume294.json`：胡注原文、白话、年头、衔接文字、对齐结果和版本提示。
- `dist/search1.json` 至 `dist/search294.json`：分卷全文检索，含古文、胡注、白话、待核对来源。
- `dist/coverage.json`：完整性和缺译统计。
- `year` 为兼容原型的排序键，正数为公元前，负数为公元后；没有0。新卷 `calendarYear` 使用通常的有符号纪年，等于 `-year`。请不要把排序键当作公历年份。
- 卷11前202年：`#volume-11-year-202`；卷294公元959年：`#volume-294-year--959`。年表 `#volume-294`；卷首 `#volume-294-intro`。旧第一卷地址兼容。
- `sourceId` 定位至原卷和原段落；正文阅读锚点不越界，按原文顺序排列。

## 重建与校验

依赖 Python 3 与 `requirements.txt` 中的 lxml。原始 EPUB 仅作为本地输入，不放入部署目录。第一至十卷保留已验证的数据；新脚本重建第十一至二百九十四卷。

```sh
python scripts/build_full_book.py --original /path/to/hu.epub --translation /path/to/translation.epub --output dist
python scripts/validate_full_book.py --original /path/to/hu.epub
node --check dist/app.js
node --check dist/search-worker.js
node scripts/check_reader.cjs
```

脚本处理十六个纪、公元前后转换、改元、同年跨卷、合卷、源年头误字和注释括号异常。匹配规范化仅作用于比较副本，不回写原文。古文内容匹配与动态规划辅助识别译本排版，低置信度分开显示；没有对应译文的原文不会删除。三个纯古文章节经 `finalize_full_book.py` 排除，防止把古文显示成白话。

`full-source-audit.json` 与 `full-alignment-report.json` 保存源位置、年份异常、未对应内容及审核线索。脚本会实际生成统计；扩展版本后按实际统计更新本说明。

本次检查：294卷原文逐段重建、1362个连续年份、无公元0年、所有段落唯一覆盖或明确缺译、所有事件锚点、公元前后边界、同年续篇、全书后台搜索、五卷缓存、历史地址与返回状态。`check_reader.cjs` 使用简化 DOM 验证逻辑和生成内容，不代替实际浏览器视觉检查。本环境未完成浏览器视觉验收。

事件标题按第一卷标准重写：第2至294卷共30,402条，均已逐条阅读对应正文并人工重写。人工标题记录原文段落及对应对照组的校验值，正文变化时重建会拒绝套用过期标题；原文、译文、年份和阅读锚点不由标题处理改写。

运行 `python scripts/summarize_event_titles.py --data dist` 可重新应用标题；人工标题维护在 `scripts/event-title-overrides.json`，附对应原文段落校验值，来源改变时停止而不套用旧标题。两个构建流程已接入标题处理。各卷已重写与待校对数量、较长标题见 `dist/event-title-report.json`。
