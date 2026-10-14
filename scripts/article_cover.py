"""Verify a real 2.35:1 article cover and its four-character host-reviewed keyword."""
import argparse
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from PIL import Image
from article_layout import body_hash
from workflow_common import count_text


def check_cover(article, report_path, review):
    if not 1 <= count_text(article) <= 500:
        raise ValueError('封面必须基于当前非空且不超过500字的文章')
    path = Path(report_path).resolve()
    report = json.loads(path.read_text(encoding='utf-8-sig'))
    if report.get('passed') is not True or report.get('article_sha256') != body_hash(article):
        raise ValueError('封面未通过或对应旧文章')
    keyword = report.get('keyword')
    if not isinstance(keyword, str) or not re.fullmatch(r'[\u3400-\u4dbf\u4e00-\u9fff]{4}', keyword):
        raise ValueError('封面总结必须恰好4个汉字，不含空格标点英文数字')
    for key in ('core_summary','keyword_reason'):
        if not isinstance(report.get(key),str) or not report[key].strip():
            raise ValueError('需记录全文核心概括及四字提炼理由')
    candidates=report.get('keyword_candidates')
    if not isinstance(candidates,list) or len(candidates)<2:
        raise ValueError('四字提炼需比较至少两个不同候选')
    words=[]
    for candidate in candidates:
        if (not isinstance(candidate,dict) or not isinstance(candidate.get('keyword'),str)
                or not re.fullmatch(r'[\u3400-\u4dbf\u4e00-\u9fff]{4}',candidate['keyword'])
                or not isinstance(candidate.get('reason'),str) or not candidate['reason'].strip()):
            raise ValueError('四字候选需有准确四汉字及具体比较理由')
        words.append(candidate['keyword'])
    if len(set(words)) != len(words) or keyword not in words:
        raise ValueError('四字候选不能重复，最终总结必须来自已比较候选')
    freshness = keyword.startswith(('刚刚','最新','今日','今天','本周','本月'))
    if freshness:
        evidence=report.get('publication_evidence')
        if not isinstance(evidence,dict):
            raise ValueError('时效封面词需有真实发布来源和日期证据')
        url=evidence.get('source_url')
        if not isinstance(url,str) or urlparse(url).scheme not in ('http','https') or not urlparse(url).hostname:
            raise ValueError('时效封面词缺少可追溯发布来源')
        try:
            published=date.fromisoformat(evidence['published_on'])
            checked=date.fromisoformat(evidence['checked_on'])
        except (KeyError,TypeError,ValueError):
            raise ValueError('时效封面词需记录真实发布日期与核对日期')
        if published>checked or not isinstance(evidence.get('notes'),str) or not evidence['notes'].strip():
            raise ValueError('时效证据日期矛盾或缺少核对依据')
    filename = report.get('file')
    if not isinstance(filename, str) or not filename:
        raise ValueError('封面报告缺少实际图片文件')
    image = (path.parent/filename).resolve()
    if not image.is_relative_to(path.parent) or not image.is_file():
        raise ValueError('封面文件不存在或路径越界')
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    if digest != report.get('sha256'):
        raise ValueError('封面图片哈希变化')
    with Image.open(image) as im:
        width,height = im.size
        im.verify()
    if width*20 != height*47 or report.get('ratio') != '2.35:1':
        raise ValueError('公众号封面必须为2.35:1，不能混作3:4二创页')
    if (report.get('width'),report.get('height')) != (width,height):
        raise ValueError('封面报告尺寸与实际图片不一致')
    if (review.get('article_cover_reviewed') is not True
            or review.get('article_cover_report_sha256') != hashlib.sha256(path.read_bytes()).hexdigest()):
        raise ValueError('封面尚未实际看图复核或对应旧报告')
    inspection = review.get('cover_check')
    if (not isinstance(inspection,dict) or inspection.get('sha256') != digest
            or inspection.get('keyword') != keyword or inspection.get('article_sha256') != body_hash(article)):
        raise ValueError('封面复核对应旧图片、旧主题词或旧文章')
    if (any(inspection.get(key) is not True for key in ('text_correct','layout_passed','theme_matched','keyword_summary_reviewed'))
            or inspection.get('issues') != [] or not isinstance(inspection.get('notes'),str)
            or not inspection['notes'].strip()):
        raise ValueError('封面四字文字、排版或文章主题匹配尚未通过')
    if freshness and inspection.get('freshness_reviewed') is not True:
        raise ValueError('需实际核对刚刚/最新等封面词的时效依据')
    return {'passed':True,'keyword':keyword,'width':width,'height':height,'ratio':'2.35:1',
            'files':[str(image),str(path)],'verification':'host_visual_review_not_automatic_ocr'}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--article',required=True);p.add_argument('--report',required=True);p.add_argument('--review',required=True)
    a=p.parse_args()
    try:
        result=check_cover(Path(a.article).read_text(encoding='utf-8-sig'),a.report,
                           json.loads(Path(a.review).read_text(encoding='utf-8-sig')))
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except Exception as error:
        print(json.dumps({'passed':False,'error':str(error)},ensure_ascii=False));sys.exit(2)
