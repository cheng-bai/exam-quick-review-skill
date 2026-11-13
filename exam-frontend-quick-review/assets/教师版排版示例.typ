// 版式示例：替换为核对过的本卷内容；不要把整题放进不可跨页的盒子或表格。
#set page(paper: "a4", margin: (x: 20mm, y: 18mm), numbering: "1")
#set text(font: "Songti SC", size: 11pt, fill: rgb("#21312a"))
#set par(leading: 0.75em, spacing: 0.8em, justify: true)
#let theme = rgb("#087b52") // 与数学前端版一致；其他学科替换为对应色卡。
#let label(t) = block(above: 10pt, below: 5pt, breakable: false, sticky: true)[#text(fill: theme, weight: "bold", size: 11.5pt, t)]
#let question(n, body) = [
  #block(above: 14pt, below: 7pt, breakable: false, sticky: true)[#text(fill: theme, weight: "bold", size: 14pt)[第 #n 题]]
  #body
]

#text(size: 19pt, fill: theme, weight: "bold")[数学教师版 · 排版示例]

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
