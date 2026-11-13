import fs from 'node:fs/promises';
import path from 'node:path';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';

const [input, out, flag, modules] = process.argv.slice(2);
if (!input || !out || (flag && (flag !== '--modules' || !modules)) || (!flag && modules)) {
  throw new Error('Usage: node export_review.mjs input.json output-dir [--modules node_modules-path]');
}
const d = JSON.parse(await fs.readFile(input, 'utf8'));
const colors = JSON.parse(await fs.readFile(new URL('../assets/subject-colors.json', import.meta.url), 'utf8'));
const palette = colors[d.public_review?.subject || '生物'];
if (!palette) throw new Error('缺少用户图片确认的学科配色，请先提供对应色卡并配置。');
if (!palette) throw new Error('学科配色未配置');
if (!d.title || !Array.isArray(d.items) || !d.items.length) throw new Error('缺少标题或逐题数据');
const ids = new Set();
for (const x of d.items) {
  if (!x.id || ids.has(x.id)) throw new Error(`缺失或重复题号: ${x.id}`);
  ids.add(x.id);
  if (x.stars !== null && (!Number.isInteger(x.stars) || x.stars < 1 || x.stars > 5)) throw new Error(`星级非法: ${x.id}`);
  if (x.score !== null && (!Number.isFinite(x.score) || x.score < 0)) throw new Error(`分值非法: ${x.id}`);
  for (const k of ['type','module','topic','reason','method','pitfall','verification']) {
    if (typeof x[k] !== 'string' || !x[k]) throw new Error(`${x.id} 缺少 ${k}`);
  }
}
const knownScores = d.items.filter(x => x.score !== null);
const scoreSum = knownScores.reduce((sum,x) => sum+x.score,0);
if (d.total_score !== null && d.total_score !== undefined) {
  if (!Number.isFinite(d.total_score) || d.total_score <= 0) throw new Error('总分非法');
  if (scoreSum > d.total_score || (knownScores.length === d.items.length && scoreSum !== d.total_score)) throw new Error('已知配分与总分不一致');
}
const req = modules ? createRequire(path.join(path.dirname(path.resolve(modules)), 'package.json')) : createRequire(import.meta.url);
const {Workbook, SpreadsheetFile} = await import(pathToFileURL(req.resolve('@oai/artifact-tool')).href);
const wb = Workbook.create();
const overview = wb.worksheets.add('快评');
const details = wb.worksheets.add('逐题评价');
const headers = ['题号','题型','模块','考点','分值','星级数','五星显示','难度依据','关键方法','易错点','答案摘要','核验状态','知识树位置'];
const rows = d.items.map(x => [x.id,x.type,x.module,x.topic,x.score,x.stars,x.stars === null ? '待核' : '★'.repeat(x.stars),x.reason,x.method,x.pitfall,x.answer || '',x.verification,(x.tree || []).map(t=>`${t.sheet}!${t.cell} ${t.label}（${t.match}）`).join('\n')]);
details.getRange('A1').write([headers,...rows]);
const n = rows.length + 1;
const reviewTable = details.tables.add(`A1:M${n}`,true,'QuestionReview');
reviewTable.showFilterButton = true;
details.freezePanes.freezeRows(1);
details.freezePanes.freezeColumns(1);
details.getRange(`A1:M${n}`).format = {font:{name:'Arial',size:11},verticalAlignment:'center',wrapText:true,rowHeight:76};
const widths = [100,110,150,240,65,65,100,360,300,260,260,250,440];
widths.forEach((w,i)=>details.getRangeByIndexes(0,i,n,1).format.columnWidthPx=w);
for (let i=0;i<rows.length;i++) { const lines=Math.max(...rows[i].map((v,j)=>String(v??'').split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil(line.length/(widths[j]/10))),0))); details.getRange(`A${i+2}:M${i+2}`).format.rowHeight=Math.max(62,lines*16+12); }
// 按列宽估算换行，给待核说明和知识树长文本足够行高。
rows.forEach((row,i)=> {
  const lines = row.map((value,j)=>String(value ?? '').split('\n').reduce((sum,line)=>sum+Math.max(1,Math.ceil([...line].reduce((n,c)=>n+(c.charCodeAt(0)>255?11:6),0)/(widths[j]-16))),0));
  details.getRange(`A${i+2}:M${i+2}`).format.rowHeight=Math.max(76, Math.max(...lines)*16+20);
});
details.getRange('A1:M1').format = {fill:palette.ink,font:{name:'Arial',size:11,bold:true,color:'#FFFFFF'},rowHeight:30};
details.getRange(`E2:F${n}`).setNumberFormat('0');
details.getRange(`F2:F${n}`).conditionalFormats.add('cellIs',{operator:'greaterThanOrEqual',formula:4,format:{fill:palette.tint,font:{bold:true}}});

const overviewRows = [
 ['试卷快评',d.title],['试卷标识',d.identity || d.title],['总体判断',d.summary],
 ['满分',d.total_score ?? '未提供'],['时长（分钟）',d.duration_minutes ?? '未提供'],
 ['评价单元数',null],['已知分值合计',null],['配分说明',`已知配分${knownScores.length}/${d.items.length}个评价单元；仅累计明确分值，空白不代表0分。`],
 ['一星单元数',null],['二星单元数',null],['三星单元数',null],['四星单元数',null],['五星单元数',null],['待核单元数',null],
 ['难度口径','同年级中等水平学生的结构预估；没有实测得分率。'],
 ['命题亮点',(d.highlights || []).join('\n')],['讲评建议',(d.teaching || []).join('\n')],
 ['覆盖与限制',(d.limits || []).join('\n')],['来源',(d.sources || []).join('\n')]
];
overview.getRange('A2').write(overviewRows);
overview.getRange('A2:B20').format = {font:{name:'Arial',size:11},verticalAlignment:'center',wrapText:true,rowHeight:32};
overview.getRange('A2:A20').format.columnWidthPx=150;
overview.getRange('B2:B20').format.columnWidthPx=850;
overview.getRange('A2:B2').format.font={name:'Arial',size:15,bold:true};
overview.getRange('A3:A20').format.font={name:'Arial',size:11,bold:true,color:palette.ink};
for (const r of [3,4,9,16]) overview.getRange(`A${r}:B${r}`).format.rowHeight=52;
for (const r of [17,18,19,20]) overview.getRange(`A${r}:B${r}`).format.rowHeight=115;
for(let i=0;i<overviewRows.length;i++) { const value=String(overviewRows[i][1]??''); const lines=value.split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil(line.length/66)),0); overview.getRange(`A${i+2}:B${i+2}`).format.rowHeight=Math.max(i===0?42:30,lines*18+16); }
overview.getRange('B7').formulas=[[`=COUNTA('逐题评价'!A2:A${n})`]];
overview.getRange('B8').formulas=[[`=IF(COUNT('逐题评价'!E2:E${n})=0,"未提供",SUM('逐题评价'!E2:E${n}))`]];
for(let s=1;s<=5;s++) overview.getRange(`B${s+9}`).formulas=[[`=COUNTIF('逐题评价'!F2:F${n},${s})`]];
overview.getRange('B15').formulas=[[`=COUNTBLANK('逐题评价'!F2:F${n})`]];
for (const sheet of [overview,details]) sheet.showGridLines=false;
await fs.mkdir(out,{recursive:true});
wb.recalculate();
const counts = overview.getRange('B7:B15').values;
if (counts[0][0] !== d.items.length) throw new Error('公式计算的单元数不一致');
if (counts[1][0] !== (knownScores.length ? scoreSum : '未提供')) throw new Error('公式计算的分值不一致');
for(let s=1;s<=5;s++) if(counts[s+2][0] !== d.items.filter(x=>x.stars===s).length) throw new Error('星级统计不一致');
if (counts[8][0] !== d.items.filter(x=>x.stars===null).length) throw new Error('待核统计不一致');
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#NUM!|#SPILL!|#CALC!|#N/A|#NULL!',options:{useRegex:true,maxResults:20},maxChars:2000});
await fs.writeFile(path.join(out,'公式检查.json'),errors.ndjson);
for (const line of errors.ndjson.split('\n').filter(Boolean)) {
  const record=JSON.parse(line);
  if (record.kind !== 'notice') throw new Error(`公式检查发现需处理的结果：${line}`);
}
for(const [sheetName,range,file] of [['快评','A2:B20','快评预览.png'],['逐题评价',`A1:I${Math.min(n,7)}`,'逐题预览.png'],['逐题评价',`H${Math.max(2,n-5)}:M${n}`,'末段与映射预览.png']]) {
 const preview=await wb.render({sheetName,range,scale:1,format:'png'});
 await fs.writeFile(path.join(out,file),new Uint8Array(await preview.arrayBuffer()));
}
await (await SpreadsheetFile.exportXlsx(wb)).save(path.join(out,'试卷快评.xlsx'));
console.log(JSON.stringify({output:path.join(out,'试卷快评.xlsx'),units:d.items.length,counts:counts.map(r=>r[0])}));
