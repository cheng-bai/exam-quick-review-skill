# Subagent Prompts

Use these prompts for independent passes. Replace placeholders with absolute paths. Ask agents to report issues only; keep edits in the parent agent so corrections remain coordinated.

## A. Markdown and OCR Structure Audit

```
Use the installed math-markdown-pdf-polisher skill.

Audit this OCR-derived math Markdown for structural and OCR problems:
- source: {source_md}
- working copy: {output_md}

Check headings, duplicated titles, broken Chinese phrases, missing or mismatched image references, raw HTML image tags, suspicious OCR fragments, and display-math fences. Do not edit files. Return a concise issue list with file/line evidence, severity, confidence, and suggested correction.
```

## B. HTML and PDF Rendering Audit

```
Use the installed math-markdown-pdf-polisher skill.

Audit the rendered artifacts for print/layout defects:
- Markdown: {output_md}
- HTML: {html}
- PDF: {pdf}

Check MathJax render errors, visible image filenames/captions, missing images, blank pages, page size, clipped formulas, formula overflow, excessive page breaks, and final-page integrity. Do not edit files. Return only reproducible findings with commands or page numbers.
```

## C. Math Concept and Formula Audit

```
Use the installed math-markdown-pdf-polisher skill.

Audit the working Markdown as high-school math teaching material:
- source: {source_md}
- working copy: {output_md}

Look for high-confidence mathematical errors introduced by OCR or formatting: swapped definitions, wrong inequality direction, missing conditions, mislabeled theorem axes/centers, determinant sign/order errors, and conic/geometry classification mistakes. Do not solve every problem from scratch. Do not edit files. Return only high-confidence issues with nearby context and a proposed correction; mark uncertain items separately.
```
