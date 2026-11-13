#!/usr/bin/env python3
"""Build local XDF student PDFs from a verified teacher schema or reviewed JSON."""
import argparse
import collections
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

import fitz
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw

PREFIX = 'https://xdf-local.invalid/'
LINE_PT = 10.9 * 1.6
TYPE_GROUP = {'填空题': '填选题', '选择题': '填选题', '填选题': '填选题', '解答题': '解答题'}
DIFFICULTIES = ('基础题', '中档题', '难题')
CSS = '''
h2, h1.doc-title + h2 {
 text-align:left!important; font-size:13pt!important; color:#24272d!important;
 font-weight:700!important; margin:35pt 0 12pt!important; padding:0!important;
 border:none!important; letter-spacing:normal!important;
}
h3 {font-size:11.5pt!important;color:#24272d!important;font-weight:700!important;
 margin:18pt 0 56pt!important;padding:0!important;border:none!important;}
a.audit-marker:has(> h2), a.audit-marker:has(> h3), a.audit-marker:has(> h1)
 {break-after:avoid;page-break-after:avoid;break-inside:avoid;}
.question-block {display:flow-root;break-inside:avoid;page-break-inside:avoid;
 margin:0 0 42pt!important;}
.question-block > :last-child {margin-bottom:0!important;}
a.audit-marker {display:block;color:inherit!important;text-decoration:none!important;}
'''


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def clean_stem(raw):
    removed = []
    lines, editorial = [], False
    for line in raw.splitlines():
        quoted = bool(re.match(r'^\s*>', line))
        if quoted and re.match(r'^\s*>\s*(?:\*\*)?(?:校订提示|编者注)', line):
            editorial = True
        elif not quoted and line.strip():
            editorial = False
        if editorial and (quoted or not line.strip()):
            removed.append(line)
        else:
            lines.append(line)
    text = '\n'.join(lines)
    def remove(match):
        removed.append(match[0])
        return ''
    text = re.sub(r'!\[[^\]]*\]\((?:<[^>\n]+>|[^()\n]+)\)', remove, text)
    text = re.sub(r'!\[\[[^\]\n]+\]\]', remove, text)
    text = re.sub(r'<img\b[^>]*>', remove, text, flags=re.I)
    text = re.sub(r'\n{3,}', '\n\n', text).strip()
    require(bool(text), '删除提示和图片后题干为空')
    require(not re.search(r'!\[|<img\b', text, re.I), '存在未支持的图片语法，需人工适配')
    require(not re.search(r'^\s*(?:#{1,6}\s|\*\*|【)?(?:来源[：:]|原成品参考|参考答案|本题分析|校订提示)', text, re.M),
            '题干有来源或教师栏目残留，请检查栏目边界')
    prose = re.sub(r'\$\$[\s\S]+?\$\$|\$[^$\n]+?\$', '', text)
    require(not re.search(r'<\/?[a-zA-Z][^>]*>', prose), '题干有额外 HTML，请先转换为纯题目 Markdown')
    return text, removed


def extract(src, title):
    if src.suffix.lower() == '.json':
        data = json.loads(src.read_text(encoding='utf-8'))
        title = title or data.get('title', '')
        candidates = data['questions']
    else:
        text = src.read_text(encoding='utf-8')
        boundaries = list(re.finditer(r'^(### |##### )(.+)$', text, re.M))
        candidates, category = [], None
        for i, match in enumerate(boundaries):
            if match[1] == '### ':
                category = match[2].strip()
                continue
            block = text[match.end():boundaries[i+1].start() if i+1 < len(boundaries) else len(text)]
            qid = match[2].split('｜')[0].strip()
            raw_match = re.search(r'^###### 原题与原成品内容\s*\n([\s\S]*?)(?=^###### |\Z)', block, re.M)
            link = re.search(r'\[原卷第(\d+)题\]\(<([^>]+)>\)', block)
            require(category and raw_match and link, f'{qid}: 不是受支持的教师汇编结构，缺分类、原题栏目或来源')
            candidates.append(dict(id=qid, category=category, stem=raw_match[1].strip(),
                                   question_type=next((t for t in TYPE_GROUP if t in match[2]), None),
                                   source=dict(link=link[2], original_number=int(link[1]))))
        if not title:
            heading = re.search(r'^## (.+)$', text, re.M)
            title = heading[1].strip() if heading else src.stem
    require(candidates, '未识别到题目；请使用支持的教师汇编结构或经核对的 JSON')
    require(title and '\n' not in title and not re.search(r'[<>$]', title), '标题不能为空或包含换行、HTML、数学定界符')
    rows, seen = [], set()
    for n, q in enumerate(candidates, 1):
        require(all(q.get(k) for k in ('id', 'category', 'stem', 'source')), f'第{n}题缺字段')
        require(isinstance(q['id'], str) and q['id'] not in seen, f'第{n}题 ID 非字符串或重复')
        require(isinstance(q['category'], str) and '\n' not in q['category'] and not re.search(r'[<>$]', q['category']),
                f'第{n}题分类名称无效')
        seen.add(q['id'])
        stem, removed = clean_stem(q['stem'])
        rows.append(dict(number=n, id=q['id'], category=q['category'], stem=stem, source=q['source'],
                         original_order=n, question_type=q.get('question_type'),
                         difficulty=q.get('difficulty'), difficulty_basis=q.get('difficulty_basis'),
                         removed=removed, raw_stem_sha256=hashlib.sha256(q['stem'].encode()).hexdigest(),
                         output_stem_sha256=hashlib.sha256(stem.encode()).hexdigest()))
    return title, rows


def stratify(rows, classification=None):
    annotations = json.loads(classification.read_text(encoding='utf-8')) if classification else {}
    require(isinstance(annotations, dict), '分层标注应为按题目 ID 索引的 JSON 对象')
    require(set(annotations) <= {q['id'] for q in rows}, '分层标注有源稿中不存在的 ID')
    missing = []
    for q in rows:
        entry = annotations.get(q['id'], {})
        require(isinstance(entry, dict), f'{q["id"]}: 分层标注应为对象')
        for key in ('question_type', 'difficulty', 'difficulty_basis'):
            if key in entry:
                q[key] = entry[key]
        if (not isinstance(q['question_type'], str) or q['question_type'] not in TYPE_GROUP or q['difficulty'] not in DIFFICULTIES
                or not isinstance(q['difficulty_basis'], str) or not q['difficulty_basis'].strip()):
            missing.append(q['id'])
        else:
            q['type_group'] = TYPE_GROUP[q['question_type']]
    require(not missing, '请先阅读原题并补充分层标注（题型、三档难度、依据），缺失或无效 ID：' + '、'.join(missing))
    categories = list(dict.fromkeys(q['category'] for q in rows))
    ordered = sorted(rows, key=lambda q: (categories.index(q['category']),
                     ('填选题', '解答题').index(q['type_group']), DIFFICULTIES.index(q['difficulty']), q['original_order']))
    for n, q in enumerate(ordered, 1):
        q['number'] = n
    return ordered


def prepare(title, rows, md, ledger, src, classification=None):
    parts = [f'---\ntitle: {title}\n---\n\n# {title}\n']
    category, group = None, None
    for q in rows:
        if q['category'] != category:
            category = q['category']
            parts.append(f'\n## {category}\n')
            group = None
        current = (q['type_group'], q['difficulty'])
        if current != group:
            group = current
            parts.append(f'\n### {current[0]} · {current[1]}\n')
        parts.append(f'\n<div class="question-block" data-question-number="{q["number"]}">\n\n'
                     f'**{q["number"]}.** {q["stem"]}\n\n</div>\n')
    md.write_text('\n'.join(parts), encoding='utf-8')
    data = dict(source_file=str(src), source_sha256=sha(src), title=title, questions=rows,
                question_count=len(rows), category_count=len(set(q['category'] for q in rows)),
                grouping_order='小主题 → 填选题/解答题 → 基础题/中档题/难题',
                layer_counts=dict(collections.Counter(f'{q["category"]} / {q["type_group"]} / {q["difficulty"]}' for q in rows)))
    if classification:
        data.update(classification_file=str(classification), classification_sha256=sha(classification))
    save(ledger, data)
    return data


def build(args, md):
    spec = importlib.util.spec_from_file_location('xdf_prose_engine', args.engine)
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    engine.CHROME = str(args.chrome or engine.CHROME)
    require(Path(engine.CHROME).is_file(), f'Chrome 不存在: {engine.CHROME}')
    engine.MINIMAL += CSS
    # The prose engine incorrectly rejects valid one-page PDFs. Its generic
    # check is replaced locally; validate() below checks every page and block.
    def engine_check(path, theme='minimal'):
        with fitz.open(path) as document:
            require(len(document) >= 1 and any(p.get_text().strip() for p in document),
                    '引擎未生成有效正文 PDF')
    engine.check_pdf = engine_check
    original = engine.tag_classes
    def tagged(html):
        result = original(html)
        soup = BeautifulSoup(result['html'], 'html.parser')
        require(not soup.select('a, img, .katex-error'), '正文有链接、图片或公式渲染错误，需人工检查')
        h = 0
        for node in list(soup.select('.question-block, h2, h3, h1.doc-title')):
            if 'question-block' in node.get('class', []):
                label = 'q/' + node['data-question-number']
            elif node.name in ('h2', 'h3'):
                h += 1
                label = 'h/' + str(h)
            else:
                label = 'title'
            marker = soup.new_tag('a', href=PREFIX+label)
            marker['class'] = 'audit-marker'
            node.wrap(marker)
        result['html'] = str(soup)
        return result
    engine.tag_classes = tagged
    build_dir = args.work / 'build'
    build_dir.mkdir()
    (build_dir / 'node_modules').symlink_to(args.modules, target_is_directory=True)
    old_argv, old_cwd = sys.argv, Path.cwd()
    try:
        sys.argv = [str(args.engine), '--src', str(md), '--out', str(args.work/'中间稿.pdf'),
                    '--build', str(build_dir), '--theme', 'minimal', '--no-page-number']
        engine.main()
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
    return build_dir / 'raw.pdf', build_dir / 'build_pretty.html'


def validate(raw_pdf, html, data, args):
    soup = BeautifulSoup(html.read_text(encoding='utf-8'), 'html.parser')
    count = len(data['questions'])
    require(len(soup.select('.question-block')) == count, 'HTML 题块数量不一致')
    expected_math = sum(len(re.findall(r'\$\$[\s\S]+?\$\$|\$[^$\n]+?\$', q['stem'])) for q in data['questions'])
    require(len(soup.select('.katex')) == expected_math and not soup.select('.katex-error'), '公式数量或渲染错误')
    doc = fitz.open(raw_pdf)
    groups, gaps, heading_gaps, errors, details = collections.defaultdict(list), [], [], [], []
    for pn, page in enumerate(doc, 1):
        if abs(page.rect.width-595.28)>2 or abs(page.rect.height-841.89)>2:
            errors.append(f'第{pn}页不是 A4')
        require(not page.get_images(), f'第{pn}页有图片残留')
        links = page.get_links()
        require(all(link.get('uri', '').startswith(PREFIX) for link in links), '存在非核验链接')
        spans = [s for b in page.get_text('dict')['blocks'] for l in b.get('lines', [])
                 for s in l['spans'] if s['text'].strip() and s['text'].strip() not in ('\u200b', '\ufeff')]
        owned = collections.defaultdict(list)
        for span in spans:
            box = fitz.Rect(span['bbox'])
            center = (box.tl + box.br) / 2
            owners = {link['uri'][len(PREFIX):] for link in links
                      if (fitz.Rect(link['from']) + (-3, -12, 3, 12)).contains(center)}
            if len(owners) != 1:
                errors.append(f'第{pn}页未归属或多重归属文字: {span["text"]!r}')
                continue
            label = next(iter(owners))
            owned[label].append(span)
            if box.x0 < 45 or box.x1 > 551 or box.y0 < 40 or box.y1 > 802:
                errors.append(f'第{pn}页越界: {span["text"]!r}')
        bounds = []
        for label, ss in owned.items():
            top = min(s['bbox'][1] for s in ss)
            bottom = max(s['bbox'][3] for s in ss)
            groups[label].append(dict(page=pn, top=top, bottom=bottom))
            bounds.append((top, bottom, label))
            if label.startswith('q/'):
                n = int(label.split('/')[1])
                if not any(re.match(r'^\s*'+str(n)+r'\.(?:\s|$)', s['text']) for s in ss):
                    errors.append(f'第{pn}页题块{n}缺题号，可能跨页')
                sizes = collections.Counter()
                for s in ss:
                    if 'KaTeX' not in s['font'] and 'Arial Unicode' not in s['font']:
                        sizes[round(s['size'], 2)] += len(s['text'])
                    rgb = [(s['color'] >> offset) & 255 for offset in (16, 8, 0)]
                    if max(rgb)-min(rgb)>12:
                        errors.append(f'第{pn}页题块{n}出现非灰阶文字，需检查公式错误')
                if sizes and abs(sizes.most_common(1)[0][0]-10.9)>0.06:
                    errors.append(f'第{pn}页题块{n}正文字号异常，可能发生整页缩放')
        bounds.sort()
        for prev, curr in zip(bounds, bounds[1:]):
            if curr[2].startswith('q/'):
                gap = curr[0] - prev[1]
                row = dict(page=pn, previous=prev[2], question=curr[2], gap_pt=round(gap, 2))
                if prev[2].startswith('q/'):
                    gaps.append(row)
                    if gap < LINE_PT*2-0.05:
                        errors.append(f'第{pn}页{curr[2]}题间净空不足两行: {gap:.2f}pt')
                elif prev[2].startswith('h/'):
                    heading_gaps.append(row)
                    if gap < LINE_PT*3-0.05:
                        errors.append(f'第{pn}页{curr[2]}标题净空不足三行: {gap:.2f}pt')
        details.append(dict(page=pn, question_labels=[b[2] for b in bounds if b[2].startswith('q/')]))
    expected = {'q/'+str(n) for n in range(1, count+1)}
    require({k for k in groups if k.startswith('q/')} == expected, 'PDF 题块缺失或多出')
    for label, fragments in groups.items():
        if len(fragments) != 1:
            errors.append(f'{label} 跨页: {[f["page"] for f in fragments]}')
    expected_order = ['q/'+str(n) for n in range(1, count+1)]
    if [q for p in details for q in p['question_labels']] != expected_order:
        errors.append('PDF 题序不一致或题块跨页')
    if len(heading_gaps) != len(soup.select('h3')):
        errors.append('分类标题未与首题在同一页或标题缺失')
    for heading in soup.select('h2, h3'):
        label = heading.parent['href'][len(PREFIX):]
        following = heading.find_next(class_='question-block')
        qlabel = 'q/' + following['data-question-number'] if following else None
        if label not in groups or qlabel not in groups or groups[label][0]['page'] != groups[qlabel][0]['page']:
            errors.append(f'标题与所属首题分离: {heading.get_text()}')
    html_labels = [(node.find_previous('h2').get_text(), node.find_previous('h3').get_text())
                   for node in soup.select('.question-block')]
    if html_labels != [(q['category'], f'{q["type_group"]} · {q["difficulty"]}') for q in data['questions']]:
        errors.append('HTML 题目分层与内部台账不一致')
    require(sha(Path(data['source_file'])) == data['source_sha256'], '原稿在构建期间被修改')
    if data.get('classification_file'):
        require(sha(Path(data['classification_file'])) == data['classification_sha256'], '分层标注在构建期间被修改')
    if '**' in ''.join(page.get_text() for page in doc):
        errors.append('PDF 有未渲染的 Markdown 加粗标记')
    report = dict(pages=len(doc), questions=count, categories=data['category_count'], rendered_math=expected_math,
                  grouping_order=data['grouping_order'], layer_counts=data['layer_counts'],
                  minimum_question_gap_pt=min((g['gap_pt'] for g in gaps), default=None),
                  minimum_heading_gap_pt=min((g['gap_pt'] for g in heading_gaps), default=None),
                  question_gap_threshold_pt=LINE_PT*2, heading_gap_threshold_pt=LINE_PT*3,
                  question_pages={k:v for k,v in groups.items() if k.startswith('q/')},
                  question_gaps=gaps, heading_gaps=heading_gaps, errors=errors,
                  visual_review='待人工查看拼图和复杂页', workbench_status='未上传，未验证工作台识别或匹配')
    save(args.work/'自动核验.json', report)
    require(not errors, 'PDF 核验失败；查看工作目录的自动核验.json')
    for page in doc:
        for link in page.get_links():
            page.delete_link(link)
    doc.save(args.out, garbage=4, deflate=True)
    doc.close()
    final = fitz.open(args.out)
    require(not any(p.get_links() for p in final), '交付 PDF 链接未清除')
    cards = []
    for pn, page in enumerate(final, 1):
        png = args.work/f'page-{pn:03}.png'
        page.get_pixmap(dpi=125).save(png)
        img = Image.open(png).convert('RGB')
        img.thumbnail((330, 467))
        card = Image.new('RGB', (350,500), '#dddddd')
        card.paste(img, ((350-img.width)//2,10))
        ImageDraw.Draw(card).text((10,480), str(pn), fill='black')
        cards.append(card)
    for start in range(0,len(cards),8):
        sheet = Image.new('RGB',(1400,1000),'#bbbbbb')
        for i,card in enumerate(cards[start:start+8]):
            sheet.paste(card,((i%4)*350,(i//4)*500))
        sheet.save(args.work/f'contact-{start//8+1}.png')
    report.update(pdf=str(args.out), pdf_sha256=sha(args.out), final_links=0)
    save(args.work/'自动核验.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('question_pages','question_gaps','heading_gaps')},ensure_ascii=False,indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--src', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--title')
    ap.add_argument('--classification', type=Path, help='按题目 ID 索引的题型、难度和依据 JSON；原稿未标注时先由 agent 编制')
    ap.add_argument('--modules', type=Path, default=os.environ.get('XDF_STUDENT_NODE_MODULES'))
    ap.add_argument('--engine', type=Path, default=Path.home()/'.workbuddy/skills/math-handout-pdf/scripts/build-prose-pretty.py')
    ap.add_argument('--chrome', type=Path)
    args = ap.parse_args()
    for key in ('src','out','work','engine','modules','chrome','classification'):
        value = getattr(args,key)
        if value is not None:
            setattr(args,key,Path(value).expanduser().resolve())
    require(args.src.is_file(), '源文件不存在')
    require(args.engine.is_file(), '现有 PDF 引擎不存在，请用 --engine 指定')
    require(args.modules and all((args.modules/p).is_dir() for p in ('katex','markdown-it')),
            '缺少已有 KaTeX/markdown-it 目录，请用 --modules 指定')
    require(args.out.suffix.lower()=='.pdf', '--out 必须是 PDF 文件名')
    require(not args.out.exists() and not args.out.with_suffix('.md').exists(), '输出文件已存在，请换新文件名')
    require(not args.work.exists(), '工作目录已存在，请使用新目录以保留恢复依据')
    title, rows = extract(args.src,args.title)
    rows = stratify(rows,args.classification)
    args.work.mkdir(parents=True)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    md = args.out.with_suffix('.md')
    data = prepare(title,rows,md,args.work/'来源与抽取台账.json',args.src,args.classification)
    raw_pdf, html = build(args,md)
    validate(raw_pdf,html,data,args)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError) as exc:
        print(f'未完成: {exc}',file=sys.stderr)
        sys.exit(1)
