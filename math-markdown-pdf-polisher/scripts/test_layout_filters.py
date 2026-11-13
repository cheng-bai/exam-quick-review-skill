#!/usr/bin/env python3
"""Pandoc checks for exam question boxes and teacher-handout figure caps."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


SKILL = Path(__file__).resolve().parent.parent
EXAM_FILTER = SKILL / "scripts" / "exam-blocks.lua"
HANDOUT_FILTER = SKILL / "scripts" / "teacher-handout-blocks.lua"


def pandoc_latex(markdown: str, lua_filter: Path) -> str:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "sample.md"
        source.write_text(markdown, encoding="utf-8")
        result = subprocess.run(
            ["pandoc", str(source), f"--lua-filter={lua_filter}", "-t", "latex"],
            check=True,
            capture_output=True,
            text=True,
        )
    return result.stdout


def between(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def test_exam_blocks() -> None:
    latex = pandoc_latex(
        """# 填空题

1. 有序列表题干

答案：1

解析：由条件得 (ii) 成立。

1．全角分隔题干

答案：2

解析：第二题。

1、顿号题干

3.无空格题干

1\\. 转义半角题干

已知这不是题号。

１２．全角数字题干

2. 相邻第二题
3. 相邻第三题

1. 外层题干
   1. 嵌套小问
   2. 仍属本题

（1）括号小问不是新题号
第1题不是自动题号

解析：图前解析

![](between.png)

1. 图后题目
""",
        EXAM_FILTER,
    )
    assert latex.count(r"\begin{questionbox}") == 10, latex
    assert latex.count(r"\end{questionbox}") == 10, latex
    assert latex.count(r"\begin{answerbox}") == 2, latex
    assert latex.count(r"\begin{analysisbox}") == 3, latex

    first = between(latex, r"\begin{questionbox}", r"\end{questionbox}")
    assert "有序列表题干" in first
    assert r"\begin{enumerate}" in first

    analysis = between(latex, r"\begin{analysisbox}", r"\end{analysisbox}")
    assert "(ii)" in analysis
    assert "有序列表题干" not in analysis

    assert "全角分隔题干" in latex
    assert "顿号题干" in latex
    assert "无空格题干" in latex
    assert "转义半角题干" in latex
    assert "全角数字题干" in latex
    assert "相邻第二题" in latex and "相邻第三题" in latex
    assert latex.count(r"\setcounter{enumi}{1}") >= 1
    assert latex.count(r"\setcounter{enumi}{2}") >= 1

    outer = latex.split("外层题干", 1)[1].split("图前解析", 1)[0]
    assert outer.count(r"\begin{questionbox}") == 0
    assert "嵌套小问" in outer and "仍属本题" in outer
    assert "括号小问不是新题号" in outer
    assert "第1题不是自动题号" in outer

    assert r"\end{analysisbox}" in latex
    image_at = latex.index(r"\includegraphics{between.png}")
    assert latex.rfind(r"\end{analysisbox}", 0, image_at) > latex.rfind(
        r"\begin{analysisbox}", 0, image_at
    )
    assert image_at < latex.index("图后题目")
    escaped = latex.split("转义半角题干", 1)[1].split(r"\end{questionbox}", 1)[0]
    assert "已知这不是题号" in escaped
    assert "全角数字题干" not in escaped


def test_teacher_figure_height() -> None:
    latex = pandoc_latex(
        """![](tall.png)

![](wide.png){width=80%}

![](custom-height.png){height=40%}

![](absolute.png){width=70% height=4cm}

![](macro.png){height=0.27\\textheight}

![](100%.png)

正文不是图片
""",
        HANDOUT_FILTER,
    )
    assert r"height=0.27\linewidth" not in latex
    assert r"height=0.27\textwidth" not in latex
    assert "height=27%" not in latex
    assert latex.count(r"\begin{center}") == 6
    assert (
        r"\includegraphics[width=0.58\linewidth,height=0.27\textheight,keepaspectratio]{macro.png}"
        in latex
    )
    assert r"height=\textheight," not in latex

    default = between(latex, r"\begin{center}", r"\end{center}")
    assert r"\includegraphics[width=0.58\linewidth,height=0.27\textheight,keepaspectratio]{tall.png}" in default

    wide = latex.split("wide.png", 1)[0]
    assert r"width=0.8\linewidth,height=0.27\textheight,keepaspectratio" in wide

    assert (
        r"\includegraphics[width=0.58\linewidth,height=0.4\textheight,keepaspectratio]{custom-height.png}"
        in latex
    )

    absolute = latex.split("absolute.png", 1)[0]
    assert r"width=0.7\linewidth,height=4cm,keepaspectratio" in absolute

    assert r"100\%.png" in latex
    assert "正文不是图片" in latex
    assert r"\includegraphics" not in latex.split("正文不是图片", 1)[1]


def main() -> int:
    test_exam_blocks()
    test_teacher_figure_height()
    print("LAYOUT FILTER TESTS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
