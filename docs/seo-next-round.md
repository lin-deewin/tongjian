# SEO后续修复：2026-10-16

> 后续又增加1362个逐年页；当前共1732个生成页和1741条地图地址，细节见 [逐年独立地址](seo-year-pages.md)。本页的369页／378条统计保留为逐年页上线前的阶段记录。

## 已上线

- 用户手动清除Cloudflare缓存后，普通根 `/robots.txt` 公网复查为200、BYPASS，含正确规则及根地图声明。旧缓存问题已收尾。
- 萧何53条已关联记载：17条主要经历、30条相关提及、6条史家评论。补查全书姓名、封号和省称，逐条核读现收录来源及上下文。前205年守关中为主要经历。
- 乐毅15条：9条主要经历、6条相关提及。新增谋齐、济西、整军、围二邑、奔赵、受封、书信与卒赵；排除乐闲活动，附叙卒年不误系前279年。
- 人物页仅表示现收录条目已核读，不能据此宣称全书代词／官称无遗漏、外部纪年全部一致或生平完全穷尽。
- 新增萧何独立静态页，当前70个人物独立页、369个生成页、378个地图URL。
- 两篇免费史事细读：`history/xiao-he-guanzhong/`、`history/yue-yi-qi-campaign/`。专题目录、阅读目录、人物页、原文卷页互链。
- 文章属于本站整理与分析，不是上传译本白话；原文引文、来源校验值、研究边界记录在 `scripts/seo/history-articles.json` 与 `reports/seo-next-round/research-notes.json`。
- 渲染由 `scripts/history_articles.py` 接入 `build_seo.py`；原文或引文变化时拒绝旧绑定。294卷原始JSON、上传白话和私有付费交付文件未因文章新增而改写。

## 观测与平台边界

服务器已安装并启用 `tongjian-seo.timer`，每小时运行技术观测，首次 `tongjian-seo.service` 成功。
运行代码在 `/root/projs/tongjian/scripts/ops/seo_snapshot.py`，报告位于服务器私有目录
`/root/projs/tongjian/reports/seo-observation/`。默认查13个代表页、根robots、地图及旧入口跳转。
本地 `--full` 已完成378个公共页面的公网检查，结果见 `reports/seo-observation/latest.json`。

流量脚本识别 `TongjianSEOCheck/` 请求，在总负载中保留，但从访客／页面访问数剔除，并单列
`self_monitor_requests` 和 `requests_excluding_self_monitor`。文章 `/history/` 入口计入页面访问。
其他未知机器人、人工QA请求及Cloudflare缓存仍影响日志口径，不能拿日志页面访问数充当搜索点击。

新增 `import_search_performance.py` 可导入实际Google／百度CSV，保留文件校验值、维度和数据范围。
当前没有取得实际平台导出文件，没有验证Google／百度站点所有权，也没有代报提交地图或收录成功。
用户表示尚不清楚平台状态，已请其打开Search Console并提供页面截图，后续按实际界面接入。

## 实际验收

- `check_people_audit.py`：451档案、8939条来源绑定记录，身份／日期／分类回归通过。
- `audit_people.py`：结构错误0；仍有其他人物的语义核查候选，不将机器风险标记直接当成已确认错误。
- `check_seo.py`：369生成页、378地图地址、源顺序及普通内链通过。
- `check_seo_browser.py`：369页禁用JavaScript可读，294卷与阅读器一致；1440／390／320px模板和阅读交互通过。
- 两篇文章、两个人物页及专题目录另做15个桌面／手机场景；来源跳转、浏览器返回、无横向溢出与无脚本异常通过。
- EPUB全书精确重建及原阅读器1419个年卷条目、搜索、返回回归通过。
- 公网全量378页的状态、canonical、H1、noindex与地图／跳转通过；12个代表部署文件与本地SHA-256一致。
- Caddy与账号服务保持active；未改DNS、数据库、账号、付费范围和支付开关。

证据：`artifacts/seo-next-round/`、`reports/seo-next-round/`、`reports/seo-observation/`。
服务器静态备份：`/root/projs/tongjian/backups/20261016-seo-content2/`。
后续先观察真实收录和查询词，再决定新的人物与文章批次，不承诺排名或增长百分比。
