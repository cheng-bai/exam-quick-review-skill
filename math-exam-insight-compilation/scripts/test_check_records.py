#!/usr/bin/env python3
"""Synthetic invariant tests; not mathematical or prompt-replay validation."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from check_records import check_records

ROOT = Path(__file__).resolve().parents[1]


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'examples/counting-fixture.json').read_text())

    def test_overlap_dedup_transfer_pending_and_denominator(self):
        r = check_records(self.data)
        self.assertTrue(r['ok'], r['errors'])
        self.assertEqual(r['included_paper_count'], 2)
        self.assertEqual(r['groups'][0]['coverage'], '2/2')
        self.assertEqual(r['groups'][0]['direct'], {'unit_count': 3, 'question_count': 3, 'paper_count': 2})
        self.assertEqual(r['groups'][0]['transfer']['unit_count'], 1)
        self.assertEqual(r['groups'][0]['excluded_unit_ids'], ['U5', 'U6'])
        self.assertEqual(r['groups'][0]['unverified_solution_unit_ids'], ['U4'])
        self.assertEqual(r['global_direct'], {'unit_count': 4, 'question_count': 3, 'paper_count': 2})
        self.assertEqual(r['global_any_membership']['unit_count'], 4)
        self.assertTrue(r['warnings'])

    def test_transfer_does_not_increase_coverage(self):
        self.data['groups'][0]['members'] = [{'unit_id':'U1','kind':'direct','reason':'入口'}, {'unit_id':'U4','kind':'transfer','reason':'迁移'}]
        r = check_records(self.data)
        self.assertEqual(r['groups'][0]['coverage'], '1/2')
        self.assertEqual(r['groups'][0]['transfer']['paper_count'], 1)

    def test_incomplete_stem_excluded(self):
        self.data['questions'][0]['stem_complete'] = False
        r = check_records(self.data)
        self.assertNotIn('U1', r['eligible_unit_ids'])
        self.assertNotIn('U2', r['eligible_unit_ids'])

    def test_same_question_many_subquestions_counts_once(self):
        r = check_records(self.data)
        self.assertEqual(r['groups'][1]['direct']['unit_count'], 2)
        self.assertEqual(r['groups'][1]['direct']['question_count'], 1)

    def test_duplicate_source_and_unit_rejected(self):
        for field in ('origin', 'unit'):
            with self.subTest(field=field):
                d = deepcopy(self.data)
                if field == 'origin':
                    d['questions'][1]['origin_id'] = d['questions'][0]['origin_id']
                else:
                    d['units'].append({**d['units'][0], 'id':'U7'})
                self.assertFalse(check_records(d)['ok'])

    def test_subquestion_aliases_rejected(self):
        for alias in ('(1)', '（1）', '1', ' s1 ', 's01'):
            with self.subTest(alias=alias):
                d = deepcopy(self.data)
                d['units'].append({**d['units'][0], 'id':'U7', 'subquestion':alias})
                self.assertFalse(check_records(d)['ok'])

    def test_unknown_ids_and_conflicting_membership(self):
        for member in ({'unit_id':'NOPE','kind':'direct','reason':'测试'}, {'unit_id':'U1','kind':'transfer','reason':'冲突'}):
            with self.subTest(member=member):
                d = deepcopy(self.data)
                d['groups'][0]['members'].append(member)
                self.assertFalse(check_records(d)['ok'])

    def test_invalid_schema_and_status(self):
        self.assertFalse(check_records([])['ok'])
        self.data['units'][0]['task_status'] = 'guess'
        self.assertFalse(check_records(self.data)['ok'])

    def test_files_anchor_line_hash_and_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root/'synthetic-source.md'
            source.write_text('# Source\n<a id="q1"></a>\n题干\n')
            (root/'diagram.svg').write_text('<svg/>')
            q = self.data['questions'][0]
            q['images'] = ['diagram.svg']
            q['source'].update(anchor='q1', sha256=hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertTrue(check_records(self.data, root, True)['ok'])
            for edit in ('image', 'line', 'anchor', 'hash', 'source'):
                with self.subTest(edit=edit):
                    d = deepcopy(self.data)
                    if edit == 'image': d['questions'][0]['images'] = ['missing.svg']
                    if edit == 'line': d['questions'][0]['source']['line'] = 99
                    if edit == 'anchor': d['questions'][0]['source']['anchor'] = 'missing'
                    if edit == 'hash': d['questions'][0]['source']['sha256'] = '0'*64
                    if edit == 'source': d['questions'][0]['source']['path'] = 'missing.md'
                    self.assertFalse(check_records(d, root, True)['ok'])


if __name__ == '__main__':
    unittest.main()
