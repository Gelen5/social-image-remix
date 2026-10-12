from datetime import date,timedelta
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from topic_tags import select_tags,tag_line,check_topics
from workflow_common import content_digest


class TopicTagTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.content={'selected_indices':[2,3],'cards':[{},{}]}
        self.candidates={'content_sha256':content_digest(self.content),'relevance_reviewed':True,'candidates':[
            {'keyword':'词'+str(i),'relevance_score':.8,'source_indices':[2,3],'reason':'合成内容匹配测试'} for i in range(6)]}
        evidence=self.root/'raw.json';evidence.write_text('合成指数测试证据，非真实微信数据',encoding='utf-8')
        self.index={'metric':'wechat_index','source_reviewed':True,'period_days':7,'as_of':date.today().isoformat(),
                    'source':{'kind':'export','name':'合成测试','evidence_file':'raw.json','evidence_sha256':hashlib.sha256(evidence.read_bytes()).hexdigest()},
                    'records':[{'keyword':'词'+str(i),'value':i*100} for i in range(6)]}
        self.save(self.root/'index.json',self.index)

    def save(self,p,data): p.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    def tearDown(self): self.tmp.cleanup()

    def test_fallback_exactly_five_without_fake_numbers(self):
        result=select_tags(self.content,self.candidates)
        self.assertEqual(len(result['tags']),5)
        self.assertEqual(result['data_status'],'unverified_index')
        self.assertTrue(all(t['index_value'] is None for t in result['tags']))
        self.assertIn('未验证',result['notice'])

    def test_index_tiebreak_and_relevance_priority(self):
        result=select_tags(self.content,self.candidates,self.root/'index.json')
        self.assertEqual(result['tags'][0]['keyword'],'词5')
        self.assertEqual(result['data_status'],'provided_index')
        candidates=copy.deepcopy(self.candidates)
        candidates['candidates'][5]['relevance_score']=.3
        result=select_tags(self.content,candidates,self.root/'index.json')
        self.assertNotIn('词5',[t['keyword'] for t in result['tags']])

    def test_bad_index_sources_dates_and_metrics_block(self):
        for changes in ({'metric':'search_volume'},{'source_reviewed':False},{'as_of':(date.today()+timedelta(days=1)).isoformat()},
                        {'as_of':(date.today()-timedelta(days=31)).isoformat()},{'period_days':True}):
            self.save(self.root/'index.json',dict(self.index,**changes))
            with self.assertRaises(ValueError): select_tags(self.content,self.candidates,self.root/'index.json')
        changed=copy.deepcopy(self.index);changed['records'][0]['value']=float('nan')
        self.save(self.root/'index.json',changed)
        with self.assertRaises(ValueError): select_tags(self.content,self.candidates,self.root/'index.json')
        self.save(self.root/'index.json',self.index)
        (self.root/'raw.json').write_text('changed')
        with self.assertRaisesRegex(ValueError,'哈希'): select_tags(self.content,self.candidates,self.root/'index.json')

    def test_scope_count_and_stale_review_block(self):
        for change in ({'content_sha256':'old'},{'relevance_reviewed':False},{'candidates':self.candidates['candidates'][:4]}):
            with self.assertRaises(ValueError): select_tags(self.content,dict(self.candidates,**change))
        candidates=copy.deepcopy(self.candidates);candidates['candidates'][0]['source_indices']=[1]
        with self.assertRaisesRegex(ValueError,'未选'): select_tags(self.content,candidates)
        result=select_tags(self.content,self.candidates)
        self.save(self.root/'topics.json',result)
        (self.root/'topics.txt').write_text(tag_line(result),encoding='utf-8')
        review={'topics_reviewed':True,'topics_sha256':hashlib.sha256((self.root/'topics.json').read_bytes()).hexdigest()}
        self.assertEqual(check_topics(self.root,self.content,review)['count'],5)
        result['notice']='热搜第一'
        self.save(self.root/'topics.json',result)
        review['topics_sha256']=hashlib.sha256((self.root/'topics.json').read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError,'边界'): check_topics(self.root,self.content,review)

    def test_provided_and_partial_records_remain_traceable(self):
        for count,status in ((6,'provided_index'),(1,'partial_index')):
            index=copy.deepcopy(self.index);index['records']=index['records'][:count]
            self.save(self.root/'index.json',index)
            result=select_tags(self.content,self.candidates,self.root/'index.json')
            result['index_input_file']='index.json'
            self.assertEqual(result['data_status'],status)
            self.save(self.root/'topics.json',result)
            (self.root/'topics.txt').write_text(tag_line(result),encoding='utf-8')
            review={'topics_reviewed':True,'topics_sha256':hashlib.sha256((self.root/'topics.json').read_bytes()).hexdigest()}
            self.assertEqual(check_topics(self.root,self.content,review)['data_status'],status)


if __name__=='__main__': unittest.main()
