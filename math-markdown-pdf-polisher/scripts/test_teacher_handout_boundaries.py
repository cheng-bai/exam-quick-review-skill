#!/usr/bin/env python3
"""Regression tests for teacher-handout semantic boundaries."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def load_preparer():
    path = Path(__file__).with_name("prepare_teacher_handout.py")
    spec = importlib.util.spec_from_file_location("teacher_prepare", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def first_body(text: str, class_name: str) -> str:
    marker = f"::: {{.{class_name}}}"
    return text.split(marker, 1)[1].split(":::", 1)[0]


def main() -> int:
    prepare = load_preparer().prepare

    mixed = """# 标题
【例 1】题干
【答案】A
【解析】方法一。

(1) 解析内部步骤
方法二：第二种方法。
(2) 解析内部第二步
方法三：第三种方法。

(2) 下一小题第一行
下一小题续行题干
A. 选项甲 B. 选项乙
【难度】★★★
【答案】B
【解答】完整解答。
"""
    prepared, counts = prepare(mixed)
    body = first_body(prepared, "kami-teacher-solution")
    assert counts["answers"] == 2 and counts["solutions"] == 2, counts
    assert "(1) 解析内部步骤" in body
    assert "(2) 解析内部第二步" in body
    assert "方法二" in body and "方法三" in body
    assert "(2) 下一小题第一行" not in body

    top_question = """# 标题
1. 第一题
【答案】1
【解析】第一题解析
方法二：继续
2. 第二题
【答案】2
【解析】第二题解析
"""
    prepared, counts = prepare(top_question)
    body = first_body(prepared, "kami-teacher-solution")
    assert counts["answers"] == 2 and counts["solutions"] == 2, counts
    assert "方法二：继续" in body and "2. 第二题" not in body

    notes = """讲义标题
<table><tr><td>教学目标</td><td>目标 1<br>目标 2</td></tr></table>
【要点注释】
(1) 第一条
(2) 第二条
【知识补充】
1. 补充一
2. 补充二
## 新章节
"""
    prepared, counts = prepare(notes)
    assert prepared.startswith("# 讲义标题")
    assert "<table" not in prepared and ".kami-teacher-summary" in prepared
    assert counts["notes"] == 2
    assert "(1) 第一条" in prepared and "(2) 第二条" in prepared

    print("TEACHER HANDOUT BOUNDARY TESTS PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
