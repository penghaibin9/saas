"""Synthetic fixtures for isolated tests; never seed public production news."""
from io import BytesIO
import json, zipfile
from website_app.news.package import SCHEMA

def make_bundle(count=1, prefix="A", override=None, extra=None, compression=zipfile.ZIP_DEFLATED):
    entries={}; articles=[]
    for i in range(count):
        text=f"# 测试批次 {prefix} 的第 {i+1} 篇\n\n" + ("本文仅用于自动测试导入、来源记录、审核确认与排期的行为，不是生产新闻，也不应出现在公开生产页面。"*4) + f"\n\n独立条目编号：{prefix}-{i+1}。"
        name=f"articles/{i+1:04}.md";entries[name]=text.encode()
        article={"title":f"{prefix} 教务测试条目 {i+1}","summary":"这是一篇验证新闻资源包导入和整包审核功能的独立测试摘要。","file":name,"sources":[{"title":"测试原始来源","url":"https://example.com/news/"+str(i+1),"published_at":"2026-09-09"}]}
        article.update(source_type='original',author_name='隔离测试作者',editor_name='隔离测试编辑',
                       rights_basis='仅用于隔离验收的原创合成正文与图片',rights_scope='正文和图片仅在隔离验收环境使用')
        if override: override(article, entries, i)
        articles.append(article)
    entries['manifest.json']=json.dumps({"schema":SCHEMA,"title":f"{prefix} 测试资源包","articles":articles},ensure_ascii=False).encode()
    if extra: entries.update(extra)
    out=BytesIO()
    with zipfile.ZipFile(out,'w',compression) as z:
        for n,data in entries.items():z.writestr(n,data)
    return out.getvalue()
