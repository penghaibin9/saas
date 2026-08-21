#!/usr/bin/env python3
"""One-shot exact-text patch for W2 large owners and compatibility constants.

The final branch removes this helper and its workflow; it exists only because the
GitHub contents API replaces whole files and the existing owners are intentionally
kept as minimal diffs instead of being rewritten wholesale.
"""
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exact block once, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_console() -> None:
    path = Path("frontend/src/modules/academicAffairs/views/AaExamConsoleView.vue")
    replace_once(
        path,
        '''          <div class="aaexam-section-title">考场异常记录</div>\n          <EmptyState v-if="!incidents.length" title="暂无异常" description="发布后监考教师可登记缺考/违纪" />\n          <ul v-else class="aaexam-incidents">\n            <li v-for="i in incidents" :key="i.incidentId">\n              <span>{{ i.studentName }} · {{ i.incidentType === 'ABSENT' ? '缺考' : i.incidentType === 'DISCIPLINE_VIOLATION' ? '违纪' : '其他' }}</span>\n              <span class="mp-cell-sub">{{ i.description || '' }}</span>\n            </li>\n          </ul>''',
        '''          <AaExamIncidentWorkbench :batch="current" />''',
    )
    replace_once(
        path,
        "import { academicAffairsExamConvenienceApi as convenienceApi } from '@/modules/academicAffairs/api/exam-convenience.api'\n",
        "import { academicAffairsExamConvenienceApi as convenienceApi } from '@/modules/academicAffairs/api/exam-convenience.api'\nimport AaExamIncidentWorkbench from '@/modules/academicAffairs/components/AaExamIncidentWorkbench.vue'\n",
    )
    replace_once(
        path,
        '''    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState,\n    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert,''',
        '''    ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AaExamIncidentWorkbench,\n    AppButton, AppDrawer, AppTextInput, AppNumberInput, AppFormItem, AppConfirmDialog, AppInlineAlert,''',
    )
    replace_once(
        path,
        "      current: null, courses: [], stats: null, incidents: [], readiness: null, readinessError: '',\n",
        "      current: null, courses: [], stats: null, readiness: null, readinessError: '',\n",
    )
    replace_once(
        path,
        '''      const [cs, st, inc, ready] = await Promise.all([\n        api.listCourses(this.current.batchId, { pageSize: 200 }),\n        api.batchStats(this.current.batchId),\n        api.listIncidents({ batchId: this.current.batchId, pageSize: 100 }),\n        convenienceApi.getReadiness(this.current.batchId)\n      ])\n      this.courses = cs.code === 0 ? cs.data.list : []\n      this.stats = st.code === 0 ? st.data : null\n      this.incidents = inc.code === 0 ? inc.data.list : []\n      this.readiness = ready.code === 0 ? ready.data : null''',
        '''      const [cs, st, ready] = await Promise.all([\n        api.listCourses(this.current.batchId, { pageSize: 200 }),\n        api.batchStats(this.current.batchId),\n        convenienceApi.getReadiness(this.current.batchId)\n      ])\n      this.courses = cs.code === 0 ? cs.data.list : []\n      this.stats = st.code === 0 ? st.data : null\n      this.readiness = ready.code === 0 ? ready.data : null''',
    )


def patch_existing_regression() -> None:
    path = Path("backend/tests/test_aa_exam_fact_guards.py")
    replace_once(
        path,
        '''    client.post(f"{BASE}/exam/incidents", headers=admin,\n                json={"examCourseId": str(cid), "studentId": str(ids["s1"]), "incidentType": "ABSENT"})\n    seats = client.get(f"{BASE}/exam/rooms/{rid}/seats", headers=admin).json()["data"]["items"]''',
        '''    incident = client.post(\n        f"{BASE}/exam/incidents",\n        headers=admin,\n        json={"examCourseId": str(cid), "studentId": str(ids["s1"]), "incidentType": "ABSENT"},\n    )\n    assert incident.status_code == 200, incident.text\n    incident_id = incident.json()["data"]["incidentId"]\n    seats = client.get(f"{BASE}/exam/rooms/{rid}/seats", headers=admin).json()["data"]["items"]''',
    )
    replace_once(
        path,
        '''    db.commit(); db.close()\n    assert client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin).status_code == 200''',
        '''    db.commit(); db.close()\n    close_incident = client.post(\n        f"{BASE}/exam/incidents/{incident_id}/resolve",\n        headers=admin,\n        json={\n            "action": "CLOSE",\n            "reason": "缺考风险已联动完成，正式确认考务异常闭环后再结束批次",\n        },\n    )\n    assert close_incident.status_code == 200, close_incident.text\n    assert client.post(f"{BASE}/exam/batches/{bid}/finish", headers=admin).status_code == 200''',
    )


def preserve_public_source_contract() -> None:
    service = Path("backend/app/modules/academic_affairs/services/academic_affairs_exam_incident_lifecycle_service.py")
    replace_once(
        service,
        '"source": "CANONICAL_EXAM_INCIDENT_LIFECYCLE",',
        '"source": "CANONICAL_EXAM_INCIDENT_FACTS",',
    )
    test = Path("backend/tests/test_aa_exam_incident_lifecycle.py")
    replace_once(
        test,
        'assert before["source"] == "CANONICAL_EXAM_INCIDENT_LIFECYCLE"',
        'assert before["source"] == "CANONICAL_EXAM_INCIDENT_FACTS"',
    )


if __name__ == "__main__":
    patch_console()
    patch_existing_regression()
    preserve_public_source_contract()
    print("W2 one-shot owner/compatibility patch applied")
