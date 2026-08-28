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


def append_once(path: str, marker: str, content: str) -> None:
    text = read(path)
    if marker in text:
        return
    write(path, text.rstrip() + "\n\n" + content.strip() + "\n")


def patch_backend_service(changed: list[str]) -> None:
    path = "backend/app/services/affairs_discipline_service.py"
    replace_once(path, '''def get_case(case_id, user) -> dict:\n    with session() as db:\n        x, s = _load(db, case_id)\n        _scope_or_403(db, x.student_id, user)\n        return _row(x, s)''', '''def get_case(case_id, user) -> dict:\n    \"\"\"处分单条详情：仅在 detail 读取最新申诉摘要，避免主列表逐行查询。\"\"\"\n    with session() as db:\n        from app.models import DisciplineAppeal\n        x, s = _load(db, case_id)\n        _scope_or_403(db, x.student_id, user)\n        row = _row(x, s)\n        appeal = db.scalars(select(DisciplineAppeal).where(\n            DisciplineAppeal.tenant_id == _tid(), DisciplineAppeal.case_id == int(x.id),\n            DisciplineAppeal.is_deleted.is_(False)\n        ).order_by(DisciplineAppeal.id.desc())).first()\n        row[\"appealSummary\"] = None if not appeal else {\n            \"appealId\": str(appeal.id), \"status\": appeal.status,\n            \"statusLabel\": _L_APPEAL.get(appeal.status, appeal.status), \"result\": appeal.result or None,\n        }\n        return row''')
    replace_once(path, 'def list_appeals(user, status=None, page=1, page_size=50):', 'def list_appeals(user, status=None, page=1, page_size=50, case_id=None, appeal_id=None):')
    replace_once(path, '''        conds = [DisciplineAppeal.tenant_id == _tid(), DisciplineAppeal.is_deleted.is_(False)]\n        if status:\n            conds.append(DisciplineAppeal.status == status)\n        rows = db.scalars(select(DisciplineAppeal).where(*conds).order_by(''', '''        conds = [DisciplineAppeal.tenant_id == _tid(), DisciplineAppeal.is_deleted.is_(False)]\n        if status:\n            conds.append(DisciplineAppeal.status == status)\n        if case_id not in (None, \"\"):\n            try:\n                conds.append(DisciplineAppeal.case_id == int(case_id))\n            except (TypeError, ValueError):\n                return [], 0\n        if appeal_id not in (None, \"\"):\n            try:\n                conds.append(DisciplineAppeal.id == int(appeal_id))\n            except (TypeError, ValueError):\n                return [], 0\n        rows = db.scalars(select(DisciplineAppeal).where(*conds).order_by(''')
    changed.append(path)


def patch_backend_api(changed: list[str]) -> None:
    path = "backend/app/api/v1/student_affairs.py"
    replace_once(path, '''@router.get("/discipline/appeals", summary="处分申诉列表")\ndef discipline_appeals(status: Optional[str] = None, page: int = Query(1, ge=1), pageSize: int = Query(50, ge=1, le=200),\n                       user=Depends(require_permission("studentAffairs.discipline.view"))):\n    items, total = disc_svc.list_appeals(user, status, page, pageSize)\n    return success(paginate(items, total, page, pageSize))''', '''@router.get("/discipline/appeals", summary="处分申诉列表")\ndef discipline_appeals(status: Optional[str] = None, caseId: Optional[int] = None, appealId: Optional[int] = None,\n                       page: int = Query(1, ge=1), pageSize: int = Query(50, ge=1, le=200),\n                       user=Depends(require_permission("studentAffairs.discipline.view"))):\n    items, total = disc_svc.list_appeals(user, status, page, pageSize, case_id=caseId, appeal_id=appealId)\n    return success(paginate(items, total, page, pageSize))''')
    changed.append(path)


def patch_frontend_api(changed: list[str]) -> None:
    path = "frontend/src/modules/studentAffairs/api/studentAffairs.api.js"
    replace_once(path, '''  getDisciplineAppeals({ status = '', page = 1, pageSize = 100 } = {}) {\n    const params = { page, pageSize }\n    if (status) params.status = status\n    return callStrict(() => request('/student-affairs/discipline/appeals', { params }))\n  },''', '''  getDisciplineAppeals({ status = '', caseId = '', appealId = '', page = 1, pageSize = 100 } = {}) {\n    const params = { page, pageSize }\n    if (status) params.status = status\n    if (caseId) params.caseId = caseId\n    if (appealId) params.appealId = appealId\n    return callStrict(() => request('/student-affairs/discipline/appeals', { params }))\n  },''')
    changed.append(path)


def patch_workbench(changed: list[str]) -> None:
    path = "frontend/src/modules/studentAffairs/views/DisciplineWorkbenchView.vue"
    replace_once(path, '          <details class="dp-tech">', '''          <section v-if="postEffectState" class="dp-post-effect">\n            <div><strong>{{ postEffectState.title }}</strong><p>{{ postEffectState.description }}</p></div>\n            <StatusTag :type="postEffectState.tone" :label="postEffectState.label" dot />\n          </section>\n\n          <details class="dp-tech">''')
    replace_once(path, '''    detailActions() {\n      const s = this.selected && this.selected.status''', '''    postEffectState() {\n      const row = this.selected\n      if (!row || row.status !== 'EFFECTIVE') return null\n      const appeal = row.appealSummary\n      if (!row.deliveredAt) return { key: 'DELIVERY_REQUIRED', label: '待送达', title: '处分已生效，下一步应先登记决定送达', description: '送达是后续申诉处理的前置业务动作；解除仍保留，但不应抢占当前主动作。', actionLabel: '登记送达', permission: 'studentAffairs.discipline.deliver', tone: 'warning' }\n      if (appeal && ['SUBMITTED', 'REVIEWING'].includes(appeal.status)) return { key: 'APPEAL_OPEN', label: appeal.statusLabel || '申诉中', title: '该处分正在申诉复核', description: '优先进入申诉复核处理当前 appeal；解除保留为次级动作。', actionLabel: '处理申诉', permission: 'studentAffairs.discipline.appeal.review', tone: 'warning' }\n      if (appeal) return { key: 'APPEAL_CLOSED', label: appeal.statusLabel || '申诉已结案', title: '处分申诉已有正式复核结论', description: '可查看复核结论；若处分仍保持生效，解除流程可恢复为较高优先级。', actionLabel: '查看复核结论', permission: 'studentAffairs.discipline.view', tone: 'success' }\n      return { key: 'DELIVERED_NO_APPEAL', label: '已送达', title: '决定已送达，当前可进入送达与申诉工作区', description: '如学生提出申诉，应在同一案件上下文登记并复核；解除继续作为次级动作。', actionLabel: '进入送达与申诉', permission: 'studentAffairs.discipline.view', tone: 'success' }\n    },\n    detailActions() {\n      const s = this.selected && this.selected.status''')
    replace_once(path, "      if (s === 'EFFECTIVE') return [{ key: 'remove', label: '发起解除', tone: 'primary', code: 'studentAffairs.discipline.remove.create' }]", '''      if (s === 'EFFECTIVE') {\n        const effect = this.postEffectState\n        const next = { key: 'postEffect', label: effect.actionLabel, tone: effect.key === 'APPEAL_CLOSED' ? 'default' : 'primary', code: effect.permission }\n        const remove = { key: 'remove', label: '发起解除', tone: effect.key === 'APPEAL_CLOSED' ? 'primary' : 'default', code: 'studentAffairs.discipline.remove.create' }\n        return effect.key === 'APPEAL_CLOSED' ? [remove, next] : [next, remove]\n      }''')
    replace_once(path, '''    onAction(key) {\n      const map = {''', '''    goPostEffect() {\n      if (!this.selected || !this.postEffectState) return\n      const query = { caseId: String(this.selected.caseId), from: 'discipline-workbench' }\n      if (this.selected.appealSummary?.appealId) query.appealId = String(this.selected.appealSummary.appealId)\n      this.$router.push({ path: '/admin/student-affairs/discipline/appeals', query })\n    },\n    onAction(key) {\n      if (key === 'postEffect') { this.goPostEffect(); return }\n      const map = {''')
    replace_once(path, '.dp-tech { margin: calc(var(--space-2) * -1) 0 var(--space-4);', '.dp-post-effect { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); margin: 0 0 var(--space-4); padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-lg); background: var(--bg-section); }\n.dp-post-effect strong { color: var(--text-primary); }\n.dp-post-effect p { margin: 4px 0 0; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }\n.dp-tech { margin: calc(var(--space-2) * -1) 0 var(--space-4);')
    changed.append(path)


def patch_appeal_view(changed: list[str]) -> None:
    path = "frontend/src/modules/studentAffairs/views/discipline/DisciplineAppealView.vue"
    replace_once(path, '      <section class="sa-summary-strip">', '      <p v-if="focusNotice" class="ap-focus-note">{{ focusNotice }}</p>\n      <section class="sa-summary-strip">')
    replace_once(path, '>发起申诉</AppPermissionButton>', '>代学生登记申诉</AppPermissionButton>')
    replace_once(path, 'title="提交处分申诉"', 'title="代学生登记处分申诉"')
    replace_once(path, "      pendingAppealCount: '—',\n      appealStatus: '',", "      pendingAppealCount: '—',\n      caseFocusId: '', appealFocusId: '', focusNotice: '',\n      appealStatus: '',")
    replace_once(path, '  mounted() { this.loadAll() },\n  beforeUnmount()', '''  mounted() { this.applyRouteFocus(); this.loadAll() },\n  watch: {\n    '$route.query'(value, previous) {\n      const nextCase = String(value?.caseId || ''), prevCase = String(previous?.caseId || '')\n      const nextAppeal = String(value?.appealId || ''), prevAppeal = String(previous?.appealId || '')\n      if (nextCase !== prevCase || nextAppeal !== prevAppeal) { this.applyRouteFocus(); this.loadAll() }\n    }\n  },\n  beforeUnmount()''')
    replace_once(path, '''  methods: {\n    canBtn(code) { return canCode(this.ctx, code) },''', '''  methods: {\n    applyRouteFocus() {\n      const q = this.$route.query || {}\n      this.caseFocusId = String(q.caseId || '').trim()\n      this.appealFocusId = String(q.appealId || '').trim()\n      this.focusNotice = this.caseFocusId ? `已锁定处分案件 #${this.caseFocusId}；所有查询仍由后端权限与数据范围重新校验。` : ''\n      this.casePagination.page = 1; this.appealPagination.page = 1\n    },\n    canBtn(code) { return canCode(this.ctx, code) },''')
    replace_once(path, "    canAppeal(row) { return this.allows(row, 'APPEAL', row.status === 'EFFECTIVE') },", "    canAppeal(row) { return !!row.deliveredAt && this.allows(row, 'APPEAL', row.status === 'EFFECTIVE') },")
    replace_once(path, '''      const page = this.casePagination.page\n      const pageSize = this.casePagination.pageSize\n      this.caseError = ''\n      const response = await studentAffairsApi.getDisciplineCases({\n        status: 'EFFECTIVE', page, pageSize\n      })''', '''      const page = this.casePagination.page\n      const pageSize = this.casePagination.pageSize\n      this.caseError = ''\n      if (this.caseFocusId) {\n        const response = await studentAffairsApi.getDisciplineDetail(this.caseFocusId)\n        if (seq !== this.caseLoadSeq) return\n        if (response.code !== 0 || !response.data) { this.effectiveCases = []; this.casePagination.total = 0; this.caseError = response.message || '该处分案件不存在、已不可见或不在当前数据范围内'; return }\n        if (response.data.status !== 'EFFECTIVE') { this.effectiveCases = []; this.casePagination.total = 0; this.caseError = `该案件当前状态为${response.data.statusLabel || response.data.status || '未知状态'}，不再属于已生效送达/申诉工作区`; return }\n        this.effectiveCases = [response.data]; this.casePagination.total = 1; return\n      }\n      const response = await studentAffairsApi.getDisciplineCases({ status: 'EFFECTIVE', page, pageSize })''')
    replace_once(path, '      const response = await studentAffairsApi.getDisciplineAppeals({ status, page, pageSize })', '''      const response = await studentAffairsApi.getDisciplineAppeals({\n        status, caseId: this.caseFocusId || undefined, appealId: this.appealFocusId || undefined, page, pageSize\n      })''')
    replace_once(path, '''      this.appeals = response.data.items || []\n      this.appealPagination.total = response.data.total != null ? response.data.total : this.appeals.length''', '''      this.appeals = response.data.items || []\n      this.appealPagination.total = response.data.total != null ? response.data.total : this.appeals.length\n      if (this.appealFocusId && !this.appeals.some((item) => String(item.appealId) === String(this.appealFocusId))) this.appealError = '该申诉不存在、已不可见，或不属于当前处分案件' ''')
    replace_once(path, '.sa-grid--metrics { display: grid;', '.ap-focus-note { margin: 0 0 var(--space-3); padding: var(--space-2) var(--space-3); border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); }\n.sa-grid--metrics { display: grid;')
    changed.append(path)


def patch_backend_test(changed: list[str]) -> None:
    path = "backend/tests/test_affairs_discipline_appeal.py"
    append_once(path, 'test_detail_post_effect_appeal_summary_truth', '''\ndef test_detail_post_effect_appeal_summary_truth(client, db_mode):\n    hdr = _hdr(client, "school_admin01")\n    cid = _seed_case(db_mode["student"], "EFFECTIVE")\n    before = client.get(f"{BASE}/discipline/cases/{cid}", headers=hdr).json()["data"]\n    assert before["status"] == "EFFECTIVE" and before["deliveredAt"] is None and before["appealSummary"] is None\n    post_versioned(client, f"{BASE}/discipline/cases/{cid}/deliver", headers=hdr, json={"method": "DIRECT", "remark": "本人签收"})\n    assert client.get(f"{BASE}/discipline/cases/{cid}", headers=hdr).json()["data"]["appealSummary"] is None\n    submitted = client.post(f"{BASE}/discipline/cases/{cid}/appeal", headers=hdr, json={"reason": "对处分认定事实有异议，申请正式复核"}).json()["data"]\n    aid = submitted["appealId"]\n    detail = client.get(f"{BASE}/discipline/cases/{cid}", headers=hdr).json()["data"]\n    assert detail["status"] == "EFFECTIVE" and detail["appealSummary"] == {"appealId": aid, "status": "SUBMITTED", "statusLabel": "待复核", "result": None}\n    focused = client.get(f"{BASE}/discipline/appeals?caseId={cid}&appealId={aid}", headers=hdr).json()["data"]\n    assert focused["total"] == 1 and focused["items"][0]["appealId"] == aid\n    post_versioned(client, f"{BASE}/discipline/appeals/{aid}/review", headers=hdr, json={"result": "UPHELD", "opinion": "经复核事实清楚证据充分，维持原处分"})\n    detail = client.get(f"{BASE}/discipline/cases/{cid}", headers=hdr).json()["data"]\n    assert detail["status"] == "EFFECTIVE" and detail["appealSummary"]["status"] == "UPHELD" and detail["appealSummary"]["result"] == "UPHELD"\n''')
    changed.append(path)


def add_frontend_contract(changed: list[str]) -> None:
    path = "frontend/tests/student-affairs-discipline-post-effect-flow.contract.test.mjs"
    write(path, '''import test from 'node:test'\nimport assert from 'node:assert/strict'\nimport fs from 'node:fs'\nconst read = (p) => fs.readFileSync(new URL(`../${p}`, import.meta.url), 'utf8')\ntest('EFFECTIVE 后动作按送达/申诉真值排序', () => { const src = read('src/modules/studentAffairs/views/DisciplineWorkbenchView.vue'); for (const key of ['DELIVERY_REQUIRED','DELIVERED_NO_APPEAL','APPEAL_OPEN','APPEAL_CLOSED']) assert.ok(src.includes(key)); assert.ok(src.includes("['SUBMITTED', 'REVIEWING'].includes(appeal.status)")); assert.ok(src.includes("effect.key === 'APPEAL_CLOSED' ? [remove, next] : [next, remove]")); assert.ok(src.includes("path: '/admin/student-affairs/discipline/appeals'")); })\ntest('处分主工作台消费 detail appealSummary', () => { const src = read('src/modules/studentAffairs/views/DisciplineWorkbenchView.vue'); assert.ok(src.includes('const appeal = row.appealSummary')); assert.ok(src.includes('getDisciplineDetail(recordId)')); })\ntest('送达与申诉页按 caseId/appealId 精确过滤并 fail closed', () => { const view = read('src/modules/studentAffairs/views/discipline/DisciplineAppealView.vue'); const api = read('src/modules/studentAffairs/api/studentAffairs.api.js'); assert.ok(view.includes("this.caseFocusId = String(q.caseId || '').trim()")); assert.ok(view.includes("this.appealFocusId = String(q.appealId || '').trim()")); assert.ok(view.includes('getDisciplineDetail(this.caseFocusId)')); assert.ok(view.includes('代学生登记申诉')); assert.ok(api.includes('if (caseId) params.caseId = caseId')); assert.ok(api.includes('if (appealId) params.appealId = appealId')); })\n''')
    changed.append(path)


def main() -> None:
    changed: list[str] = []
    patch_backend_service(changed); patch_backend_api(changed); patch_frontend_api(changed)
    patch_workbench(changed); patch_appeal_view(changed); patch_backend_test(changed); add_frontend_contract(changed)
    (ROOT / '.sa-flow-changed-files').write_text('\n'.join(changed) + '\n', encoding='utf-8')
    (ROOT / '.sa-flow-commit-message').write_text('fix(student-affairs): prioritize discipline delivery and appeal\n', encoding='utf-8')
    print('P1-03 patched files:\n' + '\n'.join(changed))


if __name__ == '__main__':
    main()
