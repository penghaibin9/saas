import io, json, stat, unittest, zipfile
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from website_app.news import package as p, render
from helpers import make_bundle

class PackageRules(unittest.TestCase):
    def test_future_product_uses_same_catalog_for_editorial_validation(self):
        from pathlib import Path
        from website_app.news import service
        catalog=json.loads(Path('../products.json').read_text(encoding='utf-8'))
        sample={'key':'extension-check','name':'仅供目录扩展验收','domain':'campus','path':'/products/extension-check','public':True}
        catalog['products'].append(sample)
        with patch.object(Path,'read_text',return_value=json.dumps(catalog)):
            self.assertEqual(service.product_catalog()[sample['key']],sample)
            service.rights_check(SimpleNamespace(source_type='original',author_name='验收作者',editor_name='验收编辑',
                rights_basis='隔离样本由测试作者创作',rights_scope='只供目录扩展验收环境',rights_valid_until=None,related_products=[sample['key']]))
    def test_authorization_expiry_preserved_with_timezone_and_invalid_date_isolated(self):
        from datetime import datetime
        parsed=p.parse_package(make_bundle(1,override=lambda a,e,i:a.update(rights_valid_until='2001-01-01T08:00:00+08:00')))
        self.assertEqual(parsed['articles'][0]['rights_valid_until'],datetime(2001,1,1))
        for value in ('2027-01-01','nonsense',42):
            parsed=p.parse_package(make_bundle(1,override=lambda a,e,i:a.update(rights_valid_until=value)))
            self.assertEqual(parsed['articles'][0]['state'],'INVALID')
    def test_75_articles_not_limited_to_30(self):
        a=p.parse_package(make_bundle(75));self.assertEqual(len(a['articles']),75);self.assertTrue(all(x['state']=='READY' for x in a['articles']))
    def test_repeated_parsing_is_deterministic(self):
        data=make_bundle(3);self.assertEqual(p.parse_package(data),p.parse_package(data))
    def test_untrusted_manifest_cannot_approve(self):
        data=make_bundle(1,override=lambda a,e,i:a.update(state='PUBLISHED',approved=True));self.assertEqual(p.parse_package(data)['articles'][0]['state'],'READY')
    def test_missing_source_isolated_not_whole_package_loss(self):
        a=p.parse_package(make_bundle(2,override=lambda a,e,i:a.update(sources=[]) if i==0 else None))['articles'];self.assertEqual([x['state'] for x in a],['INVALID','READY'])
    def test_supplied_and_inferred_categories(self):
        self.assertEqual(p.classify('教师发展与职称评审','高校人事工作'),'hr');self.assertEqual(p.classify('其他','不相关','教务管理'),'academic')
    def test_non_string_category_is_invalid_row(self):
        self.assertEqual(p.parse_package(make_bundle(1,override=lambda a,e,i:a.update(category=[])))['articles'][0]['state'],'INVALID')
    def test_bad_paths(self):
        for name in ['../a','/a','C:/a','articles//x.md','articles/./x.md','articles\\x.md','articles/%2e%2e/x.md','a\x00b']:
            with self.subTest(name=name),self.assertRaises(p.PackageError):p.safe_path(name)
    def test_archive_traversal_rejected(self):
        with self.assertRaises(p.PackageError):p.parse_package(make_bundle(extra={'../evil.py':b'x'}))
    def test_executable_member_rejected(self):
        with self.assertRaises(p.PackageError):p.parse_package(make_bundle(extra={'assets/a.svg':b'<svg/>'}))
    def test_zip_expansion_guard(self):
        with self.assertRaises(p.PackageError):p.parse_package(make_bundle(extra={'articles/bomb.md':b'Z'*100000}))
    def test_broken_zip_rejected(self):
        for data in [b'not-zip',b'PK00',b'']:
            with self.assertRaises(p.PackageError):p.parse_package(data)
    def test_duplicate_json_keys_rejected(self):
        with self.assertRaises(p.PackageError):p.load_json(b'{"schema":1,"schema":2}')
    def test_confusable_duplicate_members_rejected(self):
        with self.assertRaises(p.PackageError):p.parse_package(make_bundle(extra={'articles/A.md':b'a','articles/a.md':b'b'}))
    def test_symlink_rejected(self):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            info=zipfile.ZipInfo('articles/link.md');info.create_system=3;info.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(info,'/etc/passwd')
        with self.assertRaises(p.PackageError):p.parse_package(out.getvalue())
    def test_unsafe_source_urls(self):
        for s in ['javascript:alert(1)','http://127.0.0.1/x','http://10.0.0.1','https://localhost/','https://a.local/x','https://u:p@example.com','https://example.com:8080','https://a.com/\nfoo']:
            with self.subTest(url=s),self.assertRaises(p.PackageError):p.public_url(s)
    def test_external_images_do_not_trigger_network(self):
        def change(a,e,i):e[a['file']]+=b'\n![x](https://example.com/x.png)'
        with patch('urllib.request.urlopen',side_effect=AssertionError('No remote fetch')):
            self.assertEqual(p.parse_package(make_bundle(override=change))['articles'][0]['state'],'INVALID')
    def test_image_reencoding_and_identity(self):
        im=Image.new('RGB',(60,40),(30,70,200));out=io.BytesIO();im.save(out,format='PNG');blob=out.getvalue()
        def change(a,e,i):a['cover']='assets/cover.png';e['assets/cover.png']=blob;e[a['file']]+=b'\n![campus](assets/cover.png)'
        parsed=p.parse_package(make_bundle(override=change));self.assertEqual(parsed['articles'][0]['state'],'READY');asset=parsed['assets']['assets/cover.png'];self.assertEqual(asset['mime'],'image/webp');self.assertEqual(asset['id'],p.digest(asset['content']));self.assertTrue(asset['content'].startswith(b'RIFF'))
    def test_corrupt_image_isolates_affected_article(self):
        def change(a,e,i):
            if i==0:a['cover']='assets/bad.png'
        r=p.parse_package(make_bundle(2,override=change,extra={'assets/bad.png':b'bad image'}));self.assertEqual([a['state'] for a in r['articles']],['INVALID','READY'])
    def test_checksum_mismatch_is_invalid(self):
        self.assertEqual(p.parse_package(make_bundle(override=lambda a,e,i:a.update(sha256='a'*64)))['articles'][0]['state'],'INVALID')
    def test_markup_is_inert(self):
        html=render.markdown('<img src=x onerror=alert(1)>\n\n[link](javascript:bad)\n\n<script>alert(1)</script>',{})
        self.assertNotIn('<script>',html);self.assertNotIn('<img',html);self.assertNotIn('href="javascript',html);self.assertIn('&lt;script&gt;',html)
    def test_editor_formats_are_rendered_without_activating_html(self):
        result=render.markdown('# 小标题\n\n重点：**可信结果**\n\n- 第一项\n- 第二项\n\n> 可核验引用\n\n**<script>alert(1)</script>**',{})
        for text in ('<h2>小标题</h2>','<strong>可信结果</strong>','<ul><li>第一项</li><li>第二项</li></ul>','<blockquote>可核验引用</blockquote>','&lt;script&gt;'):
            self.assertIn(text,result)
        self.assertNotIn('<script>',result)
    def test_jsonld_script_breakout_escaped(self):
        html=render.page('x','x','ok',structured={'x':'</script><script>bad()</script>'});self.assertEqual(html.count('</script>'),1);self.assertIn('\\u003c',html)
    def test_public_origin_not_request_host(self):
        with patch.dict('os.environ',{'WEBSITE_NEWS_ORIGIN':'https://hnyueke.com'}):self.assertIn('https://hnyueke.com/news',render.page('test','desc','test'))
    def test_newsroom_layout_uses_published_article_content(self):
        article=SimpleNamespace(
            cover_id='a'*64,slug='teacher-growth',title='<教师发展>',summary='来自正式内容发布系统的摘要',
            category='hr',published_at=datetime(2026,9,10,2,0,0),
        )
        page=render.list_html([article],1,1,query='<教师>')
        self.assertIn('近期资讯',page);self.assertIn('按业务栏目阅读',page);self.assertIn('name="q"',page)
        self.assertIn('来自正式内容发布系统的摘要',page);self.assertNotIn('<教师发展>',page);self.assertIn('&lt;教师发展&gt;',page)
        self.assertIn('%3C%E6%95%99%E5%B8%88%3E',page)
    def test_status_source_and_ai_flags_strict(self):
        for field,value in [('ai_assisted','false'),('content_kind','scraped-fulltext'),('sources',[{'title':'x','url':None}])]:
            with self.subTest(field=field):self.assertEqual(p.parse_package(make_bundle(override=lambda a,e,i:a.update({field:value})))['articles'][0]['state'],'INVALID')
