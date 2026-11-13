#!/usr/bin/env python3
"""生成单页摘要草稿及独立简图；不生成正式多页合册。"""
from pathlib import Path
import argparse, collections, json, subprocess, shutil

def lit(value):
    return json.dumps(str(value),ensure_ascii=False)

def run(data_path, output, colors_path, learner_level=None):
    data=json.loads(data_path.read_text()); public=data['public_review']; items=data['items']
    ids=[str(i['id']) for i in items]
    if len(ids)!=len(set(ids)) or not ids: raise ValueError('作答项题号必须非空且唯一')
    for x in items:
        if x['stars'] is not None and (type(x['stars']) is not int or not 1<=x['stars']<=5):
            raise ValueError('星级须为1—5整数或null')
    routes=public.get('teaching_routes', [])
    levels=['基础巩固','常规提升','综合突破']
    if routes:
        if len(routes)!=3 or {r['level'] for r in routes}!=set(levels):
            raise ValueError('分层讲评须完整列出基础巩固、常规提升、综合突破三档')
        for r in routes:
            if not r.get('ids') or not set(r['ids']).issubset(ids):
                raise ValueError('分层讲评引用了不存在的题号')
            if any(next(x for x in items if x['id']==i)['stars'] is None for i in r['ids']):
                raise ValueError('待核题不能作为分层练习或复测题')
            if not r.get('goal') or not r.get('retest'):
                raise ValueError('分层讲评须写清讲评目标和复测方式')
    selected=learner_level or public.get('learner_level')
    if selected and selected not in levels: raise ValueError('无法识别学生层次；请保留三档供教师选择')
    selected_route=next((r for r in routes if r['level']==selected),None)
    if selected and selected_route is None: raise ValueError('缺少该学生层次的讲评安排')
    if selected_route:
        public=dict(public)
        ordered='、'.join(selected_route['ids'])
        public['actions']=[f'先讲 {ordered}。'+selected_route['goal'], selected_route['retest']]
        public['card_action']='先讲 '+ordered+'。'+selected_route['goal']
        public['learning_advice']=selected_route['retest']
        output=output/selected
    if not str(public.get('learning_advice', '')).strip():
        raise ValueError('请提供结合本卷考点的学习建议')
    palettes=json.loads(colors_path.read_text())
    if public['subject'] not in palettes:
        raise ValueError(f"缺少{public['subject']}经用户提供图片确认的配色；请先取得对应色卡并配置，不能自行套用其他色系。")
    palette=palettes[public['subject']]
    focus=public['focus']
    if len(focus)!=3: raise ValueError('请精选3个有题号支撑的重点')
    for f in focus:
        if not f['ids'] or not set(f['ids']).issubset(ids): raise ValueError('重点引用了不存在的题号')
    modules=collections.Counter(x['module'] for x in items)
    if set(modules)!=set(public['module_notes']): raise ValueError('模块介绍须与实际模块一致')
    counts=collections.Counter(x['stars'] for x in items)
    output.mkdir(parents=True,exist_ok=True)
    def text(s): return '#text('+lit(s)+')\n\n'
    def label(s): return '#label('+lit(s)+')\n'
    def compile_doc(name, card=False):
        # 独立简图的版心固定；超高时拒绝交付多张拼接图片。
        page='width: 190mm, height: 246mm' if card else 'paper: "a4"'
        t=f'''#set document(title: {lit(public['school']+' · '+public['subject']+'试卷快评')}, author: "")
#set page({page}, margin: (x: 15mm, top: 12mm, bottom: 12mm))
#set text(font: ("Songti SC", "Times New Roman"), size: {'9.4' if card else '10.5'}pt, fill: rgb("26312e"), lang: "zh")
#set par(leading: 0.6em, spacing: 0.65em)
#let accent = rgb({lit(palette['accent'])})
#let ink = rgb({lit(palette['ink'])})
#let tint = rgb({lit(palette['tint'])})
#let label(s) = block(above: 8pt, below: 5pt)[#text(size: 11pt, weight: "bold", fill: ink, s)]
'''
        t+='#text(size: 9pt, fill: ink, weight: "bold", '+lit(public['brand'])+')\n\n'
        t+='#text(size: 23pt, weight: "bold", '+lit(public['subject']+'试卷快评')+')\n\n'
        t+='#text(size: 12pt, weight: "bold", '+lit(public['school'])+')\n\n'+text(public['exam'])
        t+='#line(length: 100%, stroke: 2pt + accent)\n'
        t+=label('整卷看点｜'+public['headline'])
        t+='#block(fill: tint, inset: 9pt, width: 100%)[#text('+lit(public['verdict'])+')]\n'
        t+=label('题量与结构难度')
        t+=text(f'{len(items)}个独立作答项')
        rated=[(s,counts[s]) for s in range(1,6) if counts[s]]
        if counts[None]: rated.append(('待核',counts[None]))
        t+='#grid(columns: ('+','.join('1fr' for _ in rated)+'), gutter: 5pt, '
        for s,n in rated:
            title=str(s)+'星' if isinstance(s,int) else s
            t+='block(fill: tint, inset: 7pt, width: 100%)[#text(size: 9pt, fill: ink, '+lit(title)+') #linebreak() #text(size: 16pt, weight: "bold", '+lit(str(n))+') #text(size: 8pt)[项]],'
        t+=')\n'
        t+=label('考查重点')
        if len(modules)>9:
            t+='#table(columns: (1.1fr, 0.25fr, 1.6fr, 1.1fr, 0.25fr, 1.6fr), stroke: 0.4pt + rgb("e4e5e3"), fill: (x,y) => if y == 0 { tint } else { none }, inset: (x: 4pt, y: 4pt), table.header([模块], [项], [要求], [模块], [项], [要求]),'
            pairs=list(modules.items()); half=(len(pairs)+1)//2
            for idx in range(half):
                for pos in (idx,idx+half):
                    if pos < len(pairs):
                        m,n=pairs[pos]
                        for value in (m,str(n),public['module_notes'][m]):t+='text('+lit(value)+'),'
                    else:t+='[],[],[],'
        else:
            t+='#table(columns: (1.2fr, 0.8fr, 3fr), stroke: 0.4pt + rgb("e4e5e3"), fill: (x, y) => if y == 0 { tint } else { none }, inset: (x: 5pt, y: 4.5pt), table.header([模块], [作答项数], [主要要求]),'
            for m,n in modules.items():
                for value in (m,str(n),public['module_notes'][m]): t+='text('+lit(value)+'),'
        t+=')\n'
        t+=label('三处值得关注')
        for k,f in enumerate(focus,1):
            t+='#text(weight: "bold", fill: ink, '+lit(f'{k:02d}  '+f['title'])+')\n\n'+text(f['text'])
        if not card:
            t+=label(('讲评顺序｜'+selected) if selected else '考后怎么用')
            for a in public['actions']: t+=text('· '+a)
        else:
            t+='#block(fill: tint, inset: 8pt, width: 100%)[#text(weight: "bold", fill: ink)[讲评与复测] #linebreak() #text('+lit(public['card_action'])+')]\n'
        if public.get('learning_advice'):
            t+=label('学习建议')+text(public['learning_advice'])
        t+='#v(1fr)\n#text(size: 8pt, fill: rgb("626965"), '+lit(public['note'])+')\n\n'
        t+='#text(size: 7.5pt, fill: rgb("626965"), '+lit(public['source_label'])+')\n'
        source=output/(name+'.typ'); pdf=output/(name+'.pdf'); source.write_text(t)
        subprocess.run(['typst','compile',str(source),str(pdf)],check=True)
        info=subprocess.check_output(['pdfinfo',str(pdf)],text=True)
        pages=int(next(line.split(':',1)[1] for line in info.splitlines() if line.startswith('Pages:')))
        if pages!=1: raise ValueError(f'{name}生成{pages}页；请精简文案或调整版式再交付')
        subprocess.run(['pdftoppm','-singlefile','-scale-to','1800','-png',str(pdf),str(output/name)],check=True)
        return source,pdf
    for tool in ('typst','pdfinfo','pdftoppm'):
        if not shutil.which(tool): raise RuntimeError('缺少实际依赖：'+tool)
    compile_doc('整卷快评-家长学生版')
    compile_doc('简版快评图',card=True)
    md=['# '+public['school']+'｜'+public['subject']+'试卷快评',public['exam'],'## 整卷看点',public['verdict'],'## 考查重点','|模块|作答项数|主要要求|','|---|---:|---|']
    md += [f'|{m}|{n}|{public["module_notes"][m]}|' for m,n in modules.items()]
    md+=['## 值得关注']+[f'**{f["title"]}**：{f["text"]}' for f in focus]+['## 考后建议']+public['actions']+[public['note'],public['source_label']]
    if public.get('learning_advice'): md+=['## 学习建议',public['learning_advice']]
    (output/'整卷快评-家长学生版.md').write_text('\n\n'.join(md))
    (output/'出版统计.json').write_text(json.dumps({'items':len(items),'module_counts':dict(modules),'stars':{str(k):v for k,v in counts.items()},'palette':palette,'learner_level':selected},ensure_ascii=False,indent=2))
    print('已生成单页摘要草稿及简版图；完整快评、教师讲评和逐题图表须另行制作与核验。')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('data',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--colors',type=Path,default=Path(__file__).resolve().parents[1]/'assets/subject-colors.json')
    parser.add_argument('--learner-level',choices=['基础巩固','常规提升','综合突破'])
    a=parser.parse_args();run(a.data,a.output,a.colors,a.learner_level)
