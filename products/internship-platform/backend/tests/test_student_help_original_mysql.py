"""Preserve the manual help original after staff follow-up replaces the latest note."""
from test_student_pc_dashboard_reports_mysql import story,ok
from test_yiyang_write_flows_mysql import login,context

def test_manual_help_original_remains_complete_after_teacher_handles_and_closes(story):
    original=('仅用于合成验收的原始求助说明。'*20)+'原文末尾仍应保留'
    assert 200<len(original)<=500
    with login(story,'STUDENT') as student,login(story,'INTERN_MENTOR') as teacher:
        created=ok(student.post('/api/v1/mobile/internship/context/help',json={**context(story),'title':'原始求助留存核验','content':original,'riskLevel':'LOW'}))
        path='/api/v1/internship/risks/'+created['id']
        detail=ok(teacher.get(path));accepted=ok(teacher.post(path+'/handle',json={'comment':'已受理这份合成求助并核对原文','expectedVersion':detail['version']}))
        ok(teacher.post(path+'/close',json={'result':'RESOLVED','comment':'合成问题已处理完毕，原始说明继续保留','expectedVersion':accepted['version']}))
        detail=ok(teacher.get(path));trail=next(row for row in detail['auditTrail'] if row['action']=='STUDENT_HELP')
        assert detail['status']=='CLOSED' and trail['detail']['content']==original
        read=ok(student.get('/api/v1/mobile/internship/context/help',params=context(story)))
        assert read['items'][0]['id']==created['id'] and read['items'][0]['status']=='CLOSED'
