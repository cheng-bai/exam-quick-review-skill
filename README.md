# 常用教学与教研 Skills

这里收集可复用的 AI 工作流程。目前包含六学科试卷快评、高中数学多卷考情与分类汇编，以及讲义和工作台 PDF 制作。每个 Skill 是可供支持技能的 AI 工具读取的一组说明、参考资料和可选脚本，不是一键生成软件。

## 按任务查找

| Skill | 适用任务 | 检索标签 |
|---|---|---|
| [试卷洞见与分类汇编](math-exam-insight-compilation/) | 多套高中数学试卷的单卷分析、跨卷考情、分类汇编及教学说明 | 高中数学、多卷汇编、考点分析、难度分层、分类汇编、教研洞察 |
| [讲义 PDF 版式](lecture-pdf-layout/) | 为已确定的数学讲义内容设计与验证 PDF 版式 | 数学讲义、排版、目录、书签 |
| [工作台学生版 PDF](xdf-workbench-student-pdf/) | 将数学分类汇编制作成供高中工作台识别的学生版 PDF | 分类汇编、学生版、工作台、PDF |
| [数学试卷快评](exam-quick-review/math-exam-quick-review/) | 单卷数学快评及按需制作教师版 | 数学、试卷快评、PDF、教师版 |
| [语文试卷快评](exam-quick-review/chinese-exam-quick-review/) | 单卷语文快评 | 语文、试卷快评、PDF |
| [英语试卷快评](exam-quick-review/english-exam-quick-review/) | 单卷英语快评 | 英语、试卷快评、PDF |
| [物理试卷快评](exam-quick-review/physics-exam-quick-review/) | 单卷物理快评 | 物理、试卷快评、PDF |
| [化学试卷快评](exam-quick-review/chemistry-exam-quick-review/) | 单卷化学快评 | 化学、试卷快评、PDF |
| [生物试卷快评](exam-quick-review/biology-exam-quick-review/) | 单卷生物快评 | 生物、试卷快评、PDF |

仓库顶层按技能或技能系列组织：`exam-quick-review/` 集中存放六学科快评和通用快评技能；其他顶层技能各自独立。每个快评子目录也是独立 Skill，安装时选择其中需要的完整子目录。

## 安装与使用

1. 下载所需 Skill 的**完整目录**，保留 `SKILL.md` 及其引用的相对路径。Codex 可放入 `~/.codex/skills/`，其他工具按其技能安装方式操作；必要时刷新或重启工具。
2. 提供有权使用的试卷、答案、解析及目标要求。没有自动发现能力的工具，可要求 AI 读取该目录的 `SKILL.md` 和按需引用的资料。
3. 单卷面向家长的快速解读使用学科快评；跨卷找规律、按数学机制汇编及教学决策使用分类汇编。生成后仍需按实际用途核对原题、数学、统计与版式。

## 数学分类汇编

详见 [技能介绍与使用指南](math-exam-insight-compilation/README.md)。从可追溯原卷与题目底稿出发，先按卷分析，再按专题和数学任务组织汇编，以稳定题号与统计口径支撑考点、难度与来源分析。按需生成 Markdown 题集、卷内分析、专题说明和统计记录；PDF 和可视化按当次要求制作。

## 讲义与工作台 PDF

[讲义 PDF 版式](lecture-pdf-layout/SKILL.md)提供版式原则及可选 LaTeX 模板，不替代数学审校。[工作台学生版 PDF](xdf-workbench-student-pdf/SKILL.md)提供分类、生成和核验流程；其脚本依赖另行配置的兼容 `math-handout-pdf` 引擎以及 Python、Node、Chrome 和相应依赖，仓库不包含该引擎。本地验收不等于工作台识别成功。

## 六学科试卷快评

将一份试卷整理为面向家长和学生的前端快评，包含整卷判断、考点分布、逐题考点、难度、分值和答案摘要；可按要求增加教师版，数学另有逐题详细解析规范。通用入口为 [exam-frontend-quick-review](exam-quick-review/exam-frontend-quick-review/)。PDF 排版需要相应工具和字体，可选 [Typst 版式骨架](exam-quick-review/exam-frontend-quick-review/assets/版式起点.typ)；生成后应逐页检查。[案例说明](exam-quick-review/exam-frontend-quick-review/examples/案例说明.md)介绍公开版边界。

## 协作与使用边界

请阅读 [AI 协作约定](AGENTS.md) 和 [贡献指南](CONTRIBUTING.md)，通过独立分支与 Pull Request 协作。外部试卷、知识图谱、商标及使用者提供的材料，其权利由各自权利人保留；不得提交无权公开的原题、学生资料、密钥或品牌素材。项目原创内容采用 [MIT 许可证](LICENSE)。
