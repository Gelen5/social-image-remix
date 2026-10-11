import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from check_delivery import check, text_signature
from workflow_common import content_digest, count_text, work_key
from style_registry import reserve
from render_cards import choose_style, render
from browser_extract import dom_query, host_matches, CDNS


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root/'source'
        self.out = self.root/'out'
        self.source.mkdir(); self.out.mkdir()
        Image.new('RGB',(300,400)).save(self.source/'01.png')
        Image.new('RGB',(600,800)).save(self.out/'01.png')
        self.content = {'source_url':'https://v.m.chenzhongtech.com/fw/photo/abc?token=1',
                        'transcription_reviewed':True,'selected_indices':[1],
                        'cards':[{'source_image':'01.png','title':'测试','subtitle':'','footer':'',
                                  'blocks':[{'heading':'条件','fields':[{'label':'学历','text':'本科'}]}]}]}
        self.manifest = {'complete':True,'expected_count':1,'errors':[], 'source_url':self.content['source_url'],
                         'images':[{'index':1,'file':'01.png','sha256':self.sha(self.source/'01.png')}]}
        self.image_report = {'passed':True,'template':'test-design','work_key':work_key(self.content['source_url']),
                             'content_sha256':content_digest(self.content),'cards':[{'source_index':1,'source_image':'01.png',
                             'file':'01.png','sha256':self.sha(self.out/'01.png')}]}
        self.write(self.root/'content.json',self.content)
        self.write(self.source/'manifest.json',self.manifest)
        self.write(self.out/'review.json',self.image_report)
        self.texts(600)

    def tearDown(self):
        self.tmp.cleanup()

    def sha(self,p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    def write(self,p,v):
        p.write_text(json.dumps(v,ensure_ascii=False),encoding='utf-8')

    def texts(self,length,caption='图中条件供参考。',titles=None):
        (self.root/'article.txt').write_text('文'*length,encoding='utf-8')
        (self.root/'caption.txt').write_text(caption,encoding='utf-8')
        self.write(self.root/'titles.json',titles if titles is not None else ['标题一','标题二','标题三'])
        self.write(self.root/'text-review.json',dict(content_sha256=content_digest(self.content),selected_indices=[1],
            text_sha256=text_signature(self.root),facts_reviewed=True,scope_reviewed=True,titles_reviewed=True,
            images_visually_reviewed=True,cleanup_reviewed=True,notes='合成测试数据，仅验证门禁，不是实际文字质量证明'))

    def run_check(self):
        return check(self.root/'content.json',self.source/'manifest.json',self.out/'review.json',self.root)

    def test_length_boundaries_titles_and_caption(self):
        for n in (580,600,620):
            self.texts(n)
            self.assertEqual(self.run_check()['article_characters'],n)
        for n in (579,621):
            self.texts(n)
            with self.assertRaises(ValueError): self.run_check()
        for caption in ('', '字'*201, '一段\n另一段'):
            self.texts(600,caption)
            with self.assertRaises(ValueError): self.run_check()
        for titles in (['一','二'], ['一','二','三','四'], ['一','一','三'], ['一','','三']):
            self.texts(600,titles=titles)
            with self.assertRaises(ValueError): self.run_check()
        self.assertEqual(count_text(' 中 文\n2027， '),7)

    def test_stale_texts_scope_and_extra_files_block(self):
        (self.root/'article.txt').write_text('新'*600,encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'版本'): self.run_check()
        self.texts(600)
        report = copy.deepcopy(self.image_report)
        report['cards'][0]['source_index']=2
        self.write(self.out/'review.json',report)
        with self.assertRaisesRegex(ValueError,'范围'): self.run_check()
        self.write(self.out/'review.json',self.image_report)
        (self.out/'03.png').write_bytes((self.out/'01.png').read_bytes())
        with self.assertRaisesRegex(ValueError,'旧PNG'): self.run_check()

    def test_cli_invalidates_old_success(self):
        import subprocess
        (self.root/'delivery.json').write_text('{"passed":true}',encoding='utf-8')
        self.texts(579)
        result=subprocess.run([sys.executable,str(Path(__file__).resolve().parents[1]/'scripts/check_delivery.py'),
            '--content',str(self.root/'content.json'),'--manifest',str(self.source/'manifest.json'),
            '--image-report',str(self.out/'review.json'),'--text-root',str(self.root)],capture_output=True)
        self.assertEqual(result.returncode,2)
        saved=json.loads((self.root/'delivery.json').read_text(encoding='utf-8'))
        self.assertFalse(saved['passed'])
        self.assertNotIn('images',saved)

    def test_work_style_persists_across_scope_and_tracking(self):
        self.assertEqual(work_key(self.content['source_url']),work_key('https://www.kuaishou.com/short-video/abc?x=2'))
        history = self.root/'history.json'
        design = self.root/'design.json'
        self.write(design,{'palette':['white','purple','teal'],'cards':'thin border'})
        bound = reserve(self.content['source_url'],history,design)
        changed = dict(self.content,selected_indices=[2,3])
        style,_ = choose_style(changed,self.root/'other-output',history)
        self.assertEqual(style['template'],bound['template'])
        self.assertEqual(reserve(self.content['source_url'],history)['design'],bound['design'])
        other,_ = choose_style(dict(changed,source_url='https://www.kuaishou.com/short-video/different'),self.root/'next',history)
        self.assertNotEqual(other['template'],bound['template'])

    def test_renderer_refuses_old_output_without_deleting(self):
        args=argparse.Namespace(content=self.root/'content.json',manifest=self.source/'manifest.json',output=self.out,
                                history=self.root/'history.json',template=None,font_file=None)
        before=self.sha(self.out/'01.png')
        with self.assertRaisesRegex(ValueError,'新的输出目录'): render(args)
        self.assertEqual(before,self.sha(self.out/'01.png'))
        self.assertFalse(json.loads((self.out/'review.json').read_text())['passed'])

    def test_kuaishou_atlas_lazy_images_and_multiple_groups(self):
        from playwright.sync_api import sync_playwright
        self.assertTrue(any(host_matches('p5.a.yximgs.com',d) for d in CDNS))
        with sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page()
            page.route('**/*',lambda route:route.abort())
            html='<div>1 / 4</div>'+''.join(f'<figure class="swiper-card"><img class="image-main" src="https://p5.a.yximgs.com/ufile/atlas/group_{i}.jpg"></figure>' for i in range(4))
            page.set_content(html)
            value=json.loads(page.evaluate(dom_query('kuaishou',None)))
            self.assertEqual(len(value['images']),4)
            self.assertEqual(value['expected_count'],4)
            page.set_content(html+'<figure class="swiper-card"><img class="image-main" src="https://p5.a.yximgs.com/ufile/atlas/other_0.jpg"></figure>')
            with self.assertRaisesRegex(Exception,'多个快手图集'): page.evaluate(dom_query('kuaishou',None))
            browser.close()


if __name__=='__main__': unittest.main()
