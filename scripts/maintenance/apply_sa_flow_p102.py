from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    text = read(path)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one anchor, got {count}: {old[:140]!r}")
    write(path, text.replace(old, new, 1))


def append_once(path: str, marker: str, content: str) -> None:
    text = read(path)
    if marker not in text:
        write(path, text.rstrip() + "\n\n" + content.strip() + "\n")


def patch_workbench(changed: list[str]) -> None:
    path = "frontend/src/modules/studentAffairs/views/FundingWorkbenchView.vue"
    replace_once(
        path,
        '''        <AppPermissionButton :allowed="canBtn('studentAffairs.funding.publicity.manage')" code="studentAffairs.funding.publicity.manage" variant="secondary" size="sm" :loading="scanning" @click="onScan">公示扫描</AppPermissionButton>\n        <AppPermissionButton :allowed="canBtn('studentAffairs.funding.create')"''',
        '''        <AppPermissionButton :allowed="canBtn('studentAffairs.funding.publicity.manage')" code="studentAffairs.funding.publicity.manage" variant="secondary" size="sm" :loading="scanning" @click="onScan">公示扫描</AppPermissionButton>\n        <AppPermissionButton :allowed="canBtn('studentAffairs.funding.publicity.manage')" code="studentAffairs.funding.publicity.manage" variant="secondary" size="sm" :disabled="!batchId || !projectId" @click="goPublicity">公示待办</AppPermissionButton>\n        <AppPermissionButton :allowed="canBtn('studentAffairs.funding.create')"'''
    )
    replace_once(
        path,
        '''    async onScan() {\n      this.scanning = true''',
        '''    goPublicity() {\n      if (!this.batchId || !this.projectId) return\n      this.$router.push({\n        path: '/admin/student-affairs/funding/publicity',\n        query: { batchId: String(this.batchId), projectId: String(this.projectId), source: 'funding-workbench' }\n      })\n    },\n    async onScan() {\n      this.scanning = true'''
    )
    changed.append(path)


def patch_publicity(changed: list[str]) -> None:
    path = "frontend/src/modules/studentAffairs/views/funding/FundingPublicityView.vue"
    replace_once(
        path,
        '''                    @back="$router.push('/admin/student-affairs/funding')">\n      <div class="sa-toolbar">''',
        '''                    @back="backToFunding">\n      <div v-if="batchId" class="fp-context">\n        <strong>当前批次：#{{ batchId }}</strong>\n        <span v-if="projectId">项目 #{{ projectId }}</span>\n        <span>仅处理该批次公示队列；身份、权限与数据范围仍由后端重新校验。</span>\n      </div>\n      <div class="sa-toolbar">'''
    )
    replace_once(
        path,
        '''        <p v-else class="sa-empty">当前无公示中的资助申请</p>\n        <!-- 本页仅展示''',
        '''        <div v-else-if="handoffReady" class="fp-complete">\n          <strong>本批次公示已完成</strong>\n          <span>当前批次已无 PUBLICITY 待办，可继续生成正式发放台账。</span>\n          <button type="button" class="fp-handoff" @click="goDisbursement">本批次公示已完成 → 生成发放台账</button>\n        </div>\n        <p v-else class="sa-empty">当前无公示中的资助申请</p>\n        <!-- 本页仅展示'''
    )
    replace_once(
        path,
        '''  data() { return { publicityColumns: PUBLICITY_COLUMNS, loading: true, scanning: false, actingId: '', errorMessage: '', items: [] } },''',
        '''  data() { return { publicityColumns: PUBLICITY_COLUMNS, loading: true, scanning: false, actingId: '', errorMessage: '', items: [], batchId: '', projectId: '', source: '' } },'''
    )
    replace_once(
        path,
        '''    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },\n    metricCards() {''',
        '''    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },\n    handoffReady() { return !!this.batchId && !this.loading && !this.errorMessage && this.items.length === 0 },\n    metricCards() {'''
    )
    replace_once(
        path,
        '''  mounted() { this.load() },\n  methods: {\n    canBtn(code) { return canCode(this.ctx, code) },\n    async load() {\n      this.loading = true; this.errorMessage = ''\n      const res = await studentAffairsApi.getFundingApplications({ status: 'PUBLICITY', pageSize: 200 })''',
        '''  mounted() { this.applyRouteContext(); this.load() },\n  watch: {\n    '$route.query'(value, previous) {\n      if (String(value?.batchId || '') !== String(previous?.batchId || '') || String(value?.projectId || '') !== String(previous?.projectId || '')) {\n        this.applyRouteContext(); this.load()\n      }\n    }\n  },\n  methods: {\n    canBtn(code) { return canCode(this.ctx, code) },\n    applyRouteContext() {\n      const q = this.$route.query || {}\n      this.batchId = String(q.batchId || '').trim()\n      this.projectId = String(q.projectId || '').trim()\n      this.source = String(q.source || '').trim()\n    },\n    backToFunding() {\n      const query = {}\n      if (this.batchId) query.batchId = this.batchId\n      if (this.projectId) query.projectId = this.projectId\n      this.$router.push({ path: '/admin/student-affairs/funding', query })\n    },\n    goDisbursement() {\n      if (!this.batchId) return\n      const query = { batchId: this.batchId, source: 'publicity' }\n      if (this.projectId) query.projectId = this.projectId\n      this.$router.push({ path: '/admin/student-affairs/funding/disbursements', query })\n    },\n    async load() {\n      this.loading = true; this.errorMessage = ''\n      const res = await studentAffairsApi.getFundingApplications({ status: 'PUBLICITY', batchId: this.batchId || undefined, pageSize: 200 })'''
    )
    replace_once(
        path,
        '''.fp-note { color: var(--text-tertiary); font-size: var(--font-size-sm); margin-bottom: var(--space-3); }''',
        '''.fp-context { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; margin-bottom: var(--space-3); padding: var(--space-2) var(--space-3); border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); }\n.fp-context strong { color: var(--text-primary); }\n.fp-note { color: var(--text-tertiary); font-size: var(--font-size-sm); margin-bottom: var(--space-3); }\n.fp-complete { display: grid; gap: var(--space-2); justify-items: start; padding: var(--space-5); border: 1px solid var(--success-200, #bbf7d0); border-radius: var(--radius-lg); background: var(--success-50, #f0fdf4); }\n.fp-handoff { border: 0; border-radius: var(--radius-md); padding: 8px 14px; background: var(--color-primary); color: #fff; font: inherit; font-weight: 600; cursor: pointer; }'''
    )
    changed.append(path)


def patch_disbursement(changed: list[str]) -> None:
    path = "frontend/src/modules/studentAffairs/views/funding/FundingDisbursementView.vue"
    replace_once(
        path,
        '''      <div class="sa-toolbar">\n        <div class="sa-grid sa-grid--metrics">''',
        '''      <AppInlineAlert v-if="genBatchId && routeSource === 'publicity'" type="info" :description="`已承接公示批次 #${genBatchId}；下方记录、生成与导出保持同一批次上下文。`" />\n      <p v-if="genBatchId" class="fd-scope-note">统计卡仍是当前权限范围的全局概览；下方发放记录与 Excel 导出按当前批次 #{{ genBatchId }} 收敛。</p>\n      <div class="sa-toolbar">\n        <div class="sa-grid sa-grid--metrics">'''
    )
    replace_once(
        path,
        '''          <AppFundingBatchPicker v-model="genBatchId" class="fd-genpick" :options="batchOptions" placeholder="选择批次生成…" />''',
        '''          <AppFundingBatchPicker v-model="genBatchId" class="fd-genpick" :options="batchOptions" placeholder="选择批次生成…" @change="onBatchContextChange" />'''
    )
    replace_once(
        path,
        '''      genBatchId: '',\n      pagination:''',
        '''      genBatchId: '', routeProjectId: '', routeSource: '',\n      pagination:'''
    )
    replace_once(
        path,
        '''  mounted() { this.load() },\n  beforeUnmount()''',
        '''  mounted() { this.applyRouteContext(); this.load() },\n  watch: {\n    '$route.query.batchId'(value, previous) {\n      if (String(value || '') === String(previous || '')) return\n      this.applyRouteContext(); this.pagination.page = 1; this.loadRecords()\n    }\n  },\n  beforeUnmount()'''
    )
    replace_once(
        path,
        '''  methods: {\n    canBtn(code) { return canCode(this.ctx, code) },''',
        '''  methods: {\n    canBtn(code) { return canCode(this.ctx, code) },\n    applyRouteContext() {\n      const q = this.$route.query || {}\n      const batchId = String(q.batchId || '').trim()\n      this.genBatchId = batchId\n      this.routeProjectId = String(q.projectId || '').trim()\n      this.routeSource = String(q.source || '').trim()\n    },\n    onBatchContextChange() {\n      const batch = this.batches.find((item) => String(item.batchId) === String(this.genBatchId))\n      const query = { ...this.$route.query }\n      if (this.genBatchId) query.batchId = String(this.genBatchId); else delete query.batchId\n      if (batch?.projectId) query.projectId = String(batch.projectId); else delete query.projectId\n      this.$router.replace({ query }).catch(() => {})\n      this.pagination.page = 1\n      this.loadRecords()\n    },'''
    )
    replace_once(
        path,
        '''      const response = await studentAffairsApi.getFundingDisbursements({\n        bankStatus: this.activeStatus,''',
        '''      const response = await studentAffairsApi.getFundingDisbursements({\n        batchId: this.genBatchId || undefined,\n        bankStatus: this.activeStatus,'''
    )
    replace_once(
        path,
        '''      if (response.code === 0 && response.data) this.batches = response.data.items || []\n      else { this.batches = []; this.batchError = response.message || '资助批次加载失败，暂不能生成发放台账' }''',
        '''      if (response.code === 0 && response.data) {\n        this.batches = response.data.items || []\n        if (this.genBatchId) {\n          const batch = this.batches.find((item) => String(item.batchId) === String(this.genBatchId))\n          if (!batch) this.batchError = '承接的资助批次当前不可见，已停止自动回退到其他批次'\n          else if (this.routeProjectId && String(batch.projectId || '') !== String(this.routeProjectId)) this.batchError = '批次与项目上下文不一致，请返回资助工作台重新进入'\n        }\n      } else { this.batches = []; this.batchError = response.message || '资助批次加载失败，暂不能生成发放台账' }'''
    )
    replace_once(
        path,
        '''      const response = await fundingExportApi.create({\n        purpose,\n        bankStatus: this.activeStatus || undefined''',
        '''      const response = await fundingExportApi.create({\n        purpose,\n        batchId: this.genBatchId || undefined,\n        bankStatus: this.activeStatus || undefined'''
    )
    replace_once(
        path,
        '''.fd-gen { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; justify-content: flex-end; }''',
        '''.fd-scope-note { margin: 0 0 var(--space-3); color: var(--text-tertiary); font-size: var(--font-size-sm); }\n.fd-gen { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; justify-content: flex-end; }'''
    )
    changed.append(path)


def add_contract(changed: list[str]) -> None:
    path = "frontend/tests/student-affairs-funding-handoff.contract.test.mjs"
    write(path, '''import test from 'node:test'\nimport assert from 'node:assert/strict'\nimport fs from 'node:fs'\n\nconst read = (p) => fs.readFileSync(new URL(`../${p}`, import.meta.url), 'utf8')\n\ntest('资助工作台进入公示必须携带同一 projectId/batchId', () => {\n  const src = read('src/modules/studentAffairs/views/FundingWorkbenchView.vue')\n  assert.ok(src.includes("path: '/admin/student-affairs/funding/publicity'"))\n  assert.ok(src.includes("batchId: String(this.batchId)"))\n  assert.ok(src.includes("projectId: String(this.projectId)"))\n  assert.ok(src.includes("source: 'funding-workbench'"))\n})\n\ntest('公示页只收当前批次且清空后由人工 CTA 进入发放', () => {\n  const src = read('src/modules/studentAffairs/views/funding/FundingPublicityView.vue')\n  assert.ok(src.includes("batchId: this.batchId || undefined"))\n  assert.ok(src.includes('this.items.length === 0'))\n  assert.ok(src.includes('本批次公示已完成 → 生成发放台账'))\n  assert.ok(src.includes("path: '/admin/student-affairs/funding/disbursements'"))\n  assert.ok(src.includes("source: 'publicity'"))\n  assert.ok(!src.includes("toast.success('已确认获资助')\\n        this.goDisbursement"), '逐条确认后不得强制跳页')\n})\n\ntest('发放页的记录、生成上下文和 Excel 导出使用同一 batchId', () => {\n  const src = read('src/modules/studentAffairs/views/funding/FundingDisbursementView.vue')\n  assert.ok(src.includes("this.genBatchId = batchId"))\n  assert.ok(src.includes('batchId: this.genBatchId || undefined'))\n  assert.ok(src.includes('fundingExportApi.create({'))\n  assert.ok(src.includes('统计卡仍是当前权限范围的全局概览'))\n  assert.ok(src.includes('已停止自动回退到其他批次'))\n})\n''')
    changed.append(path)


def main() -> None:
    changed: list[str] = []
    patch_workbench(changed)
    patch_publicity(changed)
    patch_disbursement(changed)
    add_contract(changed)
    (ROOT / ".sa-flow-changed-files").write_text("\n".join(changed) + "\n", encoding="utf-8")
    (ROOT / ".sa-flow-commit-message").write_text("fix(student-affairs): preserve funding publicity handoff\n", encoding="utf-8")
    print("P1-02 patched files:\n" + "\n".join(changed))


if __name__ == "__main__":
    main()
