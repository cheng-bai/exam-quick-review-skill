# 贡献指南

1. Fork 或在有权限时创建分支，说明使用场景及修改原因。
2. 修改 Skill 时保持 `SKILL.md` 入口简洁，将学科细则放入相应参考资料；仓库内部使用相对链接。
3. 执行 `python3 scripts/check_links.py`。修改 Typst 模板时运行 `typst compile exam-frontend-quick-review/assets/版式起点.typ /tmp/exam-review-template.pdf`，并目视检查结果。实际案例需核对题目、公式和来源。
4. 提交 Pull Request，写明修改内容、实际检查与尚未覆盖的部分。请勿提交密钥、学生数据、无权公开的试卷或素材。

跨 AI 协作时，以仓库文件和 Pull Request 记录为准；不同平台的个人记忆和本地路径不构成共享依据。

教师版模板变更时还需运行 `typst compile exam-frontend-quick-review/assets/教师版排版示例.typ /tmp/exam-teacher-template.pdf`，并以长段落、长公式和跨页题目试排、目视检查。
