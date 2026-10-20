# 通鉴年鉴：全书294卷

静态网站，保持原有纸色、墨绿、朴素年表和独立阅读页。桌面原文与白话左右对照，手机按组上下排列。

已载入用户提供的胡三省注版全部294卷，覆盖前403年至959年、1362个连续年份。原书部分年份分属相邻卷，网站有1419个年卷条目，并提供本年续篇链接。原文逐段按源顺序重建，与 EPUB 完全相同。第二百、二百零一卷在原 EPUB 中文件顺序颠倒，依卷题及内容归位。

目前30584段原文正文中28856段有上传译文对应，1728段缺译或待核对。本次从原上传文件恢复285段此前漏配的白话，没有使用生成译文。上传白话 EPUB 第113、200卷仅有古文；第28卷为古文与白话混合，已恢复其中13段可核对的白话。第189、214—218、223卷因重复或错置章节而缺失白话，第31卷部分白话截断；其余文字差异、排版粘连、遗漏与未可靠对齐段落另行标注。全书原文已收录，不代表所有白话已完成人工校对。

## 运行

```sh
python -m http.server 8000 --directory dist
```

主页：`http://localhost:8000/`（`dist/index.html`），参考资治通鉴在线的介绍与导航结构；“开始阅读”进入 `reader.html`。年表与阅读页面位于 `dist/reader.html`，顶部可返回主页。`home.html` 保留为主页兼容入口；根地址上的旧阅读与人物锚点会自动转到阅读页面。

打开 `http://localhost:8000`。无前端构建或第三方依赖。原文正文按卷加载，正文缓存最多五卷。全书搜索在 Web Worker 内以四个请求并发读取分卷索引，显示检索进度并分页展示结果。

## 账号与邮箱注册

阅读内容由静态站点提供；注册、登录、找回密码和账号页由独立 Django/PostgreSQL 后端提供。线上入口为 `https://deewins.top/tongjian/`，登录、注册和账号页分别是 `account/login/`、`account/register/`、`account/`。本机开发入口仍为 `http://100.108.212.5:3003/tongjian/`。

```sh
systemctl --user restart tongjian-accounts.service tongjian-atlas.service
```

线上账号服务由服务器 systemd 与 PostgreSQL 管理，后端仅监听回环地址并经 Caddy 代理；生产配置保存在服务器 `/etc/tongjian-commerce/commerce.env`，不进入 Git。现有账号密码哈希已迁移，旧会话已失效，需要重新登录。支持邮箱验证码注册、密码登录、修改/找回密码及无 JavaScript 退出；从阅读事件登录后返回原位置。购买与支付保持关闭。本机 3003 开发入口配置见 [本机入口说明](ops/local/README.md)。

首次安装与运行见 [后端手册](backend/README.md)，验收和邮件投递限制见 [账号集成记录](docs/account-integration.md)。

## 全站 SEO（2026-10-16 已发布）

本轮补齐萧何（53条，其中17条主要经历）与乐毅（15条，其中9条主要经历）的当前关联记载，增加两篇史事细读和1362个独立年份页。当前70个人物独立页、1732个生成页、1741个地图地址。robots旧缓存已由用户清除并公网复验通过；搜索观测及平台数据边界见 [观测说明](docs/seo-monitoring.md)。

当前主地址为 **https://deewins.top/**，旧 `/tongjian/` 链接按路径永久跳转。根域名迁移与验收见 [迁移记录](docs/root-domain-migration.md)。

讨论、取舍、修改前基线与待办见 [SEO 讨论记录](docs/seo-discussion.md)，全站实施见
[全站改造说明](docs/seo-full-site.md)。`dist/reading.html` 为阅读入口，
`dist/volume/index.html` 按十六纪列出294卷，`dist/people/index.html` 列出70位已核读人物。
所有294卷均有静态正文页；另381个人物档案的已收录条目尚未全部完成上下文复核，
继续在原阅读器中保留，不为SEO直接列入独立人物页与地图。独立年份页按年合并跨卷记事，正文与卷页共享稳定原文锚点。
原年表、搜索、人物档案与 fragment 阅读地址保持可用。新增页首次 HTML 即含核心正文，
不依赖 JavaScript 抓取；可从首页普通链接进入，卷页桌面左右对照、手机同组上下排列。

```sh
python scripts/build_seo.py
python scripts/check_seo.py
python scripts/check_seo_browser.py
```

卷、人物或公开专题HTML改变后重新生成；生成器校验当前目录所选的译文补充／替换与人物复核绑定，
不会重建或改写294卷基础 JSON。`scripts/seo/site.json` 为全站配置，
`scripts/seo/pilot.json` 保留初始试点记录；两篇史事及来源绑定在 `scripts/seo/history-articles.json`，本轮发布与观测见 [后续修复](docs/seo-next-round.md)；`dist/seo-manifest.json` 保存输入、生成页与未纳入人物。
根抓取配置及未来发布检查见
[SEO 配置说明](ops/seo/README.md)。已发布全部静态页面与生产根路由，尚未配置搜索平台或提交地图。
根 `/robots.txt` 已设 no-store，用户清除Cloudflare旧缓存后已公网复验正确。已启用小时技术观测；平台验证和地图提交仍需实际账号完成。

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

脚本处理十六个纪、公元前后转换、改元、同年跨卷、合卷、源年头误字和注释括号异常。匹配规范化仅作用于比较副本，不回写原文。古文内容匹配与动态规划辅助识别译本排版，低置信度分开显示；没有对应译文的原文不会删除。原流程按纯古文排除第28、113、200卷；专项复核确认第28卷为混合章节，通过独立补充文件恢复其中的白话，第113、200卷仍不将古文显示成白话。

`full-source-audit.json` 与 `full-alignment-report.json` 保存源位置、年份异常、未对应内容及审核线索。脚本会实际生成统计；扩展版本后按实际统计更新本说明。

本次检查：294卷原文逐段重建、1362个连续年份、无公元0年、所有段落唯一覆盖或明确缺译、所有事件锚点、公元前后边界、同年续篇、全书后台搜索、五卷缓存、历史地址与返回状态。`check_reader.cjs` 使用简化 DOM 验证逻辑和生成内容，不代替实际浏览器视觉检查。本环境未完成浏览器视觉验收。

事件标题按第一卷标准重写：第2至294卷共30,402条，均已逐条阅读对应正文并人工重写。人工标题记录原文段落及对应对照组的校验值，正文变化时重建会拒绝套用过期标题；原文、译文、年份和阅读锚点不由标题处理改写。

运行 `python scripts/summarize_event_titles.py --data dist` 可重新应用标题；人工标题维护在 `scripts/event-title-overrides.json`，附对应原文段落校验值，来源改变时停止而不套用旧标题。两个构建流程已接入标题处理。各卷已重写与待校对数量、较长标题见 `dist/event-title-report.json`。

## 人物档案与生平时间线

阅读页中带虚线的人名可点击进入独立人物页；对照段落末尾另有“本段人物”入口。页面顶部的“人物档案”可按姓名或别名查找。年表点击“人物”分类后，下方展示当前卷有主要经历且已建档的人物；切卷同步更新，点击姓名可查看时间轴。

目前收录451个人物档案、8939条经历、提及与史家评论，覆盖第1至294卷；人物年表筛选每卷均有已建档人物。第1至2卷首批8人（吴起、魏文侯、赵襄子、智伯、豫让、商鞅、孙膑、庞涓）共57条，第3卷另有48人、98条。第4至294卷原新增335人，本次核查另将混杂的同名、姓名前缀与庙号身份分离为60个档案；条目关联年表标题和原文段落。标题、人物归属及时间判断仍有待逐条终审，不把来源校验通过视为历史判断全部正确。追叙与评论按“相关提及 / 史家评论”显示，不把记载年份误作人物经历年份。档案不是全书所有人名的穷尽清单，也不宣称人物传记完整；未建档的人名仍可通过全书搜索查找。人物目录会显示当前收录数量，各人物页显示各自范围。

- 从阅读页进入时，默认只显示截至当前阅读年份已记载的经历；“查看后续经历”可展开其余内容。从人物独立地址首次打开时显示全部已收录经历。
- 支持“主要经历 / 全部已收录记载”和经历类型筛选。明确年份从左到右按时间排列，同年按原书记载顺序；横轴按事件等距排布，间距不代表年份间隔。桌面可使用左右按钮，手机可左右滑动，键盘可聚焦后使用方向键；追叙、跨年附叙、年份未详和史论另列，不以记载年份代替发生年份。已核对明确生年的档案在事件年份旁显示“约N岁”，按年份差估算（无公元0年），不是精确周岁或虚岁。生年来源见人物页，维护于 `scripts/people/life-years.json`；生年有争议、事件年份未详及出生前或去世后的记载不显示年龄。原391个档案保留原生年核查记录；现451个档案中：185人生年明确，170人生年未详，15人生年有争议，13人仅有估计生年，68人尚未取得身份吻合且可确认生年的资料（包括本轮分离的60人）。逐人来源与状态见 `scripts/people/life-years.json`，核查依据见 `scripts/people/research/life-years-audit.json`，全书事件年龄统计见 `dist/people-life-report.json`。这些生年资料独立于上传原文，原书内容与事件出处不因此改写。
- 时间轴卡片展示可点击跳转至原文的事件标题及可展开的完整原文依据，不展示说明摘要及重复的本年记事提示；追叙等时间归属提醒保留。出处跳转保存卷、年、段落锚点；从人物页进入原文后，主返回按钮按来源显示“返回某某时间轴”；从年表进入则显示“返回年表”。可返回人物时间线，再返回最初阅读位置，保留阅读模式、字号与注释设置。
- 人名只在核对过的段落内关联，别名按人物身份归并。“孙子”“襄子”等不做全书字符串替换；不同人物共享别名时正文保留文字，段落人物列表按身份分别展示。
- 独立人物地址：`#person-wu-qi`、`#person-shang-yang`；目录：`#people`。带出处锚点的阅读地址示例：`#volume-1-year-381-para-0`。

刘备、诸葛亮、张飞、关羽先行接入中文维基百科完整条目快照。人物页提供“人物资料 / 通鉴时间轴”切换，资料保留全部条目章节、信息表、图片说明、注释、参考资料和相关条目；桌面有侧边章节目录，手机目录可折叠，基本信息表可展开。图片按原始分辨率取用或采用960px版本，本地保存优化后的展示图片，不人工放大低分辨率来源；点击图片可查看外站原始分辨率。每页附原始版本、贡献者历史、CC BY-SA 4.0文字许可及逐图作者和许可。这些外部资料独立于通鉴原文、上传白话及核对过的时间轴。

资料位于 `dist/biographies/`，来源快照和图片元数据位于 `sources/wikipedia/`。`pip install -r requirements.txt` 后运行 `python scripts/import_wikipedia_people.py` 可从存档重建，`--refresh` 获取新条目快照；不改写 `dist/people/*.json` 或全书数据。`python scripts/check_biographies_browser.py` 检查全文章节、引用、本地图片、桌面与手机排版、目录和脚注锚点、时间轴和原文返回；浏览器截图输出至 `artifacts/biographies/`。

萧何档案已逐条复核原有20条记录，纠正前206、前205及前201年经历的类型和年份，并补充9条记载，共29条；审计记录见 `scripts/people/research/xiao-he-audit.json`。


### 全人物核查（2026-10-15，尚未完成全部语义终审）

本轮机器检查覆盖修订前391人、8845条记录及全书294卷30584段原文。已修正一批同名人物、姓名前缀和帝号错配、出处锚点、即位与去世分类、追叙及史家评论归年问题。原文完整保留；13条不能成立的人物关联已撤销，原记录保存在核查日志中。修订后451个档案、8832条关联记录。

- `python scripts/audit_people.py`：只读扫描全部当前档案、记录、来源及全书姓名匹配候选，输出 `reports/people-audit/`。
- `python scripts/check_people_audit.py`：本次发现问题的身份、纪年、分类及出处回归检查。
- `scripts/people/research/full-audit-decisions.json`：逐项保存修改前后、原因及核查层级，区分按标题纠正分类与具体上下文修订。
- `reports/people-audit/README.md` 与 `summary.json`：核查范围、待核数量和限制；`profiles.json` 覆盖每人，`events.json` 覆盖每条记录，`missing-name-candidates.json` 保存可能漏收的原文位置。

**机器检查不能认证历史正确率或无遗漏。** 姓名命中可能是同名、复姓、动词、引语、胡注或追叙；原文也可能仅用字、官名、爵号与代词。仍须逐条结合上下文终审，不能把候选直接加入时间轴、不能把零结构错误称为“100%正确”。

数据维护：`scripts/people/reviewed.json` 保存核对记录和源段落校验值；`python scripts/build_people.py` 验证后生成 `dist/people-index.json` 及 `dist/people/*.json`。正文变化会拒绝使用旧记录；阅读并修订变化段落后才可执行 `--bind-reviewed-sources` 更新绑定。重建卷数据后也应运行此脚本检查人物出处。

`node scripts/check_reader.cjs` 检查既有阅读功能；`python scripts/check_people_browser.py` 在本地临时 HTTP 服务和无头 Chromium 中验证人名、日期筛选、出处、段落深链、返回位置、浏览器后退与手机布局。浏览器检查需额外安装 Python `playwright`，优先使用系统 Chrome，或使用 `python -m playwright install chromium` 安装测试浏览器。


## 专题：通鉴中的君主之死

入口为 `dist/ruler-deaths.html`，主页导航和阅读导航区均有入口。沿用纸色与墨绿，以“一点一人”的君主结局点阵、死因环图与条形图、分时代100%堆叠图、四段原文案例及可筛选表格呈现。支持姓名与因素搜索、时代/政权/结局筛选、排序、分页、筛选地址恢复、CSV导出、原文详情及卷年段落跳转。

当前逐条绑定291位实际君主的死亡记载，覆盖周、战国至五代及契丹，含先秦称公侯的国君、帝王和独立政权君主，不纳入仅有王爵的普通宗室。当前并非全书君主的穷尽名单，图表和百分比仅代表已收录记录。每人只计一次；“崩、薨、卒”不自动归为病死或自然死亡，所引段未述死因的126条和记载存疑/多因的5条均保留在分母内。病中去世记录病情上下文，不作现代医学诊断；服药相关与确切置毒、鸩杀分别处理。表格按通鉴条目记载年定位，追叙及附叙不保证与实际卒年相同，正文解释中保留时间提示。

人工核对记录位于 `scripts/rulers/reviewed.json`，每条解释都绑定原文、卷、年、段落及源段落校验值。`scripts/rulers/registry.json` 是检索候选名单，卒年仅是定位线索，不作为统计来源，也不自动发布。运行 `python scripts/build_ruler_deaths.py` 校验并生成 `dist/ruler-deaths.json`；构建脚本不从关键词自动判断死因。来源变化时会拒绝旧绑定，必须重新核对后才可用 `--bind-reviewed-sources` 更新。

校验：`python scripts/check_ruler_deaths_browser.py`，检查逐条原文对应、人数与分类总和、图表和筛选同步、分页、筛选地址恢复、原文深链、CSV导出、空结果与桌面/平板/390px/320px手机布局，截图存于 `artifacts/ruler-deaths/`。页面数据与全书正文、白话及已有档案数据分开维护。

## 历史河流：饥荒专项补漏

本地饥荒索引经2026-10-13专项补漏，从190条更新为247条，涉及202个年份。
补收71条，同年同地归并9条，5条饥荒分类转待核；战争及天灾的其他分类保留。
条数按年记灾情，连续跨年饥荒各年记录，不代表独立饥荒过程总次数。

本轮扫描814段关键词线索并查看摘录，全文核读201个不同原段；旧190条检查来源
引文。448段仍只完成摘录初筛，85个疑难段及5条撤回分类保留待核，没有全书通读
或独立第二审。详见 `scripts/river_events/famine-report.md`、`dist/famine-audit-report.json`。

运行 `python scripts/river_events/prepare_famine.py` 生成复查原段队列，
`python scripts/build_river.py` 校验绑定并重建，
`python scripts/check_famine_supplement.py` 验证引文、归年、分类保留及重建一致性。

## 上传白话专项补漏（2026-10-13）

本次仅从上传 EPUB 恢复白话。285段由139段原先落入“版本差异”的译文、133段被排版或年份边界干扰的原文白话对，以及第28卷13段明确的白话组成。23处旧字段粘连了后续古文与其他记事，按上传段落边界分离，不改写译文字句。跨年匹配保留胡注原文的原定位，并在阅读中提示译本记年差异。

补充数据位于 `dist/translation-supplements/volumeN.json`，按原文校验值绑定；阅读及搜索使用同一批补充数据。294卷基础数据字节不变，事件锚点和历史河流的原文绑定保持有效。统计见 `dist/translation-supplement-report.json`。用户已明确不采用AI补译，草稿未发布，也不参与统计。

重建与校验：

```sh
python scripts/translations/recover.py
python scripts/build_translation_supplements.py
python scripts/check_translation_supplements.py
python scripts/validate_full_book.py --original sources/hu-sansheng.epub
node scripts/check_reader.cjs
```

`validate_full_book.py` 默认核验补充后的可读数据；加 `--base-only` 可核验补漏前的基础数据。若重建了基础卷，须重新运行恢复与补充构建，旧补充的来源校验值不可直接沿用。

## 逐年独立阅读页

新增1362个年份正文页与 `year/` 目录，例如 `year/bce-403/`、`year/ce-1/`；初始HTML完整保留跨卷续篇、原文及所据白话。年度页复用 `reader.html` 的界面与阅读工具，保留年度网址和段落定位；禁用JavaScript时可读完整静态正文。只更新年度界面可运行 `python scripts/year_reader.py`，完整生成仍用 `python scripts/build_seo.py`。自身canonical、普通链接与站点地图保留。维护与验收见 [逐年页面说明](docs/seo-year-pages.md)。

全书已有1148张译本配图已按相关记事插入年度正文；1131张随正文段落显示，17张无对应年度原文的图保留为背景参考。位置维护与重建方法见 [逐年页面说明](docs/seo-year-pages.md#既有配图的正文位置)。
