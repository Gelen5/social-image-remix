"""WeChat inline article fragments based on customer-write red/orange-black specs."""
import argparse
import base64
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from workflow_common import count_text

THEMES = {'red-black':'#C00000', 'orange-black':'#E67E17'}


def canonical(text):
    return ''.join(c for c in text if not c.isspace())


def body_hash(text):
    return hashlib.sha256(text.strip().encode('utf-8')).hexdigest()


class FragmentParser(HTMLParser):
    def __init__(self, accent):
        super().__init__(convert_charrefs=True)
        self.stack=[]; self.text=[]; self.accent=accent

    def handle_starttag(self, tag, attrs):
        if tag not in ('section','p','span'):
            raise ValueError('正文存在非兼容标签：'+tag)
        attrs=dict(attrs)
        if set(attrs)-{'style','leaf'} or 'style' not in attrs and tag != 'span':
            raise ValueError('正文只允许内联style与span leaf属性')
        if tag=='span' and attrs.get('leaf')!='':
            raise ValueError('文字必须使用span leaf包裹')
        style=attrs.get('style','')
        if re.search(r'url\s*\(|expression\s*\(|var\s*\(|background\s*:|position\s*:|gradient|@',style,re.I):
            raise ValueError('正文包含不支持或外部依赖样式')
        for color in re.findall(r'#[0-9a-fA-F]{6}',style):
            if color.upper() not in {'#000000','#FFFFFF','#767676','#DDDDDD',self.accent}:
                raise ValueError('正文混入另一强调色或非规范颜色')
        is_note='font-size:14px' in style and 'border-left:2px solid #DDDDDD' in style
        if tag=='p' and not is_note and re.search(r'(?:padding|margin)-(?:left|right)\s*:\s*(?!0(?:px)?(?:;|$))',style):
            raise ValueError('普通正文不可左右内缩')
        self.stack.append(tag)

    def handle_endtag(self,tag):
        if not self.stack or self.stack.pop()!=tag:
            raise ValueError('正文HTML结构不匹配')

    def handle_data(self,data):
        if data.strip() and (not self.stack or self.stack[-1]!='span'):
            raise ValueError('正文文字节点未由span leaf包裹')
        self.text.append(data)


def validate_fragment(markup, article, theme):
    if theme not in THEMES or not markup.lstrip().startswith('<section '):
        raise ValueError('缺少正文section或未知主题')
    parser=FragmentParser(THEMES[theme]); parser.feed(markup); parser.close()
    if parser.stack or canonical(''.join(parser.text))!=canonical(article):
        raise ValueError('排版文字与正文不一致，不能加标题、漏字或改字')
    if not 1<=count_text(''.join(parser.text))<=500:
        raise ValueError('排版正文必须非空且不超过500字')


def fragment(article, theme, layout=None):
    paragraphs=[p.strip() for p in re.split(r'\n\s*\n',article.strip()) if p.strip()]
    spans=(layout or {}).get('emphasis',[])
    notes=(layout or {}).get('notes',[])
    if not isinstance(notes,list) or any(type(i) is not int or not 1<=i<=len(paragraphs) for i in notes):
        raise ValueError('注释段号不合法')
    if not isinstance(spans,list): raise ValueError('emphasis需为数组')
    ranges={}; accent_count=0; emphasized=0
    for item in spans:
        p,start,end=item.get('paragraph'),item.get('start'),item.get('end')
        tone=item.get('tone','accent')
        if (type(p) is not int or not 1<=p<=len(paragraphs) or type(start) is not int or type(end) is not int
                or not 0<=start<end<=len(paragraphs[p-1]) or end-start>15 or tone not in ('accent','black')):
            raise ValueError('加粗范围/段号错误、过长或未知强调类型')
        if any(start<r[1] and end>r[0] for r in ranges.get(p,[])):
            raise ValueError('加粗范围重叠')
        ranges.setdefault(p,[]).append((start,end,tone))
        accent_count+=tone=='accent'; emphasized+=count_text(paragraphs[p-1][start:end])
    if accent_count>4 or emphasized>count_text(article)*.15:
        raise ValueError('强调过密：彩色最多4处，总加粗不超过15%')
    result=['<section style="margin:0;padding:0;background-color:#FFFFFF;">']
    for number,text in enumerate(paragraphs,1):
        chunks=[]; position=0
        for start,end,tone in sorted(ranges.get(number,[])):
            if start>position: chunks.append('<span leaf="">'+html.escape(text[position:start])+'</span>')
            color=THEMES[theme] if tone=='accent' else '#000000'
            chunks.append(f'<span leaf="" style="font-weight:700;color:{color};">'+html.escape(text[start:end])+'</span>')
            position=end
        if position<len(text): chunks.append('<span leaf="">'+html.escape(text[position:])+'</span>')
        style='margin:0 0 18px;font-size:16px;line-height:2.0;color:#000000;overflow-wrap:anywhere;'
        if number in notes:
            style='margin:0 0 28px;padding-left:12px;border-left:2px solid #DDDDDD;font-size:14px;line-height:1.9;color:#767676;overflow-wrap:anywhere;'
        result.append('<p style="'+style+'">'+''.join(chunks)+'</p>')
    result.append('</section>')
    markup='\n'.join(result)
    validate_fragment(markup,article,theme)
    return markup


def preview(markups):
    payload={theme:base64.b64encode(markup.encode()).decode() for theme,markup in markups.items()}
    options=''.join(f'<option value="{t}">'+('红黑' if t=='red-black' else '橙黑')+'</option>' for t in markups)
    return '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>文章排版预览</title>
<style>body{margin:0;background:#f3f4f6;font-family:"Microsoft YaHei",sans-serif}nav{padding:16px;display:flex;gap:8px;flex-wrap:wrap}button,select{padding:8px}.paper{box-sizing:border-box;max-width:100%;width:375px;margin:8px auto;background:white;padding:15px}.paper p{overflow-wrap:anywhere}#status{padding:0 16px}</style>
<nav><label>样式 <select id="theme">OPTIONS</select></label><label>阅读宽度 <select id="width"><option>320</option><option selected>375</option><option>430</option></select></label><button id="copy">复制正文排版</button></nav><p id="status" role="status">标题另填；复制仅含正文，实际粘贴后请预览。</p><main class="paper"><article id="article"></article></main>
<script>const payload=PAYLOAD;let markup='';function show(){markup=new TextDecoder().decode(Uint8Array.from(atob(payload[document.querySelector('#theme').value]),c=>c.charCodeAt(0)));document.querySelector('#article').innerHTML=markup;}document.querySelector('#theme').onchange=show;document.querySelector('#width').onchange=e=>document.querySelector('.paper').style.width=e.target.value+'px';document.querySelector('#copy').onclick=async()=>{try{if(navigator.clipboard&&window.ClipboardItem){await navigator.clipboard.write([new ClipboardItem({'text/html':new Blob([markup],{type:'text/html'}),'text/plain':new Blob([document.querySelector('#article').innerText],{type:'text/plain'})})]);}else{const range=document.createRange();range.selectNodeContents(document.querySelector('#article'));const selection=window.getSelection();selection.removeAllRanges();selection.addRange(range);if(!document.execCommand('copy'))throw Error();selection.removeAllRanges();}document.querySelector('#status').textContent='正文已复制，请在公众号编辑器粘贴并预览。';}catch(e){document.querySelector('#status').textContent='浏览器未允许复制，请手动选中下方正文复制。';}};show();</script></html>'''.replace('OPTIONS',options).replace('PAYLOAD',json.dumps(payload))


def mobile_checks(preview_path, themes):
    from playwright.sync_api import sync_playwright
    checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        try:
            page=browser.new_page()
            for theme in themes:
                for width in (320,375,430):
                    page.set_viewport_size({'width':width,'height':900})
                    page.goto(Path(preview_path).resolve().as_uri())
                    page.select_option('#theme',theme)
                    page.select_option('#width',str(width))
                    page.evaluate('() => document.fonts.ready')
                    overflowing=page.evaluate("() => [...document.querySelectorAll('#article,#article *')].some(e=>e.scrollWidth>e.clientWidth+2 && getComputedStyle(e).display!=='inline')")
                    if overflowing: raise ValueError(f'{theme}在{width}px阅读宽度出现横向溢出')
                    checks.append({'theme':theme,'width':width,'overflow':False})
        finally: browser.close()
    return checks


def render_article(article_path, output, themes='both', layout_path=None, mobile=True):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    (output/'article-layout-report.json').write_text(json.dumps({'passed':False}),encoding='utf-8')
    article=Path(article_path).read_text(encoding='utf-8-sig').strip()
    if not 1<=count_text(article)<=500: raise ValueError('先完成非空且不超过500字的正文，再排版')
    layout=json.loads(Path(layout_path).read_text(encoding='utf-8-sig')) if layout_path else {}
    if not isinstance(layout,dict): raise ValueError('layout需为JSON对象')
    selected=list(THEMES) if themes=='both' else [themes]
    if any(t not in THEMES for t in selected): raise ValueError('未知主题')
    if any(output.glob('*.html')): raise ValueError('排版输出目录已有HTML，使用新目录')
    markups={t:fragment(article,t,layout) for t in selected}
    files=[]
    for theme,markup in markups.items():
        path=output/f'article-{theme}.html'; path.write_text(markup,encoding='utf-8')
        files.append({'file':path.name,'theme':theme,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    path=output/'article-preview.html'; path.write_text(preview(markups),encoding='utf-8')
    checks=mobile_checks(path,selected) if mobile else []
    report={'passed':True,'article_sha256':body_hash(article),'characters':count_text(article),'files':files,
            'preview':{'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()},
            'text_match':True,'source':'customer-write inline body specs', 'mobile_checks':checks, 'automatic_visual_review':False}
    (output/'article-layout-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report


def check_layout(article, report_path):
    root=Path(report_path).resolve().parent
    report=json.loads(Path(report_path).read_text(encoding='utf-8-sig'))
    if report.get('passed') is not True or report.get('article_sha256')!=body_hash(article):
        raise ValueError('文章排版报告未通过或是旧正文')
    files=report.get('files',[])
    themes=[entry.get('theme') for entry in files]
    if not themes or len(set(themes))!=len(themes) or any(t not in THEMES for t in themes): raise ValueError('排版主题缺失/重复')
    paths=[]
    for entry in files+[report.get('preview',{})]:
        value=entry.get('file')
        if not isinstance(value,str): raise ValueError('排版文件缺失')
        path=(root/value).resolve()
        if not path.is_relative_to(root) or not path.is_file(): raise ValueError('排版路径越界或文件缺失')
        if path in paths or hashlib.sha256(path.read_bytes()).hexdigest()!=entry.get('sha256'): raise ValueError('排版文件重复或哈希变化')
        if 'theme' in entry: validate_fragment(path.read_text(encoding='utf-8'),article,entry['theme'])
        paths.append(path)
    if set(root.glob('*.html'))!=set(paths): raise ValueError('排版目录混有未列出的HTML')
    return [str(p) for p in paths]


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--article',required=True); p.add_argument('--output',required=True)
    p.add_argument('--theme',choices=['both',*THEMES],default='both');p.add_argument('--layout')
    a=p.parse_args()
    try: print(json.dumps(render_article(a.article,a.output,a.theme,a.layout),ensure_ascii=False,indent=2))
    except Exception as e: print(json.dumps({'passed':False,'error':str(e)},ensure_ascii=False),file=sys.stderr);sys.exit(2)
