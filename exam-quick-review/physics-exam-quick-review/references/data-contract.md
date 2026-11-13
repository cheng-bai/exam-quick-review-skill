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
      "module": "力学",
      "topic": "匀加速直线运动",
      "score": 4,
      "stars": 1,
      "reason": "根据速度时间关系直接代入",
      "method": "匀加速直线运动速度公式",
      "pitfall": "统一正方向和单位",
      "answer": "按原卷核验后填写",
      "verification": "关键步骤已核",
      "tree": [{"sheet": "专题树", "cell": "B4", "label": "匀加速直线运动", "match": "直接对应"}]
    }
  ]
}
```

无知识树时 `tree: []`。未知总分、时长用 null。`sources` 仅列实际读过的资料，`limits` 记录OCR疑点、答案来源与复核范围。不得将评分依据写成“按标准”“综合判定”等没有题目证据的文字。


## 多维与分层字段

`public_review` 的六维分析要求与三档 `teaching_routes` 数据结构见 [analysis-dimensions.md](analysis-dimensions.md)。`learner_level` 留空时保留三档供教师选择；指定档仅改变讲评顺序，不改变星级与统计。待核项不可纳入讲评练习与复测题号。
