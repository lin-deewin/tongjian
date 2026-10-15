# deewins.top 邮箱配置

邮箱：`linqp@deewins.top`。邮箱认证库保存 Argon2id 密码哈希，网站 SMTP 客户端所需凭据保存于受限且被 Git 忽略的 `backend/.env`；源码、本文及报告不保存明文密码或哈希。此邮箱密码与通鉴网站读者账号密码各自独立。

## 当前状态（2026-10-15）

已在 `ssh root@deewins` 的 Debian 13 主机安装并配置 Postfix 3.10、Dovecot 2.4、OpenDKIM。虚拟邮箱文件保存在 `/var/vmail/deewins.top/linqp/Maildir`；不开放系统账户或 root 的邮箱密码登录。邮箱容量 1 GiB，单封 SMTP 邮件上限 25 MiB。

**已完成公网开通**：Cloudflare 的 A、MX、SPF、DKIM、DMARC 五条记录已核验，DKIM 公钥与服务器私钥匹配。`mail.deewins.top` 的 Let’s Encrypt 证书已签发，有效期至 2027-01-13；25、465、587、993 已开放。`mail-certificate.timer` 已启用，实际通过 systemd 执行成功，后续每 6 小时同步 Caddy 自动续期证书。仓库模板仍使用回环监听作为安装初始状态，已激活的服务器配置使用 IPv4 公网监听。

已实际验证：

- 从服务器外的工作站验证 587 STARTTLS 登录、465 TLS 登录、993 TLS 登录，严格校验证书链及域名；587 未加密时不提供 AUTH。
- 从公网通过 SMTP 给同一邮箱发送测试邮件，并通过公网 IMAP 读取该测试邮件；DKIM 签名存在。
- 从公网连接 25 端口并验证 STARTTLS：向外部地址未认证转发返回 554，未知本域收件人返回 550，已知邮箱返回 250；中继验证没有提交邮件正文。
- Postfix、Dovecot、OpenDKIM 配置校验通过，原 Caddy 服务仍运行。
- Fail2ban 已启用两个邮件登录防护 jail；SMTP 日志 0600 权限、每周轮转保留 8 份。

已向负责人指定的 QQ 邮箱发送一封网站注册验证码邮件，QQ 的 `mx3.qq.com` 于 2026-10-15 02:58:52 UTC 返回 `250 OK`，服务器队列已清空。该请求没有创建读者账号。用户反馈未在 QQ 邮箱看到该邮件，最终入箱问题尚未解决；不能以 `250 OK` 视为已进入收件箱。QQ 发来的邮件于 03:08:32 UTC 保存至本邮箱 INBOX，DKIM 校验通过，用户随后确认可以收到 QQ 来信。

IP 反向解析仍是服务商默认值；负责人需在 VPS 控制台将 `104.129.181.27` 的 PTR 设置为 `mail.deewins.top`。IPv6 为隧道地址，本次邮件服务使用 IPv4，DNS 不要求新增邮件 AAAA 记录。

## DNS

精确记录保存在 [dns-records.json](../ops/mail/dns-records.json)，包含公开 DKIM 公钥。`mail` 的 A 记录指向 `104.129.181.27` 且必须为 DNS only（灰云）；MX 优先级 10。现有网站域名的 A/AAAA 和代理状态无需改动。

```bash
python ops/mail/check_dns.py
```

该命令检查五条公共记录和 PTR；退出码 2 表示 DNS 记录仍未全部匹配，不进行任何修改。DMARC 初期采用 `p=none` 收集报告；实际外部投递检查通过后再决定是否提高策略。

## 部署和恢复时的激活步骤

服务器上的配置副本和安装前备份分别在 `/root/mail-setup/config/` 与 `/root/mail-setup/backup/`。本次已完成以下步骤；恢复或重新部署时仅在 DNS 检查通过后执行。

1. 将 `ops/mail/mail.caddyfile` 安装到 `/etc/caddy/mail.caddyfile`。主 Caddyfile 已有 `import /etc/caddy/*.caddyfile`。先 `caddy validate --config /etc/caddy/Caddyfile`，成功后 reload；保留原网站和 DERP 配置。
2. 等待 Caddy 取得邮件域名证书，运行 `/usr/local/sbin/deewins-mail-sync-certificate`。脚本验证证书链、主机名、有效期和私钥匹配，再原子切换 `/etc/mail/tls` 并重载服务；不能用自签名证书或关闭客户端验证代替。
3. 用 `opendkim-testkey -d deewins.top -s mail202610 -k /etc/opendkim/keys/deewins.top/mail202610.private -vvv` 校验公钥与私钥。
4. 在 `/etc/postfix/main.cf` 将 `inet_interfaces` 改为 `all`；在 `/etc/dovecot/dovecot.conf` 将 `listen` 改为 `*`（IPv4）。校验后重启 Postfix 与 Dovecot。
5. 用 UFW 开放 TCP 25、465、587、993，保留现有 SSH、Web 及其他服务规则。无需开放明文 IMAP 143 或 POP3。
6. 运行 `systemctl enable --now mail-certificate.timer`，每 6 小时检查 Caddy 续期证书。
7. 从服务器外部运行下方检查，交互输入邮箱密码；确认公网证书、SMTP 和 IMAP 可用，并再次核对未认证中继拒绝。

```bash
python ops/mail/check_mail.py
```

校验脚本保留一封明确标记的自测邮件，不读取或删除其他邮件。跨服务商投递仅向负责人明确指定并允许测试的地址发送，不能使用任意第三方地址。

## 开通后的客户端参数

| 项目 | 配置 |
|---|---|
| 用户名 | `linqp@deewins.top`（完整地址） |
| IMAP | `mail.deewins.top`，993，SSL/TLS |
| SMTP | `mail.deewins.top`，465，SSL/TLS；或 587，STARTTLS |
| SMTP 身份验证 | 必须，使用同一完整邮箱和密码 |

此部署提供邮件协议服务，没有安装网页邮箱。Thunderbird、Foxmail 等邮件客户端可以使用上述配置。

网站本地发信已接通此 SMTP 服务：`backend/.env` 为 0600，Git 已忽略该文件，使用 587 STARTTLS 与 `linqp@deewins.top` 认证发信。邮件密码只在受限运行配置中保存明文，不出现在源码、文档或报告中。

使用唯一的 `linqp+tj-check-…@deewins.top` 临时测试地址，实际完成网站发送注册邮件 → IMAP 读取验证码 → 验证后注册 → 退出 → 密码登录 → 真实找回密码邮件 → 重设密码 → 新密码登录。HTTP 表单执行 CSRF 检查，临时账号及其邮箱挑战已清理；测试邮件保留在邮箱。此项为真实 SMTP 与数据库的 HTTP 处理流程验收，不称为浏览器视觉检查。

本地完整入口为 `http://100.108.212.5:3003/tongjian/`，注册页为 `/tongjian/account/register/`，密码登录页为 `/tongjian/account/login/`，找回密码邮件也使用该地址。本机 Caddy 代理到回环后台 18010，二者由用户 systemd 服务管理，配置与日志方式见 [本机入口说明](../ops/local/README.md)。当前关闭购买并禁用支付渠道。

本次没有发布网站动态后台：公网 `https://deewins.top/tongjian/` 仍提供已有静态网站，已检查 HTTP 200。网站在线注册还需要按账号后端的生产部署流程另行发布。

本地账号页、改密、原生退出与阅读返回路径的后续集成、验证及限制，见 [账号集成记录](account-integration.md)。

## 维护

密码哈希文件 `/etc/dovecot/mail-users` 为 root:dovecot 0640；DKIM 私钥仅 opendkim 可读；证书私钥为 root 0600。不能把这些文件、邮箱内容或 `/root/mail-setup` 整体上传到网站静态目录。邮件、认证库和 DKIM 私钥需要纳入负责人自己的受限异机备份；当前没有声称已经建立异机邮件备份。
