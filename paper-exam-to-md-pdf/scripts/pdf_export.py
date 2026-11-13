#!/usr/bin/env python3
"""Incrementally export ONE explicit Markdown file without modifying it.

Python: export_pdf(Path('试卷.md'), Path('work'), mode='student')
CLI: python pdf_export.py 试卷.md --work-dir work --mode student
     --preview-pages 1,3,5     # one-based; add missing high-resolution previews

Requires existing pandoc, XeLaTeX, PyMuPDF and Pillow. Failed builds preserve the
previous PDF. Full diagnostics live in work/pdf-export-*/builds/*, while stdout
and the function return only a compact JSON summary. mode selects layout intent;
it NEVER strips answers: pass the actual student Markdown for student output.
An existing PDF is replaced only when its hash matches this work directory's
last successful output. For an unregistered or externally edited PDF, preserve
it and export a differently named Markdown copy, or explicitly back it up and
move it away before retrying.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import unquote, urlparse

import fitz
from PIL import Image, ImageDraw

HEADER = Path(__file__).resolve().parent.parent / 'assets' / 'transcript-header.tex'
FONT_CONFIG = {
    'mainfont': 'Times New Roman', 'CJKmainfont': 'Songti SC',
    'fallback': 'Arial Unicode MS', 'fontsize': '11pt',
    'geometry': ['a4paper', 'margin=2cm'],
}
SCHEMA = 1


class ExportError(RuntimeError):
    """A failed export; summary and log_directory are available to callers."""
    def __init__(self, summary: dict, log_directory: Path):
        self.summary = summary
        self.log_directory = str(log_directory)
        super().__init__('PDF export failed: ' + '; '.join(summary['issues'])
                         + f' (logs: {log_directory})')


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha(path: Path) -> str:
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256')
    return digest.hexdigest()


def _write_json(path: Path, value: dict) -> None:
    staged = path.with_name(path.name + '.tmp')
    staged.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    staged.replace(path)


def _run(args: list[str], cwd: Path, log: Path) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
    log.write_text(result.stdout + '\n' + result.stderr)
    if result.returncode:
        raise RuntimeError(f'{Path(args[0]).name} exited {result.returncode}; see {log.name}')
    return result.stdout


def _tool(name: str, fallback: str | None = None) -> str:
    value = shutil.which(name) or (fallback if fallback and Path(fallback).is_file() else None)
    if not value:
        raise RuntimeError(f'Required tool unavailable: {name}')
    return str(Path(value).absolute())


def _walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _images(ast: dict, base: Path) -> list[dict]:
    """Use Pandoc's parser so escaped, reference and spaced URLs resolve alike."""
    urls = []
    for node in _walk(ast):
        if node.get('t') == 'Image':
            urls.append(node['c'][-1][0])
        if node.get('t') in ('RawBlock', 'RawInline'):
            fmt, raw = node['c']
            if fmt in ('tex', 'latex'):
                if re.search(r'\\(?:input|include|bibliography|addbibresource)\b', raw):
                    raise RuntimeError('External TeX inputs are unsupported; inline the content')
                urls.extend(re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}', raw))
            elif re.search(r'<img\b', raw, re.I):
                raise RuntimeError('Raw HTML images are unsupported in XeLaTeX; use Markdown images')
    entries = []
    for url in sorted(set(urls)):
        parsed = urlparse(url)
        if parsed.scheme not in ('', 'file') or parsed.netloc:
            raise RuntimeError(f'Image must be a local file: {url}')
        path = Path(unquote(parsed.path))
        path = (base / path).resolve() if not path.is_absolute() else path.resolve()
        if not path.is_file():
            raise RuntimeError(f'Missing image: {path}')
        entries.append({'url': url, 'path': str(path), 'sha256': _file_sha(path)})
    return entries


def _prepare_tex(tex: str, mode: str = 'teacher') -> str:
    tex = re.sub(r'\\mathrm\s*\{\s*~?\s*米\s*\}', r'\\text{米}', tex)
    # Keep diagrams inline, bounded in both dimensions. implicit_figures is off.
    def size_image(match):
        options = match[1] or ''
        if re.search(r'\b(?:width|height)\s*=', options):
            return match[0]
        return r'\includegraphics[width=65mm,height=48mm,keepaspectratio,' + options + ']'
    tex = re.sub(r'\\includegraphics(?:\[([^\]]*)\])?', size_image, tex)
    # Wrap level 1-5 Chinese question headings; stop at every same/higher heading.
    sections = {'section': 1, 'subsection': 2, 'subsubsection': 3,
                'paragraph': 4, 'subparagraph': 5}
    heading = re.compile(r'\\(section|subsection|subsubsection|paragraph|subparagraph)\*?\{')
    all_headings = list(heading.finditer(tex))
    edits = []
    for index, item in enumerate(all_headings):
        tail = tex[item.end():]
        if not re.match(r'第\s*[0-9０-９]+\s*题(?:\}|[（(:：\s])', tail):
            continue
        level = sections[item[1]]
        end = tex.find(r'\end{document}', item.end())
        if end < 0:
            end = len(tex)
        for later in all_headings[index + 1:]:
            if sections[later[1]] <= level:
                end = later.start()
                break
        # Pandoc starts each heading's hypertarget before the heading command.
        prefix = tex.rfind('\\hypertarget', 0, item.start())
        start = prefix if prefix >= 0 and re.fullmatch(r'\\hypertarget\{[^{}]*\}\{\s*', tex[prefix:item.start()]) else item.start()
        next_target = tex.rfind('\\hypertarget', item.end(), end)
        if next_target >= 0 and re.fullmatch(r'\\hypertarget\{[^{}]*\}\{\s*', tex[next_target:end]):
            end = next_target
        edits.append((start, end))
    for start, end in reversed(edits):
        if mode == 'teacher':
            # Keep only the title and opening lines together. Teacher answers
            # stay in the normal page flow instead of moving a whole question.
            tex = tex[:start] + '\\Needspace{5\\baselineskip}\n' + tex[start:]
        else:
            tex = tex[:start] + '\\begin{transcriptquestion}\n' + tex[start:end] + '\n\\end{transcriptquestion}\n' + tex[end:]
    return tex


def _owned_pdf_hash(pdf: Path, state: dict) -> str | None:
    if not pdf.exists():
        return None
    current_hash = _file_sha(pdf)
    expected_hash = state.get('pdf_sha256')
    if not expected_hash or current_hash != expected_hash:
        reason = '没有本模块在当前 work_dir 的成功导出登记' if not expected_hash else '内容哈希与本模块上次输出不同，可能已被人工或其他程序修改'
        raise RuntimeError(
            f'拒绝覆盖现有 PDF：{pdf}；{reason}。'
            '请将 Markdown 复制为新文件名再导出，或确认备份并移走现有 PDF 后重跑；'
            '如曾用本模块导出，请先核对是否传入了原来的 work_dir。')
    return current_hash


def _issues(log: str) -> list[str]:
    patterns = r'(?:Missing character|Overfull \\[hv]box|Undefined control sequence|LaTeX Error|Package [^\n]* Error|Fatal error|Emergency stop)[^\n]*'
    return list(dict.fromkeys(re.findall(patterns, log)))


def _formula_page(doc) -> int:
    # Font evidence survives layout changes and recognizes TeX math even when
    # extracted Unicode loses a fraction or a radical.
    scores = []
    for page in doc:
        score = 0
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                for span in line['spans']:
                    if re.search(r'(?:CMMI|CMSY|CMEX|Math|Cambria)', span['font'], re.I):
                        score += len(span['text'])
                    score += len(re.findall(r'[∑∫√≠≤≥∞∈∴∵]', span['text'])) * 3
        scores.append(score)
    return max(range(len(scores)), key=scores.__getitem__) + 1


def _previews(pdf: Path, folder: Path, manifest: dict, requested, summary: dict) -> dict:
    pdf_hash = _file_sha(pdf)
    with fitz.open(pdf) as doc:
        page_count = len(doc)
        if requested is not None and any(isinstance(p, bool) or not isinstance(p, int) or p < 1 or p > page_count for p in requested):
            raise ValueError(f'preview_pages must be integers between 1 and {page_count}')
        # A manifest is accepted only for this exact PDF; never reuse page names
        # from an older version that happens to have the same number of pages.
        if manifest.get('pdf_sha256') != pdf_hash:
            manifest = {'pdf_sha256': pdf_hash, 'files': {}, 'pages': page_count}
        folder.mkdir(parents=True, exist_ok=True)
        wanted = sorted(set([1, _formula_page(doc), page_count] + (requested or [])))
        def valid(name):
            path = folder / name
            return path.is_file() and manifest['files'].get(name) == _file_sha(path)
        overview_name = '整册总览.jpg'
        if not valid(overview_name):
            tiles = []
            for i, page in enumerate(doc):
                pix = page.get_pixmap(matrix=fitz.Matrix(.45, .45), alpha=False)
                summary['preview_calls'] += 1
                im = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
                im.thumbnail((220, 312))
                tile = Image.new('RGB', (240, 340), '#eeeeee')
                tile.paste(im, ((240 - im.width) // 2, 22))
                ImageDraw.Draw(tile).text((8, 5), f'Page {i + 1}', fill='black')
                tiles.append(tile)
            sheet = Image.new('RGB', (960, 340 * math.ceil(page_count / 4)), 'white')
            for i, tile in enumerate(tiles):
                sheet.paste(tile, ((i % 4) * 240, (i // 4) * 340))
            sheet.save(folder / overview_name, quality=75)
            manifest['files'][overview_name] = _file_sha(folder / overview_name)
        for number in wanted:
            name = f'第{number:03}页.png'
            if not valid(name):
                doc[number - 1].get_pixmap(matrix=fitz.Matrix(1.7, 1.7), alpha=False).save(folder / name)
                summary['preview_calls'] += 1
                manifest['files'][name] = _file_sha(folder / name)
        # Only recognized pages belonging to the current manifest survive.
        for path in folder.iterdir():
            if (re.fullmatch(r'第\d+页\.png', path.name) or path.name == overview_name) and path.name not in manifest['files']:
                path.unlink()
    return manifest


def export_pdf(md_path: Path, work_dir: Path, mode='teacher', preview_pages=None) -> dict:
    started = time.monotonic()
    md_path, work_dir = Path(md_path).resolve(), Path(work_dir).resolve()
    pdf = md_path.with_suffix('.pdf')
    summary = {'status': 'failed', 'pages': 0, 'pdf': str(pdf), 'compile_calls': 0,
               'preview_calls': 0, 'elapsed_seconds': 0.0, 'issues': []}
    key = _sha(str(md_path).encode())[:16]
    folder = work_dir / f'pdf-export-{key}'
    folder.mkdir(parents=True, exist_ok=True)
    build = Path(tempfile.mkdtemp(prefix='run-', dir=folder))
    state_path = folder / 'state.json'
    try:
        if mode not in ('student', 'teacher'):
            raise ValueError('mode must be student or teacher')
        if not md_path.is_file() or md_path.suffix.lower() != '.md':
            raise ValueError(f'Pass an existing explicit .md file: {md_path}')
        if preview_pages is not None:
            preview_pages = list(preview_pages)
        try:
            state = json.loads(state_path.read_text())
        except (OSError, ValueError):
            state = {}
        original_pdf_hash = _owned_pdf_hash(pdf, state)
        pandoc = _tool('pandoc')
        xelatex = _tool('xelatex', '/Library/TeX/texbin/xelatex')
        versions = {name: _run([path, '--version'], md_path.parent, build / f'{name}-version.log')
                    for name, path in [('pandoc', pandoc), ('xelatex', xelatex)]}
        source_bytes = md_path.read_bytes()
        ast_text = _run([pandoc, str(md_path), '-f', 'markdown-implicit_figures', '-t', 'json'],
                        md_path.parent, build / 'pandoc-parse.log')
        ast = json.loads(ast_text)
        dependencies = _images(ast, md_path.parent)
        fingerprint_data = {'schema': SCHEMA, 'md_sha256': _sha(source_bytes),
                            'images': dependencies, 'module_sha256': _file_sha(Path(__file__)),
                            'header_sha256': _file_sha(HEADER), 'fonts': FONT_CONFIG,
                            'tools': {'pandoc': pandoc, 'xelatex': xelatex},
                            'versions': versions, 'mode': mode}
        fingerprint = _sha(json.dumps(fingerprint_data, sort_keys=True, ensure_ascii=False).encode())
        _write_json(build / 'fingerprint.json', fingerprint_data)
        cached = state.get('fingerprint') == fingerprint and original_pdf_hash is not None
        staged_pdf = None
        if cached:
            with fitz.open(pdf) as doc:
                summary['pages'] = len(doc)
            summary['status'] = 'cached'
        else:
            tex = build / 'document.tex'
            args = [pandoc, str(md_path), '-f', 'markdown-implicit_figures', '--standalone',
                    '--pdf-engine=xelatex', '-H', str(HEADER), '-o', str(tex)]
            for name in ('mainfont', 'CJKmainfont', 'fontsize'):
                args.extend(['-V', f'{name}={FONT_CONFIG[name]}'])
            for geometry in FONT_CONFIG['geometry']:
                args.extend(['-V', f'geometry:{geometry}'])
            _run(args, md_path.parent, build / 'pandoc-tex.log')
            tex.write_text(_prepare_tex(tex.read_text(), mode))
            for run in range(2):
                summary['compile_calls'] += 1
                _run([xelatex, '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error',
                      '-output-directory=' + str(build), str(tex)], md_path.parent,
                     build / f'xelatex-{run + 1}.log')
            diagnostics = tex.with_suffix('.log').read_text(errors='replace')
            summary['issues'] = _issues(diagnostics)
            if summary['issues']:
                raise RuntimeError('Compilation produced missing glyphs, overflow or TeX errors')
            staged_pdf = tex.with_suffix('.pdf')
            with fitz.open(staged_pdf) as doc:
                if len(doc) < 1 or doc.is_encrypted:
                    raise RuntimeError('Generated PDF is empty or encrypted')
                for page in doc:
                    if page.rect.width <= 0 or page.rect.height <= 0:
                        raise RuntimeError('Generated PDF has invalid page geometry')
                summary['pages'] = len(doc)
            # Source/image changes during compilation must not be blessed by a
            # fingerprint captured before the edit.
            if md_path.read_bytes() != source_bytes or any(_file_sha(Path(dep['path'])) != dep['sha256'] for dep in dependencies):
                raise RuntimeError('Source or image changed during compilation; retry export')
            summary['status'] = 'built'
        preview_pdf = pdf if cached else staged_pdf
        preview_folder = folder / 'previews' / _file_sha(preview_pdf)
        manifest = _previews(preview_pdf, preview_folder, state.get('previews', {}), preview_pages, summary)
        if cached and (not pdf.exists() or _file_sha(pdf) != original_pdf_hash):
            raise RuntimeError(
                f'PDF 在缓存核验期间发生外部变化：{pdf}。已保留当前文件，请检查后重跑。')
        # Render and validate requested previews before committing a new PDF.
        # Invalid page requests or renderer failures preserve the previous PDF.
        if not cached:
            with tempfile.NamedTemporaryFile(prefix='.' + pdf.stem + '-', suffix='.pdf', dir=pdf.parent, delete=False) as stream:
                staged_destination = Path(stream.name)
            try:
                shutil.copyfile(staged_pdf, staged_destination)
                current_pdf_hash = _file_sha(pdf) if pdf.exists() else None
                if current_pdf_hash != original_pdf_hash:
                    raise RuntimeError(
                        f'拒绝覆盖 PDF：{pdf} 在导出过程中发生外部变化。'
                        '已保留当前文件；请检查该文件，或将 Markdown 复制为新文件名再导出。')
                os.replace(staged_destination, pdf)
            finally:
                staged_destination.unlink(missing_ok=True)
        manifest['directory'] = str(preview_folder)
        _write_json(state_path, {'schema': SCHEMA, 'fingerprint': fingerprint,
                                'pdf_sha256': _file_sha(pdf), 'pages': summary['pages'],
                                'previews': manifest, 'last_build': str(build)})
        summary['elapsed_seconds'] = round(time.monotonic() - started, 3)
        _write_json(build / 'result.json', summary)
        return summary
    except Exception as exc:
        for path in build.glob('document.log'):
            summary['issues'].extend(_issues(path.read_text(errors='replace')))
        summary['issues'] = list(dict.fromkeys(summary['issues'] + [str(exc)]))
        summary['status'] = 'failed'
        summary['elapsed_seconds'] = round(time.monotonic() - started, 3)
        _write_json(build / 'result.json', summary)
        raise ExportError(summary, build) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('markdown', type=Path)
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--mode', choices=('teacher', 'student'), default='teacher')
    parser.add_argument('--preview-pages', help='Comma-separated one-based page numbers')
    args = parser.parse_args()
    try:
        pages = None if args.preview_pages is None else [int(p) for p in args.preview_pages.split(',') if p]
        result = export_pdf(args.markdown, args.work_dir, args.mode, pages)
    except ExportError as exc:
        print(json.dumps(exc.summary, ensure_ascii=False))
        return 1
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
