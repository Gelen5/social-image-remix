import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from article_layout import fragment, validate_fragment, render_article, check_layout


class ArticleLayoutTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.article='关键条件要核对。'+'资料'*145+'\n\n'+'保留全部信息。'+'正文'*146
        self.article+='文'*(600-sum(not c.isspace() for c in self.article))
        (self.root/'article.txt').write_text(self.article,encoding='utf-8')
        self.plan={'emphasis':[{'paragraph':1,'start':0,'end':7,'tone':'accent'}, {'paragraph':2,'start':0,'end':6,'tone':'black'}]}
        (self.root/'plan.json').write_text(json.dumps(self.plan),encoding='utf-8')

    def tearDown(self): self.tmp.cleanup()

    def test_both_themes_mobile_preview_and_copy_payload(self):
        out=self.root/'layout'
        report=render_article(self.root/'article.txt',out,layout_path=self.root/'plan.json')
        self.assertEqual(len(report['mobile_checks']),6)
        self.assertEqual(len(check_layout(self.article,out/'article-layout-report.json')),3)
        for theme,color in (('red-black','#C00000'),('orange-black','#E67E17')):
            markup=(out/f'article-{theme}.html').read_text(encoding='utf-8')
            self.assertIn(color,markup)
            self.assertNotIn('#E67E17' if theme=='red-black' else '#C00000',markup)
            self.assertNotIn('<title',markup)
            self.assertNotIn('<script',markup)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser=p.chromium.launch()
            page=browser.new_page()
            page.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{write:async(items)=>{window.copied=await items[0].getType('text/html').then(b=>b.text());}}});")
            page.goto((out/'article-preview.html').as_uri())
            page.select_option('#theme','orange-black')
            page.click('#copy')
            page.wait_for_function('window.copied !== undefined')
            self.assertEqual(page.evaluate('window.copied'),(out/'article-orange-black.html').read_text(encoding='utf-8'))
            browser.close()

    def test_markup_escape_missing_text_and_color_pollution(self):
        dangerous='<script>alert(1)</script>&'
        article=dangerous+'文'*(600-len(dangerous))
        markup=fragment(article,'red-black')
        self.assertIn('&lt;script&gt;',markup)
        validate_fragment(markup,article,'red-black')
        for changed in (markup.replace('alert','different'),markup.replace('#000000','#E67E17'),markup+'<script>x</script>'):
            with self.assertRaises(ValueError): validate_fragment(changed,article,'red-black')

    def test_bad_emphasis_and_stale_layout_block(self):
        for spans in ([{'paragraph':9,'start':0,'end':2}], [{'paragraph':1,'start':0,'end':16}],
                      [{'paragraph':1,'start':0,'end':4},{'paragraph':1,'start':2,'end':5}]):
            with self.assertRaises(ValueError): fragment(self.article,'red-black',{'emphasis':spans})
        out=self.root/'single'
        render_article(self.root/'article.txt',out,themes='red-black',mobile=False)
        self.assertEqual(len(check_layout(self.article,out/'article-layout-report.json')),2)
        with self.assertRaises(ValueError): check_layout(self.article.replace('条件','要求'),out/'article-layout-report.json')
        with self.assertRaises(ValueError): render_article(self.root/'article.txt',out)
        self.assertFalse(json.loads((out/'article-layout-report.json').read_text())['passed'])


if __name__=='__main__': unittest.main()
