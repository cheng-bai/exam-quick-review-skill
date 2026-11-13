"""Validate auditable delivery input; export evidence JSON, CSV and type dictionary.
Does not solve mathematics or validate the truth of textual evidence.
"""
import argparse
import csv
import json
from pathlib import Path
from question_difficulty.engine import ValidationError, DIMENSIONS
from question_difficulty.__main__ import score_input

PARAMETERS = {
    'weights': {'K': .20, 'R': .25, 'A': .15, 'V': .15, 'P': .15, 'I': .10},
    'HCT_weights': [.45, .35, .20], 'C_scale': 3,
    'repeat': [1, .7, .4], 'depth_increment': .1, 'depth_cap': 1.3,
    'band_thresholds': [35, 65], 'rounding': 'half_up'
}


def text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f'{field}: required nonempty text')


def validate(data):
    if not isinstance(data, dict):
        raise ValidationError('input must be object')
    if data.get('algorithm') != 'HCT-rules-v1.1':
        raise ValidationError('unsupported algorithm; do not relabel old records')
    if data.get('parameters') != PARAMETERS:
        raise ValidationError('parameters must match this fixed engine; custom parameters are not supported')
    if data.get('scope') not in ('paper', 'question', 'group'):
        raise ValidationError('scope must be paper/question/group')
    for k in ('analysis_id', 'source', 'parameter_version', 'dictionary_version'):
        text(data.get(k), k)
    if data['scope'] == 'paper':
        text(data.get('paper_id'), 'paper_id')
    dictionary = data.get('step_types')
    if not isinstance(dictionary, list) or not dictionary:
        raise ValidationError('step_types required')
    types = {}
    for item in dictionary:
        if not isinstance(item, dict):
            raise ValidationError('type must be object')
        for k in ('id', 'name', 'definition', 'include', 'exclude', 'status'):
            text(item.get(k), f'type.{k}')
        if not isinstance(item.get('aliases'), list):
            raise ValidationError('type.aliases must be array')
        if item['id'] in types:
            raise ValidationError('duplicate type id')
        types[item['id']] = item
    questions = data.get('questions')
    if not isinstance(questions, list) or not questions:
        raise ValidationError('questions required')
    ids = set()
    for q in questions:
        if not isinstance(q, dict):
            raise ValidationError('question must be object')
        text(q.get('id'), 'question.id')
        if q['id'] in ids:
            raise ValidationError('duplicate question id')
        ids.add(q['id'])
        for k in ('source_ref', 'verification_status'):
            text(q.get(k), k)
        if q.get('paper_id', data.get('paper_id')) != data.get('paper_id'):
            raise ValidationError('one source paper per export; export papers separately')
        if q.get('pending'):
            continue
        if q['verification_status'] != '已核验':
            raise ValidationError('unverified question must be pending; cannot publish definite score')
        text(q.get('solution_basis'), 'solution_basis')
        phases = q.get('goal_phases')
        steps = q.get('steps')
        if not isinstance(phases, list) or not phases or not isinstance(steps, list) or not steps:
            raise ValidationError('goal_phases and steps required')
        phase_ids, membership = set(), {}
        for phase in phases:
            for k in ('id', 'type_id', 'name', 'goal', 'direction', 'output'):
                text(phase.get(k), f'phase.{k}')
            if phase['id'] in phase_ids:
                raise ValidationError('duplicate phase')
            phase_ids.add(phase['id'])
            if not isinstance(phase.get('step_ids'), list) or not phase['step_ids']:
                raise ValidationError('phase.step_ids required')
            for sid in phase['step_ids']:
                text(sid, 'phase step id')
                if sid in membership:
                    raise ValidationError('step assigned to multiple phases')
                membership[sid] = phase['id']
        if set(membership) != {s['id'] for s in steps}:
            raise ValidationError('phase members must exactly match steps')
        for s in steps:
            if s.get('phase_id') != membership[s['id']]:
                raise ValidationError('step.phase_id disagrees with phase members')
            if s.get('type_id') not in types:
                raise ValidationError('unknown step type')
            text(s.get('source_ref'), 'step.source_ref')
    if data['scope'] == 'paper':
        expected = data.get('expected_question_ids')
        if (not isinstance(expected, list) or not expected or
                any(not isinstance(x, str) for x in expected) or
                len(expected) != len(set(expected)) or set(expected) != ids):
            raise ValidationError('paper expected_question_ids must match all question IDs including pending')
        text(data.get('inventory_source'), 'inventory_source')
    return data


def export(data, out):
    validate(data)
    result = score_input(data)
    out = Path(out)
    names = ['评分明细.json', '逐小问评分.csv', '步骤类型词典.json']
    if any((out / n).exists() for n in names):
        raise ValidationError('output files exist; use a new run directory')
    out.mkdir(parents=True, exist_ok=True)
    records = result['questions']
    evidence = {q['id']: q for q in data['questions']}
    detail = {k: v for k, v in data.items() if k not in ('questions', 'step_types')}
    detail.update(engine=result['engine'], scope=result['scope'], statistics=result['statistics'],
                  questions=[{'evidence': evidence[q['id']], 'computed': q} for q in records])
    (out / names[0]).write_text(json.dumps(detail, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    fields = ['analysis_id', 'paper_id', 'id', 'source_ref', 'score', 'verification_status',
              'H','C','T','D','B','band','review_flag'] + list(DIMENSIONS)
    with (out / names[1]).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields);writer.writeheader()
        for q in records:
            row = {k:q.get(k) for k in fields}
            row.update(analysis_id=data['analysis_id'], paper_id=data.get('paper_id'),
                       source_ref=evidence[q['id']]['source_ref'],
                       verification_status=evidence[q['id']]['verification_status'])
            row.update(q.get('peak') or {})
            writer.writerow(row)
    (out / names[2]).write_text(json.dumps({'version':data['dictionary_version'],
        'types':data['step_types']}, ensure_ascii=False, indent=2)+'\n')
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('input', type=Path);ap.add_argument('--out', type=Path, required=True)
    args=ap.parse_args()
    try:
        result=export(json.loads(args.input.read_text(encoding='utf-8-sig')), args.out)
        print(json.dumps({'scope':result['scope'], 'output':str(args.out)},ensure_ascii=False))
    except (OSError, ValueError, TypeError, KeyError) as e:
        ap.exit(2, f'交付校验失败：{e}\n')

if __name__=='__main__':main()
