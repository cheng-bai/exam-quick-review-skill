#!/usr/bin/env python3
"""Audit source/prepared/PDF invariants for the low-saturation teacher mode."""

from __future__ import annotations

import argparse
import importlib.util
import re
from pathlib import Path


def count_markers(text: str, labels: str) -> int:
    return len(re.findall(rf"^\s*(?:\*\*)?【(?:{labels})】", text, re.M))


def emit(level: str, name: str, detail: str) -> None:
    print(f"[{level.upper()}] {name}: {detail}")


def normalized(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def expected_prepared(source: str) -> str:
    module_path = Path(__file__).with_name("prepare_teacher_handout.py")
    spec = importlib.util.spec_from_file_location("teacher_prepare", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load prepare_teacher_handout.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result, _ = module.prepare(source)
    return result


def chinese_number(value: str) -> int | None:
    mapping = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    if value.isdigit():
        return int(value)
    return mapping.get(value)


def count_claim_warnings(text: str) -> list[str]:
    warnings: list[str] = []
    circled = "①②③④⑤⑥⑦⑧⑨⑩"
    for match in re.finditer(r"有以下([一二三四五六七八九十\d]+)个(?:代数式|式子|命题|结论|说法)", text):
        expected = chinese_number(match.group(1))
        segment = text[match.end() : match.end() + 800]
        stop = re.search(r"【难度】|^\s*(?:\*\*)?【例|^\s*\d+\s*[、．.]", segment, re.M)
        if stop:
            segment = segment[: stop.start()]
        actual = sum(1 for value in circled if value in segment)
        actual += len(set(re.findall(r"\\textcircled\{(\d+)\}", segment)))
        if expected is not None and actual and expected != actual:
            warnings.append(f"claimed={expected} enumerated={actual} near={match.start()}")
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--prepared", required=True, type=Path)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--log", required=True, type=Path)
    args = parser.parse_args()

    source = args.source.read_text(encoding="utf-8")
    prepared = args.prepared.read_text(encoding="utf-8")
    failures = 0

    checks = {
        "answers": (count_markers(source, "答案"), prepared.count(".kami-teacher-answer")),
        "solutions": (count_markers(source, "解析|解答"), prepared.count(".kami-teacher-solution")),
        "notes": (count_markers(source, "要点注释|知识补充|知识拓展"), prepared.count(".kami-teacher-note")),
        "images": (len(re.findall(r"!\[[^]]*\]\([^)]+\)", source)), len(re.findall(r"!\[\]\([^)]+\)", prepared))),
    }
    for name, (expected, actual) in checks.items():
        ok = expected == actual
        emit("pass" if ok else "fail", f"semantic.{name}", f"source={expected} prepared={actual}")
        failures += 0 if ok else 1

    raw_left = count_markers(prepared, "答案|解析|解答|要点注释|知识补充|知识拓展")
    emit("pass" if raw_left == 0 else "fail", "semantic.no_raw_markers", f"remaining={raw_left}")
    failures += 0 if raw_left == 0 else 1

    exact_transform = normalized(prepared) == normalized(expected_prepared(source))
    emit("pass" if exact_transform else "fail", "semantic.content_order", f"matches_deterministic_transform={exact_transform}")
    failures += 0 if exact_transform else 1

    html_residue = len(re.findall(r"</?(?:table|tr|td|th|br)\b", prepared, re.I))
    has_h1 = bool(re.search(r"^#\s+\S", prepared, re.M))
    emit("pass" if html_residue == 0 else "fail", "markdown.no_structural_html", f"remaining={html_residue}")
    emit("pass" if has_h1 else "fail", "markdown.has_primary_title", f"has_h1={has_h1}")
    failures += 0 if html_residue == 0 else 1
    failures += 0 if has_h1 else 1

    vector_warnings = []
    for symbol in sorted(set(re.findall(r"\\bar\{([A-Za-z])\}", source))):
        if re.search(rf"\\(?:vec|overrightarrow)\{{{re.escape(symbol)}\}}", source):
            vector_warnings.append(symbol)
    emit("warn" if vector_warnings else "pass", "math.vector_consistency", "bar/vector mixed symbols=" + (",".join(vector_warnings) or "none"))
    claim_warnings = count_claim_warnings(source)
    emit("warn" if claim_warnings else "pass", "math.enumeration_consistency", "; ".join(claim_warnings) or "none")

    try:
        from pypdf import PdfReader
    except Exception:
        from PyPDF2 import PdfReader  # type: ignore

    pdf_bytes = args.pdf.read_bytes()
    reader = PdfReader(str(args.pdf))
    pages = list(reader.pages)
    a4 = all(abs(float(page.mediabox.width) - 595.28) <= 3 and abs(float(page.mediabox.height) - 841.89) <= 3 for page in pages)
    emit("pass" if pages else "fail", "pdf.pages", f"count={len(pages)}")
    emit("pass" if a4 else "fail", "pdf.a4", f"all_a4={a4}")
    emit("pass" if pdf_bytes[:5] == b"%PDF-" and pdf_bytes.rstrip().endswith(b"%%EOF") else "fail", "pdf.structure", "header/eof")
    failures += 0 if pages else 1
    failures += 0 if a4 else 1
    failures += 0 if pdf_bytes[:5] == b"%PDF-" and pdf_bytes.rstrip().endswith(b"%%EOF") else 1

    text = "\n".join((page.extract_text() or "") for page in pages)
    lines = [line.strip() for line in text.splitlines()]
    visible_answer_titles = sum(line == "参考答案" for line in lines)
    visible_solution_titles = sum(line == "解析" for line in lines)
    emit("pass" if visible_answer_titles == checks["answers"][0] else "fail", "pdf.answer_titles", f"expected={checks['answers'][0]} actual={visible_answer_titles}")
    emit("pass" if visible_solution_titles == checks["solutions"][0] else "fail", "pdf.solution_titles", f"expected={checks['solutions'][0]} actual={visible_solution_titles}")
    failures += 0 if visible_answer_titles == checks["answers"][0] else 1
    failures += 0 if visible_solution_titles == checks["solutions"][0] else 1

    note_expected = {kind: count_markers(source, kind) for kind in ("要点注释", "知识补充", "知识拓展")}
    note_actual = {kind: sum(line == kind for line in lines) for kind in note_expected}
    notes_ok = note_expected == note_actual
    emit("pass" if notes_ok else "fail", "pdf.note_titles", f"expected={note_expected} actual={note_actual}")
    failures += 0 if notes_ok else 1

    image_objects = 0
    for page in pages:
        try:
            image_objects += len(page.images)
        except Exception:
            pass
    expected_images = checks["images"][0]
    emit("pass" if image_objects >= expected_images else "fail", "pdf.image_objects", f"expected_at_least={expected_images} actual={image_objects}")
    failures += 0 if image_objects >= expected_images else 1

    residues = sum(text.count(token) for token in ("【答案】", "【解析】", "![](", "**", "$$"))
    emit("pass" if residues == 0 else "fail", "pdf.no_source_residue", f"count={residues}")
    failures += 0 if residues == 0 else 1

    log_text = args.log.read_text(encoding="utf-8", errors="replace") if args.log.exists() else ""
    fatal_patterns = {
        "fatal": r"Fatal error|Emergency stop",
        "undefined": r"Undefined control sequence",
        "missing_character": r"Missing character",
        "latex_error": r"^! LaTeX Error",
    }
    log_hits = {name: len(re.findall(pattern, log_text, re.M)) for name, pattern in fatal_patterns.items()}
    log_ok = args.log.exists() and not any(log_hits.values())
    emit("pass" if log_ok else "fail", "latex.log_errors", f"exists={args.log.exists()} hits={log_hits}")
    failures += 0 if log_ok else 1
    overfull = len(re.findall(r"Overfull \\hbox|Overfull \\vbox", log_text))
    emit("warn" if overfull else "pass", "latex.overfull", f"count={overfull}")

    print(f"MECHANICAL SUMMARY status={'FAIL' if failures else 'PASS'} failures={failures}; visual/math review remains required")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
