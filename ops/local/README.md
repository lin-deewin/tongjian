# 本机 3003 入口

当前访问地址为 `http://100.108.212.5:3003/tongjian/`。注册、登录、找回密码和阅读共用该地址；`127.0.0.1:18010` 只作为本机账号后台。此配置没有部署到公网服务器。

`Caddyfile` 使用原有 IPv4 3003 监听范围，静态内容只从项目 `dist/` 提供，动态路径代理到回环地址 18010。原来 `/reader.html#…` 等根路径书签跳转至 `/tongjian/reader.html#…`，查询与浏览器 fragment 保留。代理覆盖 `X-Real-IP`，后台只信任回环代理，动态响应禁止缓存。

## 已安装的用户服务

```bash
systemctl --user status tongjian-atlas.service tongjian-accounts.service
systemctl --user restart tongjian-accounts.service tongjian-atlas.service
```

`tongjian-atlas.service` 原来是 Python 纯静态服务，现改为 Caddy。替换前的配置备份在 `/tmp/tongjian-accounts/tongjian-atlas.before-account-proxy.service`。账号后端现在由用户 systemd 管理，不能再另开同端口的 `runserver`，也不再依赖临时 PID 文件。

首次重新安装本机服务时，在项目根执行：

```bash
mkdir -p ~/.config/systemd/user
cp ops/local/tongjian-atlas.service ops/local/tongjian-accounts.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tongjian-accounts.service
systemctl --user enable --now tongjian-atlas.service
```

服务文件按当前项目绝对路径配置。Caddy 二进制是已有的 `tmp/commerce-tools/caddy`，Python 环境是 `.venv-commerce`；首次准备依赖和 PostgreSQL 见 [后端手册](../../backend/README.md)。PostgreSQL 容器必须处于运行状态，服务文件不负责新建或删除数据库。

本机受限 `backend/.env` 已设置 `SITE_URL=http://100.108.212.5:3003`、相应允许的 Host/Origin 和回环代理网段，真实 SMTP 凭据不写入本目录。找回密码链接使用该地址，其他设备不会再收到指向它们自己 127.0.0.1 的链接。

日志通过 `journalctl --user -u tongjian-atlas.service -u tongjian-accounts.service` 查看。重启前可执行：

```bash
tmp/commerce-tools/caddy validate --config ops/local/Caddyfile --adapter caddyfile
systemd-analyze --user verify ops/local/tongjian-atlas.service ops/local/tongjian-accounts.service
```
