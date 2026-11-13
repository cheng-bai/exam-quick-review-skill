---
name: math-markdown-pdf-polisher
description: "清理和排版中文高中数学 OCR/公式密集 Markdown，修复公式、图片、题块和分页并验证 PDF；仅审校已有答案时直接逐题独立核算，按题型重建用 high-school-math-handout-pipeline。"
---

# 数学 Markdown/PDF 精排与审计

本 skill 用来把公式密集的 OCR Markdown 变成可打印 PDF，并避免破坏数学语法。公式渲染应保留已验证基线；没有基线时，正式 PDF 默认优先走 Pandoc -> XeLaTeX 或原生 LaTeX 模板；HTML + MathJax 只作为 OCR 清理工作台、快速预览、对比出口或 fallback。最终必须检查渲染后的 PDF。

## 模式路由

- **仅数学审校**：源文件只读，在任务副本或审校记录中逐题独立核算，保留来源、修订理由和待核项；复杂任务按适用约定复核。不运行清理和渲染流程，除非用户也要求排版。
- **标准试卷模式**：题号以 `数字.` 为主，标签为 `答案：`/`解析：`，使用现有 `exam-blocks.lua` 和 `latex-exam-polish-header.tex`。
- **低饱和教师讲义模式**：出现 `【例 N】`、`【答案】`、`【解析】`、`【知识补充】` 等方括号标签，或用户要求完整解析彩色框、低饱和蓝绿讲义风格时，必须读取 [references/teacher-kami-mode.md](references/teacher-kami-mode.md)，使用其中的预处理器、Lua filter、LaTeX header 和语义审计。
- **原生 LaTeX 新讲义**：内容不是 OCR/Markdown 清理而是从零编写时，可配合 `lecture-pdf-layout` 的模板；不要把原生模板路线硬套到已有长 Markdown。
- `kami` 只提供视觉反馈与验收方法；数学语义边界和公式正确性仍由本 skill 负责。

## 总流程

开始实际清理/渲染前，必须读取 [完整执行流程](references/workflow-details.md)。

1. 预检源文件、图片、工具及用户确认的渲染基线。
2. 建立有语义文件名的工作副本，保留原稿。
3. 清理题干/答案/解析结构、OCR 与公式；只修高置信问题。
4. 按模式选择现有滤镜和 header，优先 XeLaTeX；教师讲义使用持久化 TeX/日志的专用脚本。
5. 检查日志、图片、公式、分页，修订后重新渲染；机械 PASS 不能替代视觉检查。
6. 教师转录只陈述实际课堂覆盖内容；长文档分别检查结构、渲染和数学问题。独立复核后修复 P0/P1 再交付。

## 渲染与验证入口

运行标准试卷渲染、HTML fallback 或验证命令前，读取 [命令与版式细则](references/render-commands-layout.md) 对应章节。低饱和教师模式仍优先使用上方模式路由的专用参考，不套标准试卷滤镜。

## 硬性失败条件

出现以下情况不能交付：

- HTML/PDF 缺失、PDF 不可读、0 字节、页面尺寸错误。
- LaTeX 正式路线没有尝试，且没有说明为什么必须使用 HTML fallback。
- LaTeX 编译日志中有未处理的 fatal/error/undefined control sequence。
- 本地图片丢失、仍有远程图片引用、图片文件名或 `figcaption` 打印进页面。
- HTML/PDF 中可见 `$$`、raw `\frac`、`.jpg/.png/.webp`、明显 OCR 残片。
- 公式肉眼破损，即使 `mjx-merror = 0`。
- 数学字母、函数名、区间或几何对象因未包 `$...$` 而使用正文字体，导致同一公式/推导内字体混杂。
- 大题标题包含长题干或公式，导致标题过大、跨页异常或公式加粗失真。
- 试卷 Markdown 在渲染前不可读：答案脱离题目、题块不稳定、选项/小问错位、表格/图形离题过远。
- 最终 Markdown 或质量报告仍使用 `source.md`、`cleaned.md`、`student.md`、`teacher.md`、`QUALITY_REPORT.md` 等泛名。
- 教师版答案与题目隔着大片空白，或因 `break-inside: avoid` 造成异常分页。
- 缩略图发现空白页、公式裁切、图片缺失或异常大空白。

`pdf.empty_text_pages` 是警告，不一定失败；只有逐页缩略图确认不是空白输出时才可接受。

## 抽查策略

- 总是检查第一页、最后一页、至少一页公式密集页和至少一页图片密集页。
- 专门抽查：裸数学字母字体、`\textcircled` 等 raw TeX 残留、选择题选项间距、长题标题是否混入题干、题与题之间是否有清晰分隔。
- 试卷解析版还要抽查：题干/答案/解析盒颜色是否分层，图片是否过大，解析内部小序号是否误入题干盒。
- `pdf.empty_text_pages` 提到的每一页都要看缩略图。
- 长 PDF 按四分位抽查，再补查文本扫描中可疑位置。
- 低饱和教师讲义模式或用户已逐页批注的长 PDF 不使用抽查代替全检：必须生成全页缩略图，并放大复核图片页、跨页解析页和所有批注页。

## 已知返工检查

交付前对照 [常见误区](references/known-pitfalls.md)，确认未重现公式、图片、答案位置或分页问题。

## 最终汇报

交付时说明：

- 最终 PDF 路径、页数、文件大小。
- 使用的路线：LaTeX/XeLaTeX、Pandoc MathML、HTML fallback，及选择理由。
- LaTeX 日志或 HTML audit 的关键结果。
- 哪些检查无法运行。
- 剩余低置信 OCR/数学风险。
- 整书输出还要说明目录、书签、合并 PDF 和页码核对结果。
