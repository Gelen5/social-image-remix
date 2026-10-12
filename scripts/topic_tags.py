"""Select five relevant topic tags, using optional evidenced WeChat index data."""
import argparse
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from workflow_common import content_digest

NOTICES={'provided_index':'已参考核验后导入的微信指数热度，不是搜索次数。',
         'partial_index':'部分标签未取得微信指数，缺失值不补造；按内容匹配推荐。',
         'unverified_index':'未验证微信指数；以下为内容匹配标签，不代表热度或搜索量排名。'}


def load(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def load_index(path, today=None):
    data=load(path); today=today or date.today()
    if data.get('metric')!='wechat_index': raise ValueError('只接受wechat_index热度，不将它当搜索次数')
    if data.get('source_reviewed') is not True: raise ValueError('指数来源尚未由宿主实际核验')
    source=data.get('source',{})
    if source.get('kind') not in ('screenshot','export','provider') or not isinstance(source.get('name'),str) or not source['name'].strip():
        raise ValueError('指数需要明确来源类型与名称')
    if not isinstance(source.get('evidence_file'),str): raise ValueError('需保留截图/原始返回等本地证据')
    root=Path(path).resolve().parent
    evidence=(root/source['evidence_file']).resolve()
    if not evidence.is_relative_to(root) or not evidence.is_file(): raise ValueError('指数证据不存在或路径越界')
    if hashlib.sha256(evidence.read_bytes()).hexdigest()!=source.get('evidence_sha256'): raise ValueError('指数证据哈希不一致')
    if data.get('period_days') not in (7,30,90) or type(data.get('period_days')) is not int: raise ValueError('指数周期需为7/30/90天')
    as_of=date.fromisoformat(data['as_of'])
    if not 0<=(today-as_of).days<=30: raise ValueError('指数日期在未来或超过30天，需刷新后使用')
    records=data.get('records')
    if not isinstance(records,list) or not records: raise ValueError('没有指数记录')
    lookup={}
    for r in records:
        word=r.get('keyword'); value=r.get('value')
        if not isinstance(word,str) or not word.strip() or word in lookup: raise ValueError('关键词缺失或重复')
        if type(value) not in (int,float) or not math.isfinite(value) or value<0: raise ValueError('指数值错误')
        lookup[word]=value
    return lookup, {'metric':'wechat_index','as_of':data['as_of'],'period_days':data['period_days'],
                    'source':source,'evidence_sha256':source['evidence_sha256'],
                    'index_input_sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def tag_line(result):
    return ' '.join('#'+t['keyword'] for t in result['tags'])


def select_tags(content, candidates, index_path=None, today=None):
    scope=content.get('selected_indices')
    if scope is None:
        if content.get('mode')=='smart': raise ValueError('智能模式需明确selected_indices')
        scope=list(range(1,len(content['cards'])+1))
    if candidates.get('content_sha256')!=content_digest(content) or candidates.get('relevance_reviewed') is not True:
        raise ValueError('候选标签需基于当前content实际完成语义匹配')
    lookup,source=load_index(index_path,today) if index_path else ({},None)
    rows=candidates.get('candidates')
    if not isinstance(rows,list): raise ValueError('缺少候选标签')
    eligible=[]; seen=set()
    for item in rows:
        word=item.get('keyword'); score=item.get('relevance_score'); pages=item.get('source_indices')
        if not isinstance(word,str) or not re.fullmatch(r'[^\s#<>]{1,24}',word) or word in seen: raise ValueError('标签为空、重复或含空白/特殊标记')
        seen.add(word)
        if type(score) not in (int,float) or not math.isfinite(score) or not 0<=score<=1: raise ValueError('相关性规则分需在0–1之间')
        if (not isinstance(pages,list) or not pages or any(type(i) is not int or i not in scope for i in pages)
                or len(set(pages))!=len(pages)): raise ValueError('标签引用未选页或错误来源')
        if not isinstance(item.get('reason'),str) or not item['reason'].strip(): raise ValueError('标签需记录具体内容匹配理由')
        if score>=.6:
            eligible.append(dict(keyword=word,relevance_score=score,source_indices=pages,reason=item['reason'],index_value=lookup.get(word)))
    if len(eligible)<5: raise ValueError('不足5个相关候选，不能为了数量填无关热门词')
    # Relevance first; index is only a tie breaker, never override an irrelevant topic.
    eligible.sort(key=lambda r:(-r['relevance_score'],-(r['index_value'] if r['index_value'] is not None else -1),r['keyword']))
    tags=eligible[:5]
    matched=sum(t['index_value'] is not None for t in tags)
    status='provided_index' if matched==5 else 'partial_index' if matched else 'unverified_index'
    notice=NOTICES[status]
    return {'passed':True,'content_sha256':content_digest(content),'selected_indices':scope,'tags':tags,
            'data_status':status,'index_source':source if matched else None,'notice':notice,
            'ranking':'relevance_then_index_tiebreak','automatic_semantic_verification':False}


def check_topics(root, content, review):
    root=Path(root);path=root/'topics.json'
    data=load(path)
    if review.get('topics_reviewed') is not True or review.get('topics_sha256')!=hashlib.sha256(path.read_bytes()).hexdigest():
        raise ValueError('话题标签尚未实际核对或是旧版本')
    if data.get('passed') is not True or data.get('content_sha256')!=content_digest(content): raise ValueError('标签对应旧content')
    scope=content.get('selected_indices',list(range(1,len(content['cards'])+1)))
    if data.get('selected_indices')!=scope: raise ValueError('标签选页范围不一致')
    # Revalidate all content references and ranking records, without pretending to query live data.
    candidates={'content_sha256':content_digest(content),'relevance_reviewed':True,'candidates':data.get('tags')}
    select_tags(content,candidates)
    if len(data.get('tags',[]))!=5 or tag_line(data)!=(root/'topics.txt').read_text(encoding='utf-8-sig').strip():
        raise ValueError('需要5个唯一标签，标签文本与报告不一致')
    status=data.get('data_status')
    values=[t.get('index_value') for t in data['tags']]
    if status=='unverified_index':
        if any(v is not None for v in values) or data.get('index_source') is not None: raise ValueError('未验证模式不得填指数数据')
    elif status in ('provided_index','partial_index'):
        source=data.get('index_source')
        relative=data.get('index_input_file')
        if not isinstance(relative,str): raise ValueError('缺少原始指数输入')
        index_file=(root/relative).resolve()
        if not index_file.is_relative_to(root.resolve()): raise ValueError('指数路径越界')
        lookup,actual=load_index(index_file)
        if source!=actual: raise ValueError('指数来源记录被修改')
        if any(t.get('index_value')!=lookup.get(t['keyword']) for t in data['tags']): raise ValueError('标签指数与原始数据不一致')
        matched=sum(v is not None for v in values)
        if (status=='provided_index' and matched!=5) or (status=='partial_index' and not 0<matched<5): raise ValueError('指数覆盖状态错误')
    else: raise ValueError('未知指数状态')
    if data.get('notice')!=NOTICES[status]: raise ValueError('数据边界说明不能省略或改成搜索量/热度承诺')
    return {'count':5,'data_status':status,'notice':data['notice'],'files':[str(path.resolve()),str((root/'topics.txt').resolve())]}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--content',required=True);p.add_argument('--candidates',required=True)
    p.add_argument('--index-input');p.add_argument('--output',required=True)
    a=p.parse_args();output=Path(a.output).resolve();output.mkdir(parents=True,exist_ok=True)
    (output/'topics.json').write_text('{"passed":false}',encoding='utf-8')
    try:
        result=select_tags(load(a.content),load(a.candidates),a.index_input)
        if a.index_input:
            index_path=Path(a.index_input).resolve()
            if not index_path.is_relative_to(output): raise ValueError('指数输入及证据必须保存在标签输出目录内，便于复核')
            result['index_input_file']=str(index_path.relative_to(output))
        (output/'topics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        (output/'topics.txt').write_text(tag_line(result),encoding='utf-8')
        print(json.dumps({'count':5,'data_status':result['data_status'],'notice':result['notice'],'tags':tag_line(result)},ensure_ascii=False))
    except Exception as e:
        print(json.dumps({'passed':False,'error':str(e)},ensure_ascii=False),file=sys.stderr);sys.exit(2)
