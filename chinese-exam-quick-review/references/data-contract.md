# 数据契约

UTF-8 JSON。`items` 每行对应一个填空、选择或解答小问。`score` 是分值，`stars` 是整数星级，不是分值；未知均用 null。

以下为格式示意，并非真实试卷或已核对的知识树定位。

```json
{
  "title": "试卷原题名",
  "identity": "地区及考试称谓；注明归属证据",
  "total_score": 150,
  "duration_minutes": 120,
  "summary": "整体判断及关键题号",
  "highlights": ["具体亮点"],
  "teaching": ["按题号给出的讲评建议"],
  "limits": ["结构预估，无学生实测数据"],
  "sources": ["原卷相对于交付目录的路径", "转录稿相对于交付目录的路径"],
  "items": [
    {
      "id": "1",
      "type": "选择",
      "module": "示例模块",
      "topic": "示例考点",
      "score": 4,
      "stars": 1,
      "reason": "依据原题填写难度理由",
      "method": "依据原题填写方法",
      "pitfall": "依据原题填写易错点",
      "answer": "按原卷核验后填写",
      "verification": "关键步骤已核",
      "tree": [{"sheet": "实际图谱文件名", "cell": "实际行号", "label": "示例考点", "match": "直接对应"}]
    }
  ]
}
```

无知识树时 `tree: []`。未知总分、时长用 null。`sources` 仅列实际读过的资料，`limits` 记录OCR疑点、答案来源与复核范围。不得将评分依据写成“按标准”“综合判定”等没有题目证据的文字。


## 对外内容字段

出版脚本使用 `public_review`；字段及限制见 [publication.md](publication.md)。图谱为 Markdown 时，`tree.sheet` 填实际文件名，`tree.cell` 填行号或定位标记，`label` 填节点原文，`match` 标直接或邻近。公开资料不展示本机路径。
