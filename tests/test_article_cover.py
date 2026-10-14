import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from article_cover import check_cover
from article_layout import body_hash


class ArticleCoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.article='留学生实习按岗位方向选择企业。'
        self.file=self.root/'cover.png';Image.new('RGB',(470,200)).save(self.file)
        self.path=self.root/'cover-report.json'
        self.report=dict(passed=True,article_sha256=body_hash(self.article),keyword='实习选岗',
                         file='cover.png',sha256=self.sha(self.file),width=470,height=200,ratio='2.35:1',core_summary='通过岗位方向帮助留学生选择实习企业',keyword_reason='实习选岗覆盖全文选岗问题，非单个企业',keyword_candidates=[dict(keyword='实习选岗',reason='选岗核心'),dict(keyword='岗位对照',reason='强调对照方式，弱化实习语境')])
        self.save(self.report)
        self.review=dict(article_cover_reviewed=True,article_cover_report_sha256=self.sha(self.path),
            cover_check=dict(sha256=self.sha(self.file),keyword='实习选岗',article_sha256=body_hash(self.article),
                text_correct=True,layout_passed=True,theme_matched=True,keyword_summary_reviewed=True,issues=[],notes='合成门禁数据，不是图内文字和语义的视觉证明'))

    def tearDown(self):self.tmp.cleanup()
    def sha(self,p):return hashlib.sha256(p.read_bytes()).hexdigest()
    def save(self,value):self.path.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')

    def test_valid_cover_ratio_and_four_character_keyword(self):
        result=check_cover(self.article,self.path,self.review)
        self.assertEqual(result['keyword'],'实习选岗')
        self.assertEqual(result['ratio'],'2.35:1')
        for value in ('实习','实习选岗表','实习19','实习 选','实习选。'):
            self.save(dict(self.report,keyword=value))
            with self.assertRaisesRegex(ValueError,'4个汉字'):check_cover(self.article,self.path,self.review)

    def test_core_summary_and_candidate_comparison_required(self):
        for change in ({'core_summary':''},{'keyword_reason':''},{'keyword_candidates':[]},
                       {'keyword_candidates':[{'keyword':'实习选岗','reason':'单个候选'}]},
                       {'keyword_candidates':[{'keyword':'实习选岗','reason':'理由'},{'keyword':'实习选岗','reason':'重复'}]},
                       {'keyword_candidates':[{'keyword':'岗位对照','reason':'对照'},{'keyword':'实习指南','reason':'领域'}]}):
            self.save(dict(self.report,**change))
            with self.assertRaises(ValueError):check_cover(self.article,self.path,self.review)

    def test_announcement_freshness_requires_source_date_and_actual_review(self):
        value=copy.deepcopy(self.report)
        value['keyword']='最新发布'
        value['keyword_candidates'][0]['keyword']='最新发布'
        review=copy.deepcopy(self.review)
        review['cover_check']['keyword']='最新发布'
        def prepare():
            self.save(value)
            review['article_cover_report_sha256']=self.sha(self.path)
        prepare()
        with self.assertRaisesRegex(ValueError,'时效'):check_cover(self.article,self.path,review)
        value['publication_evidence']=dict(source_url='https://example.com/notice',published_on='2026-10-14',checked_on='2026-10-14',notes='合成来源，仅测试门禁，不是实际最新公告证据')
        prepare()
        with self.assertRaisesRegex(ValueError,'时效'):check_cover(self.article,self.path,review)
        review['cover_check']['freshness_reviewed']=True
        self.assertTrue(check_cover(self.article,self.path,review)['passed'])
        value['publication_evidence']['published_on']='2026-10-15'
        prepare()
        with self.assertRaisesRegex(ValueError,'日期'):check_cover(self.article,self.path,review)

    def test_stale_review_theme_or_article_blocks(self):
        for change in ({'text_correct':False},{'layout_passed':False},{'theme_matched':False},{'keyword_summary_reviewed':False},
                       {'issues':['四字错字']},{'notes':''},{'keyword':'岗位推荐'},{'sha256':'old'}):
            review=copy.deepcopy(self.review);review['cover_check'].update(change)
            with self.assertRaises(ValueError):check_cover(self.article,self.path,review)
        for change in ({'article_cover_reviewed':False},{'article_cover_report_sha256':'old'}):
            with self.assertRaises(ValueError):check_cover(self.article,self.path,dict(self.review,**change))
        with self.assertRaisesRegex(ValueError,'旧文章'):check_cover(self.article+'改变',self.path,self.review)

    def test_wrong_ratio_dimensions_hash_or_path_blocks(self):
        for change in ({'width':471},{'ratio':'3:4'},{'sha256':'old'},{'file':'../cover.png'}):
            self.save(dict(self.report,**change))
            with self.assertRaises(ValueError):check_cover(self.article,self.path,self.review)
        Image.new('RGB',(300,400)).save(self.file)
        self.save(dict(self.report,width=300,height=400,sha256=self.sha(self.file)))
        with self.assertRaisesRegex(ValueError,'2.35:1'):check_cover(self.article,self.path,self.review)


if __name__=='__main__':unittest.main()
