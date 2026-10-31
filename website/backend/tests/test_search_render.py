import json, re, unittest
from datetime import datetime
from types import SimpleNamespace
from website_app.news import render

class SearchRender(unittest.TestCase):
    def test_public_article_has_stable_publisher_and_private_preview_has_no_graph(self):
        article=SimpleNamespace(id='a'*32,slug='search-evidence',title='正式内容的来源说明',summary='依据已审核资料组织内容，不把演示数据当作实际结果。',body='正文示例',category='company',media_map={},cover_id=None,author_name='隔离验收编辑部',source_type='original',related_products=[],ai_assisted=True,sources=[{'title':'核验来源','url':'https://example.com/source'}],published_at=datetime(2026,10,10),updated_at=datetime(2026,10,11))
        html=render.article_html(article)
        graph=json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>',html).group(1))['@graph']
        posting=next(node for node in graph if node.get('@type')=='BlogPosting')
        organization=next(node for node in graph if node.get('@type')=='Organization')
        self.assertEqual(posting['publisher']['@id'],organization['@id'])
        self.assertEqual(posting['citation'],['https://example.com/source'])
        self.assertEqual(posting['datePublished'],'2026-10-10T00:00:00Z')
        self.assertNotIn('application/ld+json',render.article_html(article,preview=True))

    def test_product_filter_survives_categories_search_and_pagination(self):
        article=SimpleNamespace(cover_id=None,slug='product-news',title='实习说明',summary='原文摘要',category='company',published_at=datetime(2026,10,10),author_name='编辑部')
        html=render.list_html([article],2,30,product='internship',product_name='岗位实习系统')
        self.assertIn('与 岗位实习系统 相关的已发布资讯',html)
        self.assertIn('name="product" value="internship"',html)
        self.assertIn('product=internship&amp;page=3',html)
        self.assertIn('category=academic&amp;product=internship',html)
        hot=re.search(r'<p class="hot-terms">(.*?)</p>',html).group(1)
        self.assertEqual(hot.count('product=internship'),4)
        self.assertIn('noindex,nofollow',html)

if __name__=='__main__':unittest.main()
