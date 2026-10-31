"""Normal editor/publisher, real isolated MySQL, no state-forcing writes."""
import re
from datetime import datetime,timedelta
from io import BytesIO
from uuid import uuid4
from unittest.mock import patch
from PIL import Image
from sqlalchemy import select,func
from test_auth_mysql import WebsiteAuthCase
from website_app.news import service
from website_app.news.models import NewsArticle,NewsRevision,NewsAudit

class EditorialStory(WebsiteAuthCase):
    def test_related_product_pages_only_return_matching_published_news(self):
        self.login()
        _,first=self.draft(title='岗位实习关联稿'+uuid4().hex[:6]);aid=first['article']['id']
        first=self.approve_schedule(aid,first);self.assertEqual(self.publish(),1)
        _,other=self.draft(title='人事关联稿'+uuid4().hex[:6],relatedProducts=['renshi']);other_id=other['article']['id']
        other=self.approve_schedule(other_id,other);self.assertEqual(self.publish(),1)
        _,private=self.draft(title='仍在内部的实习稿'+uuid4().hex[:6]);private_id=private['article']['id']
        self.client.post('/api/auth/logout')
        latest=self.client.get('/api/news/latest?product=internship')
        self.assertEqual(latest.status_code,200)
        self.assertEqual([item['id'] for item in latest.json()['data']['items']],[aid])
        response=self.client.get('/news?product=internship&category=company')
        self.assertEqual(response.status_code,200)
        self.assertIn(first['article']['title'],response.text)
        self.assertNotIn(other['article']['title'],response.text)
        self.assertNotIn(private['article']['title'],response.text)
        self.assertIn('name="product" value="internship"',response.text)
        self.assertIn('product=internship',response.text)
        self.assertIn('noindex,nofollow',response.text)
        self.assertEqual(self.client.get('/api/news/latest?product=unapproved').status_code,404)
        self.assertEqual(self.client.get('/news?product=unapproved').status_code,404)
        self.assertEqual(self.client.get('/news?product=internship&page=2').status_code,404)
        self.assertEqual(self.client.get('/api/manage/news/articles/'+private_id).status_code,401)

    def image(self, aid, data, color, revision=None):
        image=BytesIO();Image.new('RGB',(80,50),color).save(image,format='PNG')
        params={'expectedVersion':data['package']['version'],'alt':'隔离封面配图','basis':'此图由隔离测试生成，仅供内部验收'}
        if revision:params['revisionId']=revision
        result=self.client.post(f'/api/manage/news/articles/{aid}/media',params=params,files={'file':('test.png',image.getvalue(),'image/png')})
        self.assertEqual(result.status_code,200,result.text)
        row=result.json()['data']
        return row,re.findall(r'\(assets/([a-f0-9]{64})\.webp\)',row['article']['body'])[-1]

    def test_cover_selection_is_versioned_rejects_foreign_media_and_requires_review(self):
        self.login('editor');_,data=self.draft();aid=data['article']['id']
        data,first=self.image(aid,data,(20,90,160));data,second=self.image(aid,data,(180,90,20))
        current=data['package']['version']
        body={'expectedVersion':current,'mediaId':second}
        selected=self.client.post(f'/api/manage/news/articles/{aid}/cover',json=body)
        self.assertEqual(selected.status_code,200,selected.text);data=selected.json()['data']
        read=self.client.get(f'/api/manage/news/articles/{aid}').json()['data']
        self.assertEqual(read['coverId'],second);self.assertEqual(read['editorialState'],'DRAFT')
        self.assertEqual(self.client.get('/news/media/'+second).status_code,404)
        _,foreign=self.draft();other=foreign['article']['id'];foreign,foreign_id=self.image(other,foreign,(20,180,90))
        version=read['packageVersion']
        self.assertEqual(self.client.post(f'/api/manage/news/articles/{aid}/cover',json={'expectedVersion':version}).status_code,422)
        self.assertEqual(self.client.post(f'/api/manage/news/articles/{aid}/cover',json={'expectedVersion':True,'mediaId':first}).status_code,422)
        self.assertEqual(self.client.post(f'/api/manage/news/articles/{aid}/cover',json={'expectedVersion':version,'mediaId':foreign_id}).status_code,400)
        self.assertEqual(self.client.post(f'/api/manage/news/articles/{aid}/cover',json=body).status_code,409)
        self.assertEqual(self.client.get(f'/api/manage/news/articles/{aid}').json()['data']['packageVersion'],version)
        self.client.post('/api/auth/logout');self.login('publisher')
        data=self.action(aid,data,'submit');data=self.action(aid,data,'approve',reviewDigest=data['article']['contentDigest'])
        changed=self.client.post(f'/api/manage/news/articles/{aid}/cover',json={'expectedVersion':data['package']['version'],'mediaId':first})
        self.assertEqual(changed.status_code,200,changed.text);data=changed.json()['data']
        self.assertEqual(data['article']['editorialState'],'DRAFT')
        self.action(aid,data,'schedule',409,publishAt=service.iso(datetime.utcnow()+timedelta(minutes=2)))
        same=self.client.post(f'/api/manage/news/articles/{aid}/cover',json={'expectedVersion':data['package']['version'],'mediaId':first})
        self.assertEqual(same.status_code,200);self.assertEqual(same.json()['data']['package']['version'],data['package']['version'])
        self.client.post('/api/auth/logout')
        self.assertEqual(self.client.post(f'/api/manage/news/articles/{aid}/cover',json={'expectedVersion':data['package']['version'],'mediaId':second}).status_code,401)

    def test_private_cover_revision_does_not_replace_public_cover_before_approval(self):
        self.login();_,data=self.draft();aid=data['article']['id'];data,first=self.image(aid,data,(40,60,160))
        data=self.approve_schedule(aid,data);self.publish()
        read=self.client.get(f'/api/manage/news/articles/{aid}').json()['data'];old=self.client.get(read['url']).text
        revision=self.client.post(f'/api/manage/news/articles/{aid}/revisions',json={'expectedVersion':read['packageVersion']}).json()['data']
        rid=revision['article']['revisionId'];revision,second=self.image(aid,revision,(140,60,20),rid)
        changed=self.client.post(f'/api/manage/news/articles/{aid}/cover',json={'expectedVersion':revision['package']['version'],'revisionId':rid,'mediaId':second})
        self.assertEqual(changed.status_code,200,changed.text);data=changed.json()['data']
        self.assertEqual(self.client.get(read['url']).text,old)
        self.assertEqual(self.client.get('/news/media/'+second).status_code,404)
        self.assertEqual(self.client.post(f'/api/manage/news/articles/{aid}/cover',json={'expectedVersion':data['package']['version'],'mediaId':second}).status_code,409)
        data=self.approve_schedule(aid,data);self.assertEqual(self.publish(),1)
        latest=self.client.get(f'/api/manage/news/articles/{aid}').json()['data']
        self.assertEqual(latest['coverId'],second);self.assertEqual(latest['publishedAt'],read['publishedAt'])
        self.assertEqual(self.client.get('/news/media/'+second).status_code,200)

    def draft(self, **changes):
        body={'requestId':uuid4().hex,'title':'原创隔离验收新闻'+uuid4().hex[:6],
            'summary':'此稿仅用于独立官网环境核对正常账号的审核、发布与修订流程。',
            'body':('仅供隔离验收使用，按正常编辑、审核和明确排期的责任交接核对。'*7)+uuid4().hex,
            'sources':[{'title':'隔离验收出处','url':'https://example.com/editorial'}],
            'authorName':'隔离验收作者','editorName':'隔离验收编辑','rightsBasis':'由隔离验收作者创作的测试文字',
            'rightsScope':'正文与图片仅用于隔离测试环境','relatedProducts':['internship'],**changes}
        r=self.client.post('/api/manage/news/drafts',json=body);self.assertEqual(r.status_code,200,r.text)
        return body,r.json()['data']

    def action(self,aid,data,action,code=200,**kw):
        row=data['article'];body={'expectedVersion':data['package']['version'],'revisionId':row.get('revisionId'),**kw}
        url=f'/api/manage/news/articles/{aid}/'+('submit' if action=='submit' else 'actions/'+action)
        r=self.client.post(url,json=body);self.assertEqual(r.status_code,code,r.text)
        return r.json().get('data') if code==200 else data

    def approve_schedule(self,aid,data):
        data=self.action(aid,data,'submit')
        data=self.action(aid,data,'approve',reviewDigest=data['article']['contentDigest'])
        return self.action(aid,data,'schedule',publishAt=service.iso(datetime.utcnow()+timedelta(seconds=30)))

    def publish(self,at=None):
        with self.factory() as db:
            count=service.publish_due(db,at or datetime.utcnow()+timedelta(minutes=2));db.commit();return count

    def test_editor_return_reedit_exact_approval_pause_resume_and_public_readback(self):
        self.login('editor');body,data=self.draft(summary='未写完',body='未写完',sources=[{'title':'','url':''}])
        aid=data['article']['id'];self.assertEqual(data['article']['body'],'未写完')
        self.action(aid,data,'submit',400)
        _,complete=self.draft()
        body.update({key:complete['article'][key] for key in ('summary','body','sources')});body.pop('requestId');body['body']+='\n独立稿件：'+aid
        r=self.client.put(f'/api/manage/news/articles/{aid}',json={**body,'expectedVersion':0})
        self.assertEqual(r.status_code,200,r.text);data=r.json()['data']
        data=self.action(aid,data,'submit')
        self.action(aid,data,'approve',403,reviewDigest=data['article']['contentDigest'])
        self.client.post('/api/auth/logout');self.login('publisher')
        self.action(aid,data,'return',400,reason='')
        data=self.action(aid,data,'return',reason='请补充摘要里需要读者核对的事项')
        self.assertIn('请补充',data['article']['reviewReason'])
        r=self.client.put(f'/api/manage/news/articles/{aid}',json={**body,'summary':body['summary']+'已经补充说明。','expectedVersion':data['package']['version']})
        self.assertEqual(r.status_code,200,r.text);data=r.json()['data']
        data=self.action(aid,data,'submit')
        self.action(aid,data,'approve',409,reviewDigest='0'*64)
        data=self.action(aid,data,'approve',reviewDigest=data['article']['contentDigest'])
        data=self.action(aid,data,'schedule',publishAt=service.iso(datetime.utcnow()+timedelta(seconds=30)))
        day=(datetime.fromisoformat(data['article']['scheduledAt'].replace('Z','+00:00'))+timedelta(hours=8)).date().isoformat()
        self.assertEqual(self.client.get('/api/manage/news/articles',params={'sort':'scheduled','day':day}).json()['data']['total'],1)
        self.assertEqual(self.client.get('/api/manage/news/articles',params={'sort':'scheduled','day':'2001-01-01'}).json()['data']['total'],0)
        self.assertEqual(self.client.get(data['article']['url']).status_code,404)
        data=self.action(aid,data,'pause');self.assertEqual(self.publish(),0)
        data=self.action(aid,data,'resume');self.assertEqual(self.publish(),1);self.assertEqual(self.publish(),0)
        public=self.client.get(data['article']['url']);self.assertEqual(public.status_code,200)
        self.assertIn('已经补充说明',public.text)
        self.assertIn(aid,self.client.get('/api/manage/news/articles',params={'product':'internship'}).text)
        self.assertIn('批准版本',self.client.get('/api/manage/news/audit').text)

    def test_repost_without_authorization_rejected_and_private_evidence_never_public(self):
        self.login();body,data=self.draft(sourceType='licensed-repost',rightsEvidence='')
        aid=data['article']['id'];self.action(aid,data,'submit',400)
        body.pop('requestId');body['rightsEvidence']='仅用于隔离验收的私有授权凭证说明-PRIVATE-DO-NOT-PUBLISH'
        r=self.client.put(f'/api/manage/news/articles/{aid}',json={**body,'expectedVersion':data['package']['version']})
        self.assertEqual(r.status_code,200,r.text);data=self.approve_schedule(aid,r.json()['data'])
        self.publish();public=self.client.get(data['article']['url'])
        self.assertNotIn('PRIVATE-DO-NOT-PUBLISH',public.text)
        self.assertNotIn('PRIVATE-DO-NOT-PUBLISH',self.client.get('/api/news/latest').text)
        self.assertEqual(self.client.get('/api/manage/news/articles',params={'state':'PUBLISHED'}).json()['data']['total'],1)

    def test_revision_media_private_until_apply_retains_url_date_and_atomic_history(self):
        self.login();body,data=self.draft();aid=data['article']['id'];data=self.approve_schedule(aid,data)
        self.publish();old=self.client.get(data['article']['url']).text
        read=self.client.get(f'/api/manage/news/articles/{aid}').json()['data']
        published=read['publishedAt'];revision=self.client.post(f'/api/manage/news/articles/{aid}/revisions',json={'expectedVersion':read['packageVersion']})
        self.assertEqual(revision.status_code,200,revision.text);data=revision.json()['data'];rid=data['article']['revisionId']
        body.pop('requestId');body['body']='更正后的公开版本。'+body['body']
        body.update(title='新修订标题：审核筛选验证',category='graduation',relatedProducts=['graduation'])
        changed=self.client.put(f'/api/manage/news/articles/{aid}',json={**body,'expectedVersion':data['package']['version'],'revisionId':rid})
        self.assertEqual(changed.status_code,200,changed.text);data=changed.json()['data']
        for filters in ({'q':'新修订标题'},{'category':'graduation'},{'product':'graduation'}):
            self.assertEqual(self.client.get('/api/manage/news/articles',params=filters).json()['data']['total'],1)
        image=BytesIO();Image.new('RGB',(80,50),(20,90,160)).save(image,format='PNG')
        uploaded=self.client.post(f'/api/manage/news/articles/{aid}/media',params={'expectedVersion':data['package']['version'],'revisionId':rid,'alt':'隔离测试配图说明','basis':'此图由隔离测试生成，仅用于验收'},files={'file':('test.png',image.getvalue(),'image/png')})
        self.assertEqual(uploaded.status_code,200,uploaded.text);data=uploaded.json()['data'];media_url=data['article']['coverUrl']
        reviewed=self.client.get(f'/api/manage/news/articles/{aid}',params={'revisionId':rid}).json()['data']
        self.assertIn('此图由隔离测试生成',reviewed['materials'][0]['basis'])
        self.assertEqual(self.client.get(media_url).status_code,404)
        self.assertIn('更正后的',self.client.get(f'/api/manage/news/articles/{aid}/preview',params={'revisionId':rid}).text)
        self.assertEqual(self.client.get(data['article']['url'] or read['url']).text,old)
        data=self.approve_schedule(aid,data)
        with self.factory() as db,patch.object(service,'sync_media_links',side_effect=RuntimeError('isolated failure')):
            with self.assertRaises(RuntimeError): service.publish_due(db,datetime.utcnow()+timedelta(minutes=2))
            db.rollback()
        self.assertEqual(self.client.get(read['url']).text,old)
        self.assertEqual(self.publish(),1);self.assertEqual(self.publish(),0)
        self.assertIn('更正后的',self.client.get(read['url']).text);self.assertEqual(self.client.get(media_url).status_code,200)
        latest=self.client.get(f'/api/manage/news/articles/{aid}').json()['data'];self.assertEqual(latest['publishedAt'],published)
        self.assertEqual(len(latest['history']),2)
        with self.factory() as db:
            self.assertEqual(db.scalar(select(func.count()).select_from(NewsAudit).where(NewsAudit.action=='APPLY_REVISION')),1)
        self.assertEqual(self.client.post(f'/api/manage/news/articles/{aid}/withdraw',json={'expectedVersion':latest['packageVersion'],'reason':'验收结束，撤下隔离合成文章'}).status_code,200)
        self.assertEqual(self.client.get(read['url']).status_code,404);self.assertEqual(self.client.get(media_url).status_code,404)
        self.assertNotIn(read['url'],self.client.get('/news/sitemap.xml').text)

    def test_long_withdraw_reason_with_scheduled_revision_is_atomic(self):
        self.login();_,data=self.draft();aid=data['article']['id'];self.approve_schedule(aid,data);self.publish()
        read=self.client.get(f'/api/manage/news/articles/{aid}').json()['data']
        result=self.client.post(f'/api/manage/news/articles/{aid}/revisions',json={'expectedVersion':read['packageVersion']})
        self.assertEqual(result.status_code,200,result.text);data=self.approve_schedule(aid,result.json()['data'])
        reason='隔离下架原因'*166+'结束说明'
        self.assertLessEqual(len(reason),1000)
        result=self.client.post(f'/api/manage/news/articles/{aid}/withdraw',json={'expectedVersion':data['package']['version'],'reason':reason})
        self.assertEqual(result.status_code,200,result.text)
        with self.factory() as db:
            self.assertEqual(db.get(NewsArticle,aid).state,'WITHDRAWN')
            self.assertEqual(db.get(NewsRevision,data['article']['revisionId']).editorial_state,'CANCELLED')
            self.assertEqual(db.scalar(select(NewsAudit).where(NewsAudit.action=='WITHDRAW')).detail['reason'],reason)

    def test_expired_authorization_does_not_block_another_article_and_recovery_rechecks(self):
        self.login();body,data=self.draft(rightsValidUntil=service.iso(datetime.utcnow()+timedelta(seconds=60)))
        aid=data['article']['id'];data=self.approve_schedule(aid,data)
        _,other=self.draft();other_id=other['article']['id'];other=self.approve_schedule(other_id,other)
        self.assertEqual(self.publish(datetime.utcnow()+timedelta(minutes=2)),1)
        failed=self.client.get(f'/api/manage/news/articles/{aid}').json()['data']
        self.assertEqual(failed['editorialState'],'FAILED');self.assertIn('到期',failed['issue'])
        self.assertEqual(self.client.get(other['article']['url']).status_code,200)
        self.action(aid,{'article':failed,'package':{'version':data['package']['version']}},'cancel',409)
        current={'article':failed,'package':{'version':failed['packageVersion']}}
        current=self.action(aid,current,'cancel');body.pop('requestId');body['rightsValidUntil']=None
        result=self.client.put(f'/api/manage/news/articles/{aid}',json={**body,'expectedVersion':current['package']['version']})
        self.assertEqual(result.status_code,200,result.text);self.approve_schedule(aid,result.json()['data'])
        self.assertEqual(self.publish(),1)

    def test_withdraw_restore_keeps_first_publication_and_records_reason(self):
        self.login();_,data=self.draft();aid=data['article']['id'];self.approve_schedule(aid,data);self.publish()
        read=self.client.get(f'/api/manage/news/articles/{aid}').json()['data'];first=read['publishedAt']
        result=self.client.post(f'/api/manage/news/articles/{aid}/withdraw',json={'expectedVersion':read['packageVersion'],'reason':'隔离验收：核对后恢复'})
        self.assertEqual(result.status_code,200,result.text)
        read=self.client.get(f'/api/manage/news/articles/{aid}').json()['data']
        restore={'expectedVersion':read['packageVersion'],'reviewDigest':read['contentDigest'],'reason':'隔离验收：原批准版本确认有效','publishAt':service.iso(datetime.utcnow())}
        self.assertEqual(self.client.post(f'/api/manage/news/articles/{aid}/restore',json={**restore,'reviewDigest':'0'*64}).status_code,409)
        result=self.client.post(f'/api/manage/news/articles/{aid}/restore',json=restore);self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.publish(),1);self.assertEqual(self.publish(),0)
        read=self.client.get(f'/api/manage/news/articles/{aid}').json()['data'];self.assertEqual(read['publishedAt'],first)
        records=self.client.get('/api/manage/news/audit').json()['data']['items'];self.assertIn('恢复发布',[r['actionName'] for r in records])
        self.assertTrue(all('actorName' in r for r in records))
