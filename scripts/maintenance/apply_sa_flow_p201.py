from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, got {count}: {old[:160]!r}")
    write(path, text.replace(old, new, 1))


def patch_talk(changed: list[str]) -> None:
    path = "frontend/src/modules/studentAffairs/views/TalkWorkbenchView.vue"
    replace_once(path, '''              <p v-if="selected.relatedRiskId" class="tk-linked">已转风险单 #{{ selected.relatedRiskId }}</p>\n              <p v-if="selected.relatedContactId" class="tk-linked">已转家校联系 #{{ selected.relatedContactId }}</p>''', '''              <button v-if="selected.relatedRiskId" type="button" class="tk-linked" @click="goRelatedRisk">已转风险单 #{{ selected.relatedRiskId }} → 查看风险处置</button>\n              <button v-if="selected.relatedContactId" type="button" class="tk-linked" @click="goRelatedFamily">已转家校联系 #{{ selected.relatedContactId }} → 查看联系记录</button>''')
    replace_once(path, '''    onAction(key) {\n      const map = {''', '''    goRelatedRisk() {\n      if (!this.selected?.relatedRiskId) return\n      this.$router.push({ name: 'student-affairs-risk-detail', params: { riskId: String(this.selected.relatedRiskId) }, query: { studentId: String(this.selected.studentId || ''), from: 'talk', talkId: String(this.selected.talkId || '') } })\n    },\n    goRelatedFamily() {\n      if (!this.selected?.relatedContactId || !this.selected?.studentId) return\n      this.$router.push({ path: '/admin/student-affairs/family', query: { studentId: String(this.selected.studentId), contactId: String(this.selected.relatedContactId), from: 'talk', talkId: String(this.selected.talkId || '') } })\n    },\n    onAction(key) {\n      const map = {''')
    replace_once(path, '''.tk-linked {\n  font-size: var(--font-size-xs);\n  color: var(--primary-600);\n  margin: 0 0 var(--space-1);\n}''', '''.tk-linked { display: block; border: 0; background: transparent; padding: 0; font: inherit; font-size: var(--font-size-xs); color: var(--primary-600); margin: 0 0 var(--space-1); cursor: pointer; text-align: left; }\n.tk-linked:hover { text-decoration: underline; }''')
    changed.append(path)


def patch_family(changed: list[str]) -> None:
    path = "frontend/src/modules/studentAffairs/views/FamilyContactView.vue"
    replace_once(path, '    <EmptyState v-if="!studentId" title="请选择一名学生"', '    <p v-if="focusNotice" class="fc-focus-note">{{ focusNotice }}</p>\n    <EmptyState v-if="!studentId" title="请选择一名学生"')
    replace_once(path, '        <li v-for="c in contacts" :key="c.contactId" class="fc-item">', '        <li v-for="c in contacts" :key="c.contactId" class="fc-item" :class="{ \'is-focused\': String(c.contactId) === String(contactFocusId) }">')
    replace_once(path, "      studentId: '', loading: false, error: '', contacts: [], acting: false,\n      routeIntentConsumed: false,", "      studentId: '', contactFocusId: '', focusNotice: '', loading: false, error: '', contacts: [], acting: false,\n      routeIntentConsumed: false,")
    replace_once(path, '''  created() {\n    const q = this.$route.query || {}\n    if (q.studentId) {\n      this.studentId = String(q.studentId)\n      this.load()\n    }\n    this.consumeRouteIntent()\n  },\n  watch: {\n    '$route.query.studentId'(v) {\n      if (v) {\n        this.studentId = String(v)\n        this.page = 1\n        this.load()\n      }\n    }\n  },''', '''  created() { this.applyRouteContext(); if (this.studentId) this.load(); this.consumeRouteIntent() },\n  watch: {\n    '$route.query'(value, previous) {\n      const nextStudent = String(value?.studentId || ''), prevStudent = String(previous?.studentId || '')\n      const nextContact = String(value?.contactId || ''), prevContact = String(previous?.contactId || '')\n      if (nextStudent !== prevStudent || nextContact !== prevContact) { this.applyRouteContext(); this.page = 1; if (this.studentId) this.load() }\n    }\n  },''')
    replace_once(path, '''  methods: {\n    canBtn(code) { return canCode(this.ctx, code) },''', '''  methods: {\n    applyRouteContext() { const q = this.$route.query || {}; this.studentId = String(q.studentId || '').trim(); this.contactFocusId = String(q.contactId || '').trim(); this.focusNotice = '' },\n    applyContactFocus() {\n      if (!this.contactFocusId) { this.focusNotice = ''; return }\n      const hit = this.contacts.some((item) => String(item.contactId) === String(this.contactFocusId))\n      this.focusNotice = hit ? `已定位谈话转出的家校联系 #${this.contactFocusId}` : '该联系记录未在当前页，已定位到该生时间线；可翻页继续查看，不会跨学生搜索。'\n    },\n    canBtn(code) { return canCode(this.ctx, code) },''')
    replace_once(path, '''    onPick() {\n      this.page = 1\n      if (this.studentId) this.load()\n    },''', '''    onPick() {\n      this.page = 1; this.contactFocusId = ''; this.focusNotice = ''\n      const query = this.studentId ? { studentId: String(this.studentId) } : {}\n      this.$router.replace({ query }).catch(() => {})\n      if (this.studentId) this.load()\n    },''')
    replace_once(path, "      if (res.code === 0 && res.data) { this.contacts = res.data.items || []; this.total = res.data.total || 0 }\n      else { this.contacts = []; this.total = 0; this.error = res.message || '加载失败' }", "      if (res.code === 0 && res.data) { this.contacts = res.data.items || []; this.total = res.data.total || 0; this.applyContactFocus() }\n      else { this.contacts = []; this.total = 0; this.focusNotice = ''; this.error = res.message || '加载失败' }")
    replace_once(path, '.fc-picker { display: flex;', '.fc-focus-note { margin: 0 0 var(--space-3); padding: var(--space-2) var(--space-3); border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); }\n.fc-picker { display: flex;')
    replace_once(path, '.fc-item__content { min-width: 0; padding:', '.fc-item.is-focused .fc-item__content { border-color: var(--primary-500); box-shadow: 0 0 0 2px var(--primary-100); }\n.fc-item__content { min-width: 0; padding:')
    changed.append(path)


def patch_dorm_backend(changed: list[str]) -> None:
    path = "backend/app/services/affairs_dorm_service.py"
    replace_once(path, '''        resolved = _resolve_exception_students(db, rows)\n        out = []\n        for x in rows:''', '''        resolved = _resolve_exception_students(db, rows)\n        from app.models import AffairsRiskRecord, User\n        from app.services.affairs_risk_service import L_RISK\n        exception_ids = [int(x.id) for x in rows]\n        risks = db.scalars(select(AffairsRiskRecord).where(AffairsRiskRecord.tenant_id == _tid(), AffairsRiskRecord.source == "DORM", AffairsRiskRecord.source_ref_id.in_(exception_ids), AffairsRiskRecord.is_deleted.is_(False))).all() if exception_ids else []\n        risk_by_exception = {int(r.source_ref_id): r for r in risks if r.source_ref_id}\n        owner_ids = {int(r.owner_id) for r in risks if r.owner_id}\n        owners = db.scalars(select(User).where(User.tenant_id == _tid(), User.id.in_(owner_ids), User.is_deleted.is_(False))).all() if owner_ids else []\n        owner_name_by_id = {int(u.id): (u.real_name or u.login_name or "") for u in owners}\n        out = []\n        for x in rows:''')
    replace_once(path, '''            out.append({"exceptionId": str(x.id), "csStudentId": str(x.cs_student_id or ""),\n                       "studentId": str(global_sid or ""),\n                       "realName": real_name, "studentNo": student_no,\n                       "excType": x.exc_type or "", "detail": x.detail or "", "status": x.status,\n                       "createdAt": _iso(x.created_at), "version": x.version})''', '''            risk = risk_by_exception.get(int(x.id))\n            related_risk = None if not risk else {"riskId": str(risk.id), "riskLevel": risk.risk_level, "status": risk.status, "statusLabel": L_RISK.get(risk.status, risk.status), "ownerId": str(risk.owner_id or ""), "ownerName": owner_name_by_id.get(int(risk.owner_id), "") if risk.owner_id else ""}\n            out.append({"exceptionId": str(x.id), "csStudentId": str(x.cs_student_id or ""), "studentId": str(global_sid or ""), "realName": real_name, "studentNo": student_no, "excType": x.exc_type or "", "detail": x.detail or "", "status": x.status, "createdAt": _iso(x.created_at), "version": x.version, "relatedRisk": related_risk})''')
    changed.append(path)


def patch_dorm_frontend(changed: list[str]) -> None:
    path = "frontend/src/modules/studentAffairs/views/dorm/DormExceptionView.vue"
    replace_once(path, '          <template #cell-status="{ row }"><AppStatusTag', '''          <template #cell-relatedRisk="{ row }">\n            <button v-if="row.relatedRisk?.riskId" type="button" class="dorm-risk-link" @click="goRisk(row)">{{ row.relatedRisk.riskLevel }} · {{ row.relatedRisk.statusLabel || row.relatedRisk.status }}<span v-if="row.relatedRisk.ownerName"> · {{ row.relatedRisk.ownerName }}</span> →</button>\n            <span v-else class="sa-muted">未生成风险</span>\n          </template>\n          <template #cell-status="{ row }"><AppStatusTag''')
    replace_once(path, "  { key: 'detail', title: '说明' },\n  { key: 'status', title: '状态' },", "  { key: 'detail', title: '说明' },\n  { key: 'relatedRisk', title: '关联风险', width: '220px' },\n  { key: 'status', title: '状态' },")
    replace_once(path, '''    handle(x) {\n      this.dlg = {''', '''    goRisk(row) {\n      const riskId = row.relatedRisk?.riskId\n      if (!riskId) return\n      this.$router.push({ name: 'student-affairs-risk-detail', params: { riskId: String(riskId) }, query: { studentId: String(row.studentId || ''), from: 'dorm-exception', exceptionId: String(row.exceptionId || '') } })\n    },\n    handle(x) {\n      this.dlg = {''')
    replace_once(path, '.dorm-exception-detail { color:', '.dorm-risk-link { border: 0; background: transparent; padding: 0; color: var(--primary-600); font: inherit; font-size: var(--font-size-xs); cursor: pointer; text-align: left; }\n.dorm-risk-link:hover { text-decoration: underline; }\n.dorm-exception-detail { color:')
    changed.append(path)


def add_backend_test(changed: list[str]) -> None:
    path = "backend/tests/test_affairs_dorm_risk_link.py"
    write(path, '''from __future__ import annotations\nTID = 1000000000000000001\nBASE = "/api/v1/student-affairs"\ndef _hdr(client, login_name):\n    data = client.post("/api/v1/auth/mock-login", json={"loginName": login_name, "password": "any"}).json()["data"]\n    return {"Authorization": f"Bearer {data['accessToken']}"}\ndef test_dorm_exception_batch_enriches_existing_risk_relation(client, db_mode):\n    from app.db.session import get_sessionmaker\n    from app.models import AffairsRiskRecord, CsDormException, User\n    db = get_sessionmaker()(); sid = int(db_mode["student"])\n    linked = CsDormException(tenant_id=TID, cs_student_id=sid, exc_type="NIGHT_ABSENCE", detail="夜间检查发现未按时归寝", status="PENDING_HANDLE")\n    plain = CsDormException(tenant_id=TID, cs_student_id=sid, exc_type="HYGIENE", detail="卫生检查需要整改", status="PENDING_HANDLE")\n    db.add_all([linked, plain]); db.flush()\n    owner = db.query(User).filter(User.tenant_id == TID, User.login_name == "school_admin01", User.is_deleted.is_(False)).first()\n    risk = AffairsRiskRecord(tenant_id=TID, student_id=sid, source="DORM", source_ref_id=linked.id, risk_level="HIGH", status="PROCESSING", owner_id=owner.id if owner else None, title="宿舍异常联动风险")\n    db.add(risk); db.commit(); linked_id, plain_id, risk_id = linked.id, plain.id, risk.id; owner_name = owner.real_name if owner else ""; db.close()\n    data = client.get(f"{BASE}/dorm/exceptions?studentId={sid}&page=1&pageSize=50", headers=_hdr(client, "school_admin01")).json()["data"]\n    by_id = {int(row["exceptionId"]): row for row in data["items"]}; related = by_id[linked_id]["relatedRisk"]\n    assert related["riskId"] == str(risk_id) and related["riskLevel"] == "HIGH" and related["status"] == "PROCESSING" and related["statusLabel"] == "处置中"\n    if owner_name: assert related["ownerName"] == owner_name\n    assert by_id[plain_id]["relatedRisk"] is None\ndef test_dorm_risk_enrichment_is_page_batched():\n    import inspect\n    from app.services import affairs_dorm_service\n    src = inspect.getsource(affairs_dorm_service.list_exceptions)\n    assert "AffairsRiskRecord.source_ref_id.in_(exception_ids)" in src and "User.id.in_(owner_ids)" in src and "risk_by_exception.get(int(x.id))" in src\n    loop = src.split("for x in rows:", 1)[1]\n    assert "db.get(AffairsRiskRecord" not in loop and "db.get(User" not in loop\n''')
    changed.append(path)


def add_frontend_contract(changed: list[str]) -> None:
    path = "frontend/tests/student-affairs-cross-domain-links.contract.test.mjs"
    write(path, '''import test from 'node:test'\nimport assert from 'node:assert/strict'\nimport fs from 'node:fs'\nconst read = (p) => fs.readFileSync(new URL(`../${p}`, import.meta.url), 'utf8')\ntest('谈话转风险精确跳风险详情', () => { const s=read('src/modules/studentAffairs/views/TalkWorkbenchView.vue'); assert.ok(s.includes("name: 'student-affairs-risk-detail'")); assert.ok(s.includes('riskId: String(this.selected.relatedRiskId)')); assert.ok(s.includes("from: 'talk'")); })\ntest('谈话转家校保持 studentId/contactId', () => { const s=read('src/modules/studentAffairs/views/TalkWorkbenchView.vue'); assert.ok(s.includes("path: '/admin/student-affairs/family'")); assert.ok(s.includes('contactId: String(this.selected.relatedContactId)')); assert.ok(s.includes('studentId: String(this.selected.studentId)')); })\ntest('家校仅当前学生时间线聚焦 contactId', () => { const s=read('src/modules/studentAffairs/views/FamilyContactView.vue'); assert.ok(s.includes("this.contactFocusId = String(q.contactId || '').trim()")); assert.ok(s.includes('该联系记录未在当前页，已定位到该生时间线')); assert.ok(s.includes('getFamilyContacts(this.studentId')); })\ntest('宿舍异常展示 DORM 风险并精确跳转', () => { const s=read('src/modules/studentAffairs/views/dorm/DormExceptionView.vue'); assert.ok(s.includes("name: 'student-affairs-risk-detail'")); assert.ok(s.includes("from: 'dorm-exception'")); assert.ok(s.includes('未生成风险')); })\n''')
    changed.append(path)


def main() -> None:
    changed=[]; patch_talk(changed); patch_family(changed); patch_dorm_backend(changed); patch_dorm_frontend(changed); add_backend_test(changed); add_frontend_contract(changed)
    (ROOT/'.sa-flow-changed-files').write_text('\n'.join(changed)+'\n',encoding='utf-8')
    (ROOT/'.sa-flow-commit-message').write_text('fix(student-affairs): link cross-domain affairs outcomes\n',encoding='utf-8')
    print('P2-01 patched files:\n'+'\n'.join(changed))


if __name__ == '__main__':
    main()
