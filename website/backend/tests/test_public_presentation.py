import unittest
from website_app.news import render


class PublicPresentation(unittest.TestCase):
    def test_news_and_preview_use_company_shell_without_exposing_content(self):
        for noindex in (False, True):
            page = render.page('<新闻>', '摘要', '<main class="article-shell">正文</main>', noindex=noindex)
            for value in ('/official-site/company-shell.css', 'class="brand-mark">跃', 'aria-label="官网导航"',
                          'aria-label="手机官网导航"', 'class="footer-wrap"', 'tel:13549666867', '湘ICP备2026031107号', 'id="main"'):
                self.assertIn(value, page)
            self.assertIn('&lt;新闻&gt;', page)
            self.assertEqual('noindex,nofollow' in page, noindex)

    def test_initial_empty_news_and_empty_search_have_different_next_steps(self):
        initial = render.list_html([], 1, 0)
        self.assertIn('暂时没有已发布的资讯', initial)
        self.assertIn('先了解跃科产品', initial)
        self.assertNotIn('暂时没有匹配的内容', initial)
        filtered = render.list_html([], 1, 0, query='<无结果>')
        self.assertIn('暂时没有匹配的内容', filtered)
        self.assertIn('返回全部资讯', filtered)
        self.assertIn('&lt;无结果&gt;', filtered)
        self.assertNotIn('<无结果>', filtered)


if __name__ == '__main__':
    unittest.main()
