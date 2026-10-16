# 根域名搜索观测与平台接入

当前主站为 https://deewins.top/，地图为 https://deewins.top/sitemap.xml。
2026-10-16用户手动清除Cloudflare缓存后，普通根robots公网复查已正确，返回BYPASS。

## 已具备的观测

`python scripts/ops/seo_snapshot.py --full` 抓取地图中所有公共页面，记录状态、canonical、H1、
noindex、地图及旧地址跳转；默认不带 `--full` 只查代表页，适合小时观测。
报告存入 `reports/seo-observation/`，不放进dist。每份包含UTC检查时间、robots缓存状态和边缘节点信息。
线上小时任务由 `ops/seo/tongjian-seo.service` 与 `.timer` 提供；实际启用状态见本轮发布记录。
这测量公网HTTP响应，不能证明Google或百度已抓取、收录或给予排名。

## Google Search Console

1. 在 https://search.google.com/search-console/ 登录自己的账号。
2. 若已有 `deewins.top` 域名资源，沿用该资源；若没有，可添加网址前缀资源 `https://deewins.top/`。
3. 按平台给出的实际验证方式操作。HTML标签验证需要平台提供的真实token；DNS验证需要真实TXT记录。
   不要新建占位token，也不用把账号密码发给开发者。仅有Cloudflare登录不代表已有Search Console资源。
4. 验证后进入“站点地图”，提交 `https://deewins.top/sitemap.xml`。
5. 用网址检查检查主页、卷1、萧何页和两篇史事文章；记录抓取状态及搜索引擎所选规范地址。
6. 在“搜索结果／效果”中导出CSV。按日期、页面、查询词分别保存导出，保留平台选择的日期范围。

此次为同域路径迁移，保持旧308跳转与新canonical；不要反复改URL。
提交地图、请求编入索引不等于已经收录。

## 百度搜索资源平台

在 https://ziyuan.baidu.com/ 依当前账号实际提供的站点添加、验证和链接提交能力操作。
站点使用根域名；平台要求的验证文件／标签只采用真实提供的内容。
是否有地图提交入口以当前账号界面为准，不预设所有账号拥有相同权限。
取得点击、展现等搜索数据时保留导出文件与日期范围；不得把访问日志代作这些数据。

## 导入实际平台CSV

```bash
python scripts/ops/import_search_performance.py --platform gsc \
  --input /path/to/export.csv --output reports/seo-observation/gsc-export.json
```

百度使用 `--platform baidu`。工具识别常见中英文列名，必须有点击与展现／曝光列。
保留原导出SHA-256、导入时间、日期／页面／查询维度和每行数据。
汇总只代表导出的行：搜索平台可能隐藏匿名查询或截断行数，不能自动称作全站总数。
此脚本不登录平台、不提交地图，也不凭导入动作授予站点验证状态。

## 每周记录与判断

| 情况 | 核查与动作 |
| --- | --- |
| 新URL未发现 | 检查目录普通链接、地图和访问限制 |
| 已抓取未收录 | 看内容覆盖、重复与规范地址选择，不机械凑字数 |
| 有曝光少点击 | 按真实查询词检查标题和首屏是否准确回应需求 |
| 点击后少继续阅读 | 看人物、史事和原文之间的路径，不能仅看资源请求量 |
| 人物内容待核 | 完成原文及上下文核读，再进入独立人物页 |

分别记录发现、抓取、收录、曝光和点击；无平台数据时保留unknown/null，不能写0。
源站日志含机器人与资源请求，Cloudflare命中和fragment切换也可能不进入日志，因此不等同于真实读者人数。

小时任务请求带 `TongjianSEOCheck/` 标识；源站流量统计将其单列并从访客与页面访问数剔除，避免把自检当成流量增长。其他未知机器人仍可能混在日志中。
