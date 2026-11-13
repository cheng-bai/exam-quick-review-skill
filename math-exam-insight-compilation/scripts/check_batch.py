#!/usr/bin/env python3
"""Read-only scope, order and declared build-dependency audit. Not a content audit."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


def check_batch(data, base_dir):
    base = Path(base_dir)
    errors, warnings, scope_reports, product_reports, coverage_reports, stale = [], [], [], [], [], []

    def result():
        return dict(ok=not errors and not stale, errors=errors, warnings=warnings,
                    scopes=scope_reports, products=product_reports,
                    coverage=coverage_reports, stale_artifacts=stale)

    def string(value):
        return isinstance(value, str) and bool(value.strip())

    def index(field):
        rows = data.get(field)
        if not isinstance(rows, list):
            errors.append(f'{field}: expected array')
            return {}
        out = {}
        for row in rows:
            if not isinstance(row, dict) or not string(row.get('id')):
                errors.append(f'{field}: each entry needs a nonempty id')
                continue
            key = row['id']
            if key in out:
                errors.append(f'{field}: duplicate id {key}')
            else:
                out[key] = row
        return out

    def ids(value, label, unique=False):
        if not isinstance(value, list) or any(not string(x) for x in value):
            errors.append(f'{label}: expected array of nonempty IDs')
            return []
        if unique and len(value) != len(set(value)):
            errors.append(f'{label}: duplicate IDs')
        return value

    if not isinstance(data, dict):
        errors.append('manifest must be an object')
        return result()
    if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        errors.append('schema_version must be 1')
    if not string(data.get('batch_id')):
        errors.append('batch_id required')
    if not string(data.get('records_path')):
        errors.append('records_path required')
        return result()
    try:
        records = json.loads((base / data['records_path']).read_text(encoding='utf-8'))
        if not isinstance(records, dict) or type(records.get('schema_version')) is not int or records['schema_version'] != 1:
            raise ValueError('canonical records schema_version must be 1')
        questions = records.get('questions') if isinstance(records, dict) else None
        if not isinstance(questions, list):
            raise ValueError('questions must be an array')
        qids = [q.get('id') for q in questions if isinstance(q, dict)]
        if len(qids) != len(questions) or any(not string(q) for q in qids) or len(qids) != len(set(qids)):
            raise ValueError('question IDs invalid or duplicated')
        known = set(qids)
    except (OSError, ValueError) as exc:
        errors.append(f'cannot read canonical question IDs: {exc}')
        return result()

    scopes, products, covers, artifacts = (index(f) for f in ('scopes', 'products', 'coverage', 'artifacts'))
    if not scopes or not products:
        errors.append('at least one scope and one product required')
    if not artifacts:
        warnings.append('No artifacts declared: this is a scope plan, not a completed delivery audit.')
    scope_sets, product_lists, product_sets = {}, {}, {}
    for sid, row in scopes.items():
        values = ids(row.get('question_ids'), f'scope {sid}', unique=True)
        unknown = set(values) - known
        if unknown:
            errors.append(f'scope {sid}: unknown question IDs {sorted(unknown)}')
        scope_sets[sid] = set(values)
        scope_reports.append(dict(id=sid, unique_question_count=len(set(values))))
    for pid, row in products.items():
        values = ids(row.get('question_ids'), f'product {pid}')
        sid = row.get('scope_id')
        if not string(sid) or sid not in scope_sets:
            errors.append(f'product {pid}: unknown scope_id')
        elif set(values) - scope_sets[sid]:
            errors.append(f'product {pid}: outside parent scope {sorted(set(values)-scope_sets[sid])}')
        if not string(row.get('variant')):
            errors.append(f'product {pid}: variant required')
        product_lists[pid], product_sets[pid] = values, set(values)
        product_reports.append(dict(id=pid, scope_id=sid, display_count=len(values),
                                    unique_question_count=len(set(values)),
                                    repeated_displays={q:n for q,n in Counter(values).items() if n > 1}))
    for pid, row in products.items():
        if 'same_order_as' in row:
            other = row['same_order_as']
            if not string(other) or other not in product_lists:
                errors.append(f'product {pid}: unknown same_order_as')
            elif row.get('scope_id') != products[other].get('scope_id') or product_lists[pid] != product_lists[other]:
                errors.append(f'product {pid}: question order differs from {other}')
    for cid, row in covers.items():
        sid, mode = row.get('scope_id'), row.get('mode')
        pids = ids(row.get('product_ids'), f'coverage {cid}', unique=True)
        if not string(sid) or sid not in scope_sets or not pids or any(p not in products for p in pids):
            errors.append(f'coverage {cid}: invalid scope or product references')
            continue
        if mode not in ('partition', 'union_cover', 'selection'):
            errors.append(f'coverage {cid}: invalid mode')
            continue
        if any(products[p].get('scope_id') != sid for p in pids):
            errors.append(f'coverage {cid}: products refer to different parent scopes')
        union = set().union(*(product_sets[p] for p in pids))
        missing, extra = scope_sets[sid] - union, union - scope_sets[sid]
        counts = Counter(q for p in pids for q in product_sets[p])
        overlap = {q:[p for p in pids if q in product_sets[p]] for q,n in counts.items() if n > 1}
        coverage_reports.append(dict(id=cid, mode=mode, unique_question_count=len(union),
                                     missing_question_ids=sorted(missing), extra_question_ids=sorted(extra),
                                     overlaps=overlap))
        if extra or (mode in ('partition', 'union_cover') and missing):
            errors.append(f'coverage {cid}: coverage does not meet parent scope')
        if mode == 'partition' and overlap:
            errors.append(f'coverage {cid}: partition overlaps')

    revisions = data.get('revisions')
    if not isinstance(revisions, dict) or any(not string(k) or not string(v) for k,v in revisions.items()):
        errors.append('revisions must map input keys to nonempty version/hash strings')
        revisions = {}
    for aid, row in artifacts.items():
        if not string(row.get('product_id')) or row['product_id'] not in products:
            errors.append(f'artifact {aid}: unknown product_id')
        if not string(row.get('path')):
            errors.append(f'artifact {aid}: path required')
        if 'sha256' in row and (not isinstance(row['sha256'], str) or len(row['sha256']) != 64 or any(c not in '0123456789abcdef' for c in row['sha256'])):
            errors.append(f'artifact {aid}: invalid sha256')
        deps = row.get('depends_on')
        if not isinstance(deps, dict) or not deps or any(not string(k) or not string(v) for k,v in deps.items()):
            errors.append(f'artifact {aid}: nonempty depends_on required')
            continue
        changed = []
        for key, built in deps.items():
            if key not in revisions:
                errors.append(f'artifact {aid}: unknown dependency {key}')
            elif built != revisions[key]:
                changed.append(dict(input=key, built=built, current=revisions[key]))
        if changed:
            stale.append(dict(id=aid, product_id=row.get('product_id'), path=row.get('path'), changed_inputs=changed))
    warnings.append('Declared dependency audit only; missing dependencies, real content, mathematics, rendering and platform state are not verified.')
    return result()


def check_files(data, report, base_dir):
    """Validate specified artifact files without mutating them."""
    base = Path(base_dir)
    if isinstance(data, dict) and isinstance(data.get('artifacts'), list):
        for row in data['artifacts']:
            if not isinstance(row, dict) or not isinstance(row.get('path'), str) or not row['path'].strip():
                continue
            path = base / row['path']
            if not path.is_file():
                report['errors'].append(f'artifact {row.get("id")}: file missing {path}')
            elif isinstance(row.get('sha256'), str):
                try:
                    actual = hashlib.sha256(path.read_bytes()).hexdigest()
                    if actual != row['sha256']:
                        report['errors'].append(f'artifact {row.get("id")}: sha256 mismatch')
                except OSError as exc:
                    report['errors'].append(f'artifact {row.get("id")}: cannot read file: {exc}')
    report['ok'] = not report['errors'] and not report['stale_artifacts']
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--check-files', action='store_true')
    args = parser.parse_args()
    try:
        data = json.loads(args.manifest.read_text(encoding='utf-8'))
        report = check_batch(data, args.manifest.resolve().parent)
        if args.check_files:
            report = check_files(data, report, args.manifest.resolve().parent)
    except (OSError, ValueError) as exc:
        report = dict(ok=False, errors=[str(exc)], stale_artifacts=[])
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report['errors'] else 2 if report['stale_artifacts'] else 0


if __name__ == '__main__':
    sys.exit(main())
