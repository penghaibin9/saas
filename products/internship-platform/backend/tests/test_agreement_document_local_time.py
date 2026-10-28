from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.core import timeutil
from app.modules.internship.routers import internship_agreement_document as document


def test_agreement_watermark_uses_school_time_even_when_server_is_utc(monkeypatch):
    monkeypatch.setattr(timeutil,'utc_now',lambda:datetime(2026,10,24,23,55,tzinfo=timezone.utc))
    monkeypatch.setattr(timeutil,'tenant_tz',lambda:ZoneInfo('Asia/Shanghai'))
    detail={'studentName':'虚构学生','studentNo':'0001','renderedBody':'原协议正文','statusLabel':'草稿','status':'DRAFT'}
    monkeypatch.setattr(document.agr,'get_agreement',lambda *args,**kwargs:detail)
    captured={}
    def render(title,body,watermark):
        captured.update(body=body,watermark=watermark);return b'unit-fixture'
    monkeypatch.setattr(document,'build_text_pdf',render)
    monkeypatch.setattr(document,'pack_pdf_result',lambda *args:{'filename':'test.pdf'})
    monkeypatch.setattr(document.audit_log,'record',lambda *args,**kwargs:None)
    document.agreement_pdf('1',user={'realName':'虚构教师'})
    assert '2026-10-25 07:55' in captured['watermark']
    assert captured['body']==detail['renderedBody']=='原协议正文'
