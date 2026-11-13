# math-markdown-pdf-polisher：按需执行细则

文中的 `references/`、`scripts/`、`assets/` 相对路径均以技能根目录（包含 SKILL.md 的目录）为基准。按 SKILL.md 的触发条件读取对应章节。

## 常用 LaTeX 渲染命令

```bash
SRC="/absolute/path/试卷标题-学生版.md"
SKILL_DIR="/absolute/path/math-markdown-pdf-polisher"
BASE="${SRC%.md}"
MD="${BASE}-排版版.md"
PDF="${BASE}-排版版.pdf"

cd "$(dirname "$MD")"

pandoc "$MD" \
  -f markdown+tex_math_dollars+raw_html \
  --lua-filter="$SKILL_DIR/scripts/exam-blocks.lua" \
  --include-in-header="$SKILL_DIR/assets/latex-exam-polish-header.tex" \
  -o "$PDF" \
  --pdf-engine=xelatex \
  -V geometry:a4paper \
  -V CJKmainfont="Songti SC" \
  -V mainfont="Times New Roman" \
  -V fontsize=11pt
```

如果需要更强版式控制，生成 `.tex` 后先用 `XELATEX="$(command -v xelatex)"` 解析本机 XeLaTeX，再通过该路径编译。图片路径必须从 Markdown/TeX 所在目录可解析。

## 试卷解析版 LaTeX 版式约定

- 题干：白底、蓝色细框和左线；不要使用重彩色卡片。
- 答案：浅绿色 `answerbox`，只包答案内容。
- 解析：浅红色 `analysisbox`，只包解析/证明/讲法内容；解析内部的 `(ii)`、`(iii)`、`法二`、`法三` 不应触发新题盒。
- 图片：默认居中，最大宽度约 `0.72\linewidth`，最大高度约 `0.27\textheight`；避免统计图、几何图按原图尺寸撑出大空白。
- 图片若出现在题号前且后面紧跟分隔线/下一题，不要让它落进上一题解析盒；若图片位于解析内部，则继续留在解析盒中。
- 遇到复杂题图或整页扫描校对图，先抽查缩略图，再决定是否单独调大；整页扫描图常用 override：`\setlength{\examimagewidth}{0.88\linewidth}`、`\setlength{\examimageheight}{0.45\textheight}`。不要为了整页扫描图把所有普通题图全局放大。
- 低置信 OCR 待校稿若保留原始识别文本，先把孤立反斜杠和异常 Unicode 符号降噪为 `□` 或普通文字；不要让 `\KM`、奇怪箭头、集合符号噪声触发 `Undefined control sequence` 或 `Missing character`。

## HTML fallback 命令

仅用于 OCR 工作台、快速预览、对比或 LaTeX 短期不可用时：

```bash
CSS="${BASE}-排版版.css"
HEADER="${BASE}-mathjax-header.html"
HTML="${BASE}-排版版.html"

# 按本机安装方式准备 MathJax，并设置下方路径。

pandoc "$MD" \
  -f markdown+tex_math_dollars+raw_html \
  -t html5 \
  --standalone \
  --mathjax="vendor/mathjax/tex-svg.js" \
  --css "$CSS" \
  --include-in-header "$HEADER" \
  -o "$HTML"
```

MathJax 路径以实际安装结果为准；MathJax 3 常见路径是 `vendor/mathjax/es5/tex-svg.js`。如果已有已验证基线，复制它的 MathJax URL 和 header 配置，不要盲目换默认。

## 验证命令

LaTeX 日志检查：

```bash
rg -n 'Fatal error|Emergency stop|Undefined control sequence|Missing character|Overfull \\\\hbox' "${BASE}-排版版.log" || true
```

PDF/HTML fallback 审计：

```bash
python3 "$SKILL_DIR/scripts/audit_math_pdf.py" \
  --html "$HTML" \
  --pdf "$PDF"
```

按需使用本机可用的公式渲染检测工具；Python 缺少 `pypdf` 时，请在所用环境中安装该依赖。

缩略图检查示例：

```bash
magick -density 144 "$PDF[0]" -quality 95 /tmp/page1.png
magick -density 144 "$PDF[-1]" -quality 95 /tmp/final-page.png
```

