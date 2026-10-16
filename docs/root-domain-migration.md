> 后续更新：用户已手动清除Cloudflare缓存，2026-10-16普通根robots公网复验正确；本记录下方的缓存描述保留迁移当时状态。

# 根域名迁移：2026-10-16

> 后续另发布1362个逐年页；当前根 sitemap 包含1741个规范URL。本文迁移验收中的375页统计记录迁移时基线。

## 当前地址与发布状态

主站为 **https://deewins.top/**。已通过 `ssh root@deewins` 发布并切换生产 Caddy 与账号服务。
静态文件目录仍为 `/root/projs/tongjian/dist`，无需移动原文数据文件。

- 首页、卷次、人物、专题的 canonical、Open Graph、结构化数据和普通链接使用根域名。
- `/sitemap.xml` 返回375个根域名规范地址的 urlset；`/sitemap-index.xml` 指向它。
- `/tongjian` 与 `/tongjian/*` 以308跳转到对应根路径，保留查询参数；浏览器保留原 fragment。
- 登录、注册、找回密码、账号、购买和后台入口分别使用 `/account/`、`/api/`、`/checkout/`、`/article/`、`/admin/`；Cookie Path 改为 `/`。
- 旧支付回调 `/tongjian/api/v1/payments/*` 在 Caddy 内去除前缀后代理，兼容既有订单，不依赖支付平台跟随重定向。
- 已发布的私有文章/PDF及其校验值未改写；经过校验的文章在响应渲染时将旧站内链接迁到根路径。
- 没有数据库迁移、账号数据变更或支付开关变更。现有销售和支付仍关闭。
- Caddy访问日志覆盖整个根站；统计脚本兼容新旧首页并计入静态阅读页。

## 验收

- 全量375个公共页面公网HTTP 200，逐页SHA-256与本地发布文件一致。
- 对应375个旧地址逐页返回308，Location精确对应新地址；另验证无斜杠入口与查询参数。
- 新健康检查、匿名会话、登录、注册正常；匿名下载返回401，不存在地址返回404。
- 真实Chromium检查390/1440px首页、卷页、人物页、登录页，无横向溢出或脚本异常；登录弹窗正常。
- 旧阅读器地址跳转后同时保留查询参数和事件fragment，并加载正文。
- 全站SEO来源校验：366个生成页、294卷、69个人物、30584段原文，原文顺序精确。
- 禁用JavaScript的静态页与完整阅读器数据一致性、阅读设置和移动布局使用 `scripts/check_seo_browser.py` 验收。
- 全书EPUB精确重建、原阅读器1419个年卷条目及搜索/返回回归通过。
- 生产Caddy配置和新后端 `manage.py check --deploy --fail-level WARNING` 通过。

公网证据：`artifacts/root-migration/http-validation.json`、`browser-validation.json` 和同目录截图。
本次未用真实账号提交登录或交易，也未进行搜索平台提交，不据此宣称排名或流量增长。

## Cloudflare旧缓存边界

源站根 `/robots.txt` 已正确返回根站规则与 `Sitemap: https://deewins.top/sitemap.xml`，响应设为
`no-store, no-cache, must-revalidate`；带唯一查询参数的公网请求返回新内容并显示BYPASS。
普通根地址在本次验收仍命中发布前的 `Hello from Caddy` 对象，TTL为14400秒，验收Age约5445秒。
当前没有Cloudflare API凭据或已连接管理会话，无法主动清除此边缘对象；需等待旧对象过期后复验普通URL。
这不表示禁止抓取，但旧缓存中没有预期的地图声明和抓取规则。搜索平台应提交新的根地图。

## 回退与维护

- 配置和静态文件备份：`/root/projs/tongjian/backups/20261016-root1/`。
- 新后端：`/srv/tongjian-commerce/releases/20261016-root1`。
- 旧后端的绝对路径记录于备份中的 `backend-release`，当前symlink指向新版本。
- 切换脚本在服务或配置校验失败时恢复旧后端symlink与Caddy配置；完整人工回退还需从备份恢复旧静态文件。
- 后续先读取生产 `/etc/caddy/Caddyfile`，保留动态接口、旧回调兼容、可信代理与其他域名配置。
- 静态内容更新后先运行 `python scripts/build_seo.py`，再按项目发布技能同步dist并补ACL；不要恢复旧BASE。
- `ops/local/Caddyfile`已同步根路径结构；既有本机服务需重新载入配置才能使用新的本机根入口，本次未重启本机常驻服务。
