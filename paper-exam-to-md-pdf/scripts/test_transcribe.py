"""Offline regression tests for user-visible workflow guarantees."""
import argparse
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import transcribe as cli


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.w = Path(self.temp.name) / 'run'
        self.args = argparse.Namespace(workspace=str(self.w), editions='full', pdf=False)
        cli.root(self.args)
        student = Path(self.temp.name) / '题目.md'
        teacher = Path(self.temp.name) / '解析.md'
        self.stems = ['计算 $1+1$。', '选出正确答案。\n\nA. 甲\n\nB. 乙\n\nC. 丙\n\nD. 丁']
        self.solutions = ['**答案**：$2$\n\n**原文解析**：相加。', '**答案**：A\n\n**原文解析**：依据条件。']
        self.notes = '**转录校注**：原题存在疑点，照录。'
        text = '# 测试数学试卷\n\n来源：https://mp.weixin.qq.com/s/test\n\n'
        s = text + '## 一、填空题\n\n### 第1题\n\n' + self.stems[0]
        s += '\n\n## 二、选择题\n\n### 第2题\n\n' + self.stems[1] + '\n'
        t = s.replace(self.stems[0], self.stems[0]+'\n\n'+self.solutions[0]+'\n\n'+self.notes)
        t = t.replace(self.stems[1], self.stems[1]+'\n\n'+self.solutions[1])
        student.write_text(s); teacher.write_text(t)
        cli.import_reviewed(argparse.Namespace(workspace=str(self.w), student=str(student), teacher=str(teacher), title=None))

    def data(self):
        return cli.read_json(self.w/'题目数据.json')

    def save(self, data):
        cli.write_json(self.w/'题目数据.json', data)

    def test_import_and_default_preserve_complete_content_without_pdf(self):
        data = self.data()
        self.assertEqual(data['questions'][0]['stem'], self.stems[0])
        self.assertEqual(data['questions'][0]['solution'], self.solutions[0])
        self.assertEqual(data['questions'][0]['notes'], self.notes)
        with patch('pdf_export.export_pdf', side_effect=AssertionError('默认不应导出PDF')):
            result = cli.build(self.args)
        outputs = list((self.w/'outputs').glob('*.md'))
        self.assertEqual(len(outputs), 1)
        self.assertIn('完整转录版', outputs[0].name)
        self.assertIn(self.notes, outputs[0].read_text())
        self.assertEqual(outputs[0].read_text().count('**答案**'), 2)
        self.assertEqual(result['pdf'], {})

    def test_section_instructions_preserved_for_first_and_later_sections(self):
        data = self.data()
        student = Path(self.temp.name)/'带说明题目.md'
        teacher = Path(self.temp.name)/'带说明解析.md'
        descriptions = ['本大题每题5分，请填空。', '本大题每题4分，请选择。']
        for edition,path in [('student',student),('teacher',teacher)]:
            text = cli.render_markdown(data,edition)
            text = text.replace('## 一、填空题', '## 一、填空题\n\n'+descriptions[0])
            text = text.replace('## 二、选择题', '## 二、选择题\n\n'+descriptions[1])
            if edition=='teacher':text = text.replace(descriptions[1], descriptions[1]+'教师核对说明。')
            path.write_text(text)
        dest = Path(self.temp.name)/'带说明导入'
        cli.import_reviewed(argparse.Namespace(workspace=str(dest),student=str(student),teacher=str(teacher),title=None))
        imported = cli.read_json(dest/'题目数据.json')
        for edition in ['full','student','teacher']:
            text = cli.render_markdown(imported,edition)
            for desc in descriptions:self.assertIn(desc,text)
            self.assertLess(text.index(descriptions[0]),text.index('### 第1题'))
            self.assertLess(text.index(descriptions[1]),text.index('### 第2题'))
            self.assertEqual('教师核对说明。' in text, edition!='student')

    def test_unchanged_build_does_not_rewrite_and_solution_only_keeps_student(self):
        self.args.editions = 'full,student,teacher'
        cli.build(self.args)
        _, _, paths = cli.plan_data(self.data(), self.w)
        times = {e:p.stat().st_mtime_ns for e,p in paths.items()}
        result = cli.build(self.args)
        self.assertEqual(result['markdown_built'], [])
        self.assertEqual(times, {e:p.stat().st_mtime_ns for e,p in paths.items()})
        data = self.data(); data['questions'][0]['notes'] += '\n补充校注。'; self.save(data)
        result = cli.build(self.args)
        self.assertEqual(set(result['markdown_built']), {'full','teacher'})
        self.assertEqual(paths['student'].stat().st_mtime_ns, times['student'])
        self.assertNotIn('补充校注', paths['student'].read_text())

    def test_validation_failure_invalidates_previous_acceptance_and_recovers(self):
        cli.build(self.args)
        data = self.data(); original = copy.deepcopy(data)
        data['questions'][1]['stem'] = '缺选项'; self.save(data)
        with self.assertRaisesRegex(ValueError, '结构检查失败'):
            cli.build(self.args)
        check = cli.read_json(self.w/'work/最终验收.json')
        self.assertNotEqual(check['status'], 'built')
        self.assertEqual(check['data_sha256'], cli.digest(self.w/'题目数据.json'))
        self.save(original)
        self.assertEqual(cli.build(self.args)['status'], 'built')

    def test_manual_output_edit_is_preserved(self):
        cli.build(self.args)
        path = next((self.w/'outputs').glob('*.md'))
        path.write_text(path.read_text()+'\n人工改动。\n')
        before = path.read_bytes()
        with self.assertRaisesRegex(ValueError, '另行编辑'):
            cli.build(self.args)
        self.assertEqual(path.read_bytes(), before)

    def test_text_or_image_change_expires_review(self):
        data = self.data(); q = data['questions'][0]
        image = self.w/'outputs/题图.png'; image.write_bytes(b'original')
        q['stem'] += '\n\n![图](题图.png)'
        q['review']['content_sha256'] = cli.question_hash(q,self.w)
        self.assertFalse(any(x['code']=='review_stale' for x in cli.validate(data,self.w)[1]))
        image.write_bytes(b'changed')
        self.assertTrue(any(x.get('id')==1 and x['code']=='review_stale' for x in cli.validate(data,self.w)[1]))
        q['review']['content_sha256'] = cli.question_hash(q,self.w)
        q['stem'] += '条件更改。'
        self.assertTrue(any(x['code']=='review_stale' for x in cli.validate(data,self.w)[1]))

    def test_private_ocr_requires_authorization_and_damaged_cache_does_not_resubmit(self):
        pdf = Path(self.temp.name)/'私人.pdf'; pdf.write_bytes(b'%PDF-test')
        args = argparse.Namespace(workspace=str(self.w), pdf=str(pdf), ocr_md=None, ocr_json=None, allow_remote=False)
        with patch.object(cli, 'run_logged', side_effect=AssertionError('不得外发')):
            with self.assertRaisesRegex(ValueError, '逐文件授权'):
                cli.ocr(args)
        md = Path(self.temp.name)/'识别.md'; md.write_text('已有草稿')
        js = Path(self.temp.name)/'版面.json'; js.write_text('[]')
        args.ocr_md = str(md); args.ocr_json = str(js)
        imported = cli.ocr(args)
        self.assertEqual(imported['ocr_calls'],0)
        args.ocr_md = None; args.ocr_json = None
        self.assertEqual(cli.ocr(args)['status'],'cached')
        Path(imported['markdown']).write_text('被修改')
        with patch.object(cli, 'run_logged', side_effect=AssertionError('不得重传')):
            with self.assertRaisesRegex(ValueError, '缓存被修改'):
                cli.ocr(args)

    def test_pdf_failure_keeps_markdown_owned_and_can_retry(self):
        cli.build(self.args)
        data = self.data(); data['questions'][0]['notes'] += '后续校注。'; self.save(data)
        self.args.pdf = True
        with patch('pdf_export.export_pdf', side_effect=RuntimeError('模拟编译失败')):
            with self.assertRaisesRegex(RuntimeError,'模拟编译失败'):
                cli.build(self.args)
        self.assertNotEqual(cli.read_json(self.w/'work/最终验收.json')['status'],'built')
        data['questions'][0]['notes'] += '再次修正。'; self.save(data)
        with patch('pdf_export.export_pdf', return_value={'status':'built'}):
            self.assertEqual(cli.build(self.args)['status'],'built')


if __name__ == '__main__':
    unittest.main()
