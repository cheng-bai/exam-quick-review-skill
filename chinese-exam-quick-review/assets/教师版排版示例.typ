// 版式示例：替换为核对过的本卷内容；不要把整题放进不可跨页的盒子或表格。
#set page(paper: "a4", margin: (x: 22mm, top: 20mm, bottom: 20mm), numbering: "1")
#set text(font: "Songti SC", size: 11pt, fill: rgb("#26332d"))
#set par(leading: 0.8em, spacing: 0.85em, justify: true)
#let theme = rgb("#087b52")
#let pale = rgb("#edf6f0")
#let label(t) = block(above: 11pt, below: 5pt, sticky: true)[#text(fill: theme, weight: "bold", size: 10.5pt)[■ #t]]
#let question(n, body) = [
  #block(above: 18pt, below: 9pt, sticky: true)[
    #line(length: 100%, stroke: 0.6pt + rgb("#c7dfd1"))
    #v(6pt)
    #text(fill: theme, weight: "bold", size: 14pt)[第 #n 题]
  ]
  #body
]

#block(width: 100%, fill: theme, inset: (x: 15pt, y: 12pt))[
  #text(fill: white, size: 18pt, weight: "bold")[数学教师版] #h(1em)
  #text(fill: white, size: 10pt)[试卷分析与逐题解析]
]
#v(7pt)
#text(size: 9pt, fill: rgb("#53665b"))[版式演示 · 自编题目]

#question(1)[
  已知函数 $f(x) = x^2 - 2x + 2$，求该函数的最小值，并说明理由。
]
#label[考点] 二次函数的最值。
#label[答案] 最小值为 $1$。
#label[解析]
先配方，将二次函数转化为顶点式，以便直接判断最小值：

$ f(x) = x^2 - 2x + 2 = (x - 1)^2 + 1. $

因为 $(x - 1)^2 >= 0$，当且仅当 $x = 1$ 时取等，所以函数的最小值为 $1$。

#question(2)[
  已知 $a > 0$，考虑函数 $g(x) = x + a / x$（$x > 0$）。求其最小值，并说明取等条件。
]
#label[考点] 基本不等式与取等条件。
#label[答案] 最小值为 $2 sqrt(a)$。
#label[解析]
第一步，检查两个项的符号。由于 $x > 0$、$a > 0$，两个项均为正，可以使用基本不等式。

第二步，应用基本不等式，得到

$ g(x) = x + a / x >= 2 sqrt(x dot a / x) = 2 sqrt(a). $

第三步，检查取等条件。当 $x = a / x$，即 $x = sqrt(a)$ 时取等。因此，最小值为 $2 sqrt(a)$。
