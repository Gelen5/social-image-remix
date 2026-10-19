"""Validate an explicit deliverable set; semantic reviews are host attestations."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys
from PIL import Image
from render_cards import read_json, validate, local_asset
from workflow_common import content_digest, count_text, work_key
from reorganization import card_sources
from article_layout import check_layout
from topic_tags import check_topics
from disclaimer import decision, added_note, footer_parts, check_styles
from title_quality import validate_titles, check_title_reviews
from article_cover import check_cover


def check_reader_copy(text, label):
    # Reader copy describes the subject. Provenance/verification belongs in audit files.
    provenance = (
        r'(?:按|依照|按照)(?:整理|汇总|收集|所收集|已整理)?(?:的)?'
        r'(?:资料|素材|信息|清单)(?:所)?(?:列出|提到|显示|给出|整理|介绍|标注)|'
        r'(?<!申请)(?<!采购)(?:资料|素材|清单)(?:中|里)(?:面)?|'
        r'(?:原资料|源资料|原素材|源素材|原图|原文|原笔记)|'
        r'(?:原|源)(?:资料|素材|原文|图|文|笔记)(?:中|里|特别|明确|曾|已|所)*'
        r'(?:提到|指出|列出|整理|显示|写道|说明|表明|提供|介绍|列有)|'
        r'(?:根据|依据|据|参照|来自)(?:原|源|上述|相关|这份|这篇)?'
        r'(?:资料|素材|原文|原图|笔记|清单|公开信息)|'
        r'(?:这|本)(?:份|篇|组)(?:企业)?(?:资料|素材|笔记|清单)'
        r'(?:特别|明确)?(?:整理|列出|提到|显示|提供|涵盖|包括|介绍)|'
        r'信息(?:来[自源]|取自)|(?:取材|来源|出处|核验)(?:说明|状态)|'
        r'(?:未|尚未|未经)(?:独立|逐一|实际|官方)?(?:核验|核实|查证)|'
        r'(?:资料|素材|清单|截图|图片|内容)(?:中的|中|里|涉及|显示|表明|指出|提到|说明|描述)|'
        r'(?:不代表|并非|不能据此|无法据此)[^。！？\n]{0,45}'
        r'(?:当前|正在|招聘|岗位开放)'
    )
    if re.search(provenance, text):
        raise ValueError(label + '含取材、溯源或核验过程表述，需改为可独立阅读的直接叙述；来源与核验只记入内部文件')


def check_copy_style(caption, article):
    check_reader_copy(caption, '配文')
    check_reader_copy(article, '文章')
    # Catch known regressions; semantic independence still needs host review.
    if re.search(r'仅[作做供为]信息分享|不涉及(?:任何)?招聘|以(?:企业)?官方(?:信息|公告|发布|要求)为准|岗位是否开放', caption):
        raise ValueError('贴图配文不要重复信息分享、招聘免责声明或官方信息兜底句')
    if re.search(r'第[一二三四五六七八九十百零两\d]+张(?:图片|配图|图)|(?:这|本)(?:组(?:[一二三四五六七八九十两\d]+张)?|(?:[一二三四五六七八九十两\d]+)?张)(?:图片|配图|图)|图中(?:资料|信息|内容|列出|提到|标注)|上图|下图|如图所示|见图', article):
        raise ValueError('文章必须独立阅读，不能用图片页码或依赖配图的指代组织正文')


def check(content_path, manifest_path, image_report_path, text_root):
    content = read_json(content_path)
    manifest = read_json(manifest_path)
    validate(content, manifest, Path(manifest_path).resolve().parent)
    selected = content.get('selected_indices', list(range(1, len(manifest['images'])+1)))
    digest = content_digest(content)
    report_path = Path(image_report_path).resolve()
    images = read_json(report_path)
    if images.get('passed') is not True or images.get('content_sha256') != digest:
        raise ValueError('图片报告未通过或对应旧content')
    if images.get('work_key') != work_key(content['source_url']):
        raise ValueError('图片报告作品不一致')
    entries = images.get('cards', [])
    smart = content.get('mode', 'faithful') == 'smart'
    mappings = [e.get('source_indices') if smart else [e.get('source_index')] for e in entries]
    if mappings != card_sources(content, manifest):
        raise ValueError('输出图片范围与selected_indices不一致')
    actual_files = []
    for entry, card in zip(entries, content['cards']):
        if entry.get('disclaimer_decision') != decision(card):
            raise ValueError('图片脚注判断记录缺失或与当前内容不一致')
        if 'disclaimer' not in entry or entry['disclaimer'] != added_note(card):
            raise ValueError('新增脚注与本张语义判断不一致或固定文案有误')
        if not smart and entry.get('source_image') != card['source_image']:
            raise ValueError('图片原图对应不一致')
        path = local_asset(report_path.parent, entry['file'])
        if path in actual_files:
            raise ValueError('输出文件重复')
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry.get('sha256'):
            raise ValueError('输出图片哈希变化')
        with Image.open(path) as im:
            if im.width * 4 != im.height * 3:
                raise ValueError('输出图片不是3:4')
        actual_files.append(path)
    extras = set(report_path.parent.glob('*.png')) - set(actual_files)
    if extras:
        raise ValueError('输出目录有未列入报告的旧PNG，请使用独立目录')
    check_styles(images, content['cards'])
    root = Path(text_root).resolve()
    caption = (root/'caption.txt').read_text(encoding='utf-8-sig').strip()
    article = (root/'article.txt').read_text(encoding='utf-8-sig').strip()
    check_copy_style(caption, article)
    titles = read_json(root/'titles.json')
    caption_titles = read_json(root/'caption-titles.json')
    paragraphs = [p.strip() for p in re.split(r'[\r\n]+', caption) if p.strip()]
    if not 1 <= len(paragraphs) <= 5 or not 1 <= count_text(caption) <= 200:
        raise ValueError('配文必须为1–5个非空段落，总计1–200字符')
    if not 1 <= count_text(article) <= 500:
        raise ValueError('文章正文必须非空且不超过500字符')
    title_sets = validate_titles(caption_titles, titles)
    for title in caption_titles + titles:
        check_reader_copy(title, '标题')
    for card in content['cards']:
        for text in (card['title'], card['subtitle'], card['footer']):
            check_reader_copy(text, '图片文案')
        for block in card['blocks']:
            check_reader_copy(block['heading'], '图片文案')
            for field in block['fields']:
                check_reader_copy(field['label'] + field['text'], '图片文案')
    texts = {'caption.txt': caption, 'article.txt': article, 'titles.json': json.dumps(titles, ensure_ascii=False),
             'caption-titles.json': json.dumps(caption_titles, ensure_ascii=False)}
    signature = hashlib.sha256(json.dumps(texts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    review = read_json(root/'text-review.json')
    if (review.get('content_sha256') != digest or review.get('selected_indices') != selected
            or review.get('text_sha256') != signature):
        raise ValueError('文字复核记录与当前内容、选图或文字版本不一致')
    for key in ('facts_reviewed', 'scope_reviewed', 'titles_reviewed', 'images_visually_reviewed', 'cleanup_reviewed'):
        if review.get(key) is not True:
            raise ValueError('宿主尚未实际完成复核：' + key)
    check_title_reviews(review, title_sets)
    checks = review.get('image_checks')
    if not isinstance(checks, list) or len(checks) != len(entries):
        raise ValueError('必须逐张完成文字与排版检查，不能漏检')
    for inspection, entry, card in zip(checks, entries, content['cards']):
        keys = ('file', 'source_indices', 'sha256') if smart else ('file', 'source_index', 'sha256')
        if not isinstance(inspection, dict) or any(inspection.get(k) != entry.get(k) for k in keys):
            raise ValueError('逐图核对记录对应旧图片或错页')
        if (inspection.get('text_correct') is not True or inspection.get('layout_passed') is not True
                or inspection.get('issues') != []):
            raise ValueError('图片文字或排版未通过，需修正后重新检查')
        if inspection.get('disclaimer_reviewed') is not True:
            raise ValueError('需逐张确认脚注语义判断正确，应加则准确清晰无遮挡，并保留原图必要声明')
        if footer_parts(card)[1] and inspection.get('disclaimer_style_reviewed') is not True:
            raise ValueError('需逐张实际比较提示语字体样式、字号、字重与整组是否一致')
        if not isinstance(inspection.get('notes'), str) or not inspection['notes'].strip():
            raise ValueError('逐图检查需有实际核对说明')
    if not isinstance(review.get('notes'), str) or not review['notes'].strip():
        raise ValueError('复核需有实际核对说明')
    if not images.get('template'):
        raise ValueError('图片报告缺少整组风格标识')
    if smart and review.get('reorganization_reviewed') is not True:
        raise ValueError('智能重组需核对去重等价性、信息完整性与连贯性')
    relative=review.get('article_layout_report','article-layout/article-layout-report.json')
    if not isinstance(relative,str): raise ValueError('文章排版报告路径不合法')
    layout_report=local_asset(root,relative)
    if review.get('article_layout_reviewed') is not True or review.get('article_layout_report_sha256')!=hashlib.sha256(layout_report.read_bytes()).hexdigest():
        raise ValueError('文章排版尚未实际查看或复核记录过期')
    layout_files=check_layout(article,layout_report)
    layout=json.loads(layout_report.read_text(encoding='utf-8-sig'))
    requested=content.get('article_theme','both')
    required={'red-black','orange-black'} if requested=='both' else {requested}
    if {entry['theme'] for entry in layout['files']}!=required:
        raise ValueError('文章排版主题与用户选择不一致')
    topics=check_topics(root,content,review)
    cover_relative=review.get('article_cover_report','article-cover/cover-report.json')
    if not isinstance(cover_relative,str):raise ValueError('封面报告路径不合法')
    cover_report=local_asset(root,cover_relative)
    cover=check_cover(article,cover_report,review)
    check_reader_copy(cover['keyword'], '封面文案')
    return {'passed': True, 'content_sha256': digest, 'selected_indices': selected,
            'caption_characters': count_text(caption), 'caption_paragraphs': len(paragraphs), 'article_characters': count_text(article),
            'title_count': 6, 'caption_title_count': 3, 'article_title_count': 3,
            'caption_title_characters': [len(t) for t in caption_titles], 'article_title_characters': [len(t) for t in titles],
            'mode': content.get('mode', 'faithful'), 'output_source_indices': mappings, 'images': [str(p) for p in actual_files],
            'text_files': [str(root/n) for n in texts],
            'article_layout_files': layout_files,
            'article_cover_files':cover['files'],'article_cover_keyword':cover['keyword'],'article_cover_ratio':cover['ratio'],
            'topic_tag_files':topics['files'],'topic_tag_count':5,'topic_index_status':topics['data_status'],
            'topic_index_notice':topics['notice'],
            'semantic_verification': 'host_review_attestation_not_automatic_detection'}


def text_signature(root):
    root = Path(root)
    texts = {n: (root/n).read_text(encoding='utf-8-sig').strip() for n in ('caption.txt','article.txt')}
    texts['titles.json'] = json.dumps(read_json(root/'titles.json'), ensure_ascii=False)
    texts['caption-titles.json'] = json.dumps(read_json(root/'caption-titles.json'), ensure_ascii=False)
    return hashlib.sha256(json.dumps(texts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--content', required=True)
    p.add_argument('--manifest', required=True)
    p.add_argument('--image-report', required=True)
    p.add_argument('--text-root', required=True)
    a = p.parse_args()
    root = Path(a.text_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    result = {'passed': False}
    try:
        result = check(a.content, a.manifest, a.image_report, root)
    except Exception as e:
        result['error'] = str(e)
    (root/'delivery.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result['passed'] else 2)
