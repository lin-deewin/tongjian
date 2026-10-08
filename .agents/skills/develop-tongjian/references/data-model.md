# 数据结构

根对象：`volume`, `title`, `source`, `intro`, `years`, `translationSource`。

每个年份：

| 字段 | 含义 |
|---|---|
| year | 正整数表示公元前年份；本卷403逐步减至369 |
| king / reign | 周王名及在位年数 |
| heading / headingRuns | 原文件年头；没有年头时为空 |
| paragraphs | 按胡注本源顺序排列的正文段落 |
| after | 下一年头前衔接的王名原文 |
| recorded | 本卷是否单列记事 |
| titles / anchors | 现代索引标题及对应正文段落下标 |
| search | 原文搜索内容 |
| noteCount | 注释段计数 |
| warning | 原文件年头差异提示 |
| sourceWarning / translationWarning | 原文注释异常及译本文字差异提示（可选） |
| contextNote | 原书附叙或后续经历的时间归属提示（可选） |
| translationHeaders | 译本原文/白话年头 |
| bilingual | 原文白话匹配组，保留译本顺序 |
| translationMissing | 胡注本尚未匹配的段落下标 |

`paragraphs[i] = {runs, plain}`；每个 run 为 `{kind: 'text'|'note', text}`。
按 run 顺序连接得到源段落原文；只连接 text 得到 plain。注释保留〔〕。
不得为了美观或配对修改储存的原文。

`bilingual` 中每组：
`{huIndices, sourceOriginal, modern, score, kind, difference}`。

- huIndices：对应胡注本正文的一组下标，不同匹配组不得重复覆盖。
- sourceOriginal：译本所附古文，用于匹配和检查来源。
- modern：上传译本的白话文本。
- score：标准化古文匹配分数，用于提示校对，不等于历史正确性。
- kind：record 或 commentary。
- difference：译本有段落而胡注本未对应，单列在差异区域。

界面正常对照行按 huIndices 的第一个下标排序，保留胡注本正文次序。
不要按源译本段落顺序直接与胡注本一一拉链配对。

跨卷及公元后的 schema 应在扩展时明确设计，推荐使用稳定卷号+段落ID、
有符号公历年、来源定位和人工校对状态。不要直接把本卷的正整数BC约定
推广成整个通史的时间格式；公历没有公元0年。
