"""AP03: bulk exports must retain canonical plan fields, explicit zeros and strict IDs."""
import base64
from io import BytesIO
import zipfile
import xml.etree.ElementTree as ET
import pytest
from app.core.exceptions import AppException
from app.modules.internship.services import internship_plan_service as service


def exported_rows(payload):
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(BytesIO(base64.b64decode(payload['contentBase64']))) as archive:
        shared=[]
        if 'xl/sharedStrings.xml' in archive.namelist():
            root=ET.fromstring(archive.read('xl/sharedStrings.xml'))
            shared=[''.join(x.itertext()) for x in root]
        root=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
    result=[]
    for row in root.findall('.//s:sheetData/s:row',ns):
        values=[]
        for cell in row.findall('s:c',ns):
            raw=cell.findtext('s:v','',ns)
            values.append(shared[int(raw)] if cell.get('t')=='s' else
                          ''.join(node.text or '' for node in cell.findall('.//s:t',ns)) if cell.get('t')=='inlineStr' else raw)
        result.append(values)
    return result


def test_bulk_xlsx_preserves_procurement_fields_and_zero(monkeypatch):
    plan={'batchId':'1','batchName':'测试批次','title':'实习计划','planNo':'00001234567890123456',
          'majorName':'软件技术','educationLevel':'高职专科','subsidyStandard':'按实际天数核算',
          'basicSnapshot':{'batchNo':'B-01','plannedCount':0},
          'rulesSnapshot':{'requiredCheckinDays':0,'weeklyRequiredCount':0,'weeklyMinWordCount':0,
           'dailyRequiredCount':0,'dailyMinWordCount':30,'monthlyRequiredCount':4,
           'monthlyMinWordCount':500,'summaryRequiredCount':1,'summaryMinWordCount':1000}}
    monkeypatch.setattr(service,'_bulk_plan_views',lambda ids,user=None:[plan])
    rows=exported_rows(service.bulk_export_plans_xlsx(['1']))
    headers=next(row for row in rows if '批次名称' in row)
    values=rows[rows.index(headers)+1]
    actual=dict(zip(headers,values))
    assert actual['计划编号']=='00001234567890123456'
    assert actual['专业']=='软件技术' and actual['培养层次']=='高职专科'
    assert actual['补贴标准']=='按实际天数核算'
    for key in ['签到天数','周记篇数','周记字数','日报篇数']:
        assert actual[key]=='0', (key,actual[key])
    assert actual['月报篇数']=='4' and actual['总结字数']=='1000'


@pytest.mark.parametrize('raw',['12',{},[True],[1.5],['-1'],[0],[None],['x'],[9223372036854775808],['9'*4301]])
def test_bulk_plan_ids_fail_before_database_on_invalid_input(raw, monkeypatch):
    def must_not_read(*args, **kwargs):
        raise AssertionError('Invalid IDs reached the database lookup')
    monkeypatch.setattr(service, 'get_plan_by_batch', must_not_read)
    with pytest.raises(AppException):
        service._bulk_plan_views(raw)


def test_single_pdf_and_xlsx_keep_zero_and_all_report_word_requirements(monkeypatch):
    plan={'title':'实习计划','batchName':'测试批次','rulesSnapshot':{
        'requiredCheckinDays':0,'dailyRequiredCount':0,'dailyMinWordCount':30,
        'monthlyRequiredCount':4,'monthlyMinWordCount':500,
        'summaryRequiredCount':1,'summaryMinWordCount':1000}}
    lines=service._plan_document_lines(plan)
    assert '计划签到天数：0' in lines
    assert '日报篇数：0；最少字数：30' in lines
    assert '月报篇数：4；最少字数：500' in lines
    assert '总结篇数：1；最少字数：1000' in lines
    monkeypatch.setattr(service,'get_plan_by_batch',lambda batch_id,user=None:plan)
    rows=exported_rows(service.export_plan_xlsx('1'))
    actual={row[0]:row[1] for row in rows if len(row)==2}
    assert actual['计划签到天数']=='0'
    assert actual['日报最少字数']=='30'
    assert actual['月报最少字数']=='500'
    assert actual['总结最少字数']=='1000'


def test_missing_rule_counts_remain_unknown_not_zero():
    text='\n'.join(service._plan_document_lines({'rulesSnapshot':{}}))
    assert '计划签到天数：未配置' in text
    assert '日报篇数：未配置；最少字数：未配置' in text
