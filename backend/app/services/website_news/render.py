"""Server-rendered, publicly readable newsroom. Escapes all uploaded content."""
from __future__ import annotations

import html
import json
import os
import re
from datetime import timezone, timedelta
from urllib.parse import urlencode, urlsplit

from app.services.website_news.package import public_url, PackageError, CATEGORIES


STYLE = """
:root{color-scheme:light;font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif;color:#172f49;background:#fff;--navy:#091b2c;--ink:#172f49;--muted:#687f98;--blue:#2268df;--soft:#f3f7fc;--line:#dce6f0}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#fff;color:var(--ink)}a{color:inherit;text-decoration:none}a:hover{color:var(--blue)}a:focus-visible,button:focus-visible,input:focus-visible{outline:3px solid #77a4f0;outline-offset:3px}.site-header{background:var(--navy);color:#e8f2ff}.topnav{width:min(1300px,calc(100% - 112px));min-height:64px;margin:auto;display:flex;align-items:center;gap:34px}.brand{display:flex;align-items:center;gap:14px;margin-right:auto;white-space:nowrap}.brand strong{font-size:20px;letter-spacing:1.2px}.brand small{padding-left:14px;border-left:1px solid #ffffff30;color:#94abc3;font-size:11px}.navlinks{display:flex;align-items:center;gap:28px;font-size:13px}.navlinks a{position:relative;padding:23px 0}.navlinks a[aria-current=page]:after{content:"";position:absolute;left:0;right:0;bottom:0;height:3px;background:#4a8dff}.back-home{border:1px solid #7390ac;border-radius:6px;padding:9px 14px!important}.back-home:after{display:none!important}.news-hero{position:relative;overflow:hidden;background:var(--soft);border-bottom:1px solid var(--line)}.news-hero>.hero-campus{position:absolute;inset:0 0 0 auto;width:44%;height:100%;object-fit:cover;object-position:center;opacity:.13}.hero-inner{position:relative;z-index:1;width:min(1300px,calc(100% - 112px));min-height:174px;margin:auto;display:grid;grid-template-columns:minmax(360px,.9fr) minmax(460px,1.1fr);align-items:center;gap:72px;padding:30px 0}.kicker{margin:0 0 8px;color:var(--blue);font-size:11px;font-weight:600;letter-spacing:2px}.news-hero h1{margin:0;font-size:45px;line-height:1.22;letter-spacing:-1.5px}.intro,.meta{color:var(--muted);font-size:13px;line-height:1.8}.intro{margin:9px 0 0}.searchbox{display:flex}.searchbox input{width:100%;height:46px;border:1px solid #cbd9ea;border-right:0;border-radius:7px 0 0 7px;padding:0 17px;background:#fff;color:var(--ink);font:inherit}.searchbox button{min-width:92px;border:1px solid var(--blue);border-radius:0 7px 7px 0;background:var(--blue);color:#fff;font:600 14px inherit;cursor:pointer}.hot-terms{display:flex;gap:18px;flex-wrap:wrap;margin:9px 0 0;color:#7a8da4;font-size:11px}.hot-terms a{color:#536d89}.category-bar{border-bottom:1px solid var(--line);background:#fff}.categories{width:min(1300px,calc(100% - 112px));min-height:58px;margin:auto;display:flex;align-items:center;gap:36px;overflow:auto}.categories a{position:relative;padding:20px 0 18px;color:#31506f;font-size:13px;white-space:nowrap}.categories a.active{color:var(--blue);font-weight:650}.categories a.active:after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:3px;background:var(--blue)}.news-main{width:min(1300px,calc(100% - 112px));margin:0 auto;padding:26px 0 58px}.result-note{margin:0 0 18px;padding:11px 14px;background:#f3f7fc;border-left:3px solid var(--blue);color:#607792;font-size:12px}.lead-grid,.content-grid{display:grid;grid-template-columns:minmax(0,1.68fr) minmax(320px,1fr);gap:20px}.lead-story{position:relative;display:block;min-height:340px;border-radius:8px;overflow:hidden;background:#193853;color:#fff}.lead-story>img,.lead-story>.thumb-fallback{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.lead-copy{position:absolute;left:18px;right:18px;bottom:18px;z-index:1;max-width:760px;padding:18px;border-radius:7px;background:#091b2ce8}.lead-copy small{display:inline-block;margin-bottom:9px;padding:4px 8px;border-radius:4px;background:var(--blue);font-size:10px}.lead-copy h2{margin:0;font-size:25px;line-height:1.5;letter-spacing:-.3px}.lead-copy p{margin:7px 0 0;color:#d7e4f1;font-size:12px;line-height:1.7}.lead-copy time{display:block;margin-top:8px;color:#c0d1e2;font-size:10px}.focus{padding:20px 20px 10px;border:1px solid var(--line);border-radius:8px;background:#fbfdff}.section-title{display:flex;align-items:center;justify-content:space-between;gap:18px;margin:0 0 10px}.section-title h2{margin:0;padding-left:11px;border-left:3px solid var(--blue);font-size:19px}.section-title a{color:#768aa1;font-size:10px}.focus ol{list-style:none;margin:0;padding:0}.focus li{display:grid;grid-template-columns:28px minmax(0,1fr) auto;align-items:start;gap:10px;padding:12px 0;border-top:1px solid #e8eef5}.focus li:first-child{border-top:0}.focus b{display:grid;place-items:center;width:24px;height:24px;border-radius:4px;background:#edf3fa;color:#6a7f95;font-size:12px}.focus li:nth-child(1) b{background:#e84141;color:#fff}.focus li:nth-child(2) b{background:#f28b2b;color:#fff}.focus li:nth-child(3) b{background:#e8ad21;color:#fff}.focus a{font-size:12px;line-height:1.55}.focus time{padding-top:3px;color:#93a2b4;font-size:9px;white-space:nowrap}.content-grid{margin-top:24px}.latest{min-width:0}.article-list{border-top:1px solid var(--line)}.article-row{display:grid;grid-template-columns:165px minmax(0,1fr);gap:18px;padding:15px 0;border-bottom:1px solid var(--line)}.article-row img,.thumb-fallback{display:block;width:165px;height:92px;border-radius:7px;object-fit:cover;background:#e9f0f8}.article-row small{color:var(--blue);font-size:10px}.article-row h3{margin:4px 0 5px;font-size:17px;line-height:1.45}.article-row p{display:-webkit-box;overflow:hidden;margin:0;color:#6d8096;font-size:11px;line-height:1.7;-webkit-line-clamp:2;-webkit-box-orient:vertical}.row-meta{display:flex;gap:15px;flex-wrap:wrap;margin-top:7px;color:#91a0b1;font-size:9px}.side-stack{display:grid;align-content:start;gap:16px}.topic-center{padding:20px;border-radius:8px;background:#edf5ff}.topic-visual{position:relative;display:block;height:126px;margin-top:14px;border-radius:7px;overflow:hidden;background:#183b61;color:#fff}.topic-visual>img,.topic-visual>.thumb-fallback{width:100%;height:100%;object-fit:cover;border-radius:0}.topic-visual div{position:absolute;left:12px;right:12px;bottom:12px;padding:12px;border-radius:6px;background:#0c2d50e8}.topic-visual strong{font-size:18px}.topic-visual small{display:block;margin-top:3px;color:#cee1f4}.topic-links{margin-top:8px;border-top:1px solid #cfdfef}.topic-links a{display:block;padding:11px 2px;border-bottom:1px solid #cfdfef;font-size:12px}.subscribe{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:18px;border:1px solid var(--line);border-radius:8px}.subscribe div+div{padding-left:15px;border-left:1px solid var(--line)}.subscribe strong{display:block;font-size:14px}.subscribe p{margin:5px 0 10px;color:#8495a8;font-size:10px;line-height:1.65}.subscribe a{color:var(--blue);font-size:11px}.empty{padding:56px 24px;border:1px dashed #c6d6ec;border-radius:10px;color:#6c8099;text-align:center}.empty strong{display:block;margin-bottom:8px;color:#34546f;font-size:18px}.pagination{display:flex;justify-content:space-between;gap:20px;margin-top:26px;font-size:12px}.pagination span{color:#8091a5}.article-shell{width:min(1120px,calc(100% - 48px));margin:auto;padding:48px 0 64px}.article-grid{display:grid;grid-template-columns:minmax(0,1fr) 270px;gap:44px}.article{min-width:0}.article h1{margin:10px 0 14px;font-size:38px;line-height:1.35;letter-spacing:-.8px}.article h2{margin:32px 0 13px;font-size:24px}.article h3{margin:26px 0 10px;font-size:20px}.article p,.article li{font-size:16px;line-height:1.95;overflow-wrap:anywhere}.article img{max-width:100%;height:auto;border-radius:8px}.article figure{margin:28px 0}.article figcaption{margin-top:8px;color:#7d8da3;font-size:12px}.article blockquote{margin:24px 0;padding:13px 20px;border-left:3px solid #6796df;background:#f4f8ff}.sources{margin-top:38px;padding-top:22px;border-top:1px solid var(--line)}.sources li{margin:10px 0;font-size:13px}.notice{margin:22px 0;padding:13px 16px;border-radius:7px;background:#edf4fe;color:#5a7596;font-size:12px;line-height:1.7}.side{position:sticky;top:24px;align-self:start;padding:26px;border-radius:9px;background:#123452;color:#fff}.side h2{margin:8px 0 14px;font-size:23px}.side p{color:#c7d6e5;font-size:13px;line-height:1.85}.cta{display:block;margin-top:22px;padding:11px;border-radius:6px;background:#fff;color:#1d599e;text-align:center;font-size:13px}.site-footer{border-top:1px solid var(--line);padding:28px 24px;color:#8192aa;text-align:center;font-size:11px;line-height:1.8}.site-footer a{margin:0 9px;color:#4a70a0}@media(max-width:960px){.navlinks a:not([aria-current=page]):not(.back-home){display:none}.hero-inner{grid-template-columns:1fr;gap:20px;padding:28px 0}.lead-grid,.content-grid{grid-template-columns:1fr}.article-grid{grid-template-columns:1fr}.side{position:static}.news-hero h1{font-size:38px}}@media(max-width:640px){.topnav,.hero-inner,.categories,.news-main,.article-shell{width:min(100% - 32px,1300px)}.news-hero>.hero-campus{display:none}.topnav{min-height:58px}.brand small{display:none}.navlinks{gap:12px}.navlinks a[aria-current=page]{display:none}.back-home{font-size:11px}.news-hero h1{font-size:34px}.searchbox button{min-width:72px}.categories{gap:24px}.lead-story{min-height:330px}.lead-copy{left:12px;right:12px;bottom:12px}.lead-copy h2{font-size:21px}.focus li{grid-template-columns:28px minmax(0,1fr)}.focus time{display:none}.article-row{grid-template-columns:105px minmax(0,1fr);gap:12px}.article-row img,.article-row .thumb-fallback{width:105px;height:78px}.article-row h3{font-size:15px}.article-row p{display:none}.article h1{font-size:29px}.article p,.article li{font-size:15px}.subscribe{grid-template-columns:1fr}.subscribe div+div{padding:12px 0 0;border-top:1px solid var(--line);border-left:0}}
"""


def esc(value):
    return html.escape(str(value or ""), quote=True)


def origin():
    candidate = os.getenv("WEBSITE_NEWS_ORIGIN", "https://hnyueke.com").rstrip("/")
    try:
        public_url(candidate)
    except PackageError:
        raise RuntimeError("WEBSITE_NEWS_ORIGIN must be a public canonical origin")
    parsed = urlsplit(candidate)
    if parsed.path or parsed.query or parsed.fragment:
        raise RuntimeError("WEBSITE_NEWS_ORIGIN must not include a path/query")
    return candidate


def date(value):
    return value.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M") if value else "未发布"


def short_date(value):
    return value.replace(tzinfo=timezone.utc).astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d") if value else "未发布"


def inline(text):
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
            flush()
            level = min(4, len(heading[1]) + 1)
            result.append(f"<h{level}>{inline(heading[2])}</h{level}>")
        elif line.startswith(("- ", "* ")):
            if paragraph:
                flush()
            items.append(line[2:])
        elif line.startswith("> "):
            flush()
            result.append("<blockquote>" + inline(line[2:]) + "</blockquote>")
        else:
            if items:
                flush()
            paragraph.append(line)
    flush()
    return "".join(result)


def page(title, description, body, path="/news", structured=None, noindex=False):
    ld = ""
    if structured:
        value = json.dumps(structured, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
        ld = '<script type="application/ld+json">' + value + "</script>"
    robots = "noindex,nofollow" if noindex else "index,follow,max-image-preview:large"
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(title)}｜跃科</title><meta name="description" content="{esc(description)}"><meta name="robots" content="{robots}">'
        f'<link rel="canonical" href="{esc(origin()+path)}"><meta property="og:title" content="{esc(title)}">'
        f'<meta property="og:description" content="{esc(description)}"><meta property="og:url" content="{esc(origin()+path)}">'
        '<link rel="alternate" type="application/rss+xml" href="/news/feed.xml" title="跃科资讯">'
        f'<style>{STYLE}</style>{ld}</head><body><header class="site-header"><nav class="topnav">'
        '<a class="brand" href="/"><strong>跃科 YUEKE</strong><small>用科技助力教育更美好</small></a>'
        '<div class="navlinks"><a href="/">首页</a><a href="/#students">产品与方案</a><a href="/news" aria-current="page">新闻与资讯</a>'
        '<a href="/#delivery">关于我们</a><a class="back-home" href="/">返回跃科官网</a></div></nav></header>'
        f'{body}<footer class="site-footer">湖南跃科信息工程有限公司 · 服务学生成长，成就教师发展<br>'
        '<a href="/privacy">隐私政策</a><a href="/news/feed.xml">RSS 订阅</a><a href="/news/sitemap.xml">资讯索引</a></footer></body></html>'
    )


def _path(page_no=1, category=None, query=None):
    params = {}
    if category in CATEGORIES:
        params["category"] = category
    if query:
        params["q"] = query
    if page_no > 1:
        params["page"] = page_no
    return "/news" + ("?" + urlencode(params) if params else "")


def _cover(article, *, eager=False):
    if not article.cover_id:
        return '<span class="thumb-fallback" aria-hidden="true"></span>'
    return f'<img loading="{"eager" if eager else "lazy"}" src="/news/media/{article.cover_id}" alt="{esc(article.title)}">'


def list_html(rows, page_no, total, category=None, query=None):
    query = (query or "").strip()
    visual = next((article for article in rows if article.cover_id and article.category in ("affairs", "internship")), rows[0] if rows else None)
    hero_visual = f'<img class="hero-campus" src="/news/media/{visual.cover_id}" alt="" aria-hidden="true">' if visual and visual.cover_id else ""
    filters = [f'<a class="{"active" if not category else ""}" href="/news">全部资讯</a>']
    filters.extend(f'<a class="{"active" if category == key else ""}" href="/news?category={key}">{esc(label)}</a>' for key, label in CATEGORIES.items())
    hero = (
        '<section class="news-hero">' + hero_visual + '<div class="hero-inner"><div><p class="kicker">INSIGHTS / 教育管理新观察</p><h1>新闻与资讯</h1>'
        '<p class="intro">关注学生成长与教师发展。呈现有来源的教育动态、管理实践与产品进展。</p></div><div>'
        '<form class="searchbox" action="/news" method="get" role="search">'
        + (f'<input type="hidden" name="category" value="{esc(category)}">' if category in CATEGORIES else "")
        + f'<input type="search" name="q" maxlength="80" value="{esc(query)}" placeholder="搜索资讯、政策与案例" aria-label="搜索新闻与资讯">'
        '<button type="submit">搜索</button></form><p class="hot-terms"><span>热门搜索：</span><a href="/news?q=职业教育">职业教育</a>'
        '<a href="/news?q=教师发展">教师发展</a><a href="/news?q=人工智能">人工智能</a><a href="/news?q=校园安全">校园安全</a></p></div></div></section>'
        '<nav class="category-bar" aria-label="资讯分类"><div class="categories">' + "".join(filters) + "</div></nav>"
    )
    if not rows:
        note = f'<p class="result-note">“{esc(query)}”的搜索结果</p>' if query else ""
        body = hero + f'<main class="news-main">{note}<div class="empty"><strong>暂时没有匹配的内容</strong><span>可以换一个关键词，或返回全部资讯继续浏览。</span></div></main>'
        return page("新闻与资讯", "教育动态、管理实践与产品进展。", body, _path(page_no, category, query))

    lead = rows[0]
    lead_story = (
        f'<a class="lead-story" href="/news/{lead.slug}">{_cover(lead, eager=True)}<div class="lead-copy"><small>{esc(CATEGORIES.get(lead.category))}</small>'
        f'<h2>{esc(lead.title)}</h2><p>{esc(lead.summary)}</p><time datetime="{short_date(lead.published_at)}">{short_date(lead.published_at)}</time></div></a>'
    )
    focus = '<aside class="focus"><div class="section-title"><h2>今日关注</h2><a href="#latest">查看最新</a></div><ol>' + "".join(
        f'<li><b>{index}</b><a href="/news/{article.slug}">{esc(article.title)}</a><time datetime="{short_date(article.published_at)}">{short_date(article.published_at)}</time></li>'
        for index, article in enumerate(rows[:5], 1)
    ) + "</ol></aside>"
    article_rows = rows[1:] or rows[:1]
    latest = '<section class="latest" id="latest"><div class="section-title"><h2>最新资讯</h2><a href="/news/feed.xml">RSS 订阅</a></div><div class="article-list">' + "".join(
        f'<article class="article-row">{_cover(article)}<div><small>{esc(CATEGORIES.get(article.category))}</small><h3><a href="/news/{article.slug}">{esc(article.title)}</a></h3>'
        f'<p>{esc(article.summary)}</p><div class="row-meta"><time datetime="{short_date(article.published_at)}">{short_date(article.published_at)}</time>'
        f'<span>跃科编辑部</span><a href="/news/{article.slug}">阅读全文</a></div></div></article>' for article in article_rows
    ) + "</div></section>"
    topics = (
        '<aside class="side-stack"><section class="topic-center"><div class="section-title"><h2>专题中心</h2><a href="/news">全部专题</a></div>'
        f'<a class="topic-visual" href="/news?q=职业教育">{_cover(lead)}<div><strong>职业教育高质量发展</strong><small>政策 · 实践 · 数字化</small></div></a>'
        '<div class="topic-links"><a href="/news?category=academic">教育强国与学校治理</a><a href="/news?category=technology">人工智能与教育创新</a>'
        '<a href="/news?category=hr">教师发展与师德建设</a><a href="/news?category=affairs">学生安全与成长</a></div></section>'
        '<section class="subscribe"><div><strong>订阅更新</strong><p>通过 RSS 获取教育政策、实践案例与产品动态。</p><a href="/news/feed.xml">打开 RSS 订阅</a></div>'
        '<div><strong>内容有出处</strong><p>摘要保留原发布机构、发布日期与原文链接。</p><a href="/news/sitemap.xml">查看资讯索引</a></div></section></aside>'
    )
    prev = f'<a href="{esc(_path(page_no-1, category, query))}">上一页</a>' if page_no > 1 else "<span></span>"
    nxt = f'<a href="{esc(_path(page_no+1, category, query))}">下一页</a>' if page_no * 12 < total else "<span></span>"
    note = f'<p class="result-note">“{esc(query)}”找到 {total} 篇内容</p>' if query else (f'<p class="result-note">当前栏目：{esc(CATEGORIES[category])} · 共 {total} 篇</p>' if category in CATEGORIES else "")
    body = hero + f'<main class="news-main">{note}<div class="lead-grid">{lead_story}{focus}</div><div class="content-grid">{latest}{topics}</div><div class="pagination">{prev}<span>第 {page_no} 页</span>{nxt}</div></main>'
    return page("新闻与资讯", "教育动态、管理实践与产品进展，连接学生全生命周期管理与高校人事服务。", body, _path(page_no, category, query))


def article_html(article, preview=False):
    sources = "".join(
        f'<li><a href="{esc(source["url"])}" rel="noopener noreferrer">{esc(source["title"])}</a>'
        + (f' · 来源日期 {esc(source["published_at"][:10])}' if source.get("published_at") else "") + "</li>" for source in article.sources
    )
    mark = "AI 辅助整理 · 经运营审核发布；来源原文以原发布机构为准。" if article.ai_assisted else "跃科编辑整理；来源原文以原发布机构为准。"
    if preview:
        mark = "审核预览 · 当前内容尚未公开。" + mark
    content = (
        '<main class="article-shell"><p class="meta"><a href="/news">新闻与资讯</a> / '
        f'{esc(CATEGORIES.get(article.category))}</p><div class="article-grid"><article class="article"><h1>{esc(article.title)}</h1>'
        f'<p class="meta">跃科编辑部 · {date(article.published_at)}（北京时间）</p><p class="intro">{esc(article.summary)}</p><div class="notice">{mark}</div>'
        f'{markdown(article.body, article.media_map)}<section class="sources"><h2>信息来源与延伸阅读</h2><ol>{sources}</ol></section></article>'
        '<aside class="side"><p class="kicker">YUEKE / 面向院校</p><h2>让管理流程有序相连。</h2><p>学生全生命周期管理<br>高校人事管理与教师发展</p>'
        '<p>了解适合学校业务与部署条件的产品方案。</p><a class="cta" href="/#delivery">咨询学校方案</a></aside></div></main>'
    )
    structured = None if preview else {
        "@context": "https://schema.org", "@type": "BlogPosting", "headline": article.title, "description": article.summary,
        "datePublished": article.published_at.isoformat() + "Z", "dateModified": article.updated_at.isoformat() + "Z",
        "mainEntityOfPage": origin() + "/news/" + article.slug,
        "author": {"@type": "Organization", "name": "跃科编辑部", "url": origin() + "/about"},
        "publisher": {"@type": "Organization", "name": "湖南跃科信息工程有限公司", "url": origin()},
        "citation": [source["url"] for source in article.sources], "inLanguage": "zh-CN",
    }
    return page(article.title, article.summary, content, "/news/" + article.slug, structured, preview)
