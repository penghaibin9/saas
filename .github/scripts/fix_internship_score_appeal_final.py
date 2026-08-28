from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def write(path, text):
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


# 1) Domain service: require explicit context and expose latest appeal status to the student.
path = "backend/app/modules/internship/services/internship_score_appeal_service.py"
text = read(path)
text = replace_once(
    text,
    '    b = body or {}\n    reason = str(b.get("reason") or "").strip()\n',
    '    b = body or {}\n    if not str(b.get("batchId") or "").strip() and not str(b.get("internshipId") or "").strip():\n'
    '        raise AppException("VALIDATION_ERROR", "成绩申诉必须携带当前实习批次或实习记录上下文")\n'
    '    reason = str(b.get("reason") or "").strip()\n',
    "score appeal explicit context",
)
insert = '''\n\ndef my_latest(user: dict, *, batch_id=None, internship_id=None) -> dict:\n    """学生本人查看当前实习最近一条成绩申诉及其真实处理状态。"""\n    _require_student(user)\n    with session() as db:\n        student = resolve_student(db, user)\n        if not student:\n            raise not_found("未找到当前学生档案")\n\n        from app.modules.internship.services.internship_record_resolver import resolve_student_internship_context\n\n        ctx = resolve_student_internship_context(\n            db, student=student, batch_id=batch_id, for_write=False\n        )\n        record = ctx.record\n        explicit = str(internship_id or "").strip()\n        if explicit:\n            direct = db.get(InternshipRecord, _as_id(explicit))\n            if (\n                not direct\n                or direct.is_deleted\n                or direct.tenant_id != _tid()\n                or direct.student_id != student.id\n            ):\n                raise not_found("该实习记录不存在或不属于当前学生")\n            if batch_id and str(direct.batch_id or "") != str(batch_id):\n                raise AppException("DATA_CONFLICT", "实习记录与所选批次不一致，请刷新后重试")\n            record = direct\n        if not record:\n            return {"hasAppeal": False, "status": "", "statusLabel": "暂无成绩申诉"}\n\n        cs_student = db.scalars(\n            select(CsServiceStudent).where(\n                CsServiceStudent.tenant_id == _tid(),\n                CsServiceStudent.student_id == student.id,\n                CsServiceStudent.is_deleted.is_(False),\n            )\n        ).first()\n        if not cs_student:\n            return {"hasAppeal": False, "status": "", "statusLabel": "暂无成绩申诉"}\n\n        orders = db.scalars(\n            select(CsWorkOrder).where(\n                CsWorkOrder.tenant_id == _tid(),\n                CsWorkOrder.cs_student_id == cs_student.id,\n                CsWorkOrder.title == APPEAL_KEY,\n                CsWorkOrder.is_deleted.is_(False),\n            ).order_by(CsWorkOrder.id.desc())\n        ).all()\n        for work_order in orders:\n            try:\n                meta = _meta(work_order)\n            except AppException:\n                # 历史通用工单没有冻结成绩快照，不能冒充当前领域申诉。\n                continue\n            if str(meta.get("internshipId") or "") != str(record.id):\n                continue\n            row = _row(db, work_order, record=record, student=student)\n            return {"hasAppeal": True, **row}\n        return {"hasAppeal": False, "status": "", "statusLabel": "暂无成绩申诉"}\n'''
text = replace_once(text, '\n\ndef list_appeals(user: dict, *, page: int = 1, page_size: int = 20, status: str | None = None,\n', insert + '\n\ndef list_appeals(user: dict, *, page: int = 1, page_size: int = 20, status: str | None = None,\n', "insert my_latest")
write(path, text)

# 2) Student portal service exposes status read.
path = "backend/app/student_portal/services/internship_service.py"
text = read(path)
old = '''def score_appeal(user: dict, body: dict) -> dict:\n    """实习成绩申诉：冻结正式成绩版本并进入岗位实习成绩状态机。"""\n    from app.modules.internship.services import internship_score_appeal_service as appeal\n    return appeal.create(user, body or {})\n'''
new = old + '''\n\ndef score_appeal_status(user: dict, *, batch_id=None, internship_id=None) -> dict:\n    """本人查看当前实习最近一条成绩申诉状态。"""\n    from app.modules.internship.services import internship_score_appeal_service as appeal\n    return appeal.my_latest(user, batch_id=batch_id, internship_id=internship_id)\n'''
text = replace_once(text, old, new, "portal appeal status service")
write(path, text)

# 3) Student portal router adds GET on the same resource path.
path = "backend/app/student_portal/router.py"
text = read(path)
old = '''@router.post("/internship/score/appeal", summary="实习成绩申诉（本人）")\ndef internship_score_appeal(user=Depends(get_current_user), body: dict = Body(...)):\n    return success(internship.score_appeal(user, body))\n'''
new = '''@router.get("/internship/score/appeal", summary="本人实习成绩申诉状态")\ndef internship_score_appeal_status(batchId: str = "", internshipId: str = "", user=Depends(get_current_user)):\n    return success(internship.score_appeal_status(\n        user, batch_id=batchId or None, internship_id=internshipId or None\n    ))\n\n\n''' + old
text = replace_once(text, old, new, "portal appeal GET route")
write(path, text)

# 4) Student portal API can read status.
path = "student-portal/src/services/portalApi.js"
text = read(path)
old = "  internshipScoreAppeal: (body) => request('/portal/internship/score/appeal', { method: 'POST', body }),\n"
new = "  internshipScoreAppealStatus: (params = {}) => request(`/portal/internship/score/appeal${q(params)}`),\n" + old
text = replace_once(text, old, new, "student portal API appeal status")
write(path, text)

# 5) Student UI: show real appeal status and always submit explicit internship context.
path = "student-portal/src/views/internship/InternshipView.vue"
text = read(path)
text = replace_once(
    text,
    "const appealReason = ref('')\nconst selfEvalMeta = ref(null)\n",
    "const appealReason = ref('')\nconst appealMeta = ref(null)\nconst selfEvalMeta = ref(null)\n",
    "student appeal meta state",
)
text = replace_once(
    text,
    '''  try {\n    selfEvalMeta.value = await internshipCoreApi.selfEval()\n  } catch { selfEvalMeta.value = null }\n  await loadEnterprises()\n''',
    '''  try {\n    selfEvalMeta.value = await internshipCoreApi.selfEval()\n  } catch { selfEvalMeta.value = null }\n  try {\n    appealMeta.value = await portalApi.internshipScoreAppealStatus(currentInternshipContext())\n  } catch { appealMeta.value = null }\n  await loadEnterprises()\n''',
    "load appeal status",
)
text = replace_once(
    text,
    '''            <div class="sp-fieldlabel" style="margin-top:14px">成绩申诉理由</div>\n            <textarea v-model.trim="appealReason" class="sp-inp" style="margin-bottom:12px" placeholder="对成绩有异议？请说明理由" />\n            <button class="sp-btn sp-btn--ghost" :disabled="busy || !appealReason" @click="submitAppeal">提交成绩申诉</button>\n''',
    '''            <div v-if="appealMeta?.hasAppeal" class="notebox" style="margin-top:14px">\n              最近申诉：{{ appealMeta.statusLabel || appealMeta.status }}\n              <span v-if="appealMeta.status === 'APPROVED_RECALCULATING'"> · 原成绩已撤回，学校正在重新核算</span>\n              <span v-else-if="appealMeta.status === 'CLOSED'"> · 新成绩已重新发布</span>\n            </div>\n            <div class="sp-fieldlabel" style="margin-top:14px">成绩申诉理由</div>\n            <textarea v-model.trim="appealReason" class="sp-inp" style="margin-bottom:12px" placeholder="对成绩有异议？请说明理由" />\n            <button class="sp-btn sp-btn--ghost"\n              :disabled="busy || !appealReason || !my.score || ['PENDING','APPROVED_RECALCULATING'].includes(appealMeta?.status)"\n              @click="submitAppeal">提交成绩申诉</button>\n''',
    "student appeal UI",
)
text = replace_once(
    text,
    '''async function submitAppeal() {\n  busy.value = true\n  try { await portalApi.internshipScoreAppeal({ reason: appealReason.value }); ui.notify('成绩申诉已提交'); appealReason.value = '' }\n  catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }\n}\n''',
    '''async function submitAppeal() {\n  busy.value = true\n  try {\n    await portalApi.internshipScoreAppeal({ ...currentInternshipContext(), reason: appealReason.value })\n    ui.notify('成绩申诉已提交')\n    appealReason.value = ''\n    appealMeta.value = await portalApi.internshipScoreAppealStatus(currentInternshipContext())\n  }\n  catch (e) { ui.notify(e?.message || '提交失败') } finally { busy.value = false }\n}\n''',
    "student submit appeal context",
)
write(path, text)

# 6) Staff score API adds appeal queue actions.
path = "frontend/src/modules/internship/api/score.api.js"
text = read(path)
text = replace_once(text, "const B = '/internship/scores'\n", "const B = '/internship/scores'\nconst A = '/internship/score-appeals'\n", "score appeal API base")
text = replace_once(
    text,
    "  getScores(params = {}) { return callList(B, params) },\n",
    "  getScores(params = {}) { return callList(B, params) },\n  getAppeals(params = {}) { return callList(A, params) },\n  approveAppeal(id, body) { return call(() => request(`${A}/${id}/approve`, { method: 'POST', body })) },\n  rejectAppeal(id, body) { return call(() => request(`${A}/${id}/reject`, { method: 'POST', body })) },\n",
    "score appeal API methods",
)
write(path, text)

# 7) Staff score workspace: queue, decision actions, WITHDRAWN recalc, expectedVersion on recalc.
path = "frontend/src/modules/internship/views/ScoreView.vue"
text = read(path)
text = replace_once(
    text,
    '''      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />\n\n      <!-- 权重配置（真实 getConfig / saveConfig） -->\n''',
    '''      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />\n\n      <div class="appeals">\n        <div class="appeals__head">\n          <div><strong>成绩申诉</strong><span>与正式成绩状态机联动，受理后原成绩自动撤回</span></div>\n          <AppButton variant="ghost" size="sm" :disabled="appealsLoading" @click="loadAppeals">刷新</AppButton>\n        </div>\n        <div v-if="appealsLoading" class="state">正在加载申诉…</div>\n        <div v-else-if="!appeals.length" class="state">当前批次暂无成绩申诉</div>\n        <div v-else class="appeals__list">\n          <div v-for="item in appeals" :key="item.id" class="appeal-row">\n            <div class="appeal-row__main">\n              <div><strong>{{ item.studentName }}</strong> · {{ item.studentNo || '无学号' }} · <AppStatusTag :status="item.status">{{ item.statusLabel }}</AppStatusTag></div>\n              <div class="appeal-row__reason">申诉理由：{{ item.reason }}</div>\n              <div class="appeal-row__reason">冻结成绩：{{ item.scoreSnapshot?.totalScore ?? '—' }} · 当前成绩状态：{{ item.currentScore?.status || '—' }}</div>\n            </div>\n            <div v-if="item.status === 'PENDING'" class="appeal-row__ops">\n              <AppPermissionButton code="internship.score.publish" :allowed="canBtn('internship.score.publish')" variant="secondary" size="sm" @click="decideAppeal(item, true)">受理并撤回原成绩</AppPermissionButton>\n              <AppPermissionButton code="internship.score.publish" :allowed="canBtn('internship.score.publish')" variant="ghost" size="sm" :danger="true" @click="decideAppeal(item, false)">驳回</AppPermissionButton>\n            </div>\n            <div v-else-if="item.status === 'APPROVED_RECALCULATING'" class="appeal-row__tip">请在下方找到该学生的「已撤回」成绩并重新核算、复核、发布。</div>\n          </div>\n        </div>\n      </div>\n\n      <!-- 权重配置（真实 getConfig / saveConfig） -->\n''',
    "staff appeal queue UI",
)
text = replace_once(text, "const RECALC_STATUSES = ['PENDING_REVIEW', 'PENDING_CALC']\n", "const RECALC_STATUSES = ['PENDING_REVIEW', 'PENDING_CALC', 'WITHDRAWN']\n", "withdrawn recalc status")
text = replace_once(
    text,
    "      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',\n",
    "      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',\n      appeals: [], appealsLoading: false,\n",
    "staff appeal state",
)
text = replace_once(
    text,
    '''    this.loadConfig()\n    this.load()\n''',
    '''    this.loadConfig()\n    this.load()\n    this.loadAppeals()\n''',
    "staff initial appeal load",
)
text = replace_once(
    text,
    "    'batchStore.selectedBatchId'() { this.page = 1; this.closePanel(); this.load() }\n",
    "    'batchStore.selectedBatchId'() { this.page = 1; this.closePanel(); this.load(); this.loadAppeals() }\n",
    "staff batch appeal reload",
)
text = replace_once(
    text,
    '''    async load() {\n      if (!this.batchStore.selectedBatchId) {\n''',
    '''    async loadAppeals() {\n      if (!this.batchStore.selectedBatchId) { this.appeals = []; this.appealsLoading = false; return }\n      this.appealsLoading = true\n      const res = await scoreApi.getAppeals({ batchId: this.batchStore.selectedBatchId, page: 1, pageSize: 100 })\n      this.appealsLoading = false\n      if (res.code !== 0) { this.appeals = []; return toast.error(res.message || '成绩申诉加载失败') }\n      this.appeals = res.data.list || []\n    },\n    async decideAppeal(item, approve) {\n      const promptText = approve ? '请输入受理意见（不少于5字）' : '请输入驳回原因（不少于5字）'\n      const reason = (window.prompt(promptText) || '').trim()\n      if (reason.length < 5) return toast.error('处理意见不少于 5 字')\n      const fn = approve ? scoreApi.approveAppeal : scoreApi.rejectAppeal\n      const res = await fn(item.id, { reason, expectedVersion: item.version })\n      if (res.code !== 0) return toast.error(res.message || '申诉处理失败')\n      toast.success(res.data?.message || (approve ? '申诉已受理，原成绩已撤回' : '申诉已驳回'))\n      await this.loadAppeals()\n      await this.load()\n    },\n    async load() {\n      if (!this.batchStore.selectedBatchId) {\n''',
    "staff appeal methods",
)
text = replace_once(
    text,
    '''      const body = { internshipId: this.cForm.internshipId }\n      for (const s of SCORE_INPUTS) if (this.cForm[s.key] !== null && this.cForm[s.key] !== '') body[s.key] = this.cForm[s.key]\n      const res = await scoreApi.compute(body)\n''',
    '''      const body = { internshipId: this.cForm.internshipId }\n      for (const s of SCORE_INPUTS) if (this.cForm[s.key] !== null && this.cForm[s.key] !== '') body[s.key] = this.cForm[s.key]\n      if (this.panel.mode === 'edit') {\n        const current = this.panelRow\n        if (!current || current.version === null || current.version === undefined) {\n          this.panel.submitting = false\n          return toast.error('成绩版本已失效，请刷新后重试')\n        }\n        body.expectedVersion = current.version\n      }\n      const res = await scoreApi.compute(body)\n''',
    "score recalc expectedVersion",
)
text = replace_once(
    text,
    '''      await this.load()\n      // 若工作区正在核对该行，动作后刷新留痕\n''',
    '''      await this.load()\n      await this.loadAppeals()\n      // 若工作区正在核对该行，动作后刷新留痕\n''',
    "refresh appeal after score transition",
)
text = replace_once(
    text,
    '''.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }\n''',
    '''.appeals { border: 1px solid var(--border-base); border-radius: var(--radius-lg, 12px); padding: var(--space-3); background: var(--card, #fff); }\n.appeals__head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-2); }\n.appeals__head > div { display: flex; align-items: baseline; gap: var(--space-2); }\n.appeals__head span { color: var(--text-tertiary); font-size: var(--font-size-xs); }\n.appeals__list { display: flex; flex-direction: column; gap: var(--space-2); }\n.appeal-row { display: flex; gap: var(--space-3); align-items: center; justify-content: space-between; padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-base); background: var(--bg-subtle); }\n.appeal-row__main { min-width: 0; }\n.appeal-row__reason, .appeal-row__tip { margin-top: var(--space-1); color: var(--text-secondary); font-size: var(--font-size-xs); }\n.appeal-row__ops { display: flex; gap: var(--space-1); flex-wrap: wrap; flex: none; }\n.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }\n''',
    "appeal styles",
)
write(path, text)

# 8) Expand static contracts for the final closure.
path = "backend/tests/test_internship_prelaunch_static_contracts.py"
text = read(path)
append = '''\n\ndef test_score_appeal_is_real_domain_flow():\n    text = src("app/modules/internship/services/internship_score_appeal_service.py")\n    assert 'scoreVersion' in text\n    assert 'expected_status="PUBLISHED"' in text\n    assert 'values={"status": "WITHDRAWN"}' in text\n    assert '实习已最终归档' in text\n    assert 'def my_latest' in text\n\ndef test_score_appeal_generic_workorder_cannot_bypass_domain():\n    text = src("app/api/v1/campus_service.py")\n    assert '_is_internship_score_appeal' in text\n    assert 'internship_score_appeal.decide' in text\n\ndef test_score_recalc_supports_withdrawn_and_optimistic_lock():\n    text = (ROOT.parent / "frontend/src/modules/internship/views/ScoreView.vue").read_text(encoding="utf-8")\n    assert "'WITHDRAWN'" in text\n    assert 'body.expectedVersion = current.version' in text\n    assert 'scoreApi.getAppeals' in text\n\ndef test_student_score_appeal_sends_context_and_reads_status():\n    text = (ROOT.parent / "student-portal/src/views/internship/InternshipView.vue").read_text(encoding="utf-8")\n    assert '...currentInternshipContext(), reason: appealReason.value' in text\n    assert 'internshipScoreAppealStatus(currentInternshipContext())' in text\n\ndef test_score_appeal_router_is_registered():\n    text = src("app/api/v1/route_registration.py")\n    assert 'internship_score_appeal' in text\n'''
if "test_score_appeal_is_real_domain_flow" not in text:
    text += append
write(path, text)

print("final score appeal codemod applied")
