// 可编辑版式起点；所有示例数据须替换。根据实际题量调整热力图、分页和列宽。
#set page(paper: "a4", margin: (x: 16mm, y: 14mm), numbering: "1")
// 使用前检查本机字体；宋体及星号字体不可用时先与使用者确认替代字体。
#set text(font: "Songti SC", size: 10.5pt, fill: rgb("#21312a"))
#set par(leading: 0.7em)
#let theme = rgb("#087b52") // 对应 subject-colors.json 的数学 ink；换学科时替换
#let dark = theme // 深色标签与通栏表头使用该学科 ink；热力图另用 accent/tint
#let heading(t) = block(width: 100%, above: 4pt, below: 8pt)[#box(width: 8pt, height: 8pt, fill: theme) #h(5pt) #text(size: 16pt, weight: "bold", fill: theme, t)]
#box(fill: theme, inset: (x: 8pt, y: 4pt), radius: 2pt)[#text(size: 10pt, fill: white, weight: "bold")[［教学快评］机构名称]]
#v(5pt)
#text(size: 17pt, weight: "bold")[年份 · 学校 · 年级学期 · 学科考试快评]
#v(8pt)
#text(size: 12pt, weight: "bold", fill: theme)[整体难度　#text(font: "Arial Unicode MS")[★★★☆☆]　适中]
#v(5pt)
参考分数：合格参考　示例　｜　优秀参考　示例
#v(8pt)
// 使用同一表格行：两格自动共享行高，长文本换行时色块仍与描边框等高。
#let highlight(body) = table(
  columns: (78pt, 1fr),
  stroke: 0.8pt + theme,
  inset: (x: 9pt, y: 8pt),
  align: (center + horizon, left + horizon),
  table.cell(fill: dark)[#text(fill: white, weight: "bold")[一句话亮点]],
  table.cell(fill: white)[#body],
)
#highlight[替换为基于本卷题目的简洁判断。]
#v(14pt)
#heading[考点分布]
// 以底表统计结果替换此示例；色阶应反映数量，并标明含义。
#table(columns: (40%, 12%, 12%, 12%, 12%, 12%), inset: 6pt, stroke: 0.5pt + theme,
  [*模块 · 题号*], [*1星*], [*2星*], [*3星*], [*4星*], [*5星*],
  [示例模块 · 1题], [1], [0], [0], [0], [0],
)
#pagebreak()
#heading[逐题快评]
#table(columns: (10%, 10%, 29%, 15%, 8%, 28%), inset: (x: 3pt, y: 4pt), stroke: 0.4pt + theme,
  table.header(
    table.cell(colspan: 6, fill: dark, inset: 9pt)[#text(size: 14pt, fill: white, weight: "bold")[机构名称 · 试卷名称 · 快评]],
    [*题型*], [*题号*], [*模块 / 考点*], [*难度*], [*分值*], [*答案摘要*],
  ),
  [示例], [1], [示例考点], [#text(font: "Arial Unicode MS")[★★★☆☆]], [示例], [示例答案],
)
