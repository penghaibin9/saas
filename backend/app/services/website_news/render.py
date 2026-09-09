"""Server-rendered, publicly readable newsroom. Escapes all uploaded content."""
from __future__ import annotations
import html
import json
import os
import re
from datetime import timezone, timedelta
from urllib.parse import quote
from app.services.website_news.package import public_url, PackageError, CATEGORIES

STYLE = """
:root{color-scheme:light;font-family:system-ui,-apple-system,'Microsoft YaHei',sans-serif;color:#19304a;background:#f6f8fc}*{box-sizing:border-box}body{margin:0}a{color:#2468d9;text-decoration:none}a:hover{text-decoration:underline}a:focus-visible{outline:3px solid #77a4f0;outline-offset:4px}header{background:#fff;border-bottom:1px solid #e0e7f1}nav{max-width:1180px;margin:auto;display:flex;justify-content:space-between;align-items:center;padding:24px;gap:18px}nav strong{font-size:23px;letter-spacing:2px;color:#173555}nav span{display:flex;gap:22px;flex-wrap:wrap;font-size:14px}.container{max-width:1120px;margin:auto;padding:60px 24px}.kicker{font-size:12px;color:#3578d9;letter-spacing:2px}h1{font-size:42px;line-height:1.4;letter-spacing:-1px;margin:16px 0 18px}h2{font-size:24px;line-height:1.5;margin:32px 0 16px}h3{font-size:19px;line-height:1.5}.intro,.meta{color:#71829a;font-size:14px;line-height:1.8}.categories{display:flex;gap:10px;flex-wrap:wrap;margin:32px 0}.categories a,.tag{padding:7px 12px;background:#edf3ff;border:1px solid #dfe9fc;border-radius:7px;font-size:12px}.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px}.card{border:1px solid #e0e7f1;background:#fff;border-radius:14px;overflow:hidden;display:flex;flex-direction:column}.card img{width:100%;height:170px;object-fit:cover}.card-body{padding:24px;flex:1}.card h2{font-size:19px;margin:12px 0}.card p{font-size:14px;color:#6d809a;line-height:1.8}.card small{font-size:11px;color:#8191a7}.article-grid{display:grid;grid-template-columns:minmax(0,1fr) 240px;gap:40px}.article{padding:36px;background:#fff;border:1px solid #e2e8f1;border-radius:14px;min-width:0}.article h1{font-size:32px}.article p,.article li{line-height:1.95;font-size:16px;overflow-wrap:anywhere}.article img{max-width:100%;height:auto;border-radius:10px}.article figure{margin:26px 0}.article figcaption{font-size:12px;color:#7d8da3}.article blockquote{border-left:3px solid #6796df;padding:12px 20px;margin:24px 0;background:#f4f8ff}.sources{margin-top:36px;border-top:1px solid #e0e7f1;padding-top:20px}.sources li{font-size:13px;margin:10px 0}.notice{padding:13px 16px;border-radius:8px;background:#edf4fe;color:#5a7596;font-size:12px;margin:22px 0;line-height:1.7}.side{position:sticky;top:24px;align-self:start;background:#163756;color:#fff;padding:25px;border-radius:14px}.side h2{font-size:22px;margin-top:10px}.side p{font-size:13px;line-height:1.9;color:#c7d6eb}.cta{display:block;text-align:center;margin-top:24px;padding:12px;background:#fff;border-radius:7px;color:#1d599e;font-size:14px}.pagination{display:flex;justify-content:space-between;gap:20px;margin-top:30px}.empty{padding:45px;border:1px dashed #c6d6ec;border-radius:14px;color:#6c8099}footer{border-top:1px solid #e0e7f1;padding:30px 24px;font-size:12px;color:#8192aa;text-align:center}footer a{margin:0 10px}@media(max-width:850px){.cards{grid-template-columns:1fr 1fr}.article-grid{grid-template-columns:1fr}.side{position:static}.container{padding:35px 20px}h1{font-size:32px}}@media(max-width:540px){.cards{grid-template-columns:1fr}nav{padding:18px;align-items:flex-start}nav span{gap:12px;font-size:12px}nav strong{font-size:20px;white-space:nowrap}.article{padding:22px 18px}.article h1{font-size:27px}.article p,.article li{font-size:15px}.container{padding:28px 16px}.side{margin-bottom:20px}}
"""

def esc(value):
    return html.escape(str(value or ""), quote=True)

def origin():
    candidate = os.getenv("WEBSITE_NEWS_ORIGIN", "https://hnyueke.com").rstrip("/")
    try:
        public_url(candidate)
    except PackageError:
        raise RuntimeError("WEBSITE_NEWS_ORIGIN must be a public canonical origin")
    from urllib.parse import urlsplit
    parsed = urlsplit(candidate)
    if parsed.path or parsed.query or parsed.fragment:
        raise RuntimeError("WEBSITE_NEWS_ORIGIN must not include a path/query")
    return candidate

def date(value):
    return value.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M") if value else "未发布"

def inline(text):
    # Links only. No raw HTML, arbitrary attributes, autoloaded URLs or scripts.
    parts, last = [], 0
    for match in re.finditer(r"(?<!!)\[([^\]\n]{1,300})\]\(([^)\s]{1,1800})\)", text):
        parts.append(esc(text[last:match.start()]))
        try:
            href = public_url(match[2])
            parts.append(f'<a href="{esc(href)}" rel="noopener noreferrer">{esc(match[1])}</a>')
        except PackageError:
            parts.append(esc(match[1]))
        last = match.end()
    parts.append(esc(text[last:]))
    return "".join(parts)

def markdown(text, media_map):
    result, paragraph, items = [], [], []
    def flush():
        if paragraph:
            result.append("<p>" + "<br>".join(inline(x) for x in paragraph) + "</p>")
            paragraph.clear()
        if items:
            result.append("<ul>" + "".join("<li>" + inline(x) + "</li>" for x in items) + "</ul>")
            items.clear()
    for line in text.splitlines():
        line = line.strip()
        image = re.fullmatch(r"!\[([^\]]*)\]\(([^)]+)\)", line)
        heading = re.match(r"^(#{1,4})\s+(.+)$", line)
        if not line:
            flush()
        elif image:
            flush()
            mid = media_map.get(image[2])
            if mid and re.fullmatch(r"[a-f0-9]{64}", mid):
                result.append(f'<figure><img loading="lazy" src="/news/media/{mid}" alt="{esc(image[1])}"><figcaption>{esc(image[1])}</figcaption></figure>')
        elif heading:
            flush(); level = min(4, len(heading[1]) + 1)
            result.append(f"<h{level}>{inline(heading[2])}</h{level}>")
        elif line.startswith(("- ", "* ")):
            if paragraph: flush()
            items.append(line[2:])
        elif line.startswith("> "):
            flush(); result.append("<blockquote>" + inline(line[2:]) + "</blockquote>")
        else:
            if items: flush()
            paragraph.append(line)
    flush()
    return "".join(result)

def page(title, description, body, path="/news", structured=None, noindex=False):
    ld = ""
    if structured:
        # JSON in a script text node must escape '<' even if it is valid JSON.
        value = json.dumps(structured, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        ld = '<script type="application/ld+json">' + value + "</script>"
    robots = "noindex,nofollow" if noindex else "index,follow,max-image-preview:large"
    return f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}｜跃科</title><meta name="description" content="{esc(description)}"><meta name="robots" content="{robots}"><link rel="canonical" href="{esc(origin()+path)}"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{esc(origin()+path)}"><link rel="alternate" type="application/rss+xml" href="/news/feed.xml" title="跃科资讯"><style>{STYLE}</style>{ld}</head><body><header><nav><a href="/"><strong>跃科 YUEKE</strong></a><span><a href="/#students">学生全生命周期</a><a href="/#people">高校人事</a><a href="/news">新闻与资讯</a><a href="/contact">咨询方案</a></span></nav></header><main class="container">{body}</main><footer>湖南跃科信息工程有限公司 · 服务学生成长，成就教师发展<br><a href="/privacy">隐私政策</a><a href="/news/feed.xml">RSS 订阅</a><a href="/news/sitemap.xml">资讯索引</a></footer></body></html>'

def list_html(rows, page_no, total, category=None):
    filters = '<div class="categories"><a href="/news">全部资讯</a>' + ''.join(f'<a href="/news?category={k}">{v}</a>' for k, v in CATEGORIES.items()) + '</div>'
    cards = []
    for a in rows:
        cover = f'<img loading="lazy" src="/news/media/{a.cover_id}" alt="{esc(a.title)}">' if a.cover_id else ''
        cards.append(f'<article class="card">{cover}<div class="card-body"><small>{esc(CATEGORIES.get(a.category))} · {date(a.published_at)}</small><h2><a href="/news/{a.slug}">{esc(a.title)}</a></h2><p>{esc(a.summary)}</p><a href="/news/{a.slug}">阅读详情 →</a></div></article>')
    prev = f'<a href="/news?page={page_no-1}&category={quote(category or "")}">← 上一页</a>' if page_no > 1 else '<span></span>'
    nxt = f'<a href="/news?page={page_no+1}&category={quote(category or "")}">下一页 →</a>' if page_no * 12 < total else '<span></span>'
    body = '<p class="kicker">INSIGHTS / 教育管理新观察</p><h1>新闻与资讯</h1><p class="intro">关注学生成长与教师发展。呈现有来源的教育动态、管理实践与产品进展。</p>' + filters
    body += '<div class="cards">' + ''.join(cards) + '</div>' if cards else '<div class="empty">新的内容正在整理，审核发布后将在这里展示。</div>'
    body += f'<div class="pagination">{prev}<span>第 {page_no} 页</span>{nxt}</div>'
    return page('新闻与资讯', '教育动态、管理实践与产品进展，连接学生全生命周期管理与高校人事服务。', body,
                '/news' + (f'?category={quote(category)}' if category else '') + (('&' if category else '?') + f'page={page_no}' if page_no > 1 else ''))

def article_html(a, preview=False):
    sources = ''.join(f'<li><a href="{esc(s["url"])}" rel="noopener noreferrer">{esc(s["title"])}</a>' +
                      (f' · 来源日期 {esc(s["published_at"][:10])}' if s.get('published_at') else '') + '</li>' for s in a.sources)
    mark = 'AI 辅助整理 · 经运营审核发布；来源原文以原发布机构为准。' if a.ai_assisted else '跃科编辑整理；来源原文以原发布机构为准。'
    if preview: mark = '审核预览 · 当前内容尚未公开。' + mark
    body = f'<p class="meta"><a href="/news">新闻与资讯</a> / {esc(CATEGORIES.get(a.category))}</p><div class="article-grid"><article class="article"><h1>{esc(a.title)}</h1><p class="meta">跃科编辑部 · {date(a.published_at)}（北京时间）</p><p class="intro">{esc(a.summary)}</p><div class="notice">{mark}</div>{markdown(a.body,a.media_map)}<section class="sources"><h2>信息来源与延伸阅读</h2><ol>{sources}</ol></section></article><aside class="side"><p class="kicker">YUEKE / 面向院校</p><h2>让管理流程<br>有序相连。</h2><p>学生全生命周期管理<br>高校人事管理与教师发展</p><p>了解适合学校业务与部署条件的产品方案。</p><a class="cta" href="/contact">咨询学校方案 →</a></aside></div>'
    ld = None if preview else {'@context':'https://schema.org','@type':'BlogPosting','headline':a.title,
        'description':a.summary, 'datePublished':a.published_at.isoformat()+'Z', 'dateModified':a.updated_at.isoformat()+'Z',
        'mainEntityOfPage': origin()+'/news/'+a.slug,
        'author': {'@type':'Organization','name':'跃科编辑部','url':origin()+'/about'},
        'publisher': {'@type':'Organization','name':'湖南跃科信息工程有限公司','url':origin()},
        'citation':[s['url'] for s in a.sources], 'inLanguage':'zh-CN'}
    return page(a.title, a.summary, body, '/news/'+a.slug, ld, preview)
