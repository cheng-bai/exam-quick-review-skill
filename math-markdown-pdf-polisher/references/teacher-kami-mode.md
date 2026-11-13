# 低饱和教师讲义模式

当中文数学教师版 Markdown 使用 `【答案】`、`【解析】`、`【解答】`、`【要点注释】`、`【知识补充】` 或 `【知识拓展】`，并需要彩色但克制的 A4 PDF 时读取本文件。

## 稳定约定

- 章节标题：藏青 `#2F5563`。
- 答案：鼠尾草绿标题条 `#6F8F7A`，浅绿底 `#EDF5EF`。
- 解析：雾蓝标题条 `#5D7F8C`，浅蓝底 `#ECF3F6`。
- 要点/补充/拓展：杏橙标题条 `#B88352`，暖米底 `#F8F0E7`。
- 标题条文字必须为白色；不使用高饱和青色、渐变、阴影或大面积纯色背景。
- 一个解析框必须包含同一道题的全部段落、方法二/方法三和对应小步骤；不能只包第一段。
- 长解析允许 `tcolorbox` 自然跨页，不把“题目 + 长解析”整体设为不可分页。
- 题目与上一道题解析框之间保留约 9pt 节奏。
- 普通插图默认居中，宽度 `0.58\linewidth`，清空 alt，不显示图片文件名；只有整页扫描图或细节不可辨时才局部放大。
- 普通插图的高度上限写成 `0.27\textheight`，并带 `keepaspectratio`，按正文高度封顶，不用百分比高度。原 Markdown 明确写了 width/height 时保留该尺寸：百分比宽度相对行宽，百分比高度相对正文高度，绝对单位原样传入。

## 语义边界

预处理器识别：

- 题目：`【例 N】`、`1、`、`1.`、同一例题下的 `(1)`、`(2)`。
- 答案：从 `【答案】` 开始，到解析、难度、下一题或标题之前。
- 解析：从 `【解析】`/`【解答】` 开始，到下一题、标题或新的语义标签之前。
- `(2)` 只有在向后遇到新标题、新题号或另一个小题号之前先遇到 `【难度】` 时，才视为下一小题；中间允许题干换行、选项或图片。解析中的 `(1)/(2)` 推导继续留在当前蓝框。
- 要点注释中的 `(1)(2)(3)` 留在同一橙框；知识补充中的编号条目也留在同一橙框。

无法可靠判断边界时，不要猜着吞入下一题：保留原文并报告待校位置。

## 命令

```bash
SKILL="${SKILL:?请设置为本技能安装目录}"
SRC="/absolute/path/讲义.md"
MD="${SRC%.md}-低饱和彩色教师版.md"
PDF="${SRC%.md}-低饱和彩色教师版.pdf"

python3 "$SKILL/scripts/prepare_teacher_handout.py" "$SRC" -o "$MD"

python3 "$SKILL/scripts/render_teacher_handout.py" "$MD" \
  --resource-root "$(dirname "$SRC")" \
  --author "chengbai" \
  -o "$PDF"

python3 "$SKILL/scripts/audit_teacher_handout.py" \
  --source "$SRC" --prepared "$MD" --pdf "$PDF" \
  --log "${PDF%.pdf}.log"
```

统一渲染器会把 `.tex` 和 `.log` 保存在 PDF 旁边，以便审计 fatal、undefined control sequence、missing character 和 overfull。若系统 Python 缺 `pypdf`，审计时使用 Codex bundled Python。`MECHANICAL SUMMARY PASS` 只代表机械门槛通过，不能替代逐页视觉检查和数学内容复核。

修改预处理器的题块边界规则后，先运行固化回归：

```bash
python3 "$SKILL/scripts/test_teacher_handout_boundaries.py"
```

## 视觉验收

1. 将 PDF 全部页面渲染为 PNG，并先看整篇 contact sheet。
2. 再放大检查首页、末页、所有图片页、所有跨页解析和用户批注页。
3. 一旦发现某类问题（如解析掉框、标题重叠、图未居中），对全篇扫描同类问题，不只修批注页。
4. 最终安排独立只读复核，报告 P0/P1/P2；P0/P1 修复后才能交付。
5. 数学符号需做上下文一致性检查；同一对象在题干用 `\bar a`、解析用 `\vec a`/`\overrightarrow a` 时必须标为高优先级待核。
6. 审计提示题面计数矛盾（例如文字称“三个代数式”但列出 `①②③④`）时，回到来源核实；不静默改题。
