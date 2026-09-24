from __future__ import annotations
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

HEAD = 'dcd08ea1311150e146cc7375c80ffcfeeaeae9c4'
BASE = '86f1e64abcd1261e9ed3437720c299f8cbb5ee56'
TREE = '2d2f9ef874f92e7e60fb9cb18bb699b655f75180'
REPO = 'penghaibin9/saas'
BRANCH = 'codex/orientation-delivery-20260923'
DOC = 'docs/07-部署运维交付与商业化/module-commerce/M0-resource-boundaries.json'
PAGES = 'frontend/src/views/admin/orientation/'
ALLOWED = [
    'backend/app/api/v1/orientation.py',
    'backend/app/services/_mobile_teacher_service_impl.py',
    'backend/app/services/orientation_service.py',
    'backend/app/services/school_domain_report_service.py',
    'backend/tests/test_orientation_archive_context.py',
    'backend/tests/test_orientation_export_reports.py',
    'backend/tests/test_orientation_mobile_dashboard.py', DOC,
    'frontend/src/modules/orientation/routeContext.js',
    PAGES + 'PaymentGreenChannelView.vue',
    PAGES + 'OrientationQualificationView.vue',
    PAGES + 'DormCheckinView.vue',
    'frontend/tests/o1-orientation-batch-authority-contract.test.mjs',
    'frontend/tests/o4-orientation-qualification-contract.test.mjs',
    'frontend/tests/page-loading-navigation.behavior.test.mjs',
    'frontend/tests/orientation-route-scope-recovery.behavior.test.mjs',
    'miniapp/src/components/MobileRegionPicker.vue',
    'shared/contracts/navigation-surface-contract.json',
]

def git(*args):
    return subprocess.check_output(['git', *args]).decode('utf-8')

def replace(path, old, new, count=1):
    target = Path(path)
    text = target.read_text(encoding='utf-8')
    if text.count(old) != count:
        raise RuntimeError(f'Unexpected anchor count in {path}: {text.count(old)} != {count}: {old[:100]!r}')
    target.write_text(text.replace(old, new), encoding='utf-8', newline='\n')

def append(path, value):
    p = Path(path)
    p.write_text(p.read_text(encoding='utf-8').rstrip() + '\n\n' + value.strip() + '\n', encoding='utf-8', newline='\n')

def patch_pages():
    specs = {
        'PaymentGreenChannelView': {
            'request': "const fn = this.tab === 'payment' ? api.getPaymentStatusList : api.getGreenChannelApplications\n        const res = await fn({ ...this.filters, batchId: this.$route.query.batchId || undefined, orientationStudentId: this.$route.query.orientationStudentId || undefined, page: this.page, pageSize: this.pageSize })",
            'reset': "this.tab = this.$route.query.tab === 'green' ? 'green' : 'payment'\n      this.detailVisible = this.paymentVisible = this.approveVisible = this.rejectVisible = this.returnVisible = this.exportVisible = this.auditVisible = false\n      this.detailTarget = this.paymentTarget = null\n      this.paymentEdit = { payableAmount: 0, paidAmount: 0, status: 'UNPAID', sourceBizId: '' }\n      this.auditLogs = []",
            'busy': 'this.submitting',
            'writes': ['onApprove', 'onReject', 'onReturn', 'savePayment'],
        },
        'OrientationQualificationView': {
            'request': 'const res = await api.getOrientationQualifications({ ...this.filters, batchId: this.$route.query.batchId || undefined, orientationStudentId: this.$route.query.orientationStudentId || undefined, page: this.page, pageSize: this.pageSize })',
            'reset': "this.filters.keyword = String(this.$route.query.keyword || '')\n      this.filters.queue = String(this.$route.query.queue || '')\n      this.confirmVisible = this.activateVisible = this.finalizeVisible = this.dispositionVisible = this.credentialVisible = false\n      this.confirmRow = this.activateRow = this.finalizeRow = this.dispositionRow = this.credential = null\n      this.activateStudentNo = this.finalizeStudentNo = this.dispositionReason = this.activateRequestId = this.finalizeRequestId = ''",
            'busy': 'this.activating || this.finalizing || this.disposing || this.recalculating',
            'writes': ['onActivateConfirm', 'onFinalizeConfirm'],
        },
        'DormCheckinView': {
            'request': 'const res = await api.getDormitoryCheckinList({ ...this.filters, ...(this.batchId ? {batchId:this.batchId} : {}), orientationStudentId: this.$route.query.orientationStudentId || undefined, page: this.page, pageSize: this.pageSize })',
            'reset': 'this.selected = []\n      this.editVisible = this.confirmVisible = this.exceptionVisible = this.exportVisible = this.auditVisible = false\n      this.editing = this.exceptionTarget = null\n      this.auditLogs = []',
            'busy': 'this.submitting',
            'writes': ['onExceptionConfirm'],
        },
    }
    for name, spec in specs.items():
        path = PAGES + name + '.vue'
        replace(path, '  data() {\n    return {', '  data() {\n    return {\n      readSequence: 0, scopeGeneration: 0, scopeDisposed: false, recalculating: false,')
        replace(path, '  computed: {', "  computed: {\n    routeContextKey() {\n      const q = this.$route.query\n      return JSON.stringify([q.batchId || '', q.orientationStudentId || '', q.queue || '', q.keyword || '', q.tab || ''])\n    },")
        watcher = "  watch: {\n    routeContextKey: { flush: 'sync', handler() { return this.resetRouteContext() } }\n  },\n"
        if name == 'OrientationQualificationView':
            replace(path, "  watch: { '$route.query.keyword'(value) { if (value !== undefined) { this.filters.keyword = String(value); this.search() } } },\n", watcher)
        elif name == 'DormCheckinView':
            replace(path, '  watch: { batchId() { this.page = 1; this.load() } },\n', watcher)
        else:
            replace(path, '  async created() {', watcher + '  async created() {')
        hooks = """  beforeUnmount() {
    this.scopeDisposed = true
    this.scopeGeneration++
    this.readSequence++
  },
  beforeRouteUpdate(to, from) {
    const keys = ['batchId', 'orientationStudentId', 'queue', 'keyword', 'tab']
    if (keys.some(key => String(to.query[key] || '') !== String(from.query[key] || '')) && (BUSY)) {
      toast.error('当前记录正在保存，请完成后再切换批次或学生')
      return false
    }
  },
""".replace('BUSY', spec['busy'])
        reset_method = """    resetRouteContext() {
      this.scopeGeneration++
      this.readSequence++
      this.rows = []; this.total = 0; this.page = 1; this.error = ''
      this.filters = EMPTY_FILTERS()
      RESET
      return this.load()
    },
""".replace('RESET', spec['reset'])
        replace(path, '  methods: {\n', hooks + '  methods: {\n' + reset_method)
        text = Path(path).read_text(encoding='utf-8')
        start, end = text.index('    async load() {'), text.index('    search() {')
        load = """    async load() {
      if (this.scopeDisposed) return
      const sequence = ++this.readSequence
      const scope = this.routeContextKey
      const current = () => !this.scopeDisposed && sequence === this.readSequence && scope === this.routeContextKey
      this.loading = true; this.error = ''; this.rows = []; this.total = 0
      SELECTED
      try {
        REQUEST
        if (!current()) return
        if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total }
        else this.error = res.message || '加载失败'
      } catch (e) {
        if (current()) this.error = e.message || '加载失败'
      } finally {
        if (current()) this.loading = false
      }
    },
""".replace('REQUEST', spec['request']).replace('SELECTED', 'this.selected = []' if name == 'DormCheckinView' else '')
        Path(path).write_text(text[:start] + load + text[end:], encoding='utf-8', newline='\n')
        replace(path, 'if (ctx.code === 0) this.ctx = ctx.data', 'if (this.scopeDisposed) return\n      if (ctx.code === 0) this.ctx = ctx.data')
        if name != 'OrientationQualificationView':
            replace(path, '    async openAudit() {\n', '    async openAudit() {\n      const generation = this.scopeGeneration\n')
            replace(path, '      if (res.code === 0) this.auditLogs = res.data.list', '      if (this.scopeDisposed || generation !== this.scopeGeneration) return\n      if (res.code === 0) this.auditLogs = res.data.list')
        # A write already sent still completes on the server. Its late reply must
        # not reopen a previous student's details/credentials in a newer context.
        for method in spec['writes']:
            text = Path(path).read_text(encoding='utf-8')
            match = re.search(r'    async ' + method + r'\([^\n]*\) \{\n', text)
            if not match: raise RuntimeError(f'Missing method {name}.{method}')
            stop = text.find('\n    },', match.end())
            if stop < 0: stop = text.find('\n    }\n', match.end())
            chunk = text[match.start():stop]
            chunk = chunk.replace(match[0], match[0] + '      const generation = this.scopeGeneration\n', 1)
            anchor = '        if (!res || res.code !== 0)' if name == 'OrientationQualificationView' else '        if (res.code === 0)'
            if chunk.count(anchor) != 1: raise RuntimeError(f'Missing reply guard anchor {name}.{method}')
            chunk = chunk.replace(anchor, '        if (this.scopeDisposed || generation !== this.scopeGeneration) return\n' + anchor, 1)
            Path(path).write_text(text[:match.start()] + chunk + text[stop:], encoding='utf-8', newline='\n')
    path = PAGES + 'OrientationQualificationView.vue'
    replace(path, '    async onDisposition() { if (this.disposing', '    async onDisposition() { const generation = this.scopeGeneration; if (this.disposing')
    replace(path, 'if (r.code !== 0) return toast.error(r.message); this.dispositionVisible', 'if (this.scopeDisposed || generation !== this.scopeGeneration) return; if (r.code !== 0) return toast.error(r.message); this.dispositionVisible')
    text = Path(path).read_text(encoding='utf-8')
    start, end = text.index('    async onConfirm() {'), text.index('    async onActivateConfirm() {')
    text = text[:start] + """    async onConfirm() {
      const row = this.confirmRow
      if (!row || this.recalculating) return
      const generation = this.scopeGeneration
      this.recalculating = true
      try {
        const res = await api.recalculateOrientationQualification(row.id)
        if (this.scopeDisposed || generation !== this.scopeGeneration) return
        if (res && res.code === 0) { toast.success(`办理情况已更新：${this.qualificationText(res.data.verdict)}`); this.confirmVisible = false; await this.load() }
        else toast.error((res && res.message) || '资格重算失败')
      } finally { this.recalculating = false }
    },
""" + text[end:]
    Path(path).write_text(text, encoding='utf-8', newline='\n')


def apply():
    if git('rev-parse', 'HEAD').strip() != HEAD or git('status', '--porcelain').strip():
        raise RuntimeError('Repair requires an untouched exact PR head')
    replace('backend/app/api/v1/orientation.py', 'status: Optional[str] = None, batchId: Optional[str] = None,\n             user=Depends(require_staff)):\n    items, total = svc.list_archives', 'status: Optional[str] = None, batchId: Optional[int] = Query(None, ge=1),\n             user=Depends(require_staff)):\n    items, total = svc.list_archives')
    replace('backend/app/services/_mobile_teacher_service_impl.py', '    batch_id = d.get("batchId")\n    if not batch_id:', '    batch_id = d.get("batchId")\n    if not batch_id or d.get("batchStatus") != "ACTIVE":')
    replace('backend/app/services/orientation_service.py', '            "batchId": str(batch.id) if batch else "",\n            "batchName":', '            "batchId": str(batch.id) if batch else "",\n            "batchStatus": batch.status if batch else "",\n            "batchName":')
    path = 'backend/app/services/school_domain_report_service.py'
    replace(path, '{**L_PAY, "MISSING": "未同步缴费事实"}', '{**L_PAY, "WAIVED": "已减免", "MISSING": "未同步缴费事实"}', 2)
    replace(path, '"applyType": {"STUDENT_LOAN": "助学贷款",', '"applyType": {"POVERTY": "家庭经济困难", "DISASTER": "突发灾害",\n                      "STUDENT_LOAN": "助学贷款",')
    replace(path, '"exceptionType": L_EXCTYPE, "riskLevel": L_RISK,', '"exceptionType": {**L_EXCTYPE, "MATERIAL": "材料异常"}, "riskLevel": L_RISK,')
    replace('frontend/src/modules/orientation/routeContext.js', "      params.delete('batchId')", "      params.delete('batchId')\n      params.delete('orientationStudentId')")
    patch_pages()
    path = 'frontend/tests/o1-orientation-batch-authority-contract.test.mjs'
    text = Path(path).read_text(encoding='utf-8')
    lines = text.splitlines()
    stale = [line for line in lines if "assert.match(api" in line and ('pageSize: 1' in line or '当前没有进行中的迎新批次' in line)]
    if len(stale) != 2: raise RuntimeError('O1 old export assertions changed')
    text = text.replace(stale[0], "  const exportBody = api.slice(api.indexOf('export async function createExport'), api.indexOf('export async function getAuditLogs'))\n  assert.ok(exportBody.includes('payload.batchId'))\n  assert.ok(!exportBody.includes(\"request('/orientation/batches'\"))")
    text = text.replace(stale[1] + '\n', '')
    Path(path).write_text(text, encoding='utf-8', newline='\n')
    replace('frontend/tests/o4-orientation-qualification-contract.test.mjs', r'/my\.value\.qualification\?\.verdictLabel/', r'/my\.value\.qualification\?\.verdict\b/')
    path = 'frontend/tests/page-loading-navigation.behavior.test.mjs'
    replace(path, "import vm from 'node:vm'", "import vm from 'node:vm'\nimport { restoreOrientationBatch } from '../src/modules/orientation/routeContext.js'")
    replace(path, '    destinations: new Map(), route, mobileOpen: { value: true },', '    destinations: new Map(), route, mobileOpen: { value: true },\n    restoreOrientationBatch, sessionStorage: { getItem: () => null },')
    patch_region()
    path = 'backend/tests/test_orientation_mobile_dashboard.py'
    replace(path, '"batchId": "9007199254740993", "batchName"', '"batchId": "9007199254740993", "batchStatus": "ACTIVE", "batchName"')
    replace(path, 'lambda **kwargs: {"batchId": "18"}', 'lambda **kwargs: {"batchId": "18", "batchStatus": "ACTIVE"}')
    append(path, '''
@pytest.mark.parametrize("status", ["CLOSED", "DRAFT", "VOID", "", None])
def test_mobile_dashboard_non_active_batch_never_opens_pending_arrival_queue(monkeypatch, status):
    monkeypatch.setattr(mobile, "db_enabled", lambda: True)
    monkeypatch.setattr(mobile.orientation_service, "get_dashboard", lambda **kwargs: {"batchId": "18", "batchStatus": status})
    monkeypatch.setattr(mobile.orientation_service, "list_students", lambda *args, **kwargs: pytest.fail("Non-active queue must not run"))
    result = mobile.orientation_dashboard(TEACHER)
    assert result["hasData"] is False
    assert result["notReported"] == [] and result["notReportedTotal"] == 0
''')
    append('backend/tests/test_orientation_archive_context.py', '''
@pytest.mark.parametrize("batch_id", ["abc", "0", "-1", "1.5", " "])
def test_archive_batch_id_rejected_by_request_validation(client, auth_headers, batch_id):
    response = client.get(f"{BASE}/archives", headers=auth_headers, params={"batchId": batch_id})
    assert response.status_code == 400, response.text
    assert response.json()["bizCode"] == "VALIDATION_ERROR", response.text
''')
    path = 'backend/tests/test_orientation_export_reports.py'
    replace(path, '    # Absence of a finance fact is not unpaid.', '''    # Exercise all supported client values through the real workbook endpoint.
    for apply_type, expected_label in (("POVERTY", "家庭经济困难"), ("DISASTER", "突发灾害")):
        with get_sessionmaker()() as db:
            account = db.scalar(select(OrientationPaymentAccount).where(OrientationPaymentAccount.orientation_student_id == ids['orientationId']))
            account.status = "WAIVED"
            application = db.scalar(select(GreenChannelApplication).where(GreenChannelApplication.ori_student_id == ids['orientationId']))
            application.apply_type = apply_type
            db.commit()
        for report, column, expected_label_value in (("green-channel", "申请类型", expected_label), ("payment", "缴费状态", "已减免"), ("students", "缴费事实", "已减免")):
            created = client.post('/api/v1/export/domain/orientation', headers=auth_headers,
                                  json={'batchId': batch_id, 'reportType': report, 'purpose': '受支持业务标签台账核验用途'})
            assert created.status_code == 200, created.text
            downloaded = client.get(f"/api/v1/export/tasks/{created.json()['data']['taskId']}/download", headers=auth_headers)
            assert downloaded.status_code == 200, downloaded.text
            workbook = load_workbook(io.BytesIO(downloaded.content), read_only=True)
            values = list(workbook.active.values)
            row = dict(zip(values[1], values[2]))
            assert row[column] == expected_label_value, (report, column, row[column])
            workbook.close()

    # Absence of a finance fact is not unpaid.''')
    # Re-review the old evidence anchor rather than blindly regenerating every hash.
    doc = json.loads(Path(DOC).read_text(encoding='utf-8'))
    item = doc['evidence']['E037']
    raw = Path(item['path']).read_bytes()
    previous = subprocess.check_output(['git', 'show', BASE + ':' + item['path']])
    start, end = item['startLine'], item['endLine']
    if raw.decode().splitlines()[start-1:end] != previous.decode().splitlines()[start-1:end]:
        raise RuntimeError('Reviewed identity resolver changed; refusing automatic evidence update')
    if hashlib.sha256(raw).hexdigest() != '830312a4a4357bfce93c8370ba2179e79a86fc97735b8a1d13676aca6cf51146':
        raise RuntimeError('Unexpected mobile source content')
    replace(DOC, item['sha256'], hashlib.sha256(raw).hexdigest())
    newtest = Path('frontend/tests/orientation-route-scope-recovery.behavior.test.mjs')
    if newtest.exists(): raise RuntimeError('Test already exists')
    newtest.write_text(SCOPE_TESTS, encoding='utf-8', newline='\n')
    subprocess.run(['node', 'scripts/generate-navigation-surface-contract.mjs'], check=True)
    for path in ALLOWED:
        if path.endswith('.py'): ast.parse(Path(path).read_text(encoding='utf-8'), filename=path)
    changed = set(git('diff', '--name-only').splitlines())
    if not changed <= set(ALLOWED): raise RuntimeError('Change escaped allowlist')
    subprocess.run(['git', 'add', '--', *ALLOWED], check=True)
    subprocess.run(['git', 'diff', '--cached', '--check'], check=True)
    Path('repair-reviewed.diff').write_text(git('diff', '--cached', '--'), encoding='utf-8')
    print(git('diff', '--cached', '--stat'))


def patch_region():
    path = 'miniapp/src/components/MobileRegionPicker.vue'
    replace(path, '<template>\n', '''<template>
  <!-- #ifdef H5 -->
  <view class="mrp mrp--web" :class="{ 'is-disabled': disabled }">
    <select aria-label="省份" :disabled="disabled" :value="provinceCode" @change="chooseProvince($event.target.value)"><option value="">请选择省份</option><option v-for="item in provinces" :key="item.code" :value="item.code">{{ item.name }}</option></select>
    <select aria-label="城市" :disabled="disabled || !provinceCode" :value="cityCode" @change="chooseCity($event.target.value)"><option value="">请选择城市</option><option v-for="item in cities" :key="item.code" :value="item.code">{{ item.name }}</option></select>
    <select aria-label="区县" :disabled="disabled || !cityCode" :value="countyCode" @change="chooseCounty($event.target.value)"><option value="">请选择区县</option><option v-for="item in counties" :key="item.code" :value="item.code">{{ item.name }}</option></select>
    <text v-if="modelValue" class="mrp__saved">{{ modelValue }}</text>
  </view>
  <!-- #endif -->
  <!-- #ifndef H5 -->
''')
    replace(path, '  </picker>\n</template>', '  </picker>\n  <!-- #endif -->\n</template>')
    replace(path, '<script>\n', "<script>\n// #ifdef H5\nimport { areaList } from '@vant/area-data'\nconst entries = source => Object.entries(source).map(([code, name]) => ({ code, name }))\n// #endif\n")
    replace(path, "  emits: ['update:modelValue', 'change'],", """  emits: ['update:modelValue', 'change'],
  // #ifdef H5
  data() { return { provinceCode: '', cityCode: '', countyCode: '' } },
  watch: { modelValue: { immediate: true, handler(value) {
    if (!value) return
    const names = String(value).trim().split(/\\s+/)
    this.provinceCode = this.provinces.find(item => item.name === names[0])?.code || ''
    this.cityCode = this.cities.find(item => names.includes(item.name))?.code || ''
    this.countyCode = this.counties.find(item => names.includes(item.name))?.code || ''
  } } },
  // #endif""")
    replace(path, '  computed: {', '''  computed: {
    // #ifdef H5
    provinces() { return entries(areaList.province_list) },
    cities() { return this.provinceCode ? entries(areaList.city_list).filter(item => item.code.startsWith(this.provinceCode.slice(0, 2))) : [] },
    counties() { return this.cityCode ? entries(areaList.county_list).filter(item => item.code.startsWith(this.cityCode.slice(0, 4))) : [] },
    // #endif''')
    replace(path, '  methods: {', '''  methods: {
    // #ifdef H5
    chooseProvince(code) { if (this.disabled) return; this.provinceCode = code; this.cityCode = ''; this.countyCode = ''; this.$emit('update:modelValue', '') },
    chooseCity(code) { if (this.disabled) return; this.cityCode = code; this.countyCode = ''; this.$emit('update:modelValue', '') },
    chooseCounty(code) {
      if (this.disabled) return
      this.countyCode = code
      if (!code) { this.$emit('update:modelValue', ''); return }
      const codes = [this.provinceCode, this.cityCode, code]
      const names = [areaList.province_list[codes[0]], areaList.city_list[codes[1]], areaList.county_list[codes[2]]]
      this.onConfirm({ detail: { value: names, code: codes } })
    },
    // #endif''')
    replace(path, '    onConfirm(e) {', '    onConfirm(e) {\n      if (this.disabled) return')
    replace(path, '.mrp__text {', '''.mrp--web { flex-wrap: wrap; padding: 8px; }
.mrp--web select { flex: 1 1 90px; min-width: 0; max-width: 100%; padding: 8px 2px; border: 0; background: transparent; color: #1f2937; font-size: 14px; }
.mrp__saved { width: 100%; font-size: 12px; color: #64748b; }
.mrp__text {''')


def api(method, path, data=None):
    body = json.dumps(data).encode() if data is not None else None
    request = urllib.request.Request('https://api.github.com/repos/' + REPO + path, data=body, method=method,
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'], 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28'})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.load(response)


def publish():
    if os.environ.get('GITHUB_REPOSITORY') != REPO: raise RuntimeError('Wrong repository')
    pr = api('GET', '/pulls/274')
    if pr['head']['sha'] != HEAD or pr['base']['sha'] != BASE or pr['state'] != 'open':
        raise RuntimeError('PR moved; refusing to publish a stale candidate')
    paths = git('diff', '--cached', '--name-only').splitlines()
    if set(paths) != set(ALLOWED): raise RuntimeError('Incomplete or unexpected candidate diff')
    entries = []
    for path in paths:
        content = subprocess.check_output(['git', 'show', ':' + path])
        blob = api('POST', '/git/blobs', {'content': base64.b64encode(content).decode(), 'encoding': 'base64'})
        expected = hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()
        if blob['sha'] != expected: raise RuntimeError('Uploaded content identity mismatch')
        entries.append({'path': path, 'mode': '100644', 'type': 'blob', 'sha': blob['sha']})
    tree = api('POST', '/git/trees', {'base_tree': TREE, 'tree': entries})
    commit = api('POST', '/git/commits', {'message': 'fix(orientation): close PR274 review regressions and repair CI contracts', 'tree': tree['sha'], 'parents': [HEAD]})
    evidence = {'candidate': commit['sha'], 'parent': HEAD, 'base': BASE, 'tree': tree['sha'], 'files': paths, 'branchUpdated': False, 'merged': False}
    Path('repair-candidate.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('CANDIDATE_READY ' + json.dumps(evidence, ensure_ascii=False))


SCOPE_TESTS = r'''import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse } from '@vue/compiler-sfc'
import { restoreOrientationBatch } from '../src/modules/orientation/routeContext.js'

const ok = (id) => ({ code: 0, data: { list: [{ id }], total: 1 } })
const pending = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const cases = [
  ['PaymentGreenChannelView', 'getPaymentStatusList'],
  ['OrientationQualificationView', 'getOrientationQualifications'],
  ['DormCheckinView', 'getDormitoryCheckinList']
]
function screen(name, api) {
  const text = readFileSync(new URL(`../src/views/admin/orientation/${name}.vue`, import.meta.url), 'utf8')
  const names = []
  const script = parse(text).descriptor.script.content
    .replace(/import \* as api from [^\n]+/g, '')
    .replace(/import\s+\{([^}]+)\}\s+from\s+['"][^'"]+['"]/g, (_, imports) => { names.push(...imports.split(',').map(value => value.trim())); return '' })
    .replace('export default', 'return')
  const messages = []
  const deps = { toast: { error: value => messages.push(value), success: value => messages.push(value) }, toLabelMap: () => ({}) }
  const component = new Function('api', ...names, script)(api, ...names.map(key => deps[key] || {}))
  const view = { $route: { path: '/admin/orientation/payment', query: { batchId: '9007199254740993', orientationStudentId: '7' } } }
  Object.assign(view, component.data.call(view))
  for (const [key, fn] of Object.entries(component.methods)) view[key] = fn.bind(view)
  for (const [key, fn] of Object.entries(component.computed)) Object.defineProperty(view, key, { get: fn.bind(view) })
  return { view, component, messages, change: query => { view.$route.query = query; return component.watch.routeContextKey.handler.call(view) } }
}
for (const [name, method] of cases) {
  test(`${name}: query-only context switch clears student rows and dialogs before the next response`, async () => {
    const next = pending(), calls = []
    const state = screen(name, { [method]: args => { calls.push(args); return next.promise } })
    const v = state.view
    Object.assign(v, { rows: [{ id: 'old' }], total: 9, page: 4, filters: { keyword: '旧学生' }, auditVisible: true, credentialVisible: true, credential: { temporaryPassword: 'synthetic-only' } })
    const loading = state.change({ batchId: '9007199254740995' })
    assert.deepEqual(v.rows, []); assert.equal(v.total, 0); assert.equal(v.page, 1)
    assert.equal(calls[0].batchId, '9007199254740995'); assert.equal(calls[0].orientationStudentId, undefined)
    assert.equal(calls[0].keyword, '')
    if (name === 'OrientationQualificationView') { assert.equal(v.credential, null); assert.equal(v.credentialVisible, false) }
    else assert.equal(v.auditVisible, false)
    next.resolve(ok('new')); await loading
    assert.equal(v.rows[0].id, 'new'); assert.equal(v.loading, false)
  })
  for (const outcome of ['success', 'failure']) {
    test(`${name}: former student's late ${outcome} cannot replace current data`, async () => {
      const old = pending(); let count = 0
      const state = screen(name, { [method]: () => ++count === 1 ? old.promise : Promise.resolve(ok('new')) })
      const loading = state.view.load()
      await state.change({ batchId: '9007199254740993' })
      if (outcome === 'success') old.resolve(ok('old')); else old.reject(new Error('旧请求失败'))
      await loading
      assert.equal(state.view.rows[0].id, 'new'); assert.equal(state.view.error, ''); assert.equal(state.view.loading, false)
    })
  }
  test(`${name}: unmount invalidates pending reads and prevents follow-up loads`, async () => {
    const request = pending(); let calls = 0
    const state = screen(name, { [method]: () => { calls++; return request.promise } })
    const loading = state.view.load(); state.component.beforeUnmount.call(state.view)
    request.resolve(ok('old')); await loading; await state.view.load()
    assert.deepEqual(state.view.rows, []); assert.equal(calls, 1)
  })
  test(`${name}: failed current read is an error rather than empty success`, async () => {
    const state = screen(name, { [method]: async () => { throw new Error('本批次读取失败') } })
    await state.change({ batchId: '9', orientationStudentId: '8' })
    assert.equal(state.view.error, '本批次读取失败'); assert.deepEqual(state.view.rows, []); assert.equal(state.view.total, 0)
  })
  test(`${name}: context change is blocked while its formal write is in flight`, () => {
    const state = screen(name, {})
    Object.assign(state.view, { submitting: true, activating: true })
    const permitted = state.component.beforeRouteUpdate.call(state.view, { query: { batchId: '2' } }, { query: { batchId: '1' } })
    assert.equal(permitted, false); assert.equal(state.messages.length, 1)
  })
}
test('payment green tab uses the same scoped late-response protections', async () => {
  const calls = []
  const state = screen('PaymentGreenChannelView', { getGreenChannelApplications: async args => { calls.push(args); return ok('green') } })
  await state.change({ batchId: '8', orientationStudentId: '9', tab: 'green' })
  assert.equal(calls[0].orientationStudentId, '9'); assert.equal(state.view.rows[0].id, 'green')
})
test('a late credential reply cannot reveal a former student after the context was invalidated', async () => {
  const request = pending()
  const state = screen('OrientationQualificationView', { activateOrientationIdentity: () => request.promise, getOrientationQualifications: async () => ok('new') })
  Object.assign(state.view, { activateRow: { id: '7', version: 1 }, activateStudentNo: 'TEST-7', activateRequestId: 'test-request' })
  const saving = state.view.onActivateConfirm()
  await state.change({ batchId: '9', orientationStudentId: '8' })
  request.resolve({ code: 0, data: { initialCredential: { temporaryPassword: 'synthetic-only' } } }); await saving
  assert.equal(state.view.credential, null); assert.equal(state.view.credentialVisible, false); assert.deepEqual(state.messages, [])
})
test('restored workspace tabs drop the old student but explicit detail navigation retains it', () => {
  const storage = { getItem: () => '9007199254740995' }
  const source = '/admin/orientation/payment?batchId=1&orientationStudentId=7&tab=green'
  const restored = new URL(restoreOrientationBatch(source, storage, 'test-identity', true), 'https://example.invalid')
  assert.equal(restored.searchParams.get('batchId'), '9007199254740995')
  assert.equal(restored.searchParams.has('orientationStudentId'), false)
  assert.equal(restored.searchParams.get('tab'), 'green')
  assert.equal(restoreOrientationBatch(source, storage, 'test-identity'), source)
})
'''

if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in ('apply', 'publish'): raise SystemExit('Use apply or publish')
    {'apply': apply, 'publish': publish}[sys.argv[1]]()
