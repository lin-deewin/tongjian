# 上传译本专项补漏

用户范围：只恢复上传译本中的白话，不使用生成译文。

`recover.py` 在完整294卷基础数据中，先复查原来落入“版本差异”的组，再从上传 EPUB 找原文和白话的相邻段落。匹配只对去除胡注、标点的比较副本进行，不修改原文；相似度至少0.90，排除重复覆盖与明显古文。原文相似度不能证明相邻文字一定是译文，混合章节必须另外检查。

第28卷只允许明确复核的13对上传原文白话。章节29的第2、4、6、8、10、12、14、72、74、76、78、80、82个 `<p>`（从0计）及后一个段落分别构成原文和白话，其余不依据奇偶位置猜配。第113、200卷不恢复白话。第164卷552年59段和第171卷574年25段的相邻文字属于下一条记事，明确排除。

23处原有差异组的译文字段粘连了下一条古文及后续白话，只提取该组的第一段白话；原完整字段及指纹保留，用于准确删除原差异展示。第96卷338年39段的换行发生在“太守”二字间，保留此换行，不作边界拆分。

## 缺译原因与本次结果

- 原计2012段，恢复285段，剩1727段。恢复构成：139段既有版本差异、133段上传原文白话对、13段第28卷混合章节。
- 第189、214—218、223卷上传译本章节重复或错置，无法从当前上传文件补出缺失整卷；连同仅古文的113、200卷，9卷共1001段仍无白话。
- 第28卷66段中13段有白话，余53段未见可靠对应白话；并非整卷只有古文。
- 第31卷上传章节在刘向论陵墓的奏疏后截断，留下35段缺译。
- 其余638段涉及短残句、原文排版或注释边界、译本遗漏及不够可靠的对齐。不能把有疑点的相邻文字算成译文。
- 原书部分年头解析和译本年界不一致。恢复对照不移动原文，阅读页显示译本记年差异，保留原锚点。

## 构建

在项目根目录运行：

```sh
python scripts/translations/recover.py
python scripts/build_translation_supplements.py
python scripts/check_translation_supplements.py
python scripts/validate_full_book.py --original sources/hu-sansheng.epub
node scripts/check_reader.cjs
python scripts/check_translations_browser.py
```

恢复候选与未解决清单位于 `artifacts/translations/recovery-proposals.json`。发布的补充文件在 `dist/translation-supplements/`，只包含上传译文和来源绑定。覆盖率与主页由构建脚本同步更新，搜索索引从同一批对照组产生。基础294卷字节不改变。每卷绑定基础文件 SHA256，基础重建后必须重新生成补充文件。

AI草稿仅存本地 `artifacts/translations/unpublished-ai-drafts.json`，不读取、不发布、不计入覆盖率。历史基础审计文件仍描述补漏前数据；最新可读覆盖见 `dist/coverage.json` 和 `dist/translation-supplement-report.json`。
