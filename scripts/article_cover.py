"""Verify a real 2.35:1 article cover and its four-character host-reviewed keyword."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
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
    if (any(inspection.get(key) is not True for key in ('text_correct','layout_passed','theme_matched'))
            or inspection.get('issues') != [] or not isinstance(inspection.get('notes'),str)
            or not inspection['notes'].strip()):
        raise ValueError('封面四字文字、排版或文章主题匹配尚未通过')
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
