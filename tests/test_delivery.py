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
from check_delivery import check, text_signature, check_copy_style
from workflow_common import content_digest, count_text, work_key, IMAGE_DISCLAIMER
from style_registry import reserve
from render_cards import choose_style, render
from browser_extract import dom_query, host_matches, CDNS
from article_layout import render_article
from topic_tags import select_tags,tag_line
from disclaimer import check_styles
from title_quality import validate_titles


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
                        'cards':[{'source_image':'01.png','title':'招聘学历条件测试','subtitle':'','footer':'',
                                  'blocks':[{'heading':'条件','fields':[{'label':'学历','text':'本科'}]}]}]}
        self.content['cards'][0]['disclaimer_decision'] = {'required': True, 'classification': 'recruitment', 'reason': '本张说明招聘学历条件', 'evidence': ['招聘学历条件测试', '学历：本科']}
        self.manifest = {'complete':True,'expected_count':1,'errors':[], 'source_url':self.content['source_url'],
                         'images':[{'index':1,'file':'01.png','sha256':self.sha(self.source/'01.png')}]}
        self.disclaimer_style = dict(font_family='Microsoft YaHei',font_size_px_at_1080=22,font_weight=400,color='#143a26',alignment='center',bottom_margin_px_at_1080=36,line_height=1.4)
        self.image_report = {'passed':True,'template':'test-design','work_key':work_key(self.content['source_url']),
                             'content_sha256':content_digest(self.content),'cards':[{'source_index':1,'source_image':'01.png',
                             'file':'01.png','sha256':self.sha(self.out/'01.png'),'disclaimer':IMAGE_DISCLAIMER,'disclaimer_decision':self.content['cards'][0]['disclaimer_decision'],'disclaimer_style':copy.deepcopy(self.disclaimer_style)}], 'disclaimer_style':self.disclaimer_style}
        self.write(self.root/'content.json',self.content)
        self.write(self.source/'manifest.json',self.manifest)
        self.write(self.out/'review.json',self.image_report)
        self.texts(450)

    def tearDown(self):
        self.tmp.cleanup()

    def test_two_title_sets_exact_length_and_counting(self):
        caption=['字'*18+c for c in '甲乙丙']
        article=['文'*32,'一个自然的文章标题','不同方向的文章标题']
        self.assertEqual(len(validate_titles(caption,article)['caption']),3)
        validate_titles(['字'*16+'A1，',caption[1],caption[2]],article)
        validate_titles(['字'*8+' '+'文'*10,caption[1],caption[2]],article)
        for value in ('字'*18,'字'*20,'字'*17+'甲\u200b',' '+'字'*18,'字'*17+'  '):
            with self.subTest(title=value),self.assertRaises(ValueError):
                validate_titles([value,*caption[1:]],article)
        for values in (caption[:2],caption+[caption[0]],[caption[0],caption[0],caption[2]]):
            with self.assertRaises(ValueError):validate_titles(values,article)
        with self.assertRaises(ValueError):validate_titles(caption,['文'*33,*article[1:]])
        with self.assertRaises(ValueError):validate_titles(caption,[caption[0],*article[1:]])
        (self.root/'caption-titles.json').unlink()
        with self.assertRaises(FileNotFoundError):self.run_check()

    def test_title_and_writing_reviews_bound_to_actual_text(self):
        path=self.root/'text-review.json'
        original=json.loads(path.read_text(encoding='utf-8'))
        for change in ({'natural':False},{'appeal':False},{'facts_supported':False},
                       {'distinct':False},{'characters':18},{'issues':['凑字数']},{'notes':''},{'title':'旧标题'}):
            value=copy.deepcopy(original);value['title_checks'][0].update(change)
            self.write(path,value)
            with self.assertRaisesRegex(ValueError,'标题'):self.run_check()
        for change in ({'writing_reviewed':False},{'writing_issues':['段落拼接']},{'writing_notes':''},{'title_checks':[]}):
            self.write(path,dict(original,**change))
            with self.assertRaises(ValueError):self.run_check()
        self.write(path,original)
        self.write(self.root/'caption-titles.json',['文'*18+'甲','字'*18+'乙','字'*18+'丙'])
        with self.assertRaisesRegex(ValueError,'版本不一致'):self.run_check()
        # Even a refreshed signature cannot substitute for reviewing revised titles.
        self.write(path,dict(original,text_sha256=text_signature(self.root)))
        with self.assertRaisesRegex(ValueError,'旧标题'):self.run_check()

    def test_disclaimer_style_is_locked_across_visible_pages(self):
        report=copy.deepcopy(self.image_report)
        report['cards'].append(copy.deepcopy(report['cards'][0]))
        cards=[self.content['cards'][0],copy.deepcopy(self.content['cards'][0])]
        check_styles(report,cards)
        for field,value in [('font_family','AnotherFont'),('font_size_px_at_1080',24),
                            ('font_weight',700),('color','#888888'),('alignment','right'),
                            ('bottom_margin_px_at_1080',24),('line_height',1.8)]:
            changed=copy.deepcopy(report)
            changed['cards'][1]['disclaimer_style'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'样式一致'):
                check_styles(changed,cards)
        for value in (None,{},dict(self.disclaimer_style,font_size_px_at_1080=float('nan'))):
            with self.assertRaises(ValueError):check_styles(dict(report,disclaimer_style=value),cards)
        general=copy.deepcopy(cards[0])
        general['disclaimer_decision']=dict(required=False,classification='general',reason='通用方法',evidence=['简历写法'])
        check_styles({'cards':[{}]},[general])
        general['footer']=IMAGE_DISCLAIMER
        with self.assertRaises(ValueError):check_styles({'cards':[{}]},[general])

    def test_caption_without_boilerplate_and_article_independent_of_images(self):
        for value in ('仅作信息分享，不涉及招聘。','仅供信息分享。','以企业官方信息为准。','岗位是否开放，请自行确认。'):
            with self.subTest(caption=value),self.assertRaisesRegex(ValueError,'配文'):
                check_copy_style(value,'按行业和岗位方向介绍企业。')
        for value in ('第一张图适合技术专业。','第2张图片列出企业。','这组三张图整理企业。','这三张图提供方向。','图中资料提到实习。','如图所示。'):
            with self.subTest(article=value),self.assertRaisesRegex(ValueError,'独立阅读'):
                check_copy_style('留学生实习方向清单。',value)
        check_copy_style('2027届实习方向，涵盖技术、市场和供应链。',
                         '图像算法属于技术方向，第二季度安排需按实际材料确认。')
        self.texts(450,caption='仅作信息分享。')
        with self.assertRaisesRegex(ValueError,'配文'):self.run_check()
        self.texts(450)
        (self.root/'article.txt').write_text('第一张图'+'文'*446,encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'独立阅读'):self.run_check()

    def sha(self,p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    def write(self,p,v):
        p.write_text(json.dumps(v,ensure_ascii=False),encoding='utf-8')

    def texts(self,length,caption='图中条件供参考。',titles=None):
        (self.root/'article.txt').write_text('文'*length,encoding='utf-8')
        (self.root/'caption.txt').write_text(caption,encoding='utf-8')
        article_titles=titles if titles is not None else ['标题一','标题二','标题三']
        caption_titles=['字'*18+c for c in '甲乙丙']
        self.write(self.root/'titles.json',article_titles)
        self.write(self.root/'caption-titles.json',caption_titles)
        scope=self.content.get('selected_indices',[1])
        candidate={'content_sha256':content_digest(self.content),'relevance_reviewed':True,'candidates':[
            {'keyword':word,'relevance_score':.8,'source_indices':scope,'reason':'合成测试词，仅测试交付门禁'} for word in ['本科','学历','岗位','求职','就业']]}
        result=select_tags(self.content,candidate)
        self.write(self.root/'topics.json',result)
        (self.root/'topics.txt').write_text(tag_line(result),encoding='utf-8')
        self.write(self.root/'text-review.json',dict(content_sha256=content_digest(self.content),selected_indices=[1],
            text_sha256=text_signature(self.root),facts_reviewed=True,scope_reviewed=True,titles_reviewed=True,
            images_visually_reviewed=True,cleanup_reviewed=True,topics_reviewed=True,topics_sha256=self.sha(self.root/'topics.json'),notes='合成测试数据，仅验证门禁，不是实际文字质量证明',
            writing_reviewed=True,writing_issues=[],writing_notes='合成门禁测试，不代表实际自然度验收',
            title_checks=[dict(role=role,index=i,title=t,characters=len(t),facts_supported=True,natural=True,appeal=True,distinct=True,issues=[],notes='合成标题仅验证门禁，不是吸引力证明') for role,values in [('caption',caption_titles),('article',article_titles)] for i,t in enumerate(values,1)],
            image_checks=[dict(file='01.png',source_index=1,sha256=self.sha(self.out/'01.png'),
                               text_correct=True,layout_passed=True,disclaimer_reviewed=True,disclaimer_style_reviewed=True,issues=[],notes='合成测试图，仅检查门禁，不是实际脚注视觉证明')]))
        if 1<=length<=500:
            output=self.root/f'layout-{len(list(self.root.glob("layout-*")))}'
            render_article(self.root/'article.txt',output,mobile=False)
            review=json.loads((self.root/'text-review.json').read_text(encoding='utf-8'))
            review.update(article_layout_reviewed=True,article_layout_report=str((output/'article-layout-report.json').relative_to(self.root)),
                          article_layout_report_sha256=self.sha(output/'article-layout-report.json'))
            self.write(self.root/'text-review.json',review)

    def run_check(self):
        return check(self.root/'content.json',self.source/'manifest.json',self.out/'review.json',self.root)

    def test_length_boundaries_titles_and_caption(self):
        for n in (1,450,500):
            self.texts(n)
            self.assertEqual(self.run_check()['article_characters'],n)
        for n in (0,501):
            self.texts(n)
            with self.assertRaises(ValueError): self.run_check()
        for caption in ('', '字'*201, '\n\n'.join(['一段']*6)):
            self.texts(450,caption)
            with self.assertRaises(ValueError): self.run_check()
        for titles in (['一','二'], ['一','二','三','四'], ['一','一','三'], ['一','','三']):
            self.texts(450,titles=titles)
            with self.assertRaises(ValueError): self.run_check()
        self.assertEqual(count_text(' 中 文\n2027， '),7)

    def test_each_image_quality_review_required_and_version_bound(self):
        p=self.root/'text-review.json'
        original=json.loads(p.read_text(encoding='utf-8'))
        for change in ({'text_correct':False}, {'layout_passed':False}, {'disclaimer_reviewed':False}, {'disclaimer_style_reviewed':False}, {'issues':['标题溢出']}, {'sha256':'old'}, {'notes':''}):
            record=copy.deepcopy(original)
            record['image_checks'][0].update(change)
            self.write(p,record)
            with self.assertRaises(ValueError): self.run_check()
        for missing in (None, []):
            self.write(p,dict(original,image_checks=missing))
            with self.assertRaises(ValueError): self.run_check()
        self.write(p,original)
        self.assertTrue(self.run_check()['passed'])

    def test_disclaimer_missing_or_changed_blocks(self):
        for value in (None,'仅作信息分享','不涉及任何招聘'):
            report=copy.deepcopy(self.image_report)
            report['cards'][0]['disclaimer']=value
            self.write(self.out/'review.json',report)
            with self.assertRaisesRegex(ValueError,'脚注'): self.run_check()

    def test_general_decision_allows_no_new_note_but_requires_current_judgment(self):
        value=dict(required=False,classification='general',reason='通用学历说明，无招聘推荐',evidence=['学历：本科'])
        self.content['cards'][0]['disclaimer_decision']=value
        self.write(self.root/'content.json',self.content)
        self.image_report['content_sha256']=content_digest(self.content)
        self.image_report['cards'][0].update(disclaimer=None,disclaimer_decision=value)
        self.write(self.out/'review.json',self.image_report)
        self.texts(450)
        self.assertTrue(self.run_check()['passed'])
        for change in ({'disclaimer':IMAGE_DISCLAIMER},{'disclaimer_decision':None}):
            report=copy.deepcopy(self.image_report)
            report['cards'][0].update(change)
            self.write(self.out/'review.json',report)
            with self.assertRaisesRegex(ValueError,'脚注'):self.run_check()

    def test_caption_semantic_paragraph_count(self):
        for count in (1, 2, 5):
            self.texts(450,caption='\n\n'.join(['本段仅为结构测试。']*count))
            self.assertEqual(self.run_check()['caption_paragraphs'],count)
        self.texts(450,caption='第一段。\r\n\r\n第二段。')
        self.assertEqual(self.run_check()['caption_paragraphs'],2)

    def test_article_layout_review_and_requested_theme_block(self):
        p=self.root/'text-review.json'
        review=json.loads(p.read_text(encoding='utf-8'))
        self.write(p,dict(review,article_layout_reviewed=False))
        with self.assertRaisesRegex(ValueError,'排版'): self.run_check()
        self.write(p,dict(review,article_layout_report_sha256='old'))
        with self.assertRaisesRegex(ValueError,'过期'): self.run_check()
        self.content['article_theme']='orange-black'
        self.write(self.root/'content.json',self.content)
        report=copy.deepcopy(self.image_report)
        report['content_sha256']=content_digest(self.content)
        self.write(self.out/'review.json',report)
        review['content_sha256']=content_digest(self.content)
        self.write(p,review)
        with self.assertRaisesRegex(ValueError,'主题'): self.run_check()

    def test_stale_texts_scope_and_extra_files_block(self):
        (self.root/'article.txt').write_text('新'*450,encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'版本'): self.run_check()
        self.texts(450)
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
