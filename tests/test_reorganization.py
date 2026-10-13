import argparse
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from render_cards import validate, render
from check_delivery import check
import test_delivery


class ReorganizationTests(unittest.TestCase):
    def setUp(self):
        self.f=test_delivery.DeliveryTests()
        self.f.setUp()
        self.root=self.f.root
        manifest=self.f.manifest
        for i in range(2,6):
            name=f'{i:02d}.png'
            (self.f.source/name).write_bytes((self.f.source/'01.png').read_bytes())
            manifest['images'].append(dict(manifest['images'][0],index=i,file=name))
        manifest['expected_count']=5
        base=copy.deepcopy(self.f.content['cards'][0])
        self.content=dict(self.f.content,mode='smart',selected_indices=[1,2,3,4,5],cards=[],
            source_facts=[dict(id=f'f{i}',source_indices=[i],text=f'第{i}组岗位信息',kind='fact',action='retained') for i in range(1,6)],
            reorganization={'reviewed':True,'alternatives':[{'id':'original','page_count':5,'reason':'保留原结构'},
                {'id':'merged','page_count':3,'reason':'主题合并，减少重复标题，独有事实保留'}],
                'chosen':'merged','reason':'合成测试：5组信息合到3页，保持来源范围'})
        self.content['source_facts'].extend([
            dict(id='duplicate',source_indices=[2],text='第1组岗位信息',kind='fact',action='merged_duplicate',duplicate_of='f1',reason='同信息重复'),
            dict(id='ad',source_indices=[5],text='评论556看主页',kind='promotion',action='removed',reason='导流广告')])
        for pages in ([1,2],[3,4],[5]):
            card=copy.deepcopy(base)
            card.pop('source_image')
            card.update(source_indices=pages,fact_ids=[f'f{i}' for i in pages])
            card['blocks'][0]['fields']=[{'label':f'信息{i}','text':f'第{i}组岗位信息'} for i in pages]
            self.content['cards'].append(card)

    def tearDown(self):
        self.f.tearDown()

    def test_valid_five_to_three_and_semantic_gate(self):
        self.assertEqual(len(validate(self.content,self.f.manifest,self.f.source)),3)
        for change in ({'reviewed':False}, {'chosen':'unknown'}, {'alternatives':[]}):
            c=copy.deepcopy(self.content); c['reorganization'].update(change)
            with self.assertRaises(ValueError): validate(c,self.f.manifest,self.f.source)

    def test_dropped_unique_fact_and_invalid_duplicates_block(self):
        c=copy.deepcopy(self.content); c['source_facts'][0]['action']='removed'
        with self.assertRaisesRegex(ValueError,'独有'): validate(c,self.f.manifest,self.f.source)
        c=copy.deepcopy(self.content); c['cards'][0]['fact_ids'].remove('f2')
        with self.assertRaisesRegex(ValueError,'遗漏'): validate(c,self.f.manifest,self.f.source)
        c=copy.deepcopy(self.content); c['source_facts'][-2]['duplicate_of']='unknown'
        with self.assertRaisesRegex(ValueError,'重复合并'): validate(c,self.f.manifest,self.f.source)

    def test_source_scope_and_claimed_page_count_block(self):
        c=copy.deepcopy(self.content); c['cards'][0]['source_indices']=[1,6]
        with self.assertRaisesRegex(ValueError,'范围'): validate(c,self.f.manifest,self.f.source)
        c=copy.deepcopy(self.content); c['reorganization']['alternatives'][1]['page_count']=2
        with self.assertRaisesRegex(ValueError,'页数'): validate(c,self.f.manifest,self.f.source)
        c=copy.deepcopy(self.content); c['selected_indices']=[2,3,4,5]
        with self.assertRaisesRegex(ValueError,'未选'): validate(c,self.f.manifest,self.f.source)

    def test_real_smart_render_and_full_delivery_mapping(self):
        self.f.write(self.root/'content.json',self.content)
        self.f.write(self.f.source/'manifest.json',self.f.manifest)
        output=self.root/'smart-out'
        args=argparse.Namespace(content=self.root/'content.json',manifest=self.f.source/'manifest.json',output=output,
                                history=self.root/'history.json',template=None,font_file=None)
        self.assertEqual(render(args),0)
        report=json.loads((output/'review.json').read_text(encoding='utf-8'))
        self.assertEqual([e['source_indices'] for e in report['cards']],[[1,2],[3,4],[5]])
        self.assertEqual(len(list(output.glob('*.png'))),3)
        self.f.content=self.content
        self.f.out=output
        self.f.texts(600)
        p=self.root/'text-review.json'
        review=json.loads(p.read_text(encoding='utf-8'))
        review.update(selected_indices=[1,2,3,4,5],reorganization_reviewed=True,image_checks=[dict(file=e['file'],source_indices=e['source_indices'],sha256=e['sha256'],
            text_correct=True,layout_passed=True,disclaimer_reviewed=True,disclaimer_style_reviewed=True,issues=[],notes='合成测试；不是实际语义质量证明') for e in report['cards']])
        self.f.write(p,review)
        result=check(self.root/'content.json',self.f.source/'manifest.json',output/'review.json',self.root)
        self.assertEqual(result['output_source_indices'],[[1,2],[3,4],[5]])
        self.assertTrue(result['passed'])
        review['reorganization_reviewed']=False
        self.f.write(p,review)
        with self.assertRaisesRegex(ValueError,'去重'): check(self.root/'content.json',self.f.source/'manifest.json',output/'review.json',self.root)


if __name__=='__main__': unittest.main()
