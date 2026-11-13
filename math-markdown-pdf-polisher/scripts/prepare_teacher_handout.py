#!/usr/bin/env python3
"""Prepare bracket-labelled Chinese math Markdown for the teacher-handout mode."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


MARKER = r"(?:\*\*)?【{label}】(?:\*\*)?"


def marker_match(line: str, label: str) -> re.Match[str] | None:
    return re.match(rf"^\s*{MARKER.format(label=label)}\s*(.*)$", line)


def is_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s+", line))


def is_example(line: str) -> bool:
    return bool(re.match(r"^\s*(?:\*\*)?【例\s*\d+】", line))


def is_top_question(line: str) -> bool:
    return bool(re.match(r"^\s*\d+\s*[、．.]\s*", line))


def is_subquestion(line: str) -> bool:
    return bool(re.match(r"^\s*[（(]\s*\d+\s*[）)]", line))


def is_semantic_marker(line: str) -> bool:
    labels = "答案|解析|解答|难度|要点注释|知识补充|知识拓展"
    return bool(re.match(rf"^\s*(?:\*\*)?【(?:{labels})】", line))


def subquestion_starts_next_problem(lines: list[str], index: int) -> bool:
    """Distinguish a new subquestion from a numbered step inside a solution."""
    for line in lines[index + 1 :]:
        if not line.strip():
            continue
        if marker_match(line, "难度"):
            return True
        # If another numbered subquestion appears first, the current one is a
        # solution step rather than the start of the later problem. Ordinary
        # prose and option lines may legitimately sit before the difficulty
        # marker, so they do not end the look-ahead.
        if is_heading(line) or is_example(line) or is_top_question(line) or is_subquestion(line):
            return False
    return False


def solution_end(lines: list[str], start: int) -> int:
    for index in range(start, len(lines)):
        line = lines[index]
        if is_heading(line) or is_example(line) or is_top_question(line):
            return index
        if is_subquestion(line) and subquestion_starts_next_problem(lines, index):
            return index
        if is_semantic_marker(line):
            return index
    return len(lines)


def answer_end(lines: list[str], start: int) -> int:
    for index in range(start, len(lines)):
        line = lines[index]
        if is_heading(line) or is_example(line) or is_top_question(line):
            return index
        if is_semantic_marker(line):
            return index
    return len(lines)


def note_end(lines: list[str], start: int, kind: str) -> int:
    for index in range(start, len(lines)):
        line = lines[index]
        if is_heading(line) or is_example(line) or is_semantic_marker(line):
            return index
        if kind == "要点注释" and is_top_question(line):
            return index
    return len(lines)


def trim_blank(lines: list[str]) -> list[str]:
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def fenced(class_name: str, body: list[str], title: str | None = None) -> list[str]:
    attr = f".{class_name}"
    title_attr = f' data-title="{title}"' if title else ""
    return [f"::: {{{attr}{title_attr}}}", *trim_blank(body), ":::", ""]


def clean_html_cell(value: str) -> list[str]:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    return [line.strip() for line in value.splitlines() if line.strip()]


def convert_simple_tables(text: str) -> str:
    """Convert simple OCR HTML tables into a semantic teacher-summary Div."""
    def replace(match: re.Match[str]) -> str:
        rows: list[tuple[str, list[str]]] = []
        for row in re.findall(r"<tr\b[^>]*>(.*?)</tr>", match.group(0), flags=re.I | re.S):
            cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, flags=re.I | re.S)
            if len(cells) >= 2:
                label_lines = clean_html_cell(cells[0])
                content_lines = clean_html_cell(cells[1])
                if label_lines and content_lines:
                    rows.append((label_lines[0], content_lines))
        if not rows:
            return match.group(0)
        body: list[str] = []
        for label, content in rows:
            body.extend([f"**{label}**", "", *content, ""])
        return "\n".join(fenced("kami-teacher-summary", body)).rstrip()

    return re.sub(r"<table\b[^>]*>.*?</table>", replace, text, flags=re.I | re.S)


def promote_leading_title(text: str) -> str:
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None:
        return text
    title = lines[first].strip()
    if title.startswith(("#", "---", "<")):
        return text
    if len(title) > 40 or re.search(r"[。；;：:]|\$", title):
        return text
    following = next((line.strip() for line in lines[first + 1 :] if line.strip()), "")
    if following.startswith(("<table", "::: {.kami-teacher-summary", "## ")):
        lines[first] = "# " + title
    return "\n".join(lines)


def prepare(text: str) -> tuple[str, dict[str, int]]:
    text = text.replace(r"\\textcircled", r"\textcircled")
    text = convert_simple_tables(text)
    text = promote_leading_title(text)
    # Remove filename captions while leaving image parsing to Pandoc/Lua.
    text = re.sub(r"!\[[^]]*\]\(([^)]+)\)", r"![](\1)", text)
    lines = text.splitlines()
    out: list[str] = []
    counts = {"answers": 0, "solutions": 0, "notes": 0, "images": 0}
    index = 0

    while index < len(lines):
        line = lines[index]

        answer = marker_match(line, "答案")
        if answer:
            end = answer_end(lines, index + 1)
            out.extend(fenced("kami-teacher-answer", [answer.group(1), *lines[index + 1 : end]]))
            counts["answers"] += 1
            index = end
            continue

        solution = marker_match(line, "(?:解析|解答)")
        if solution:
            end = solution_end(lines, index + 1)
            out.extend(fenced("kami-teacher-solution", [solution.group(1), *lines[index + 1 : end]]))
            counts["solutions"] += 1
            index = end
            continue

        note = marker_match(line, "(?:要点注释|知识补充|知识拓展)")
        if note:
            kind_match = re.search(r"【(要点注释|知识补充|知识拓展)】", line)
            kind = kind_match.group(1) if kind_match else "重点"
            end = note_end(lines, index + 1, kind)
            out.extend(fenced("kami-teacher-note", [note.group(1), *lines[index + 1 : end]], kind))
            counts["notes"] += 1
            index = end
            continue

        difficulty = marker_match(line, "难度")
        if difficulty:
            value = difficulty.group(1).strip() or "未标注"
            out.extend([rf"\noindent\textcolor{{KamiNoteFrame}}{{\textbf{{难度：{value}}}}}", ""])
            index += 1
            continue

        out.append(line)
        index += 1

    prepared = "\n".join(out).rstrip() + "\n"
    counts["images"] = len(re.findall(r"!\[\]\([^)]+\)", prepared))
    return prepared, counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Source Markdown")
    parser.add_argument("-o", "--output", type=Path, help="Prepared Markdown path")
    args = parser.parse_args()

    source = args.source.expanduser().resolve()
    output = args.output.expanduser().resolve() if args.output else source.with_name(source.stem + "-低饱和彩色教师版.md")
    prepared, counts = prepare(source.read_text(encoding="utf-8"))
    output.write_text(prepared, encoding="utf-8")
    print(output)
    print(" ".join(f"{key}={value}" for key, value in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
