#!/usr/bin/env python3
"""Validate v1 handoff records and recount sets. Does not judge mathematics."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def check_records(data, base=Path('.'), check_files=False):
    errors, warnings = [], []
    result = {'ok': False, 'errors': errors, 'warnings': warnings}
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        errors.append('schema_version 必须为 1，顶层必须是对象')
        return result

    def index(name):
        rows = data.get(name)
        found = {}
        if not isinstance(rows, list):
            errors.append(f'{name} 必须是数组')
            return found
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not row['id'].strip():
                errors.append(f'{name} 中每项必须有非空字符串 id')
                continue
            if row['id'] in found:
                errors.append(f'{name} 重复 id: {row["id"]}')
            else:
                found[row['id']] = row
        return found

    def nonempty(row, fields, label):
        for field in fields:
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f'{label}.{field} 必须为非空字符串')

    def path_of(raw, label):
        if not isinstance(raw, str) or not raw.strip():
            errors.append(f'{label} 必须为非空路径')
            return None
        p = Path(raw)
        p = p if p.is_absolute() else Path(base) / p
        if check_files and not p.is_file():
            errors.append(f'{label} 文件不存在: {p}')
            return None
        return p

    papers, questions, units, groups = [index(x) for x in ('papers', 'questions', 'units', 'groups')]
    if not papers:
        errors.append('至少需要一份试卷记录')
    for pid, paper in papers.items():
        nonempty(paper, ['title'], pid)
        if not isinstance(paper.get('included'), bool):
            errors.append(f'{pid}.included 必须为布尔值')
        elif not paper['included']:
            nonempty(paper, ['excluded_reason'], pid)
    origin_ids = set()
    for qid, question in questions.items():
        nonempty(question, ['paper_id', 'origin_id', 'original_number', 'stem'], qid)
        origin = question.get('origin_id')
        if isinstance(origin, str):
            if origin in origin_ids:
                errors.append(f'同源大题必须映射单一 question: {origin}')
            origin_ids.add(origin)
        if question.get('paper_id') not in papers:
            errors.append(f'{qid} 引用未知 paper_id')
        if not isinstance(question.get('stem_complete'), bool):
            errors.append(f'{qid}.stem_complete 必须为布尔值')
        images = question.get('images')
        if not isinstance(images, list):
            errors.append(f'{qid}.images 必须为数组（无图用空数组）')
        else:
            for raw in images:
                path_of(raw, f'{qid}.images')
        source = question.get('source')
        if not isinstance(source, dict):
            errors.append(f'{qid}.source 必须是对象')
            continue
        source_path = path_of(source.get('path'), f'{qid}.source.path')
        line = source.get('line')
        if type(line) is not int or line < 1:
            errors.append(f'{qid}.source.line 必须为正整数')
        anchor = source.get('anchor')
        if anchor is not None and (not isinstance(anchor, str) or not anchor.strip()):
            errors.append(f'{qid}.source.anchor 必须为非空字符串')
        digest = source.get('sha256')
        if digest is not None and (not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)):
            errors.append(f'{qid}.source.sha256 格式错误')
        if check_files and source_path:
            raw = source_path.read_bytes()
            if digest is not None and hashlib.sha256(raw).hexdigest() != digest:
                errors.append(f'{qid} 来源哈希不一致')
            try:
                content = raw.decode('utf-8')
            except UnicodeDecodeError:
                errors.append(f'{qid} 来源需为 UTF-8 题目转录，原 PDF 另行保留')
                continue
            if type(line) is int and line > len(content.splitlines()):
                errors.append(f'{qid} 来源起始行超出文件')
            if isinstance(anchor, str) and not re.search(r'\bid\s*=\s*[\"\x27]' + re.escape(anchor) + r'[\"\x27]', content):
                errors.append(f'{qid} 来源明确 HTML 锚点不存在: {anchor}')

    eligible, pending = set(), set()
    canonical_units = set()
    for uid, unit in units.items():
        nonempty(unit, ['question_id', 'subquestion', 'key_action', 'boundary', 'verification_note', 'training_role'], uid)
        sub = unit.get('subquestion')
        if not isinstance(sub, str) or not re.fullmatch(r'whole|s[1-9][0-9]*(?:\.[1-9][0-9]*)*', sub):
            errors.append(f'{uid}.subquestion 必须为 whole 或 s1/s1.1 等规范 token')
        question = questions.get(unit.get('question_id'))
        if question is None:
            errors.append(f'{uid} 引用未知 question_id')
        else:
            key = (unit['question_id'], unit.get('subquestion'))
            if key in canonical_units:
                errors.append(f'{uid} 同一原始小问不可创建多个规范单元')
            canonical_units.add(key)
        if unit.get('task_status') not in ('verified', 'pending'):
            errors.append(f'{uid}.task_status 非法')
        if unit.get('solution_status') not in ('verified', 'conflict', 'missing', 'pending'):
            errors.append(f'{uid}.solution_status 非法')
        if question and question.get('stem_complete') is True and unit.get('task_status') == 'verified':
            if papers.get(question.get('paper_id'), {}).get('included') is True:
                eligible.add(uid)
        else:
            pending.add(uid)
    if errors:
        return result
    denominator = sum(p.get('included') is True for p in papers.values())
    if denominator == 0:
        errors.append('有效试卷分母为零')

    def summary(ids):
        return {
            'unit_count': len(ids),
            'question_count': len({units[u]['question_id'] for u in ids}),
            'paper_count': len({questions[units[u]['question_id']]['paper_id'] for u in ids}),
        }

    total_direct, total_transfer = set(), set()
    group_stats = []
    for gid, group in groups.items():
        nonempty(group, ['title', 'definition', 'include_when', 'exclude_when'], gid)
        members = group.get('members')
        if not isinstance(members, list):
            errors.append(f'{gid}.members 必须为数组')
            continue
        kinds, direct, transfer, skipped = {}, set(), set(), set()
        for member in members:
            if not isinstance(member, dict):
                errors.append(f'{gid} member 必须是对象')
                continue
            uid, kind = member.get('unit_id'), member.get('kind')
            nonempty(member, ['unit_id', 'reason'], gid)
            if not isinstance(uid, str) or uid not in units:
                errors.append(f'{gid} 引用未知 unit_id: {uid}')
                continue
            if kind not in ('direct', 'transfer'):
                errors.append(f'{gid}/{uid} kind 非法')
                continue
            if uid in kinds:
                if kinds[uid] != kind:
                    errors.append(f'{gid}/{uid} 不能同时为 direct 和 transfer')
                else:
                    warnings.append(f'{gid}/{uid} 类内重复展示，计数已去重')
            kinds[uid] = kind
            if uid not in eligible:
                skipped.add(uid)
                continue
            (direct if kind == 'direct' else transfer).add(uid)
        total_direct |= direct
        total_transfer |= transfer
        group_stats.append({
            'id': gid, 'title': group.get('title'), 'coverage': f'{summary(direct)["paper_count"]}/{denominator}',
            'direct': summary(direct), 'transfer': summary(transfer),
            'direct_unit_ids': sorted(direct), 'transfer_unit_ids': sorted(transfer),
            'excluded_unit_ids': sorted(skipped),
            'unverified_solution_unit_ids': sorted(u for u in direct | transfer if units[u]['solution_status'] != 'verified'),
        })
    result.update({
        'ok': not errors, 'included_paper_count': denominator, 'groups': group_stats,
        'global_direct': summary(total_direct), 'global_transfer': summary(total_transfer),
        'global_any_membership': summary(total_direct | total_transfer),
        'eligible_unit_ids': sorted(eligible), 'pending_or_incomplete_unit_ids': sorted(pending),
        'unclassified_eligible_unit_ids': sorted(eligible - total_direct - total_transfer),
        'checks': {'local_source_and_images': check_files, 'mathematics': False, 'rendering': False},
    })
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('records', type=Path)
    parser.add_argument('--check-files', action='store_true')
    args = parser.parse_args()
    try:
        data = json.loads(args.records.read_text(encoding='utf-8'))
        result = check_records(data, args.records.resolve().parent, args.check_files)
    except (OSError, ValueError, TypeError) as exc:
        result = {'ok': False, 'errors': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
