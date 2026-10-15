# 结构化源稿的保真校验

只有源稿包含 `pages: [{id, blocks: [...]}]` 时使用这个可选工具。普通PDF或其他JSON格式按技能正文人工记录与核对，不必为了使用脚本改造整个工作流。

## 输入

- `--source`：与用户认可PDF核对过的源JSON。
- `--article`：改编后的HTML或Markdown文件。
- `--policy`：每个源块的去向与修改记录。
- `--pdf`：可选；先核对源JSON的文字是否出现在对应PDF页。
- `--report`：可选；保存实际校验结果。

命令示例：

```bash
python scripts/verify_article.py --source source.json --article article.html --policy policy.json --pdf source.pdf --report verification.json
```

`policy.json` 使用以下结构。`page` 是源页ID，`block` 是该页块的零起始索引；每个源块都要列出，不能只列出成功保留的段落。

```json
{
  "blocks": [
    {"page": "scene", "block": 0, "action": "keep"},
    {"page": "scene", "block": 1, "action": "omit", "reason": "用户要求移除的答题指令"},
    {
      "page": "analysis", "block": 0, "action": "edit",
      "reason": "删掉问句后补足条件，余文不变",
      "expected_parts": ["即使条件不成立，同样的材料仍可能出现。"]
    }
  ]
}
```

这只是格式示例，不是一份可覆盖完整源稿的现成清单。`edit.expected_parts` 必须列出该块的完整改后文字，不仅是新增片段。列表、表格或图示有获准修改时，列齐改后标题、各项、标签与图注；未改的引用及链接仍会检查。

## 检查什么

- 去向是否覆盖所有源块，有无缺项、重复或无效索引。
- 保留块的段落、引文、图注、图示节点与边标签、表格各格文字是否实际存在。
- 已修改块是否实际包含登记的改后文字，修改与移除是否填写理由。
- 来源链接是否仍有可用对应；绝对站点链接改为同一文件与锚点的相对链接可以通过。

规范化仅移除空白和PDF提取的零宽连接符，不忽略措辞、标点或数值变化。HTML读取只取正文文本；脚本、样式和HTML注释不能冒充保留内容。

工具检查的是文字与覆盖。仍需逐项审查 `omit` 是否真的属于用户要求删除的形式、`edit` 是否最小必要；检查图示是否真实呈现、箭头方向及虚线语义是否一致。不要仅因一个标题或节点名出现在其他段落中，就声称图表完整保留。

脚本使用Python标准库；只有传入 `--pdf` 时才需要 `pypdf`。结果中出现错误时返回非零退出码，先修复再交付。
