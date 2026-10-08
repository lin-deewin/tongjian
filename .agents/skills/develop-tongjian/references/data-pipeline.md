# 数据提取与对齐

## 第一卷现有工具

依赖 Python 3 和 `lxml`。运行前查看 --help，向临时输出执行，验证通过后
再更新当前项目数据。不要直接覆盖正在开发的文件。

```bash
python SKILL/scripts/extract_volume1.py --epub HU_EPUB --output TEMP_JSON
python SKILL/scripts/align_volume1.py --epub TRANSLATION_EPUB --data TEMP_JSON
python SKILL/scripts/validate_volume.py --data TEMP_JSON
```

脚本仅适用于本次上传版的第一卷，内置第一卷年份和现代事件标题。
新增卷前必须先读取对应 EPUB 的 toc.ncx、manifest/spine 和正文结构，
参数化卷界、年号换算、事件标题与锚点；不能单改文件名后宣称支持所有卷。

## 第二卷现有工具

第二卷专用脚本：`scripts/extract_volume2.py` 与 `scripts/align_volume2.py`。
胡注本正文为 `OEBPS/text00004.html`，译本为 `OPS/chapter2.htm`；年表覆盖
前368年至前321年。输出到临时 JSON，检查后才复制到 `dist/volume2.json`：

```bash
python .agents/skills/develop-tongjian/scripts/extract_volume2.py --epub HU_EPUB --output /tmp/volume2.json
python .agents/skills/develop-tongjian/scripts/align_volume2.py --epub TRANSLATION_EPUB --data /tmp/volume2.json
python .agents/skills/develop-tongjian/scripts/validate_volume.py --data /tmp/volume2.json
```

第二卷保留40个有记事年份与8个空白年份，译本111组内容全部对应胡注本段落。
存在一处源注释缺少右括号：按源字样保留并作为注释展示，不补写括号。
事件标题与原文锚点维护于 `scripts/volume2-index.json`，按原文核对，不截断译文充当标题。
第二卷脚本仍针对已检查的上传版结构，不代表可处理其他卷。

## 原文保留

按年头和周王转换切分。保留连续35年，包括没有年头的5个年份。
保留卷首注、王名注、年头、正文与后续衔接文字，逐段重建和源文本比较。
年表按年号换算；不要静默改写异常原文。

已知异常：

- 周烈王五年在胡注本误写“己酉、前三七二”，年表定位前371，正文保留字样。
- 智氏继承叙述和日食注出现多余〔字符；解析时限定识别两处异常，
  保留所有字符，不能把后面正文吞入注释。扩展卷时不要无条件套用此修补。
- 重复标点、缺字与校勘标识不自动改写。

## 译本对齐

所上传译本的第一卷原文/白话交替排列，但数处被 `*` 排版分隔符粘在一起。
先分离这些排版边界，再按古文与白话组成配对；逐年验证偶数段落数。
按同年古文内容匹配胡注本，允许一个白话段对应1至3个连续古文段。
标准化仅用于匹配，绝不回写覆盖源文本。

当前使用去标点后 SequenceMatcher，最低阈值0.65；实际匹配最低0.933。
它是第一卷辅助匹配工具，新增卷必须检查不确定匹配、遗漏、重复与合并。
低置信度留作人工检查，不得错配来凑齐数量。

## 已知版本差异

前385年的“齐伐鲁”，以及前379年的“齐桓公亦薨，子威王因齐立”，
出现于上传译本而未出现在上传胡注本本年正文中。
在独立差异区域显示其所附古文及白话，不伪装成胡注本原文。

## 验证重点

1. 逐年范围完整、记事年份与源年头一致。
2. 原文 runs 逐字重建；源段落顺序与未删减检查。
3. 译本年头和配对文本除明确排版边界外可重建。
4. 正文段落不重复覆盖，缺失项明确，事件锚点不越界。
5. 阅读前403年长篇追叙、前387年合并内容、前371年年头异常、空白年份。
6. 不把司马光/太史公评论叫作柏杨评论。
