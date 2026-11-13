#!/usr/bin/env python3
"""Synthetic scope and dependency tests, not a mathematical/end-to-end replay."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from check_batch import check_batch, check_files

ROOT = Path(__file__).resolve().parents[1]


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.base = ROOT / 'examples'
        self.data = json.loads((self.base/'batch-fixture.json').read_text())

    def check(self, data=None):
        return check_batch(self.data if data is None else data, self.base)

    def test_partition_and_same_order_pass(self):
        r = self.check()
        self.assertTrue(r['ok'], r['errors'])
        self.assertEqual(r['coverage'][0]['unique_question_count'], 4)
        self.assertEqual(r['coverage'][0]['overlaps'], {})
        self.assertTrue(check_files(self.data, r, self.base)['ok'])

    def test_union_cover_permits_overlap_partition_rejects(self):
        self.data['products'][1]['question_ids'].insert(0, 'Q2')
        self.assertFalse(self.check()['ok'])
        self.data['coverage'][0]['mode'] = 'union_cover'
        r = self.check()
        self.assertTrue(r['ok'], r['errors'])
        self.assertEqual(r['coverage'][0]['overlaps'], {'Q2':['solid','relations']})

    def test_missing_question_and_selection(self):
        self.data['products'][1]['question_ids'].remove('Q4')
        r = self.check()
        self.assertFalse(r['ok'])
        self.assertEqual(r['coverage'][0]['missing_question_ids'], ['Q4'])
        self.data['coverage'][0]['mode'] = 'selection'
        self.assertTrue(self.check()['ok'])

    def test_foreign_parent_rejected_even_with_same_question_ids(self):
        self.data['scopes'].append({'id':'geometry-full', 'question_ids':['Q1','Q2','Q3','Q4']})
        self.data['products'][1]['scope_id']='geometry-full'
        self.assertFalse(self.check()['ok'])

    def test_outside_scope_and_unknown_canonical_id(self):
        self.data['products'][0]['question_ids'].append('Q5')
        self.assertFalse(self.check()['ok'])
        self.data['scopes'][0]['question_ids'].append('NONEXISTENT')
        self.assertFalse(self.check()['ok'])

    def test_repeated_display_does_not_inflate_union(self):
        self.data['products'][0]['question_ids'].append('Q1')
        r=self.check()
        self.assertTrue(r['ok'], r['errors'])
        self.assertEqual(r['products'][0]['display_count'],3)
        self.assertEqual(r['products'][0]['unique_question_count'],2)
        self.assertEqual(r['coverage'][0]['unique_question_count'],4)

    def test_dual_version_order_conflict(self):
        self.data['products'][3]['question_ids'].reverse()
        self.assertFalse(self.check()['ok'])

    def test_solution_revision_only_invalidates_dependent_teacher(self):
        self.data['revisions']['solution:Q1']='r2'
        r=self.check()
        self.assertEqual(r['errors'],[])
        self.assertEqual([a['id'] for a in r['stale_artifacts']],['teacher-md'])
        self.assertFalse(r['ok'])

    def test_layout_revision_only_invalidates_student(self):
        self.data['revisions']['layout:student']='l2'
        self.assertEqual([a['id'] for a in self.check()['stale_artifacts']],['student-md'])

    def test_classification_invalidates_both_and_rebuild_clears(self):
        self.data['revisions']['classification']='c2'
        self.assertEqual(len(self.check()['stale_artifacts']),2)
        for a in self.data['artifacts']:
            a['depends_on']['classification']='c2'
        self.assertTrue(self.check()['ok'])

    def test_unknown_and_empty_dependencies_rejected(self):
        for deps in ({},{'unregistered':'r1'}):
            with self.subTest(deps=deps):
                d=deepcopy(self.data);d['artifacts'][0]['depends_on']=deps
                self.assertFalse(self.check(d)['ok'])

    def test_file_and_hash_failures(self):
        d=deepcopy(self.data);d['artifacts'][0]['path']='missing.md'
        self.assertFalse(check_files(d,self.check(d),self.base)['ok'])
        d=deepcopy(self.data);d['artifacts'][0]['sha256']='0'*64
        self.assertFalse(check_files(d,self.check(d),self.base)['ok'])
        d['artifacts'][0]['sha256']=hashlib.sha256((self.base/'synthetic-source.md').read_bytes()).hexdigest()
        self.assertTrue(check_files(d,self.check(d),self.base)['ok'])

    def test_malformed_manifests_rejected_without_crash(self):
        bad=[[],{}, {'schema_version':True}]
        for field,value in [('scopes',{}),('products',[None]),('coverage',[{'id':'x','scope_id':[],'product_ids':[]}]),('revisions',[]),('artifacts',[{'id':'x','product_id':[]}])]:
            d=deepcopy(self.data);d[field]=value;bad.append(d)
        for d in bad:
            with self.subTest(data=d):self.assertFalse(self.check(d)['ok'])

    def test_duplicate_scope_ids_rejected(self):
        self.data['scopes'].append(deepcopy(self.data['scopes'][0]))
        self.assertFalse(self.check()['ok'])

    def test_missing_scope_with_order_link_rejected_without_crash(self):
        del self.data['products'][3]['scope_id']
        r=self.check()
        self.assertFalse(r['ok'])
        self.assertTrue(any('scope_id' in e for e in r['errors']))

    def test_empty_plan_and_invalid_canonical_schema(self):
        for field in ('scopes','products'):
            d=deepcopy(self.data);d[field]=[]
            self.assertFalse(self.check(d)['ok'])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'wrong-records.json'
            p.write_text(json.dumps({'schema_version':2,'questions':[{'id':'Q1'}]}))
            d=deepcopy(self.data);d['records_path']=str(p)
            self.assertFalse(self.check(d)['ok'])

    def test_cli_exit_codes_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'manifest.json'
            self.data['records_path']=str(self.base/'counting-fixture.json')
            for state,code in [('fresh',0),('stale',2),('invalid',1)]:
                d=deepcopy(self.data)
                if state=='stale':d['revisions']['classification']='c2'
                if state=='invalid':d['products'][0]['question_ids'].append('unknown')
                p.write_text(json.dumps(d));before=p.read_bytes()
                proc=subprocess.run([sys.executable,str(ROOT/'scripts/check_batch.py'),str(p)],capture_output=True,text=True)
                self.assertEqual(proc.returncode,code,proc.stderr)
                self.assertIsInstance(json.loads(proc.stdout),dict)
                self.assertEqual(p.read_bytes(),before)


if __name__ == '__main__':
    unittest.main()
