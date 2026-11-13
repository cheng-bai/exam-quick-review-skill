# math-markdown-pdf-polisher：按需执行细则

以下章节从本技能 SKILL.md 原样迁移。文中的 `references/`、`scripts/`、`assets/` 相对路径均以技能根目录（包含 SKILL.md 的目录）为基准；绝对路径及示例占位符保持原义。按 SKILL.md 的触发条件读取对应章节。

## 总流程

1. **预检**
   - 确认源 Markdown 绝对路径和相邻图片目录。
   - 如果用户指出某个 PDF/HTML/TeX“渲染正确”，先记录它的 Markdown、TeX、CSS、header、MathJax URL、编译/打印方式、页数和代表性公式页，作为基线。
   - 统计行数、图片引用、raw HTML 图片、display math 标记、标题和可疑 OCR 片段。
   - 检查工具：`pandoc`、`xelatex` 或 `/Library/TeX/texbin/xelatex`、ImageMagick 或 `qlmanage`、可用的 Python + `pypdf`。HTML fallback 才需要 Google Chrome/Playwright。

2. **建立工作副本**
   - 不直接编辑 OCR 源文件。
   - 默认在源文件旁生成：
     - `源文件名-排版版.md`
     - `源文件名-排版版.tex`（需要原生 LaTeX 模板时）
     - `源文件名-排版版.pdf`
     - HTML fallback 才生成 `源文件名-排版版.css`、`源文件名-mathjax-header.html`、`源文件名-排版版.html`
   - 面向用户交付的最终 Markdown、质量报告必须使用中文语义化文件名；不要用 `source.md`、`cleaned.md`、`student.md`、`teacher.md`、`QUALITY_REPORT.md` 这类泛名或英文名作为最终交付文件名。

3. **清理 Markdown**
   - 必要时添加简短 YAML frontmatter。
   - 将 `第N讲` 等讲义标题提升为主章节，将 `一、二、三、...` 主题标记提升为小节。
   - 试卷 `解析版` 优先采用“题干 + 答案 + 解析”紧跟题目的结构，不把所有答案堆到末尾。
   - 中文试卷的清理不是轻量格式化；清理稿在渲染前就必须可读。
   - 典型结构：`填空题` / `选择题` / `解答题` / `答案与解析`，题号稳定，题干、选项、小问、分值、表格、图形和答案解析都贴近对应题目。
   - 不运行会转义 `_`、`{}`、`\`、`$` 的通用 Markdown formatter。
   - 只修正高置信 OCR 错误；不确定处用 `【待校】` 标注，不凭空补公式。
   - OCR 把 `（1）`、`（2）`、`①`、`②`、选项粘成一段时，要主动断行。
   - MinerU/OCR 漏掉 `$...$` 时要主动修补数学语义：变量、点线面、函数、区间、坐标、集合、三角形/线段名等数学原子（如 `a`、`E`、`AB`、`ABC`、`g(x)`）出现在中文正文中时应包成行内公式；不要把普通中文或非数学英文过度包裹。
   - 大题标题只放题号、题型和分值；`已知...`、`如图...`、长公式和题干放到标题后的普通段落，避免公式被标题样式放大、加粗或分页异常。
   - 多选项粘连时拆成语义选项；选择题可用四列/等宽网格或等效 Markdown/CSS，让 A/B/C/D 等间距分布。
   - 将脆弱或渲染器不支持的 OCR LaTeX 改成稳定写法，例如正文编号优先用 `①②③`，不要保留会露出 raw TeX 的 `\textcircled{1}`。
   - display math 的 `$$` 不能变成孤立空段落。
   - 本地有对应图片时，把远程 OCR 图片 URL 改成本地相对路径。
   - 清空图片 alt，隐藏生成的 caption，避免文件名打印进 PDF。

4. **渲染**
   - 正式 PDF 默认先走 LaTeX：优先 Pandoc -> XeLaTeX；需要强版式控制时生成 `.tex` 并用模板编译。
   - 试卷/解析版 Markdown 优先套用本 skill 的 LaTeX 精排资产：
     - `assets/latex-exam-polish-header.tex`：A4 讲义式浅色盒、题干白底蓝左线、答案浅绿盒、解析浅红盒、图片尺寸上限。
   - `scripts/exam-blocks.lua`：按 `数字.`、`答案：`、`解析：` 分离题干/答案/解析；不会把解析里的 `(ii)/(iii)` 误判成新题。
   - 方括号标签教师版不要套用上述标准 filter；改用 `scripts/prepare_teacher_handout.py`、`scripts/teacher-handout-blocks.lua` 和 `assets/latex-teacher-kami-header.tex`，确保多段解析完整入框且 Markdown 内容仍由 Pandoc 正常解析。
   - 低饱和教师讲义必须用 `scripts/render_teacher_handout.py` 渲染；它持久化 `.tex` 和 `.log`，不要用会清理临时日志的单步 Pandoc 命令替代正式交付构建。
   - 第一轮 XeLaTeX 报错时，先修 Markdown/TeX 的高置信问题，如未转义的特殊字符、坏 `\frac`、缺失图片路径、错误宏、Unicode 数学符号；不要立刻退回 HTML。
   - HTML + MathJax 只用于 OCR 清理工作台、快速对比、baoyu-design 专用交付，或 LaTeX 路线短期不可用时的 fallback。
   - 使用 HTML fallback 时，用 Pandoc 生成 standalone HTML，本地化 MathJax，使用 Playwright/DevTools 打印 PDF，关闭 header/footer，等待公式渲染完成。
   - 几何/图形密集试卷需要区分正文图、选项图、成对图，并把 `图一/图二` 与对应图片绑定。
   - 分页优先使用题块级规则，不随意插入孤立 page-break div。长题若强制不分页会造成大空白，应先调图片尺寸和间距。
   - 大题如第 `17`-`21` 题通常需要足够书写空间，可一题一页；长题允许两页。

5. **审计**
   - LaTeX 路线检查 `.log`：不得有 `Fatal error`、`Emergency stop`、`Undefined control sequence`；`Missing character` 要逐项判断。
   - HTML fallback 路线运行 `scripts/audit_math_pdf.py`。
   - 抽查缩略图：第一页、最后一页、至少一页公式密集页、至少一页图片密集页。
   - 审计后再修订，每批修订后重新渲染。
   - `mjx-merror = 0` 不代表数学正确；公式密集页还要看是否有裸 `$`、raw TeX、OCR 破损符号。
   - 低饱和教师讲义模式必须运行 `scripts/audit_teacher_handout.py`，核对源标签数量、内容顺序、预处理语义块、主标题/结构 HTML、PDF 标题条、图片对象、A4 页面、PDF header/EOF、XeLaTeX 日志、源码残留、向量符号混用和高置信枚举数量矛盾。
   - 审计脚本的 PASS 是机械门槛，不代表配色、裁切、跨页框或数学内容已经人工确认。
   - 用户对长文档做过页面批注时，最终必须渲染并检查全部页面；发现一类问题后，对全篇扫描同类问题。

6. **教师版转录注释**
   - 从课堂 transcript 生成教师版时，保留原题，在题下插入紧凑的答案/讲法块。
   - `课堂内容概要` 必须来自 transcript，提到实际知识点、题号、老师提醒、修改题、跳过内容和课后订正。
   - transcript 没有覆盖的题，不能写成老师已讲；用“本讲课堂未展开本题。”等提示。
   - `课堂内容概要` 默认用灰黑克制打印样式，不用高饱和蓝卡片、渐变或网页式装饰。

7. **多轮校对**
   - 文档长或用户要求 review 时，做三类独立检查：
     - Markdown/OCR 结构检查。
     - HTML/PDF 渲染检查。
     - 数学概念/公式高置信检查。
   - 可读取 `references/subagent-prompts.md` 获取提示词。
   - 只修正有本地证据的高置信问题；不确定处列入残余风险。
   - 教师讲义视觉修复完成后安排独立只读复核；P0/P1 问题修复后才能交付。

