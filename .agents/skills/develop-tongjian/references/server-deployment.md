# 通鉴服务器发布

## 已确认的部署（2026-10-09）

- 本地项目：`/home/linqp/projs/tongjian`。
- SSH：`ssh -6 root@ssh.deewins.top`。
- 服务器项目目录：`/root/projs/tongjian`。
- 静态网站目录：`/root/projs/tongjian/dist`。
- 访问地址：`https://deewins.top/tongjian/`。
- `/tongjian` 通过 HTTP 308 跳转到 `/tongjian/`，相对资源路径依赖这个末尾斜杠。
- 由 systemd 的 `caddy.service` 提供静态文件服务，无独立通鉴后台进程，也无需前端构建。
- Caddy 配置：`/etc/caddy/Caddyfile`；另通过 `import /etc/caddy/*.caddyfile` 加载已有 DERP 配置。
- 首次部署已备份配置到 `/etc/caddy/Caddyfile.before-tongjian-20261009-010241`。

## 常规增量发布

用户要求发布时，同步当前工作区的 `dist/`，包括尚未提交但属于本次版本的文件。
源 EPUB、Git、原 Sites 的 `.openai/hosting.json` 不属于静态发布内容。

```bash
cd /home/linqp/projs/tongjian
rsync -az --chmod=D755,F644 \
  -e 'ssh -6' \
  dist/ root@ssh.deewins.top:/root/projs/tongjian/dist/
```

末尾 `/` 表示同步目录内容。默认不使用 `--delete`；若确实需要移除已撤回的线上文件，
先确认具体文件，再做定向清理。普通静态文件更新立即生效，无需重启或重载 Caddy。

`/root` 默认不可由 caddy 用户进入。首次部署安装了 `acl`，并设置了父目录穿越权限
和既有 dist 文件的读取权限。上传新文件后补齐 ACL，避免新文件权限或 rsync 替换
造成 HTTP 403；只授予父目录穿越权限，网站目录授予读取权限：

```bash
ssh -6 root@ssh.deewins.top \
  'setfacl -m u:caddy:--x /root /root/projs /root/projs/tongjian && setfacl -R -m u:caddy:r-X /root/projs/tongjian/dist'
```

服务器登录 shell 是 fish。需要 heredoc 或复杂脚本时用 `ssh -6 ... bash -s`，
把脚本从标准输入传入；不要直接把 Bash heredoc 当作远端默认 shell 命令。

## Caddy 路由与维护

主域名静态路由结构如下。2026-10-09 已额外添加访问日志、路径过滤及 Cloudflare
可信代理全局配置，维护时读取实际文件并保留这些设置：

```caddyfile
deewins.top {
    redir /tongjian /tongjian/ 308
    handle_path /tongjian/* {
        root * /root/projs/tongjian/dist
        encode zstd gzip
        file_server
    }
    handle {
        respond "Hello from Caddy"
    }
}
import /etc/caddy/*.caddyfile
```

只有修改路由或 Caddy 设置时才编辑配置。先读取服务器当前配置、保存备份，
保留其他站点和 DERP 服务；上面的配置用于说明已部署结构，不覆盖后续配置。
修改后校验成功再重载：

```bash
ssh -6 root@ssh.deewins.top \
  'caddy validate --config /etc/caddy/Caddyfile && systemctl reload caddy'
ssh -6 root@ssh.deewins.top 'systemctl status caddy --no-pager'
```

## 发布确认

确认 rsync 成功后，检查公网首页、重定向、本次更新的脚本及数据资源：

```bash
curl -6 -fsSI https://deewins.top/tongjian
curl -6 -fsS https://deewins.top/tongjian/ -o /tmp/tongjian-deployed-index.html
curl -6 -fsSI https://deewins.top/tongjian/catalog.json
```

需要确认内容时下载本次变更文件并与本地比较。首页成功不代表全部数据都可读取。
浏览器检查时关注卷加载、搜索、人物数据等本次发布涉及的功能。
公开域名前有 Cloudflare；首次部署时 urllib 请求返回过 403，而 curl 请求正常，
遇到 403 时先区分 Cloudflare 响应和源站文件权限问题。
若浏览器缓存旧脚本，强制刷新；需要让所有访客及时获取新脚本时更新 index.html
已有的脚本查询版本号。发布失败时报告实际失败步骤，不宣称发布完成。

## 访问日志与每日统计

2026-10-09 北京时间约 17:07 起启用；之前的访问无法追溯，启用当日数据不完整。
仅记录 `/tongjian` 和 `/tongjian/*`，JSON 日志在 `/var/log/caddy/tongjian.log`。
文件权限 0600，归 caddy 所有；每 50 MiB 轮转，最多 100 个归档、最长保留 90 天。
校验新日志配置时 root 可能提前创建文件，重载前确认归属，否则 Caddy 无法写入。

Caddy 全局 `trusted_proxies` 使用 Cloudflare 官方 IPv4/IPv6 网段，
`client_ip_headers CF-Connecting-IP` 和 `trusted_proxies_strict`，报告读取 `request.client_ip`。
不要无条件相信客户端自报的 IP 头；Cloudflare 更新网段时维护可信列表。

统计脚本：`scripts/ops/tongjian_stats.py`（本地与服务器项目内均有副本）。
systemd `tongjian-stats.timer` 每天北京时间 00:10 调用 `tongjian-stats.service`，
生成前一天报告；设置 `Persistent=true`，停机错过的任务在恢复后触发。
长时间停机后需要用 `--date YYYY-MM-DD` 手动补算其他日期。
报告位于 `/root/projs/tongjian/reports/traffic/YYYY-MM-DD.json`，仅 root 读取，不放进 dist。

```bash
# 在本地查看今天截至目前的汇总，并更新今天的报告
ssh -6 root@ssh.deewins.top \
  'python3 /root/projs/tongjian/scripts/ops/tongjian_stats.py --date today'
# 手动生成昨日报告
ssh -6 root@ssh.deewins.top 'systemctl start tongjian-stats.service'
# 查看自动统计任务
ssh -6 root@ssh.deewins.top 'systemctl list-timers tongjian-stats.timer --no-pager'
# 查看指定日期完整报告，包括访问 IP 与浏览器信息
ssh -6 root@ssh.deewins.top \
  'cat /root/projs/tongjian/reports/traffic/2026-10-09.json'
```

统计口径：
- `requests`：到达 Caddy 的通鉴请求数，含脚本、数据、机器人和失败请求。
- `page_views`：GET 首页或 index.html 且状态为 200/304 的请求数。
- `unique_page_view_ips`：访问页面的独立 IP 数，不等同于独立人数。
- `average_qps_full_day`：总请求数 / 86400；`average_qps_elapsed` 是当日截至目前的平均值。
- `peak_qps_1s`：单个自然秒的最大请求数。
- `visitors`：各 IP 的请求数、页面访问数、首次/最后访问时间、User-Agent。

Cloudflare 缓存命中的请求不会到达 Caddy；站内 hash 年份切换也不会产生页面请求。
日志统计因此不是所有点击或真实访客人数，不能识别姓名，尚不能自动排除机器人。
历史零请求报告也可能意味着当时尚未启用日志，而非确实无人访问。
