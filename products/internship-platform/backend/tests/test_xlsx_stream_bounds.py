"""Real OOXML packages without trusted dimensions keep stream limits enforced."""
import io, re, zipfile
import pytest
from app.core.exceptions import AppException
from app.services.xlsx_util import build_template_xlsx, read_xlsx, MAX_ROWS


def dimensionless(content):
    output=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data=source.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':
                data=re.sub(rb'<dimension[^>]*/>',b'',data,count=1)
            target.writestr(item,data)
    return output.getvalue()


def test_missing_dimensions_keep_student_number_text_and_blank_rows():
    content=build_template_xlsx(['学号'],samples=[['00123456789012345678'],[''],['SYN-02']])
    assert read_xlsx(dimensionless(content),{'学号':'studentNo'})==[{'studentNo':'00123456789012345678'},{'studentNo':'SYN-02'}]


def test_missing_dimensions_do_not_remove_row_limit():
    content=dimensionless(build_template_xlsx(['学号'],samples=[['SYN']]* (MAX_ROWS+1)))
    with pytest.raises(AppException,match='单次导入不得超过'):
        read_xlsx(content,{'学号':'studentNo'})


def test_missing_dimensions_do_not_remove_header_column_limit():
    # Reuse the real package, with the wide data row moved into the header.
    content=build_template_xlsx(['学号'],samples=[['学号']+['额外列']*100])
    output=io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content)) as source, zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as target:
        for item in source.infolist():
            data=source.read(item.filename)
            if item.filename=='xl/worksheets/sheet1.xml':
                data=re.sub(rb'<row r="1"[^>]*>.*?</row>',b'',data,count=1)
                data=data.replace(b'<row r="2"',b'<row r="1"',1)
            target.writestr(item,data)
    content=dimensionless(output.getvalue())
    with pytest.raises(AppException,match='单表列数不得超过'):
        read_xlsx(content,{'学号':'studentNo'})


def test_missing_dimensions_do_not_hide_wide_data_row():
    content=dimensionless(build_template_xlsx(['学号'],samples=[['SYN']+['额外值']*100]))
    with pytest.raises(AppException,match='单表列数不得超过'):
        read_xlsx(content,{'学号':'studentNo'})
