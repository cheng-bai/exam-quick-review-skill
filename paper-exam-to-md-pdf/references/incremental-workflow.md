# 增量转录工作流

脚本入口：`$SKILL/scripts/transcribe.py`，其中 `SKILL` 为本技能安装目录。以下用 `CLI` 表示该脚本，用 `RUN` 表示本次可写工作目录。命令不打印正文全集，详细结果保存在 `work/最近结果/`，大于8项的摘要列表会截断并给出总数。`question` 只读取指定一题。

## 来源与 OCR

```bash
python3 "$CLI" prepare --workspace "$RUN" --url 'https://mp.weixin.qq.com/s/文章ID' --source-index '/已有提取结果/标题.md'
python3 "$CLI" ocr --workspace "$RUN"
```

`prepare` 不带 `--source-index` 时调用已有公众号提取脚本；已登记来源和文件哈希都匹配时不联网。传入索引必须与 URL 一致，原始 HTML、正文图片、PDF 和被排除图片需保留。`network_calls` 为提取器调用次数，不是底层 HTTP 图片请求数；来源检查失败时不自动重抓。

`ocr` 以输入文件内容和 VLM 配置作缓存键。公开来源豁免只适用于 `prepare` 登记的同一 PDF；其他本地文件需已取得逐文件外发同意，再显式加 `--allow-remote`。凭据由现有 CLI 读取，不能写入命令、状态或报告。没有 MinerU 可用通道须说明并按技能回退；不可声称识别成功。

已有识别结果可导入，不再调用服务：

```bash
python3 "$CLI" ocr --workspace "$RUN" --ocr-md '/已有/识别稿.md' --ocr-json '/已有/版面.json'
python3 "$CLI" summarize-ocr --workspace "$RUN" --ocr-md '/已有/识别稿.md' --ocr-json '/已有/版面.json'
```

导入代表操作者声明该 OCR 与所登记原文件对应，不是脚本独立验证对应关系。草稿仍须按图核对。失败任务保留日志；存在未完成输出时先查服务任务状态，防止重复提交。缓存损坏不自动重传，先核对证据或换一个运行目录。

## 题目数据

唯一正文源为运行目录的 `题目数据.json`，字段示意：

```json
{
  "schema_version": 1,
  "title": "某校某学年数学试卷",
  "source_url": "https://mp.weixin.qq.com/s/文章ID",
  "expected_questions": 1,
  "prefixes": {"student": "# 某校数学试卷·题目版\n\n来源……", "teacher": "# 某校数学试卷·原文解析版\n\n来源……"},
  "appendices": {"student": "## 附录：原始整页图\n\n[原图](../work/原始图片/01.jpg)", "teacher": "## 附录：原始整页图\n\n[原图](../work/原始图片/01.jpg)"},
  "questions": [{
    "id": 1,
    "section": "一、填空题",
    "stem": "完整题干与必要题图，不能含答案提示。",
    "solution": "**答案**：原答案\n\n**原文解析**：原解析",
    "notes": "原文疑点另列，不能混入学生题干。",
    "review": {"state": "pending", "evidence": []}
  }]
}
```

无原答案时 `solution` 可为空，不自动补解。`expected_questions` 来自原卷确认；分值、考生注意等不可因整理遗漏，可保留在题干、分节标题或版本前言。脚本目前要求题号为连续阿拉伯数字1—N；原材料不符合时保留原标识，适配后再使用，不强行改原题号。

分节标题到首题之间的分值、答题说明使用可选 `section_preambles` 保存，例如 `{"student":{"1":"每题5分，请填空。"},"teacher":{"1":"每题5分，请填空。"}}`，键为该分节首题号，正文输出在该题之前。导入时分别保留双版说明，完整稿使用含原解析的版本说明；没有可识别题目的分节会停止导入，避免静默丢失正文。

图片放在 `outputs/题图/`；正文使用相对链接。题目版附录只链接原题整页，不链接带解析整页。图片文件名含“解析/答案”会触发题目版结构检查，但文件名扫描不能证明图片内无提示，仍需目视。

已有校订双版可导入：

```bash
python3 "$CLI" import-reviewed --workspace "$RUN" --student '/旧交付/题目版.md' --teacher '/旧交付/解析版.md'
```

导入格式是 `### 第N题`、`**答案**`、可选 `**转录校注` 和 `## 附录：…`。导入器比较双版题干，并复制相对附件；格式不符或同名附件内容不同就停止，不猜测边界、不覆盖。导入记录已有稿的来源及哈希，状态是 `imported_reviewed`，不声称本命令重新核图。原稿保持不变。

## 局部校订与复核

```bash
python3 "$CLI" plan --workspace "$RUN"
python3 "$CLI" question --workspace "$RUN" --question 20
python3 "$CLI" crop --workspace "$RUN" --source-pdf '/原始打印版.pdf' --page 4 --bbox '752,187,932,290' --name '第19题-题图'
```

`crop` 坐标必须对应实际 OCR 输入的那份 PDF，采用0—1000归一化坐标；不要将带白边A4的坐标直接乘原始照片尺寸。裁后必须打开确认图形、顶点、边线和标注齐全，图片内来源标识保留。裁切缓存命中时不再渲染。

编辑 JSON 中对应题目的字段；`plan` 检查选项缺漏、题号、小问标号、链接、公式分隔符、答案字段及复核哈希。机械检查不能判断公式真伪、图像提示、题意或数学答案。内容或相关题图改变后，旧复核标记会过期：核图/独立复核完成、证据已落盘后才能登记：

```bash
python3 "$CLI" record-review --workspace "$RUN" --question 20 --evidence '/已完成的复核记录.md' --reviewer '实际复核者'
```

登记命令只是将证据绑定到当前内容哈希，不会自动复核。缺少复核时仍可生成供审阅的稿件，但验收中的警告必须保留，不能称为审定成品。

## 构建与预览

```bash
python3 "$CLI" build --workspace "$RUN"
python3 "$CLI" build --workspace "$RUN" --pdf
python3 "$CLI" build --workspace "$RUN" --pdf --editions student,teacher
```

`build` 默认生成一份完整转录 Markdown，不自动调用编译器；原文答案和解析按题保留。只有显式 `--pdf` 才导出PDF，只有显式 `--editions student,teacher` 才生成双版。Markdown 按内容增量写入；只改解析/校注时题目版无需改变。`--pdf` 调用固定模板，以 Markdown、实际图片、模板、脚本、字体配置、工具版本的内容指纹判断重建。相同内容的二次运行不编译、不渲染。编译失败保留旧 PDF 和本轮日志；本轮验收标记不会沿用旧轮成功状态。

PDF 编译仍需以整份受影响文档为单位，不能宣称只编译一个题块。预览由PDF哈希隔离，避免旧页混入。默认全册低清总览加首页、公式密集页、末页高清图；按需用独立导出器补看修改页：

```bash
python3 "$SKILL/scripts/pdf_export.py" '/指定版本.md' --work-dir "$RUN/work/pdf" --mode teacher --preview-pages 2,9
```

未打开过预览不能记为目视验收；首次使用模板，应以公式、图形、长解析的小样实际编译验证，再扩展全卷。题目版短题按实际高度保整页，超过一页的题自然分页；教师解析保持可跨页。

## 输出、计量与恢复

- `outputs/`：按请求生成的中文语义化 Markdown/PDF 和题图。
- `题目数据.json`：可编辑正文、来源、校注和复核状态。
- `work/来源缓存.json`、`ocr-cache/`：原始依赖哈希及识别结果。
- `work/待复核清单.json`、`最近结果/`：完整机器检查和按题差异。
- `work/运行记录.jsonl`：耗时、摘要字符数；token计数未测量时明确写未测量。
- `work/最终验收.json`：本轮构建状态与警告。必须对照当前数据哈希，不以旧验收冒充新验收。

若输出 Markdown 被人工或并发修改，脚本拒绝覆盖；先把实际修改合回题目数据或换目录。来源、OCR、附件损坏先核对，不自动外发。运行目录与技能代码分开；替换技能前保存原文备份，回滚只恢复对应技能文件，不动原始教学资料。
