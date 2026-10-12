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
    root = Path(text_root).resolve()
    caption = (root/'caption.txt').read_text(encoding='utf-8-sig').strip()
    article = (root/'article.txt').read_text(encoding='utf-8-sig').strip()
    titles = read_json(root/'titles.json')
    paragraphs = [p.strip() for p in re.split(r'[\r\n]+', caption) if p.strip()]
    if not 1 <= len(paragraphs) <= 5 or not 1 <= count_text(caption) <= 200:
        raise ValueError('配文必须为1–5个非空段落，总计1–200字符')
    if not 580 <= count_text(article) <= 620:
        raise ValueError('文章正文必须为580–620字符')
    if (not isinstance(titles, list) or len(titles) != 3
            or any(not isinstance(t, str) or not t.strip() or '\n' in t or '\r' in t for t in titles)
            or len({t.strip() for t in titles}) != 3):
        raise ValueError('需要3个非空、不重复的单行标题')
    texts = {'caption.txt': caption, 'article.txt': article, 'titles.json': json.dumps(titles, ensure_ascii=False)}
    signature = hashlib.sha256(json.dumps(texts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    review = read_json(root/'text-review.json')
    if (review.get('content_sha256') != digest or review.get('selected_indices') != selected
            or review.get('text_sha256') != signature):
        raise ValueError('文字复核记录与当前内容、选图或文字版本不一致')
    for key in ('facts_reviewed', 'scope_reviewed', 'titles_reviewed', 'images_visually_reviewed', 'cleanup_reviewed'):
        if review.get(key) is not True:
            raise ValueError('宿主尚未实际完成复核：' + key)
    checks = review.get('image_checks')
    if not isinstance(checks, list) or len(checks) != len(entries):
        raise ValueError('必须逐张完成文字与排版检查，不能漏检')
    for inspection, entry in zip(checks, entries):
        keys = ('file', 'source_indices', 'sha256') if smart else ('file', 'source_index', 'sha256')
        if not isinstance(inspection, dict) or any(inspection.get(k) != entry.get(k) for k in keys):
            raise ValueError('逐图核对记录对应旧图片或错页')
        if (inspection.get('text_correct') is not True or inspection.get('layout_passed') is not True
                or inspection.get('issues') != []):
            raise ValueError('图片文字或排版未通过，需修正后重新检查')
        if not isinstance(inspection.get('notes'), str) or not inspection['notes'].strip():
            raise ValueError('逐图检查需有实际核对说明')
    if not isinstance(review.get('notes'), str) or not review['notes'].strip():
        raise ValueError('复核需有实际核对说明')
    if not images.get('template'):
        raise ValueError('图片报告缺少整组风格标识')
    if smart and review.get('reorganization_reviewed') is not True:
        raise ValueError('智能重组需核对去重等价性、信息完整性与连贯性')
    return {'passed': True, 'content_sha256': digest, 'selected_indices': selected,
            'caption_characters': count_text(caption), 'caption_paragraphs': len(paragraphs), 'article_characters': count_text(article),
            'title_count': 3, 'mode': content.get('mode', 'faithful'), 'output_source_indices': mappings, 'images': [str(p) for p in actual_files],
            'text_files': [str(root/n) for n in texts],
            'semantic_verification': 'host_review_attestation_not_automatic_detection'}


def text_signature(root):
    root = Path(root)
    texts = {n: (root/n).read_text(encoding='utf-8-sig').strip() for n in ('caption.txt','article.txt')}
    texts['titles.json'] = json.dumps(read_json(root/'titles.json'), ensure_ascii=False)
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
