#!/usr/bin/env python3
"""Local, file-backed transcription workflow. JSON summaries are intentionally small."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from urllib.parse import unquote, urlparse

VERSION = 1
QUESTION = re.compile(r'^### 第(\d+)题\s*$', re.M)
LINK = re.compile(r'(!?)\[[^\]]*\]\(([^\n]+?)\)')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def read_json(path, default=None):
    p = Path(path)
    return json.loads(p.read_text()) if p.exists() else default


def write_json(path, value):
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def atomic_write(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.tmp')
    temp.write_text(text)
    temp.replace(path)


def root(args):
    p = Path(args.workspace).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    (p / 'work').mkdir(exist_ok=True)
    (p / 'outputs').mkdir(exist_ok=True)
    return p


def local_links(text):
    for match in LINK.finditer(text):
        raw = match[2].strip()
        if raw.startswith('<'):
            target = raw[1:raw.index('>')]
        else:
            target = re.split(r'\s+["\']', raw, maxsplit=1)[0]
        parsed = urlparse(target)
        if parsed.scheme or target.startswith('#'):
            continue
        yield bool(match[1]), unquote(parsed.path)


def run_logged(command, cwd, log, timeout=1800):
    """No shell, no echoed commands or credentials; full output stays local."""
    start = time.monotonic()
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with Path(log).open('wb') as stream:
        try:
            result = subprocess.run(command, cwd=cwd, stdout=stream, stderr=stream, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f'工具超时；日志：{log}') from None
    metrics = {'elapsed_seconds': round(time.monotonic()-start, 3),
               'subprocess_calls': 1, 'log_bytes': Path(log).stat().st_size}
    if result.returncode:
        # Do not relay arbitrary service output: it may contain URLs or credentials.
        raise RuntimeError(f'工具退出码 {result.returncode}；日志：{log}')
    return metrics


def record_metrics(workspace, command, result):
    item = {'command': command, 'time': time.strftime('%Y-%m-%dT%H:%M:%S%z'), **result}
    with (workspace/'work/运行记录.jsonl').open('a') as f:
        f.write(json.dumps(item, ensure_ascii=False)+'\n')


def prepare(args):
    w = root(args)
    statefile = w/'work/来源缓存.json'
    old = read_json(statefile)
    if old:
        if old['url'] != args.url:
            raise ValueError('工作目录已属于另一来源；请使用新的工作目录')
        invalid = [p for p, h in old['artifacts'].items() if not Path(p).is_file() or digest(p) != h]
        if invalid:
            raise ValueError('来源缓存缺失或变化；请重新核对来源文件：'+str(invalid[:3]))
        return {'status': 'cached', 'network_calls': 0, 'source_index': old['source_index'], 'source_pdf': old['source_pdf']}
    if urlparse(args.url).hostname != 'mp.weixin.qq.com':
        raise ValueError('prepare 当前仅支持微信公众号；普通网页应按正文类型另行提取')
    metrics = {'network_calls': 0}
    if args.source_index:
        index = Path(args.source_index).expanduser().resolve()
    else:
        # Reuse the existing extraction implementation; do not duplicate its URL parser.
        extractor = Path(__file__).resolve().parents[2]/'weixin-article-to-pdf/weixin_exam_to_pdf.py'
        if not extractor.is_file():
            raise ValueError('缺少现有公众号提取脚本；可用 --source-index 导入已有提取结果')
        destination = w/'source'
        if destination.exists() and any(destination.iterdir()):
            raise ValueError('source 中已有未登记的工件；请核对后用 --source-index 导入，避免重复抓取')
        destination.mkdir(exist_ok=True)
        metrics.update(run_logged([sys.executable, str(extractor), args.url, str(destination)], w, w/'work/来源提取.log'))
        metrics['network_calls'] = 1  # one extractor invocation; not a count of HTTP image requests
        indices = list(destination.glob('*.md'))
        if len(indices) != 1:
            raise ValueError('未得到唯一文章索引；请检查来源提取日志')
        index = indices[0]
    text = index.read_text()
    urls = re.findall(r'^url:\s*["\']?(https?://[^\s"\']+)', text, re.M)
    if urls != [args.url]:
        raise ValueError('来源索引的 URL 与本次链接不符')
    pm = re.search(r'^print_pdf:\s*(.+)$', text, re.M)
    if not pm:
        raise ValueError('来源索引缺少 print_pdf')
    pdf = Path(json.loads(pm[1]) if pm[1].startswith('"') else pm[1]).expanduser()
    if not pdf.is_absolute():
        pdf = index.parent/pdf
    pdf = pdf.resolve()
    artifacts = {str(index): digest(index), str(pdf): digest(pdf)}
    for _, link in local_links(text):
        p = (index.parent/link).resolve()
        if not p.is_file():
            raise ValueError(f'来源链接不存在：{p}')
        artifacts[str(p)] = digest(p)
    raw = index.with_name(index.stem+'-raw-weixin.html')
    if not raw.is_file():
        raise ValueError('原始 HTML 缺失，来源提取尚不完整')
    artifacts[str(raw)] = digest(raw)
    meta = index.parent/(index.stem+'-images')/'metadata.json'
    if meta.is_file():
        artifacts[str(meta)] = digest(meta)
        for entry in read_json(meta).get('excluded_images', []):
            p = meta.parent/entry['filename']
            if not p.is_file():
                raise ValueError('被排除原图未保留：'+str(p))
            artifacts[str(p)] = digest(p)
    write_json(statefile, {'url': args.url, 'source_index':str(index), 'source_pdf':str(pdf), 'artifacts':artifacts})
    return {'status':'imported' if args.source_index else 'extracted', **metrics, 'source_index':str(index), 'source_pdf':str(pdf), 'files_verified':len(artifacts)}


def ocr(args):
    w = root(args)
    source = read_json(w/'work/来源缓存.json')
    pdf = Path(args.pdf).expanduser().resolve() if args.pdf else Path(source['source_pdf']) if source else None
    if pdf is None or not pdf.is_file():
        raise ValueError('先 prepare，或用 --pdf 指定待识别文件')
    key = fingerprint({'input_sha256':digest(pdf),'model':'vlm','ocr':True,'format':'md,json','language':'ch','schema':VERSION})
    target = w/'work/ocr-cache'/key
    receipt = target/'receipt.json'
    cached = read_json(receipt)
    if cached and all((target/name).is_file() and digest(target/name)==h for name,h in cached['artifacts'].items()):
        return {'status':'cached','ocr_calls':0,'cache_key':key,'markdown':str(target/cached['markdown']),'json':str(target/cached['json'])}
    if receipt.exists():
        raise ValueError('OCR缓存被修改；请保留证据并换工作目录，不自动重传')
    if target.exists() and any(target.iterdir()):
        raise ValueError('存在未完成OCR任务；先检查其日志及服务任务状态，避免重复提交')
    target.mkdir(parents=True, exist_ok=True)
    if bool(args.ocr_md) != bool(args.ocr_json):
        raise ValueError('--ocr-md 与 --ocr-json 必须同时提供')
    metrics = {'ocr_calls':0}
    if args.ocr_md:
        md, js = Path(args.ocr_md).expanduser().resolve(), Path(args.ocr_json).expanduser().resolve()
        # Explicitly imported OCR is tied to this input hash; it still needs original-image review.
        shutil.copy2(md, target/'识别草稿.md');shutil.copy2(js, target/'识别版面.json')
    else:
        # Public source exemption is tied to the exact PDF registered by prepare.
        public = source and str(pdf)==source['source_pdf'] and digest(pdf)==source['artifacts'].get(str(pdf))
        if not public and not args.allow_remote:
            raise ValueError('该本地文件未登记为本次公开链接素材；远程OCR须逐文件授权后加 --allow-remote')
        executable = shutil.which('mineru-open-api')
        if not executable:
            raise ValueError('mineru-open-api 不可用；未调用 MinerU。按 skill 检查现有 CLI/服务或说明回退')
        metrics.update(run_logged([executable,'extract',str(pdf),'--model','vlm','--ocr','--format','md,json','-o',str(target),'--timeout','1800'],w,target/'OCR.log'))
        metrics['ocr_calls']=1
    mds=list(target.glob('*.md'));jss=[p for p in target.glob('*.json') if p.name!='receipt.json']
    if len(mds)!=1 or len(jss)!=1 or not mds[0].stat().st_size:
        raise ValueError('OCR未得到唯一Markdown和JSON；请检查日志，未登记成功缓存')
    read_json(jss[0])
    write_json(receipt, {'input':str(pdf),'input_sha256':digest(pdf),'markdown':mds[0].name,'json':jss[0].name,'artifacts':{p.name:digest(p) for p in mds+jss},'imported':bool(args.ocr_md)})
    return {'status':'imported' if args.ocr_md else 'recognized',**metrics,'cache_key':key,'markdown':str(mds[0]),'json':str(jss[0])}


def parse_document(path):
    text = Path(path).read_text()
    matches=list(QUESTION.finditer(text))
    if not matches:
        raise ValueError('导入稿需用 ### 第N题 划分；其他格式先转换，不按猜测拆题')
    appendix=re.search(r'^## 附录[：:].*$',text,re.M)
    body_end=appendix.start() if appendix else len(text)
    sections=[s for s in re.finditer(r'^## (?!附录)(.+)$',text,re.M) if s.start()<body_end]
    preambles={}
    for i,s in enumerate(sections):
        end=sections[i+1].start() if i+1<len(sections) else body_end
        first=next((m for m in matches if s.end()<m.start()<end),None)
        if first is None:
            raise ValueError('分节标题下没有可识别题目，未丢弃正文：'+s[1])
        intro=text[s.end():first.start()].strip()
        if intro:preambles[first[1]]=intro
    items=[]
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else body_end
        content=text[m.end():end].strip()
        content=re.split(r'^## ',content,flags=re.M)[0].strip()
        section=next((s[1] for s in reversed(sections) if s.start()<m.start()),'')
        items.append({'id':int(m[1]),'section':section,'body':content})
    prefix=text[:matches[0].start()]
    if sections:
        prefix=prefix[:sections[0].start()]
    title=re.search(r'^# (.+)$',text,re.M)
    return {'title':title[1] if title else '', 'prefix':prefix.strip(), 'questions':items, 'appendix':text[body_end:].strip(), 'section_preambles':preambles}


def copy_dependencies(md, workspace):
    for _,link in local_links(md.read_text()):
        origin=(md.parent/link).resolve()
        if not origin.is_file():
            raise ValueError('导入稿链接不存在：'+str(origin))
        # Preserve the relative layout, but never let imported links escape the workspace.
        dest=(workspace/'outputs'/link).resolve()
        if not dest.is_relative_to(workspace):
            raise ValueError('链接越出工作目录，需先整理为相对附件：'+link)
        if dest.exists():
            if digest(dest)!=digest(origin):
                raise ValueError('不同内容的同名附件，不覆盖：'+str(dest))
        else:
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(origin,dest)


def question_hash(q,w):
    fields={k:q.get(k,'') for k in ['section','stem','solution','notes']}
    images={}
    for value in fields.values():
        for is_image,link in local_links(value):
            p=(w/'outputs'/link).resolve()
            if is_image:images[link]=digest(p) if p.is_file() else None
    return fingerprint({'fields':fields,'images':images})


def import_reviewed(args):
    w=root(args);student=Path(args.student).expanduser().resolve();teacher=Path(args.teacher).expanduser().resolve()
    s,t=parse_document(student),parse_document(teacher)
    if [q['id'] for q in s['questions']]!=[q['id'] for q in t['questions']]:
        raise ValueError('双版题号不一致')
    questions=[]
    for sq,tq in zip(s['questions'],t['questions']):
        stem,sep,solution=tq['body'].partition('**答案**')
        if not sep or stem.strip()!=sq['body'] or sq['section']!=tq['section']:
            raise ValueError(f'第{sq["id"]}题双版题干不一致，或缺少 **答案** 分隔')
        solution='**答案**'+solution
        solution,marker,note=solution.partition('**转录校注')
        questions.append({'id':sq['id'],'section':sq['section'],'stem':sq['body'],'solution':solution.strip(),'notes':('**转录校注'+note).strip() if marker else '', 'review':{'state':'imported_reviewed','evidence':[str(student),str(teacher)]}})
    title=args.title or s['title'].split('·')[0]
    url=re.search(r'https?://mp\.weixin\.qq\.com/[^\s)]+',s['prefix'])
    data={'schema_version':VERSION,'title':title,'source_url':url[0] if url else '', 'expected_questions':len(questions), 'prefixes':{'student':s['prefix'],'teacher':t['prefix']},'appendices':{'student':s['appendix'],'teacher':t['appendix']}, 'questions':questions, 'layout':{'keep_student_questions':True}, 'provenance':{'inputs':{str(p):digest(p) for p in [student,teacher]},'scope':'导入已有校订稿，不代表本命令独立重解或重新核图'}}
    if s['section_preambles'] or t['section_preambles']:
        data['section_preambles']={'student':s['section_preambles'],'teacher':t['section_preambles']}
    copy_dependencies(student,w);copy_dependencies(teacher,w)
    for q in questions:q['review']['content_sha256']=question_hash(q,w)
    dest=w/'题目数据.json'
    if dest.exists() and read_json(dest)!=data:
        raise ValueError('题目数据已有不同内容；请在现有JSON内按题修订，或使用新的工作目录')
    if not dest.exists():write_json(dest,data)
    return {'status':'imported','questions':len(questions),'data':str(dest)}


def load_data(w):
    data=read_json(w/'题目数据.json')
    if not data or data.get('schema_version')!=VERSION:
        raise ValueError('缺少支持版本的题目数据.json；先 import-reviewed 或按 schema 建立草稿')
    if not re.search(r'[\u3400-\u9fff]',data.get('title','')) or re.search(r'[/\\\x00]',data['title']):
        raise ValueError('标题需为中文语义化文件名，且不含路径分隔符')
    return data


def validate(data,w):
    errors=[];warnings=[];ids=[q['id'] for q in data['questions']]
    expected=data.get('expected_questions',len(ids))
    if ids!=list(range(1,expected+1)):
        errors.append({'code':'question_numbers','actual':ids,'expected':expected})
    for q in data['questions']:
        n=q['id'];stem=q.get('stem','');solution=q.get('solution','');notes=q.get('notes','')
        if not stem.strip():errors.append({'id':n,'code':'empty_stem'})
        if re.search(r'\*\*(?:答案|原文解析|转录校注)|【(?:答案|解析)】',stem):
            errors.append({'id':n,'code':'answer_in_stem'})
        if any(k in q.get('section','') for k in ['选择','单选','多选']):
            options=set(re.findall(r'(?<![A-Za-z])[A-D][.．、]',stem))
            if {x[0] for x in options}!=set('ABCD'):
                errors.append({'id':n,'code':'missing_choices','found':sorted(options)})
        # Only labels at paragraph starts; a reference such as 沿（1）中的轨道 is not a subquestion.
        parts=[int(x) for x in re.findall(r'^[（(](\d+)[）)]',stem,re.M)]
        if parts and parts!=list(range(1,len(parts)+1)):
            warnings.append({'id':n,'code':'subquestion_sequence','found':parts})
        for field,text in [('stem',stem),('solution',solution),('notes',notes)]:
            if len(re.findall(r'(?<!\\)\$',text))%2:
                errors.append({'id':n,'field':field,'code':'unpaired_math_delimiter'})
            for is_image,link in local_links(text):
                p=(w/'outputs'/link).resolve()
                if not p.is_file():errors.append({'id':n,'code':'missing_image' if is_image else 'missing_link','path':link})
                if field=='stem' and is_image and re.search(r'解析|答案|solution|answer',link,re.I):
                    errors.append({'id':n,'code':'solution_image_in_student','path':link})
        if not solution.strip():warnings.append({'id':n,'code':'no_source_solution'})
        if q.get('review',{}).get('state') not in ['imported_reviewed','reviewed']:
            warnings.append({'id':n,'code':'needs_image_review'})
        elif q.get('review',{}).get('content_sha256')!=question_hash(q,w):
            warnings.append({'id':n,'code':'review_stale','action':'内容或题图改变，重新核对后登记复核'})
    for edition,text in data.get('appendices',{}).items():
        for _,link in local_links(text):
            if not (w/'outputs'/link).is_file():errors.append({'code':'missing_appendix','edition':edition,'path':link})
    for edition,preambles in data.get('section_preambles',{}).items():
        for qid,text in preambles.items():
            if qid not in {str(n) for n in ids}:
                errors.append({'code':'orphan_section_preamble','edition':edition,'id':qid})
            if len(re.findall(r'(?<!\\)\$',text))%2:
                errors.append({'code':'unpaired_math_delimiter','edition':edition,'field':'section_preamble','id':qid})
            if edition=='student' and re.search(r'\*\*(?:答案|原文解析|转录校注)|【(?:答案|解析)】',text):
                errors.append({'code':'answer_in_student_preamble','id':qid})
            for _,link in local_links(text):
                if not (w/'outputs'/link).is_file():errors.append({'code':'missing_preamble_link','edition':edition,'id':qid,'path':link})
    return errors,warnings


def render_markdown(data,edition):
    teacher=edition in ['teacher','full']
    source_edition=edition if edition!='full' else ('teacher' if any(q.get('solution') for q in data['questions']) else 'student')
    prefix=data['prefixes'][source_edition]
    if edition=='full':prefix=re.sub(r'^# .+$','# '+data['title']+'·完整转录版',prefix,count=1,flags=re.M)
    lines=[prefix];section=None
    for q in data['questions']:
        if q['section']!=section:
            section=q['section'];lines.append('## '+section)
        intro=data.get('section_preambles',{}).get(source_edition,{}).get(str(q['id']))
        if intro:lines.append(intro)
        lines.extend([f'### 第{q["id"]}题',q['stem']])
        if teacher:
            if q.get('solution'):lines.append(q['solution'])
            if q.get('notes'):lines.append(q['notes'])
    lines.append(data.get('appendices',{}).get(source_edition,''))
    return '\n\n'.join(x.strip() for x in lines if x.strip())+'\n'


def plan_data(data,w):
    previous=read_json(w/'work/构建状态.json',{})
    per_question={str(q['id']):{'stem':fingerprint(q['stem']),'solution':fingerprint([q.get('solution'),q.get('notes')]),'review':q.get('review',{})} for q in data['questions']}
    changes=[]
    for qid,now in per_question.items():
        before=previous.get('questions',{}).get(qid,{})
        fields=[name for name in ['stem','solution'] if now[name]!=before.get(name)]
        if fields:changes.append({'id':int(qid),'changed_fields':fields})
    errors,warnings=validate(data,w)
    files={edition:w/'outputs'/(data['title']+'-'+label+'.md') for edition,label in [('full','完整转录版'),('student','题目转录版'),('teacher','原文解析转录版')]}
    dirty=[]
    for edition,path in files.items():
        text=render_markdown(data,edition)
        if not path.is_file() or path.read_text()!=text:dirty.append(edition)
    return {'changed_questions':changes,'dirty_markdown_editions':dirty,'errors':errors,'warnings':warnings},per_question,files


def plan(args):
    w=root(args);data=load_data(w);result,_,_=plan_data(data,w)
    packet={'source_url':data.get('source_url'),'changed_questions':result['changed_questions'],'errors':result['errors'],'warnings':result['warnings'], 'instructions':'按题读取JSON与对应原图；自动检查不证明数学正确。改动处的既有复核需重新确认。'}
    write_json(w/'work/待复核清单.json',packet)
    return {'status':'ready' if not result['errors'] else 'invalid',**result,'review_packet':str(w/'work/待复核清单.json')}


def build(args):
    w=root(args)
    datafile=w/'题目数据.json'
    write_json(w/'work/最终验收.json',{'status':'building','data_sha256':digest(datafile) if datafile.is_file() else None,'note':'尚未完成本轮构建，不能沿用上轮验收'})
    data=load_data(w);result,questions,files=plan_data(data,w)
    if result['errors']:
        write_json(w/'work/待复核清单.json',result)
        raise ValueError('结构检查失败；见 work/待复核清单.json，仅修复受影响题目')
    old=read_json(w/'work/构建状态.json',{});managed=old.get('outputs',{});new_managed=dict(managed);built=[];cached=[];pdf_results={}
    for edition in args.editions.split(','):
        if edition not in files:raise ValueError('版本只能为 full,student,teacher')
        md=files[edition];text=render_markdown(data,edition)
        if md.exists() and md.read_text()!=text:
            if managed.get(str(md))!=digest(md):
                raise ValueError('输出稿被另行编辑；请把修改合入题目数据，未覆盖：'+str(md))
        if not md.exists() or md.read_text()!=text:
            atomic_write(md,text);built.append(edition)
        else:cached.append(edition)
        new_managed[str(md)]=digest(md)
        # Record generated Markdown ownership even if the subsequent compiler fails.
        # Keep the old question baseline until all requested editions succeed.
        write_json(w/'work/构建状态.json',{'schema_version':VERSION,'questions':old.get('questions',{}),'outputs':new_managed})
        if args.pdf:
            from pdf_export import export_pdf
            pdf_results[edition]=export_pdf(md,w/'work/pdf',mode='teacher' if edition=='full' else edition)
    write_json(w/'work/构建状态.json',{'schema_version':VERSION,'questions':questions,'outputs':new_managed})
    check={'status':'built','data_sha256':digest(w/'题目数据.json'),'questions':len(questions),'errors':result['errors'],'warnings':result['warnings'],'pdf':pdf_results,'mathematics':'未由自动检查证明；以逐题核图和独立复核证据为准'}
    write_json(w/'work/最终验收.json',check)
    return {'status':'built','markdown_built':built,'markdown_cached':cached,'changed_questions':result['changed_questions'],'pdf':pdf_results,'warnings':result['warnings'],'verification':str(w/'work/最终验收.json')}


def inspect_question(args):
    w=root(args);data=load_data(w)
    q=next((q for q in data['questions'] if q['id']==args.question),None)
    if q is None:raise ValueError('题号不存在')
    return q


def record_review(args):
    w=root(args);data=load_data(w)
    q=next((q for q in data['questions'] if q['id']==args.question),None)
    if q is None:raise ValueError('题号不存在')
    evidence=Path(args.evidence).expanduser().resolve()
    if not evidence.is_file() or not evidence.stat().st_size:raise ValueError('需提供已实际完成的核图/复核记录文件')
    q['review']={'state':'reviewed','reviewer':args.reviewer,'content_sha256':question_hash(q,w),'evidence':[str(evidence)],'evidence_sha256':digest(evidence)}
    write_json(w/'题目数据.json',data)
    return {'status':'recorded','question':args.question,'scope':'只登记所提供的复核证据，不由此命令自动核图或证明数学正确'}


def crop(args):
    import fitz
    w=root(args);pdf=Path(args.source_pdf).expanduser().resolve()
    name=args.name
    if not re.search(r'[\u3400-\u9fff]',name) or re.search(r'[/\\\x00]',name):raise ValueError('题图名应为中文语义化名称，不能含路径分隔符')
    box=[float(x) for x in args.bbox.split(',')]
    if len(box)!=4 or not(0<=box[0]<box[2]<=1000 and 0<=box[1]<box[3]<=1000):raise ValueError('bbox需为对应OCR输入PDF的0—1000归一化坐标：x1,y1,x2,y2')
    key=fingerprint({'pdf':digest(pdf),'page':args.page,'bbox':box,'margin':args.margin,'scale':2})
    target=w/'outputs/题图'/(name+'.png');record=w/'work/题图记录'/(name+'.json')
    old=read_json(record)
    if old and old['key']==key and target.is_file() and digest(target)==old['image_sha256']:
        return {'status':'cached','image':str(target),'render_calls':0}
    if target.exists() and (not old or digest(target)!=old['image_sha256']):raise ValueError('同名题图不是当前流程生成或已被改动，未覆盖：'+str(target))
    with fitz.open(pdf) as doc:
        if not 1<=args.page<=len(doc):raise ValueError('原图页码超出范围')
        page=doc[args.page-1];rect=page.rect
        x1,y1,x2,y2=box;m=args.margin
        if m<0:raise ValueError('margin不能为负，避免自动裁掉标注')
        clip=fitz.Rect(max(0,x1-m)*rect.width/1000,max(0,y1-m)*rect.height/1000,min(1000,x2+m)*rect.width/1000,min(1000,y2+m)*rect.height/1000)
        target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name('.'+target.name)
        page.get_pixmap(matrix=fitz.Matrix(2,2),clip=clip).save(temp);temp.replace(target)
    write_json(record,{'key':key,'source_pdf':str(pdf),'page':args.page,'bbox':box,'margin':args.margin,'image_sha256':digest(target),'visually_reviewed':False})
    return {'status':'cropped','image':str(target),'markdown_link':'题图/'+target.name,'render_calls':1,'needs_visual_review':True}


def summarize_ocr(args):
    w=root(args);text=Path(args.ocr_md).read_text()
    starts=list(re.finditer(r'^(\d+)[.．、]\s*',text,re.M));occurrences={};diffs=[];alerts=[]
    headers=list(re.finditer(r'^#{1,6}\s+(.+)$',text,re.M))
    for i,m in enumerate(starts):
        block=text[m.end():starts[i+1].start() if i+1<len(starts) else len(text)].strip()
        stem=re.split(r'【答案】|\*\*答案\*\*',block,maxsplit=1)[0]
        stem=re.split(r'^#{1,6} ',stem,flags=re.M)[0].strip()
        occurrences.setdefault(m[1],[]).append(stem)
        section=next((h[1] for h in reversed(headers) if h.start()<m.start()),'')
        if any(word in section for word in ['单选','多选','选择题']):
            found=set(re.findall(r'(?<![A-Za-z])([A-D])[.．、]',stem))
            if found!=set('ABCD'):alerts.append({'id':int(m[1]),'occurrence':len(occurrences[m[1]]),'code':'incomplete_choices','found':sorted(found)})
            condition_text=re.split(r'(?<![A-Za-z])A[.．、]',stem,maxsplit=1)[0]
            circled=[ord(c)-ord('①')+1 for c in re.findall(r'[①-⑳]',condition_text)]
            if circled and circled!=list(range(1,max(circled)+1)):
                alerts.append({'id':int(m[1]),'occurrence':len(occurrences[m[1]]),'code':'statement_sequence','found':circled})
    for qid,versions in occurrences.items():
        if len(versions)>1 and len(set(versions))>1:
            # Store the text on disk; stdout only reports question numbers.
            diffs.append({'id':int(qid),'stems':versions})
    blocks=read_json(args.ocr_json) if args.ocr_json else []
    pages={}
    if isinstance(blocks,list):
        for b in blocks:
            hit=re.match(r'^(\d+)[.．、]\s*',b.get('text',''))
            if hit:pages.setdefault(hit[1],[]).append({'page':b.get('page_idx',0)+1,'bbox':b.get('bbox')})
    dest=w/'work/OCR待核题块.json'
    write_json(dest,{'questions':occurrences,'differences':diffs,'alerts':alerts,'locations':pages,'trusted':False})
    return {'status':'indexed','unique_question_count':len(occurrences),'differing_stem_ids':[x['id'] for x in diffs],'alerts':alerts,'packet':str(dest),'full_text_printed':False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    for name in ['prepare','ocr','import-reviewed','plan','build','question','record-review','crop','summarize-ocr']:
        p=sub.add_parser(name);p.add_argument('--workspace',required=True)
        if name=='prepare':p.add_argument('--url',required=True);p.add_argument('--source-index')
        if name=='ocr':
            p.add_argument('--pdf');p.add_argument('--ocr-md');p.add_argument('--ocr-json');p.add_argument('--allow-remote',action='store_true')
        if name=='import-reviewed':p.add_argument('--student',required=True);p.add_argument('--teacher',required=True);p.add_argument('--title')
        if name=='build':p.add_argument('--pdf',action='store_true');p.add_argument('--editions',default='full')
        if name=='question':p.add_argument('--question',type=int,required=True)
        if name=='record-review':p.add_argument('--question',type=int,required=True);p.add_argument('--evidence',required=True);p.add_argument('--reviewer',required=True)
        if name=='crop':
            p.add_argument('--source-pdf',required=True);p.add_argument('--page',type=int,required=True);p.add_argument('--bbox',required=True);p.add_argument('--name',required=True);p.add_argument('--margin',type=float,default=4)
        if name=='summarize-ocr':p.add_argument('--ocr-md',required=True);p.add_argument('--ocr-json')
    args=parser.parse_args();start=time.monotonic()
    functions={'prepare':prepare,'ocr':ocr,'import-reviewed':import_reviewed,'plan':plan,'build':build,'question':inspect_question,'record-review':record_review,'crop':crop,'summarize-ocr':summarize_ocr}
    try:
        result=functions[args.command](args)
        result['elapsed_seconds']=round(time.monotonic()-start,3)
        full_result=root(args)/'work/最近结果'/f'{args.command}.json'
        write_json(full_result,result)
        if args.command!='question':
            result=dict(result)
            for key,value in list(result.items()):
                if isinstance(value,list) and len(value)>8:
                    result[key]=value[:8];result[key+'_total']=len(value)
            result['full_result']=str(full_result)
        encoded=json.dumps(result,ensure_ascii=False)
        record_metrics(root(args),args.command,{'elapsed_seconds':result['elapsed_seconds'],'summary_chars':len(encoded),'token_usage':'not_measured'})
        print(encoded)
        return 1 if result.get('errors') else 0
    except (ValueError,RuntimeError,FileNotFoundError,KeyError,json.JSONDecodeError) as exc:
        print(json.dumps({'status':'error','message':str(exc)},ensure_ascii=False))
        return 1


if __name__=='__main__':
    sys.exit(main())
