#!/usr/bin/env python3
"""Render prepared teacher-handout Markdown while preserving TeX and XeLaTeX logs."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


SKILL = Path(__file__).resolve().parent.parent


def run(command: list[str], cwd: Path) -> None:
    print("+", " ".join(command))
    result = subprocess.run(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode:
        tail = "\n".join(result.stdout.splitlines()[-80:])
        if tail:
            print(tail, file=sys.stderr)
        raise SystemExit(f"Command failed with exit code {result.returncode}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prepared", type=Path)
    parser.add_argument("-o", "--output", required=True, type=Path)
    parser.add_argument("--resource-root", type=Path, help="Directory containing relative images")
    parser.add_argument("--author", help="Optional PDF author metadata")
    parser.add_argument("--font-size", default="10pt")
    args = parser.parse_args()

    prepared = args.prepared.expanduser().resolve()
    pdf = args.output.expanduser().resolve()
    pdf.parent.mkdir(parents=True, exist_ok=True)
    tex = pdf.with_suffix(".tex")
    resource_root = (args.resource_root or prepared.parent).expanduser().resolve()
    xelatex = shutil.which("xelatex") or "/Library/TeX/texbin/xelatex"
    if not Path(xelatex).is_file():
        raise SystemExit("XeLaTeX executable not found")

    pandoc = [
        "pandoc", str(prepared),
        "--standalone",
        "--from=markdown+raw_tex+fenced_divs",
        f"--lua-filter={SKILL / 'scripts/teacher-handout-blocks.lua'}",
        f"--include-in-header={SKILL / 'assets/latex-teacher-kami-header.tex'}",
        "-V", "documentclass=ctexart",
        "-V", "CJKmainfont=Songti SC",
        "-V", "mainfont=Times New Roman",
        "-V", "geometry:a4paper",
        "-V", "geometry:margin=1.8cm",
        "-V", f"fontsize={args.font_size}",
        "-o", str(tex),
    ]
    if args.author:
        pandoc[-2:-2] = ["-M", f"author={args.author}"]
    run(pandoc, resource_root)

    command = [
        xelatex,
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        f"-output-directory={pdf.parent}",
        str(tex),
    ]
    run(command, resource_root)
    run(command, resource_root)
    if not pdf.exists() or pdf.stat().st_size == 0:
        raise SystemExit(f"PDF was not created: {pdf}")
    log = tex.with_suffix(".log")
    log_text = log.read_text(encoding="utf-8", errors="replace") if log.exists() else ""
    page_match = re.search(r"Output written on .*?\((\d+) p\s*ages?\)\.", log_text, re.S)
    if page_match:
        print(f"pages={page_match.group(1)}")
    print(pdf)
    print(tex)
    print(log)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
