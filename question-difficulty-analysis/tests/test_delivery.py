import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from export_report import export, validate
from question_difficulty.engine import score_question, ValidationError
from question_difficulty.__main__ import score_input

class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.d=json.loads((ROOT/'examples/delivery-example.json').read_text())
    def test_rounding_and_depth(self):
        q=self.d['questions'][0];template=copy.deepcopy(q['steps'][0])
        q['steps']=[]
        for i, values in enumerate([(1,2,0,1,0,0),(1,1,0,0,0,0),(0,0,1,0,0,0)]):
            s=copy.deepcopy(template);s.update(id=f'S{i+1}',dependencies=[f'S{i}'] if i else [],dimensions=dict(zip('KRAVPI',values)));q['steps'].append(s)
        q['t']=[1,1,1,1,0]
        for i,x in enumerate(q['T_evidence']):x['value']=q['t'][i]
        r=score_question(q)
        self.assertEqual([r[k] for k in ['H','C','T','D']],[43,22,40,35])
        self.assertEqual(r['E'],.7625)
    def test_repeat(self):
        q=self.d['questions'][0];a=copy.deepcopy(q['steps'][0]);q['steps']=[]
        for i in range(4):
            s=copy.deepcopy(a);s.update(id=f'S{i}',dependencies=[f'S{i-1}'] if i else [],repeat_group='mechanical',repeat_evidence='同一机械动作的测试夹具');q['steps'].append(s)
        r=score_question(q)
        self.assertEqual([x['r'] for x in r['path']],[1,.7,.4,.4])
        self.assertEqual([x['d'] for x in r['path']],[1,1.1,1.2,1.3])
    def test_evidence_retained_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as t:
            export(self.d,t)
            out=json.loads((Path(t)/'评分明细.json').read_text())
            self.assertEqual(out['questions'][0]['evidence'],self.d['questions'][0])
            self.assertTrue((Path(t)/'逐小问评分.csv').exists())
            with self.assertRaises(ValidationError):export(self.d,t)
    def test_invalid_phase(self):
        self.d['questions'][0]['goal_phases'][0]['step_ids']=['S404']
        with self.assertRaises(ValidationError):validate(self.d)
    def test_unknown_type(self):
        self.d['questions'][0]['steps'][0]['type_id']='NO-SUCH-TYPE'
        with self.assertRaises(ValidationError):validate(self.d)
    def test_version_and_parameters(self):
        for key,value in [('algorithm','old-v0'),('parameters',{'H_weight':1})]:
            d=copy.deepcopy(self.d);d[key]=value
            with self.assertRaises(ValidationError):score_input(d)
    def test_cycle(self):
        q=self.d['questions'][0];q['steps'][0]['dependencies']=['S1']
        with self.assertRaises(ValidationError):score_question(q)
    def test_pending_not_zero(self):
        self.d['questions'].append(dict(id='pending',pending=True,issue='图形缺失',source_ref='示例第2题',verification_status='待核验',score=5))
        r=score_input(self.d)
        self.assertIsNone(r['questions'][1]['D'])
        self.assertEqual(r['statistics']['coverage'],.5)
        self.assertIsNone(r['statistics']['whole_question_weighted_mean'])
    def test_paper_inventory(self):
        self.d.update(scope='paper',paper_id='demo',expected_question_ids=['example-1','missing'],inventory_source='原卷题号清单')
        with self.assertRaises(ValidationError):validate(self.d)
        self.d['expected_question_ids']=['example-1'];validate(self.d)
    def test_scope_and_mixed_papers(self):
        self.d['scope']='group';r=score_input(self.d)
        self.assertIn('provided_group_weighted_mean',r['statistics'])
        a=self.d['questions'][0];a['paper_id']='A'
        b=copy.deepcopy(a);b.update(id='other',paper_id='B');self.d['questions'].append(b)
        with self.assertRaises(ValidationError):score_input(self.d)

if __name__=='__main__':unittest.main()
