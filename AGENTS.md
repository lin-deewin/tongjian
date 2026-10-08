# 通鉴年鉴：当前开发版本

先读取 `.agents/skills/develop-tongjian/SKILL.md` 和它引用的设计约定。
当前项目与本文件优先于技能内的旧第一卷快照；不要用快照覆盖当前代码。

已收录全部294卷胡三省注本原文，前403年至公元959年，共1362年。
30584段正文中28572段有上传白话对应，2012段缺译或待核对。
卷28、113、200的上传白话章节实际为古文；另有缺失、重复章节。
不得将古文充作白话，不得把生成译文署名为柏杨，不得删除缺译的原文。
详细统计见 README.md、dist/coverage.json 和两个 full-*.json 报告。

保留逐年年表、独立整页阅读、桌面左右对照、手机同组上下对照。
保留共同滚动、注释开关、字号、模式切换、事件锚点和返回浏览位置。
沿用朴素纸色与墨绿；不恢复右侧抽屉或已撤回的双页书美化。

网站入口：dist/index.html、dist/app.js、dist/search-worker.js。
数据：dist/volume1.json 至 volume294.json、search1.json 至 search294.json。
原始输入：sources/hu-sansheng.epub、sources/baiyang.epub。
年排序键 year 为正数公元前、负数公元后，没有0年；不要误作公历符号。
原文必须按来源顺序完整重建；同年可能分属相邻卷，保留本年续篇。

运行：python -m http.server 8000 --directory dist
校验：python scripts/validate_full_book.py --original sources/hu-sansheng.epub
导航及搜索校验：node scripts/check_reader.cjs
语法：node --check dist/app.js 和 node --check dist/search-worker.js
check_reader 使用简化DOM，不代表真实浏览器视觉验收。

第2至10卷处理：scripts/build_volumes.py。
第11至294卷处理：scripts/build_full_book.py（自动调用 finalize_full_book）。
第1卷可用技能中的参数化脚本。根目录两个早期脚本包含旧路径，仅作历史参考。
数据重建需 pip install -r requirements.txt；普通浏览不需要前端构建。
.openai/hosting.json 是原网站的托管标识，无部署凭据。
用户要求本地开发时直接开发本目录，不要自动发布或更改线上站点身份。
