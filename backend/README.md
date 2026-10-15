# 通鉴年鉴账号与付费服务

Python 3.12、Django 5.2 LTS、PostgreSQL 16、Gunicorn。保留原静态站，动态地址统一在 `/tongjian/` 下。

当前实现：邮箱验证码注册、密码登录、我的账号、修改/找回密码、原生表单退出与会话、商品试读、受控全文/PDF、幂等订单、微信 Native/H5 adapter、回调签名与解密、查单/关单、全额退款、后台补发、对账、告警与加密备份。正式价格、商户权限和公网验收见 [上线决定](../docs/paid-content-launch-decisions.md)。支付宝与 JSAPI 未启用，本地模拟不是支付平台沙箱。

线上入口：`https://deewins.top/tongjian/`；登录：`/tongjian/account/login/`；注册：`/tongjian/account/register/`；我的账号：`/tongjian/account/`。账号后端由服务器 `tongjian-accounts.service` 管理，只监听 `127.0.0.1:8010`，由 Caddy 代理动态路径；PostgreSQL 数据库为独立的 `tongjian_accounts`。生产环境文件位于服务器 `/etc/tongjian-commerce/commerce.env`（root 0600），不应复制进仓库或普通备份。当前用户密码哈希已迁移，旧会话和临时验证码已清除；销售与支付保持关闭，管理员路由限本机。邮件服务使用 `mail.deewins.top:587` STARTTLS。

本机开发入口仍为 `http://100.108.212.5:3003/tongjian/`，由用户 systemd 管理，配置见 [本机入口说明](../ops/local/README.md)。不要在现有服务运行时再启动手工后台。公网状态、迁移与验收记录见 [账号集成记录](../docs/account-integration.md)。

## 首次安装与手工启动

以下命令从项目根运行。已有 `.venv-commerce`、`tongjian-commerce-dev` 和已构建内容时直接执行迁移/导入与启动，不创建同名容器，也不删除已有数据库。

```bash
uv venv --python 3.12 .venv-commerce
uv pip install --python .venv-commerce/bin/python -r backend/requirements-dev.lock
docker run -d --name tongjian-commerce-dev --restart no \
  -e POSTGRES_USER=tongjian -e POSTGRES_PASSWORD=local-development-only \
  -e POSTGRES_DB=tongjian_commerce \
  -p 127.0.0.1:55432:5432 public.ecr.aws/docker/library/postgres:16-alpine
.venv-commerce/bin/python scripts/build_paid_content.py --product truth
.venv-commerce/bin/python scripts/check_paid_content_public.py --directory dist
.venv-commerce/bin/python backend/manage.py migrate
.venv-commerce/bin/python backend/manage.py import_product
SITE_URL=http://127.0.0.1:18010 \
  .venv-commerce/bin/python backend/manage.py runserver 127.0.0.1:18010 --noreload
```

注册页填邮箱、图形验证码，发送邮件验证码后填写邮件验证码和密码/确认密码，通过校验才创建账号并记录邮箱验证时间；登录页使用邮箱和密码。默认进入“我的账号”，从阅读页登录时返回原阅读事件。账号页可以修改密码、退出和查看购买记录。修改密码保留当前设备会话，其他设备需要重新登录；退出使用带 CSRF 的 POST 表单，关闭 JavaScript 仍可操作。旧验证码账号通过找回密码设置密码，账号 ID、订单和权益不变。

可通过隔离浏览器校验脚本体验 fake 模拟购买。手工需要模拟时，另行显式设置 `PAYMENT_PROVIDER=fake SALES_ENABLED=true`；这不是支付平台沙箱，不会真实扣款。模拟接口仅允许开发配置、回环来源、本人订单、有效会话和 CSRF。

### 注册邮件与真实 SMTP

注册发送邮件前须通过本地生成的 4 位图形验证码，不区分大小写，5 分钟过期，支持换图。图片绑定当前会话，每次作答即失效，换图与校验均限流；服务端只保存答案摘要。通过后保留绑定邮箱的 10 分钟注册凭证，最终注册也检查该凭证；修改邮箱须重新验证。关闭 JavaScript 仍可换图、发邮件和注册。新增 `accounts.0003_graphic_challenge` 迁移只创建验证码表，保留已有账号。

支持符合邮箱格式且能接收邮件的常见邮箱和企业邮箱，不按供应商设置白名单。验证码绑定邮箱和注册用途，10 分钟有效、60 秒重发间隔；重发使旧码失效，5 次错误后失效，成功仅能消费一次，验证和账号创建在同一事务中。登录验证码不能用于注册。发送邮件不创建账号；错误、过期或未发送的验证码不能注册。

本地未配置 `EMAIL_HOST` 时，开发环境使用 `backend/test-mail/` 文件后端，页面明确提示不会投递到真实邮箱。配置 `EMAIL_HOST` 后自动使用项目 SMTP 后端 `config.mail.EmailBackend`；生产始终使用该 SMTP 后端。后端保留 TLS 证书验证，并通过 `EMAIL_MESSAGE_ID_DOMAIN` 给注册、找回密码邮件生成正式域名的 Message-ID；这不保证任何收件商的入箱结果。

本地已通过真实 SMTP 向自有域名邮箱发送注册、找回密码邮件并通过 IMAP 读到，完成注册、登录、改密和找回密码闭环。QQ 服务器曾接受测试邮件，但用户反馈未在 QQ 收件箱看到；该方向的最终入箱仍待排查，不能用 SMTP 的 `250 OK` 代替入箱确认。浏览器自动校验显式使用文件邮件后端和独立数据库，不向 example.com 等测试地址发送真实邮件。

将以下配置写入 Git 忽略的受限 `backend/.env`（建议权限 0600），重启后端，再使用自己控制的真实收件邮箱验收。不要将 SMTP 授权码提交到 Git 或写入报告。

```dotenv
EMAIL_HOST=服务商提供的SMTP主机
EMAIL_PORT=587
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_HOST_USER=发信账号
EMAIL_HOST_PASSWORD=SMTP授权码或服务商密钥
DEFAULT_FROM_EMAIL=已获准的发信邮箱
EMAIL_MESSAGE_ID_DOMAIN=deewins.top
LEGACY_EMAIL_LOGIN_ENABLED=false
```

若服务商要求 465 端口隐式 TLS，设置 `EMAIL_PORT=465`、`EMAIL_USE_TLS=false`、`EMAIL_USE_SSL=true`；两种加密方式不要同时启用。真实验收记录服务商、收件邮箱类型、发送/到达时间与错误情况，不记录验证码或凭据。找回密码复用同一发信配置。

首页、阅读器、专题目录和试读页导航均有“登录 / 我的账号”，注册入口在登录后隐藏。静态 `dist/account.html` 保留普通登录、注册与找回链接，无 JavaScript 也可进入同源后端；未连接后端时显示服务说明。仅运行静态服务不能登录或购买。当前按篇购买，没有余额充值。

旧 `/api/v1/auth/email-code/`、`verify/` 登录接口默认关闭，避免把验证码登录自动建号当作正式注册入口；兼容部署才显式启用 `LEGACY_EMAIL_LOGIN_ENABLED`。旧账号的邮件找回密码不依赖此开关。API 退出接口保留兼容。

后台入口 `/tongjian/admin/`；管理员需单独创建：

```bash
.venv-commerce/bin/python backend/manage.py createsuperuser
```

使用另一个管理员邮箱，密码交互输入。普通读者登录不能进入管理员账号。商品编辑自动递增价格修订号；订单、支付、退款和内容版本只读。通过“阅读权益”人工补发需填写原因，支付来源的权益不允许在后台任意改写；退款在订单列表的“全额退款”入口再次验证管理员密码。

原静态浏览命令仍可读年表与试读，但不会启动账号/支付服务；完整付费功能使用上述后端启动地址。

## 可重复的检查

建立专用测试库，默认名称必须以 `_test` 结尾：

```bash
docker exec tongjian-commerce-dev psql -U tongjian -d tongjian_commerce \
  -c 'CREATE DATABASE tongjian_commerce_test;'
.venv-commerce/bin/python backend/manage.py test accounts commerce payments \
  --settings=config.settings.test --noinput
.venv-commerce/bin/python scripts/check_paid_content_public.py --directory dist
.venv-commerce/bin/python scripts/check_commerce_restore.py
node --check dist/commerce.js
node scripts/check_reader.cjs
```

测试库已存在时跳过创建。测试配置读取 `TEST_DATABASE_URL`，独立浏览器和恢复演练读取 `BROWSER_DATABASE_URL`；脚本只创建并删除自己生成的临时数据库。生产业务连接不得用于这些检查。

真实浏览器检查需要 Chrome/Chromium 和 Caddy。可将官方 Caddy 二进制放进 `tmp/commerce-tools/caddy`，或用 `CADDY_BIN` 指定现有可执行文件。本次二进制来自官方容器镜像，复制方式为：

```bash
docker pull public.ecr.aws/docker/library/caddy:2-alpine
docker create --name tongjian-commerce-caddy-tool public.ecr.aws/docker/library/caddy:2-alpine
mkdir -p tmp/commerce-tools
docker cp tongjian-commerce-caddy-tool:/usr/bin/caddy tmp/commerce-tools/caddy
docker rm tongjian-commerce-caddy-tool
.venv-commerce/bin/python scripts/check_commerce_browser.py
```

浏览器脚本使用真实 Caddy、双进程 Gunicorn、隔离 PostgreSQL 和 fake adapter，监听回环地址，保存脱敏报告及截图到 `artifacts/commerce/`，结束后关闭测试服务并删除临时数据库。它验证 1440/390/320px、密码注册/登录与找回密码、购买、下载、越权、缓存头、目录、原文深链和返回；不证明真实支付 App 或 Cloudflare 验收。

## 内容重建

原批准 HTML/PDF 在迁移前已保存校验值；现有源稿、PDF 与全文生成逻辑保留。`scripts/commerce/render_truth.py` 负责批准 PDF 的原有文字核对，`build_paid_content.py` 是公开试读的唯一写入入口；旧 `artifacts/monetization/build_pdf_article.py` 为兼容包装，不再公开全文。

版本位于 `private-content/truth/<version>/`，`delivery.json` 存校验值，`current.json` 指向最新批准版本。同版本内容改变时构建失败，先在 `content/products/truth/manifest.json` 增加新版本。生成后执行公开扫描、`import_product` 和 `verify_content`，核验段落、SVG、出处与返回，不把私有目录、源稿、备份或整个项目根作为静态根。

完整网页按当前商品版本交付，购买时的名称、价格、内容版本和条款另存订单快照。章节和白话资料不在此次付费迁移中重建。

## 生产配置与受控真实支付验收

1. 在现有服务器发布任务安排后再操作线上。先确认实际 OS/容量、PostgreSQL、TLS、商户和邮件条件；保持 `SALES_ENABLED=false`。
2. 按 `backend/.env.example` 建 `/etc/tongjian-commerce/commerce.env`，EnvironmentFile 由 root 保管为 0600，systemd 将变量传给应用；私钥及备份密钥只授予应用用户读取。使用独立随机 Django/OTP 密钥、SMTP、真实 Host、内容根和管理员网段。
3. 后端版本放 `/srv/tongjian-commerce/releases/<release>/`，虚拟环境 `/srv/tongjian-commerce/venv/`，私有内容 `/srv/tongjian-commerce/content/`。应用以 `tongjian-commerce` 用户运行，内容只读。安装锁文件，迁移、导入、`collectstatic`，再检查实际文件权限。
4. 将 `ops/commerce/Caddyfile.fragment` 合并进现有域名配置，动态 handler 优先于原静态路由。Caddy 保留完整动态前缀并覆盖 `X-Real-IP` 和实际 `X-Forwarded-Proto`。确认 Cloudflare 的可信代理链以及 Full (strict) 到源站 HTTPS，再配置 `TRUSTED_PROXY_NETWORKS=127.0.0.1/32` 与 `TRUST_HTTPS_PROXY=true`。
5. Cloudflare 对 `/tongjian/api/`、`account/`、`checkout/`、`article/`、`admin/` bypass cache；对两类支付回调排除浏览器挑战。管理员来源限制需要验证直连源站不能绕过，不能仅填写一个未核实网段。
6. 配置微信商户号、AppID、商户证书序列号、私钥、APIv3 密钥和可信平台公钥映射。`WECHAT_PUBLIC_KEYS_FILE` 是 JSON：`{"PUB_KEY_ID_实际ID":"/受限路径/wxp_pub.pem"}`。支持多个已安装的轮换公钥，未知序列号拒绝，不从回调下载或信任公钥。
7. 记录 `launch-gates.example.json` 的商户、价格/条款、SMTP 前置证据。若做真实验收，配置 `PAYMENT_VERIFICATION_ENABLED=true`、指定的非管理员买家邮箱和 `PAYMENT_VERIFICATION_PRICE_FEN`，商品金额与之相等，条款版本不能为 `unconfirmed`。公众仍不可购买；仅白名单账号获得明确提示“实际扣款”的购买入口。
8. 在已安排的商户验收环境完成桌面 Native、普通手机 H5、回调与查单、退款及次日对账。微信内 H5 不受支持，实际验证外部浏览器引导。保存渠道交易号、退款号、设备、日期和验收人，不保存密钥到报告。
9. 补齐正式条款文件 `TERMS_FILE`、负责人联系方式和其余证据；商品取消 `test_product`，设置正式价格与条款版本，关闭验收开关，配置 `COMMERCE_LIVE_READY=true`。执行 `check_launch`，完整 G0–G4 通过后才设置 `SALES_ENABLED=true`。

生产启动拒绝 fake、占位密钥、缺少邮件/管理员来源、无证据开放销售及未审核条款。`check --deploy --fail-level WARNING` 阻断其他安全警告；仅对 HSTS 全子域和 preload 两项建议作明确例外，因为此应用没有整个域名所有子域的控制权，也不自动申请长期 preload 承诺。

## 运维、备份、回退

`ops/commerce/` 提供 Web 服务、支付补偿、每日账单、每 15 分钟监控、每日备份和 OnFailure 告警单元。部署前创建服务用户、备份目录、运行目录并安装 PostgreSQL 客户端和 flock，核实所有单元路径。定时任务独立持有持久运行目录，Web 进程停止时仍可查单补偿。`OPERATOR_EMAIL` 配置后实际验证告警送达，发信异常时仍需外部服务监控或人工后台检查。

备份为 pg_dump 自定义格式与私有内容的同一 AES-GCM 加密包，密钥为独立 32 字节随机文件（0600），密钥须另存安全备份。单机定时任务仅在当前服务器生成加密包；仍需由运维将其同步到独立备份位置并约定留存策略，不能将本机单份文件称为灾难恢复完成。

```bash
# DATABASE_URL 从受限环境读取，生产 PostgreSQL 客户端必须已安装。
.venv-commerce/bin/python ops/commerce/backup.py backup \
  --directory commerce-backups --key-file /受限路径/backup.key --content-root private-content
# RESTORE_DATABASE_URL 指向明确新建的空数据库；不能覆盖已有业务表。
.venv-commerce/bin/python ops/commerce/backup.py restore \
  --file /备份路径/backup.tjcb --key-file /受限路径/backup.key \
  --content-root /新建的空内容目录 --confirm-database 新库名称
```

恢复验证所有校验值并失效会话。切流前保持销售关闭，查渠道补齐备份时点之后的支付和退款，核对权益；不要把旧库快照覆盖真实新增交易。公布价格变更、数据删除和灾难恢复需要依据实际业务记录处理。

停售只改 `SALES_ENABLED=false`，保留原渠道与密钥以继续回调、查单、退款和已购交付。回退到兼容后端与 `private-content/safe-preview/` 的已扫描试读版本；不恢复迁移前公开全文，不回退有新交易的数据库。配置变更需要重启服务；静态资源按现有发布方式更新版本并定向清理旧全文/CDN缓存。
