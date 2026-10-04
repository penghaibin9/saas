"""Real image rendering; storage providers are isolated for layout-only checks."""
from hashlib import sha256
from io import BytesIO
from types import SimpleNamespace
import pytest
from PIL import Image, ImageDraw
from app.modules.internship.services import internship_checkin_evidence_service as evidence
from app.core.exceptions import AppException

def test_missing_chinese_font_rejects_incomplete_watermark(monkeypatch):
    monkeypatch.setattr(evidence.settings, 'CHECKIN_WATERMARK_FONT_PATH', '')
    monkeypatch.setattr(evidence, '_CJK_FONTS', ())
    with pytest.raises(AppException) as failure:
        evidence._font(20, '中文现场位置')
    assert failure.value.http_status == 503

@pytest.mark.parametrize('size,text', [
    ((160,160), '2026-10-04 11:00:00 Asia/Shanghai | ' + '合成现场地址' * 45 + ' | 28.228235,112.938877'),
    ((800,600), '2026-10-04 11:00:00 Asia/Shanghai | 合成现场位置 | 28.228235,112.938877'),
    ((800,600), '教师签到 · 合成指导教师\n2026-10-04 11:00:00 Asia/Shanghai\n合成中文现场地址\nGCJ02 28.228235,112.938877'),
])
def test_every_watermark_glyph_fits_the_generated_image(tmp_path, monkeypatch, size, text):
    path=tmp_path/'original.jpg'
    Image.new('RGB',size,(228,238,246)).save(path,format='JPEG')
    original=path.read_bytes()
    captured={}
    monkeypatch.setattr(evidence.file_access_service,'require_file_access', lambda *args, **kwargs: SimpleNamespace(id=1,file_name='original.jpg',mime_type='image/jpeg',size_bytes=len(original),sha256=sha256(original).hexdigest()))
    monkeypatch.setattr(evidence.file_service,'resolve_download',lambda *args, **kwargs:(path,'original.jpg'))
    def store(data,*args,**kwargs):
        captured['data']=data
        return {'fileId':'2','sha256':sha256(data).hexdigest()}
    monkeypatch.setattr(evidence.file_service,'store_bytes',store)
    monkeypatch.setattr(evidence.file_business_binding_service,'bind_file_to_business',lambda *args, **kwargs:None)
    draw_text=ImageDraw.ImageDraw.text
    boxes=[]
    def observe(draw, xy, line, *args, **kwargs):
        bbox=draw.textbbox(xy,line,font=kwargs.get('font'),anchor=kwargs.get('anchor'))
        boxes.append((bbox,draw._image.size,line))
        return draw_text(draw,xy,line,*args,**kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw,'text',observe)
    evidence.watermark_photo(original_file_id='1',checkin_id=1,watermark_text=text,actor={},student_id=1,db=object())
    assert boxes
    for (left,top,right,bottom),(width,height),line in boxes:
        assert 0<=left<=right<=width and 0<=top<=bottom<=height, (line,(left,top,right,bottom),(width,height))
    assert ''.join(box[2] for box in boxes).replace('\n','')==text.replace('\n','')
    assert path.read_bytes()==original
    with Image.open(BytesIO(captured['data'])) as image:
        assert image.width==size[0]
        if size==(160,160): assert image.height>160
        else: assert image.size==size
