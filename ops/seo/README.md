# SEO 发布与维护

主站已迁移到域名根 `https://deewins.top/`。当前生产静态文件仍由
`/root/projs/tongjian/dist` 提供；旧 `/tongjian` 地址按路径永久跳转。

根 `/robots.txt` 直接返回 `dist/robots.txt`，根 `/sitemap.xml` 直接返回当前
`dist/sitemap.xml` 的 URL 集合；地图现有1741条规范地址。`/sitemap-index.xml` 保留为兼容入口，
指向根 sitemap。robots 响应设置 `Cache-Control: no-store, no-cache, must-revalidate`。
2026-10-16 Cloudflare 旧缓存已清除，普通根 robots 已复验为新内容。

当前生成规模为294个卷页、70个人物页、1362个逐年页、3个目录和2篇史事细读，
合计1732个生成页面；加9个既有公共入口后共1741个 sitemap URL。

## 重建与验收

```sh
python scripts/build_seo.py
python scripts/check_seo.py
python scripts/check_seo_browser.py
python scripts/check_year_pages_browser.py
node scripts/check_reader.cjs
```

人物页生成依赖 `scripts/people/semantic-reviews.json` 与当前人物档案；语义复核的来源绑定过期时，
生成器会停止。逐年页保留同年跨卷来源顺序和卷段锚点。全书原始文本仍以 `sources/`
中的 EPUB 为输入；重建数据前还须按项目现状安装 Python 依赖。

用户明确要求发布时，读取 [服务器发布流程](../../.agents/skills/develop-tongjian/references/server-deployment.md)
及[根域名迁移记录](../../docs/root-domain-migration.md)。先核对工作区范围和实际生产 Caddy 配置，
保留账号动态路由、旧路径兼容、Cloudflare 可信代理及其他站点。常规静态更新同步 `dist/`，
补齐 Caddy ACL，再抽查根 robots、地图、页面状态、资源 SHA-256 和桌面／手机浏览器。
Git 提交／推送与服务器发布分开执行。

没有提交 Google Search Console 或百度站长平台。后续应由实际账号验证站点并提交
`https://deewins.top/sitemap.xml`；提交不等于收录，不据此宣称排名或流量增长。
