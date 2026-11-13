#!/usr/bin/env python3
"""Audit rendered MathJax HTML and PDF artifacts for common OCR-to-PDF defects."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse


@dataclass
class Check:
    level: str
    name: str
    detail: str


def add(checks: list[Check], level: str, name: str, detail: str) -> None:
    checks.append(Check(level=level, name=name, detail=detail))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def img_srcs(markup: str) -> list[str]:
    pattern = re.compile(r"<img\b[^>]*\bsrc\s*=\s*(['\"])(.*?)\1", re.I | re.S)
    return [html.unescape(match.group(2).strip()) for match in pattern.finditer(markup)]


def is_local_image(src: str) -> bool:
    parsed = urlparse(src)
    return parsed.scheme in ("", "file") and not src.startswith(("data:", "#"))


def local_path_for_src(src: str, base_dir: Path) -> Path:
    parsed = urlparse(src)
    if parsed.scheme == "file":
        return Path(unquote(parsed.path))
    return base_dir / unquote(parsed.path)


def audit_html(path: Path, checks: list[Check]) -> None:
    if not path.exists():
        add(checks, "fail", "html.exists", f"Missing HTML: {path}")
        return

    markup = read_text(path)
    base_dir = path.parent

    p_dollar = len(re.findall(r"<p>\s*\$\$\s*</p>", markup, re.I))
    add(
        checks,
        "pass" if p_dollar == 0 else "fail",
        "html.no_paragraph_dollar_fences",
        f"paragraph-only $$ blocks: {p_dollar}",
    )

    figcaptions = len(re.findall(r"<figcaption\b", markup, re.I))
    add(
        checks,
        "pass" if figcaptions == 0 else "fail",
        "html.no_figcaptions",
        f"figcaption elements: {figcaptions}",
    )

    remote_images = [
        src for src in img_srcs(markup) if urlparse(src).scheme in ("http", "https")
    ]
    add(
        checks,
        "pass" if not remote_images else "fail",
        "html.no_remote_images",
        f"remote image refs: {len(remote_images)}",
    )

    mathjax_errors = len(re.findall(r"<mjx-merror\b", markup, re.I))
    add(
        checks,
        "pass" if mathjax_errors == 0 else "fail",
        "html.no_mathjax_errors",
        f"mjx-merror elements: {mathjax_errors}",
    )

    visible_filenames = re.findall(
        r">\s*[^<>\n]{0,120}\.(?:jpe?g|png|webp|gif)(?:\?[^<>\n]*)?\s*<",
        markup,
        re.I,
    )
    add(
        checks,
        "pass" if not visible_filenames else "fail",
        "html.no_visible_image_filenames",
        f"visible filename-like text nodes: {len(visible_filenames)}",
    )

    missing = []
    for src in img_srcs(markup):
        if is_local_image(src):
            candidate = local_path_for_src(src, base_dir)
            if not candidate.exists():
                missing.append(src)
    detail = f"local image refs: {len(img_srcs(markup)) - len(remote_images)}, missing: {len(missing)}"
    if missing:
        detail += "; first missing: " + ", ".join(missing[:3])
    add(checks, "pass" if not missing else "fail", "html.local_images_exist", detail)


def import_pdf_reader():
    try:
        from pypdf import PdfReader  # type: ignore

        return PdfReader
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore

            return PdfReader
        except Exception:
            return None


def page_size(page) -> tuple[float, float]:
    box = page.mediabox
    return float(box.width), float(box.height)


def is_a4(width: float, height: float, tolerance: float = 3.0) -> bool:
    a4 = (594.96, 841.92)
    return (
        abs(width - a4[0]) <= tolerance and abs(height - a4[1]) <= tolerance
    ) or (
        abs(width - a4[1]) <= tolerance and abs(height - a4[0]) <= tolerance
    )


def audit_pdf(path: Path, checks: list[Check], require_a4: bool) -> None:
    if not path.exists():
        add(checks, "fail", "pdf.exists", f"Missing PDF: {path}")
        return

    size = path.stat().st_size
    add(
        checks,
        "pass" if size > 0 else "fail",
        "pdf.nonempty_file",
        f"bytes: {size}",
    )

    reader_cls = import_pdf_reader()
    if reader_cls is None:
        add(checks, "warn", "pdf.reader_available", "Install pypdf or PyPDF2 for PDF checks")
        return

    try:
        reader = reader_cls(str(path))
        pages = list(reader.pages)
    except Exception as exc:
        add(checks, "fail", "pdf.readable", f"{type(exc).__name__}: {exc}")
        return

    add(checks, "pass" if pages else "fail", "pdf.page_count", f"pages: {len(pages)}")

    if require_a4 and pages:
        bad_sizes = []
        for index, page in enumerate(pages, start=1):
            width, height = page_size(page)
            if not is_a4(width, height):
                bad_sizes.append(f"{index}:{width:.1f}x{height:.1f}")
        add(
            checks,
            "pass" if not bad_sizes else "fail",
            "pdf.a4_page_size",
            "all pages A4" if not bad_sizes else "bad page sizes: " + ", ".join(bad_sizes[:8]),
        )

    extracted_parts: list[str] = []
    empty_text_pages = []
    for index, page in enumerate(pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if not text.strip():
            empty_text_pages.append(index)
        extracted_parts.append(text)

    text = "\n".join(extracted_parts)
    residues = {
        "$$": text.count("$$"),
        ".jpg": text.lower().count(".jpg"),
        ".jpeg": text.lower().count(".jpeg"),
        ".png": text.lower().count(".png"),
        ".webp": text.lower().count(".webp"),
    }
    residue_total = sum(residues.values())
    add(
        checks,
        "pass" if residue_total == 0 else "fail",
        "pdf.no_obvious_source_residue",
        ", ".join(f"{key}: {value}" for key, value in residues.items()),
    )

    if empty_text_pages:
        add(
            checks,
            "warn",
            "pdf.empty_text_pages",
            f"pages with no extractable text: {empty_text_pages[:20]}",
        )


def print_human(checks: Iterable[Check]) -> None:
    for check in checks:
        print(f"[{check.level.upper()}] {check.name}: {check.detail}")
    failed = sum(1 for check in checks if check.level == "fail")
    warned = sum(1 for check in checks if check.level == "warn")
    print(f"SUMMARY status={'FAIL' if failed else 'PASS'} failures={failed} warnings={warned}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", type=Path, help="Rendered HTML path")
    parser.add_argument("--pdf", type=Path, help="Rendered PDF path")
    parser.add_argument("--skip-a4", action="store_true", help="Do not require A4 PDF page size")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    if not args.html and not args.pdf:
        parser.error("Provide --html, --pdf, or both")

    checks: list[Check] = []
    if args.html:
        audit_html(args.html, checks)
    if args.pdf:
        audit_pdf(args.pdf, checks, require_a4=not args.skip_a4)

    if args.json:
        print(json.dumps([check.__dict__ for check in checks], ensure_ascii=False, indent=2))
    else:
        print_human(checks)

    return 1 if any(check.level == "fail" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
