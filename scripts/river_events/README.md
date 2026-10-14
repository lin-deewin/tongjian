# 河流事件核算

用户指定 10 个 `gpt-6-luna` 子代理，reasoning effort `low`，按连续卷号分工。
数据来源是当前 `dist/volume1.json` 至 `volume294.json` 的 `paragraphs[].plain`；
不改变原文、白话、年表或现有阅读路由。

## 口径

- 单位为**按年具体事件**。连续同一战场的攻守可以合为一个事件，独立地点或行动拆开。
- 跨年战事按年分别记录；同一事件的天灾、饥荒、战争多类别合为一个分色点。
- 自然灾害、社会饥荒和实际战争行动分开。军队断粮不自动算社会饥荒，杀使者和一般宫廷谋杀不自动算战争。
- 仅有计划、诏令、假设或史论不能证明实施。追叙无法确定发生年份时不计为当年事件。
- 明确“去年/去岁”的追叙可以归回前一年，保存 `dateBasis`；阅读链接仍去来源段所在年。
- `reviewed` 是模型实际读取原文后的语义复核，**不是人工史学终审**。`provisional` 候选不绘制为正式事件点。
- 关键词候选不保证召回全书所有事件；空白年份不表示该年没有天灾、饥荒或战争。

## 文件和重建

1. `python scripts/river_events/prepare.py` 生成10份宽召回候选，位于 `artifacts/river-audit/`。
2. 每个代理维护 `scripts/river_events/review-NN.json`。实际逐段语义核读过的段落登记在 `coverage.reviewedCandidateIds`；不能把脚本筛选数当作语义复核数。第2批同时单列全文核读段与仅看过摘录的段，汇总报告保留两种阅读口径。
3. `python scripts/build_river.py` 校验10批范围、来源、准确引文、审核ID与归年，汇总正式事件，保留待核计数。

生成文件：

- `dist/river-data.json`：主页的逐年事件数据和汇总说明。
- `dist/river-events.json`：正式事件及其全部出处。
- `dist/river-audit-report.json`：10批统计、复核方法、范围及局限。

精确重复引文合并为一个事件，类别取并集。语义相近但引文不同的重复需要模型审查；不能仅凭文字相似擅自合并不同事件。
前端不再每年截断20点，每个事件ID只绘一次，远景允许重叠。选择年份或点后可在简短事件选择框中定位，并读取对应原文。没有恢复文章节选。

## 饥荒专项补漏（2026-10-13）

新增 `prepare_famine.py` 独立扫描，不修改原十批候选及历史复核记录。
`famine-review.json` 保存本轮逐项收录、补证、同年归并、撤回饥荒分类和待核理由；
`famine_supplement.py` 在原始汇总后应用这些决定。294卷内容校验和变化时拒绝套用。
战争、天灾分类不会因为饥荒归并而消失。

当前饥荒190→247条，涉及202个年份：补收71条、合并9条重复分类、5条转待核。
814段关键词线索已查看摘录；201个不同原段全文核读，190条旧饥荒核对出处引文。
原十批覆盖数与本轮覆盖数分开，不声称对全书30584段通读，亦没有独立第二审。
`screenedOnly` 的448段仅完成摘录初筛，不能作全文排除；85段全文疑难项留队列。
原文“plain”偶有未剥离的胡注，不能仅凭其中出现饥荒字样定为本年事件。

正式条数按年统计实际社会缺食，包括战争造成的居民饥荒；同年同地灾情、价格和
赈济合并，跨年续灾按年分别记录，不等于独立饥荒过程总数。具体本年灾情可以采
奏疏证言；纯军队缺粮、假设、泛论，以及仅高粮价、卖子或普通赈济均不能自动入选。
年份不明、守军与居民范围不清者保留待核，不强行归年。

- 扫描：`python scripts/river_events/prepare_famine.py`
- 重建：`python scripts/build_river.py`
- 证据、归年、去重及原其他分类保留校验：`python scripts/check_famine_supplement.py`
- 阅读导航回归：`node scripts/check_reader.cjs`
- 变更报告：`scripts/river_events/famine-report.md`
- 完整审计：`dist/famine-audit-report.json`
- 原段复查队列：`artifacts/famine-supplement/scan.json`（可重新扫描生成）

`river-audit-report.json` 的原始825条待核经两条饥荒确证后为823条；这是原十批
事件待核数，本轮待核段落另列 `famineSupplement.decisionCounts`，两者单位不同。
