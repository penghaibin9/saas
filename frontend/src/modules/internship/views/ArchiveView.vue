<template>
  <ModulePageShell title="实习归档" subtitle="核对缺项与材料安全，确认后归档并留存档案包。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton v-if="!panel.visible" variant="ghost" @click="goMaterials">材料与证据</AppButton>
      <AppButton v-if="!panel.visible && canBtn('internship.stats.view')" variant="ghost" @click="goStats">实习统计</AppButton>
      <AppExportButton v-if="!panel.visible" :export-fn="exportFn" :has-permission="canBtn('internship.archive.package')">{{ tab === 'student' && onlyIncomplete ? '导出全部状态台账' : '导出归档台账' }}</AppExportButton>
    </template>

    <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

    <div v-if="panelMode === 'materials' && !panel.visible" class="material-entry">
      <div>
        <strong>学生材料核验</strong>
        <span>已筛选待预检或未归档学生；进入核验后查看当前缺项。</span>
      </div>
      <AppButton variant="ghost" size="sm" @click="clearMaterialEntry">查看全部归档台账</AppButton>
    </div>

    <div v-if="!panel.visible" class="tabs" role="tablist" aria-label="归档视图">
      <button v-for="t in tabs" :id="`archive-tab-${t.key}`" :key="t.key" type="button" role="tab"
        :aria-selected="tab === t.key" class="tabs__btn" :class="{ 'is-active': tab === t.key }"
        @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <!-- 按学生 -->
    <template v-if="tab === 'student'">
      <div v-if="!panel.visible" class="bar">
        <AppSearchBox v-model="keyword" placeholder="搜索姓名或学号" @search="reload" />
        <label class="chk"><input v-model="onlyIncomplete" type="checkbox" @change="reload" />仅看待预检 / 未归档</label>
        <span v-if="!loading && !error" class="bar__hint">当前筛选 {{ total }} 人</span>
      </div>
      <div v-if="error && !panel.visible" class="state is-err" role="alert">{{ error }} <button type="button" @click="load">重试</button></div>
      <template v-else>
        <DataTable v-if="!panel.visible" :columns="studentColumns" :rows="rows" row-key="id" :loading="loading"
          :pagination="pagination" row-clickable @row-click="openDetail" @page-change="onPageChange">
          <template #cell-studentName="{ row }">
            <div class="student-cell"><strong>{{ row.studentName }}</strong><span>{{ row.studentNo }}</span></div>
          </template>
          <template #cell-completeness="{ row }">
            <span v-if="row.readinessKnown" class="pct"><span class="pct__bar"><span class="pct__fill" :class="{ 'is-full': row.completeness >= 100 }" :style="{ width: row.completeness + '%' }"></span></span>{{ row.completeness }}%</span>
            <span v-else class="bar__hint">打开核验后计算</span>
          </template>
          <template #cell-missing="{ row }">
            <AppStatusTag v-if="!row.readinessKnown" type="default" size="sm">待预检</AppStatusTag>
            <AppStatusTag v-else-if="!row.missing.length" type="success" size="sm">齐全</AppStatusTag>
            <span v-else class="miss">{{ row.missing?.join('、') }}</span>
          </template>
          <template #cell-archived="{ row }">
            <AppStatusTag :type="row.archived ? 'success' : 'default'">{{ row.archived ? '已归档' : '未归档' }}</AppStatusTag>
          </template>
          <template #cell-actions="{ row }">
            <div class="ops">
              <AppButton variant="secondary" size="sm" :aria-label="`核验${row.studentName}归档材料`" @click="openDetail(row)">{{ row.archived ? '查看档案' : '核验材料' }}</AppButton>
            </div>
          </template>
        </DataTable>

        <div v-if="!panel.visible && !loading && !rows.length" class="state">当前筛选下暂无归档学生</div>

        <!-- 选中行完整性工作区（替代原「归档材料清单」居中弹窗） -->
        <div v-if="panel.visible" class="wsp" role="region" aria-labelledby="archive-workspace-title" aria-live="polite">
          <div class="wsp__head">
            <h2 id="archive-workspace-title" class="wsp__title" tabindex="-1">{{ panelStudentLabel || '归档材料核验' }}</h2>
            <template v-if="panel.data">
              <AppStatusTag :type="panel.data.archived ? 'success' : 'default'">{{ panel.data.archived ? '已归档' : '未归档' }}</AppStatusTag>
              <span v-if="panel.data.missing.length" class="miss-cell">缺 {{ panel.data.missing.length }} 项</span>
              <AppStatusTag v-else type="success" size="sm">材料齐全</AppStatusTag>
            </template>
            <AppButton class="wsp__close" variant="ghost" size="sm" :disabled="busy" @click="closePanel">返回归档台账</AppButton>
          </div>
          <div v-if="panel.loading" class="state">加载中…</div>
          <div v-else-if="panel.error" class="state is-err" role="alert">{{ panel.error }} <AppButton variant="ghost" @click="openDetailById(panel.rowId)">重试</AppButton></div>
          <template v-else-if="panel.data">
            <div class="next-step"><strong>{{ panel.data.archived ? '已归档' : '待归档核验' }}</strong><span>{{ panel.data.archived ? '可生成或下载档案包，核验后留存；需要补正时先撤销归档。' : '先处理业务缺项，再预检材料安全，确认后冻结归档记录。' }}</span></div>
            <AppDescriptionList :items="detailItems" :columns="2" />
            <div v-if="actionError && !cd.visible" class="state is-err" role="alert">{{ actionError }}</div>
            <div v-if="keptReason && !cd.visible" class="hint">上次填写的撤销原因：{{ keptReason }}</div>
            <AppButton v-if="actionConflict && !cd.visible" variant="secondary" @click="acknowledgeLatest">已核对最新状态，继续办理</AppButton>

            <div class="sec-t">待补事项</div>
            <div v-if="panel.data.missingActions?.length" class="mat-list">
              <div v-for="m in panel.data.missingActions" :key="m.code" class="mat-row is-miss">
                <AppStatusTag type="warning" size="sm">待处理</AppStatusTag>
                <span class="mat-row__label"><strong>{{ m.label }}</strong><small>{{ m.reason || '尚未满足归档规则' }}</small></span>
                <AppButton variant="ghost" size="sm" @click="goFix(m)">{{ m.actionLabel }}</AppButton>
              </div>
            </div>
            <div v-else-if="panel.data.archivePassed" class="ready-line"><div><strong>业务材料已满足归档规则</strong><small>提交前仍会重新核验文件安全状态与正式成绩版本</small></div></div>

            <div v-else class="hint">当前归档条件尚未通过，请重新核验后查看缺项。</div>

            <div class="preflight-line">
              <div>
                <strong>文件安全预检</strong>
                <span v-if="panel.data.fileVersionSafety">{{ panel.data.fileVersionSafety.ready }}/{{ panel.data.fileVersionSafety.total }} 个当前版本安全可用</span>
                <span v-else>尚未预检；预检会检查当前材料版本与安全状态</span>
              </div>
              <AppStatusTag v-if="panel.data.fileVersionSafety" :type="panel.data.fileVersionSafety.unsafe ? 'danger' : 'success'" size="sm">
                {{ panel.data.fileVersionSafety.unsafe ? `阻断 ${panel.data.fileVersionSafety.unsafe} 项` : '安全检查通过' }}
              </AppStatusTag>
              <AppButton variant="secondary" size="sm" :loading="preflightBusy" :disabled="busy || !canBtn('internship.archive.view')" @click="runPreflight(panel.data)">检查材料安全</AppButton>
            </div>

            <div v-if="panel.data.fileVersionSafety?.unsafeItems?.length" class="unsafe-files" role="status">
              <div v-for="file in panel.data.fileVersionSafety.unsafeItems" :key="file.versionId"><strong>{{ file.fileName }}</strong><span>{{ file.statusText || '当前版本安全检查未通过' }}</span></div>
            </div>
            <details v-if="panel.data.materialLabels?.length" class="material-checklist"><summary>查看材料关联清单</summary><div v-for="material in panel.data.materialLabels" :key="material.key"><span>{{ material.label }}</span><AppStatusTag :type="material.present ? 'success' : 'default'" size="sm">{{ material.present ? '已关联' : '未关联' }}</AppStatusTag></div><p class="hint">清单仅说明材料是否关联，是否可归档以当前预检结果为准。</p></details>
            <div class="sec-t">归档办理</div>
            <div class="wsp__ops">
              <AppButton variant="ghost" :disabled="busy" @click="goMaterials">查看学生材料</AppButton>
              <AppPermissionButton v-if="!panel.data.archived" code="internship.archive.execute" :allowed="canBtn('internship.archive.execute')"
                variant="primary" :loading="preflightBusy" :disabled="busy || actionConflict" @click="doArchive(panel.data)">预检并提交归档</AppPermissionButton>
              <AppPermissionButton v-else code="internship.archive.revoke" :allowed="canBtn('internship.archive.revoke')" variant="ghost" size="sm"
                :danger="true" :disabled="busy || actionConflict" @click="doRevoke(panel.data)">撤销归档</AppPermissionButton>
              <template v-if="panel.data.archived">
                <AppPermissionButton v-if="!(pkgFile || panel.data.latestPackage)?.packageId" code="internship.archive.package" :allowed="canBtn('internship.archive.package')"
                  variant="secondary" size="sm" :loading="pkgBusy" :disabled="busy" @click="buildPackage">生成归档包</AppPermissionButton>
                <AppButton v-else variant="secondary" size="sm" :loading="pkgBusy" :disabled="busy || !canBtn('internship.archive.package')" @click="downloadPackage">下载归档包 (zip)</AppButton>
                <AppButton v-if="panel.data.latestPackage || pkgFile" variant="ghost" size="sm" :loading="restoreBusy" :disabled="busy || !canBtn('internship.archive.package')" @click="verifyRestore">恢复校验</AppButton>
                <AppButton variant="ghost" size="sm" :loading="employmentBusy" :disabled="busy || !canBtn('internship.employment.view')" @click="goEmployment">衔接就业</AppButton>
              </template>
            </div>
            <p v-if="!panel.data.archived" class="hint">归档后可生成档案包，留存冻结的材料清单与扫描件。</p>
            <p v-else class="hint">“恢复校验”只核对包内行数、文件数与 SHA-256，不会覆盖当前业务数据。</p>

            <details v-if="panel.data.latestPackage || pkgFile" class="tech-details">
              <summary>展开技术证据</summary>
              <dl>
                <div><dt>Package ID</dt><dd>{{ (pkgFile || panel.data.latestPackage).packageId }}</dd></div>
                <div><dt>文件数 / 行数</dt><dd>{{ (pkgFile || panel.data.latestPackage).fileCount }} / {{ (pkgFile || panel.data.latestPackage).rowCount }}</dd></div>
                <div><dt>SHA-256</dt><dd>{{ (pkgFile || panel.data.latestPackage).sha256 }}</dd></div>
              </dl>
            </details>

            <div class="sec-t">处理记录</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无归档记录" />
          </template>
        </div>
      </template>
    </template>

    <!-- 按批次 / 按企业 -->
    <template v-else>
      <div v-if="error" class="state is-err" role="alert">{{ error }} <AppButton variant="ghost" @click="load">重试</AppButton></div>
      <div v-if="tab === 'batch' && !error" class="bar batch-package-bar">
        <div>
          <strong>批次归档包</strong>
          <span>仅当当前数据范围内全部学生已归档时生成；每片最多 20 人，逐片保留独立回执。</span>
        </div>
        <AppPermissionButton code="internship.archive.package" :allowed="canBtn('internship.archive.package')"
          variant="secondary" size="sm" :loading="batchPkgBusy" :disabled="busy || loading || !!error" @click="buildBatchPackage">
          {{ batchPackage?.hasMore ? '生成下一分片' : '生成批次归档包' }}
        </AppPermissionButton>
        <AppButton v-if="batchPackage" variant="ghost" size="sm" :loading="batchPkgBusy" :disabled="busy || !canBtn('internship.archive.package')" @click="downloadBatchPackage">下载当前分片</AppButton>
        <AppButton v-if="batchPackage" variant="ghost" size="sm" :loading="batchRestoreBusy" :disabled="busy || !canBtn('internship.archive.package')" @click="verifyBatchRestore">恢复校验</AppButton>
      </div>
      <p v-if="!error" class="hint">汇总使用已提交归档快照；待预检学生尚未计入材料完整人数。</p>
      <DataTable v-if="!error" :columns="aggColumns" :rows="aggRows" row-key="group" :loading="loading">
        <template #cell-avgCompleteness="{ row }">{{ row.avgCompleteness }}%</template>
        <template #cell-archiveRate="{ row }">{{ row.archiveRate }}%</template>
      </DataTable>
      <div v-if="!error && !loading && !aggRows.length" class="state">当前批次暂无归档汇总</div>
    </template>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="撤销原因" :submitting="cd.submitting" :confirm-disabled="actionConflict || panel.loading || !!panel.error" @confirm="onConfirm">
      <div v-if="actionError" class="is-err" role="alert">{{ actionError }}</div>
      <AppButton v-if="actionConflict" variant="ghost" :disabled="panel.loading || !!panel.error" @click="acknowledgeLatest">已核对最新状态，关闭本次确认</AppButton>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton,
  AppDescriptionList, AppAuditTrail, AppSearchBox } from '@/components/common'
import ActionReceipt from './components/ActionReceipt.vue'
import { archiveApi } from '@/modules/internship/api/archive.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const STUDENT_COLUMNS = [
  { key: 'studentName', title: '学生', width: '175px' },
  { key: 'advisorName', title: '指导教师' }, { key: 'enterpriseName', title: '企业' },
  { key: 'completeness', title: '完整度', width: '150px' }, { key: 'missing', title: '缺失材料' },
  { key: 'archived', title: '归档' }, { key: 'actions', title: '操作', width: '120px' }
]

export default {
  name: 'ArchiveView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppConfirmDialog,
    AppExportButton, AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox,
    ActionReceipt },
  data() {
    return {
      tab: 'student', panelMode: '', listSeq: 0, detailSeq: 0, viewEpoch: 0, requestKey: '',
      actionError: '', actionConflict: false, keptReason: '', removeRouteGuard: null,
      tabs: [{ key: 'student', label: '按学生' }, { key: 'batch', label: '按批次' }, { key: 'enterprise', label: '按企业' }],
      studentColumns: STUDENT_COLUMNS,
      rows: [], total: 0, page: 1, pageSize: 20, aggRows: [], loading: false, error: '',
      keyword: '', onlyIncomplete: false,
      // 选中行完整性工作区（替代原居中 modal）
      panel: { visible: false, rowId: '', loading: false, error: '', data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      pkgBusy: false,
      pkgFile: null,
      preflightBusy: false,
      restoreBusy: false,
      batchPkgBusy: false,
      batchRestoreBusy: false,
      batchPackage: null,
      employmentBusy: false,
      lastReceipt: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    aggColumns() {
      return [
        { key: 'group', title: this.tab === 'batch' ? '批次' : '企业' },
        { key: 'total', title: '实习人数' }, { key: 'complete', title: '材料完整' },
        { key: 'avgCompleteness', title: '平均完整度' }, { key: 'archived', title: '已归档' },
        { key: 'archiveRate', title: '归档率' }
      ]
    },
    panelStudentLabel() {
      const d = this.panel.data
      if (d) return `${d.studentName}（${d.studentNo}）`
      const r = this.rows.find((x) => x.id === this.panel.rowId)
      return r ? `${r.studentName}（${r.studentNo}）` : ''
    },
    detailItems() {
      const d = this.panel.data || {}
      return [
        { label: '学生', value: `${d.studentName || '-'}（${d.studentNo || '-'}）` },
        { label: '完整度', value: `${d.completeness ?? 0}%` },
        { label: '指导教师', value: d.advisorName || '—' },
        { label: '企业', value: d.enterpriseName || '—' },
        { label: '归档时间', value: d.archived ? (d.archivedAt || '—') : '未归档' }
      ]
    },
    auditRecords() {
      return (this.panel.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actionLabel: ({ ARCHIVE_PREFLIGHT: '归档预检', ARCHIVE: '完成归档', ARCHIVE_REVOKE: '撤销归档', REVOKE: '撤销归档', BUILD_PACKAGE: '生成档案包' })[t.action] || t.action, actor: t.operator,
        reason: t.detail && (t.detail.reason || t.detail.note || ''), at: t.occurredAt
      }))
    },
    scopeKey() { return JSON.stringify([this.viewEpoch, String(this.batchStore.selectedBatchId || '')]) },
    workspaceKey() { return `${this.scopeKey}:${this.panel.rowId}` },
    listKey() { return JSON.stringify([this.scopeKey, this.tab, this.keyword, this.onlyIncomplete, this.page]) },
    busy() { return this.cd.submitting || this.preflightBusy || this.pkgBusy || this.restoreBusy || this.batchPkgBusy || this.batchRestoreBusy || this.employmentBusy }
  },
  created() { this.restoreQuery(); this.load(); this.syncDetail() },
  mounted() {
    this.removeRouteGuard = this.$router.beforeEach((to, from) => to.fullPath === from.fullPath || !this.busy)
  },
  beforeUnmount() { this.viewEpoch++; this.listSeq++; this.resetPanel(); this.removeRouteGuard?.() },
  watch: {
    '$route.query'() { this.restoreQuery(); if (this.requestKey !== this.listKey) this.load(); this.syncDetail() },
    'batchStore.selectedBatchId'(next, previous) {
      this.viewEpoch++; this.resetPanel(); this.batchPackage = null; this.lastReceipt = null
      if (previous && String(next) !== String(previous)) {
        this.keyword = ''; this.page = 1
        this.navigate({ id: undefined, keyword: undefined, page: '1' }, true)
      } else this.restoreQuery()
      this.load(); this.syncDetail()
    },
    ctx: { deep: true, handler() { this.viewEpoch++; this.resetPanel(); this.batchPackage = null; this.lastReceipt = null; this.load(); this.syncDetail() } }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    goMaterials() { if (!this.busy) this.$router.push({ path: '/admin/internship/material-center', query: this.batchStore.withBatchQuery({ id: this.panel.data ? this.panel.rowId : undefined, keyword: this.keyword || undefined }) }) },
    goStats() { this.$router.push({ path: '/admin/internship/stats', query: this.batchStore.withBatchQuery() }) },
    async exportFn() {
      if (!this.batchStore.selectedBatchId) return { code: 1, message: '请先选择批次' }
      if (!this.canBtn('internship.archive.package')) return { code: 1, message: '无归档台账导出权限' }
      const key = this.scopeKey
      const res = await archiveApi.exportArchives({ keyword: this.tab === 'student' ? this.keyword : undefined, batchId: this.batchStore.selectedBatchId })
      return key === this.scopeKey ? res : { code: 1, message: '范围已切换，请重新导出' }
    },
    navigate(extra, replace = false) {
      if (this.busy) return
      return this.$router[replace ? 'replace' : 'push']({ path: '/admin/internship/archive', query: this.batchStore.withBatchQuery({ ...this.$route.query, ...extra }) })
    },
    restoreQuery() {
      const q = this.$route.query
      this.panelMode = q.panel === 'materials' ? 'materials' : ''
      this.tab = ['batch', 'enterprise'].includes(q.view) ? q.view : 'student'
      this.keyword = typeof q.keyword === 'string' ? q.keyword : ''
      this.onlyIncomplete = q.pending === '1' || (q.pending == null && this.panelMode === 'materials')
      this.page = /^[1-9]\d*$/.test(String(q.page || '')) ? Math.min(Number(q.page), 1000000) : 1
    },
    syncDetail() {
      const id = this.tab === 'student' && typeof this.$route.query.id === 'string' ? this.$route.query.id : ''
      if (id && (!this.panel.visible || this.panel.rowId !== id)) this.openDetailById(id)
      else if (!id && this.panel.visible) this.resetPanel()
    },
    clearMaterialEntry() { this.navigate({ panel: undefined, pending: undefined, view: 'student', page: '1' }) },
    switchTab(key) { this.navigate({ view: key, id: undefined, panel: undefined, page: '1' }) },
    reload() { this.navigate({ keyword: this.keyword, pending: this.onlyIncomplete ? '1' : '0', page: '1', id: undefined }); this.page = 1; this.load() },
    onPageChange(page) { this.navigate({ page: String(page), id: undefined }) },
    async load() {
      const seq = ++this.listSeq, key = this.listKey
      this.requestKey = key; this.rows = []; this.aggRows = []; this.total = 0; this.loading = false; this.error = ''
      if (!this.batchStore.selectedBatchId) { this.error = '请先选择批次'; return }
      if (!this.canBtn('internship.archive.view')) { this.error = '无归档查看权限'; return }
      this.loading = true
      const params = { batchId: this.batchStore.selectedBatchId }
      const res = this.tab === 'student'
        ? await archiveApi.getByStudent({ ...params, page: this.page, pageSize: this.pageSize, keyword: this.keyword, onlyPending: this.onlyIncomplete })
        : this.tab === 'batch' ? await archiveApi.byBatch(params) : await archiveApi.byEnterprise(params)
      if (seq !== this.listSeq || key !== this.listKey) return
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; return }
      if (this.tab === 'student') { this.rows = res.data.list || []; this.total = res.data.total }
      else this.aggRows = res.data || []
    },
    syncQueryId(id) {
      if (String(this.$route.query.id || '') !== id) this.navigate({ id: id || undefined }, true)
    },
    resetPanel() {
      this.detailSeq++
      this.panel = { visible: false, rowId: '', loading: false, error: '', data: null }
      this.pkgFile = null; this.pending = null; this.cd.visible = false; this.cd.submitting = false
      this.actionError = ''; this.actionConflict = false; this.keptReason = ''
      this.preflightBusy = false; this.pkgBusy = false; this.restoreBusy = false; this.employmentBusy = false
      this.batchPkgBusy = false; this.batchRestoreBusy = false
    },
    closePanel() { this.navigate({ id: undefined }) },
    openDetail(row) { this.navigate({ id: String(row.id) }) },
    async openDetailById(id) {
      id = String(id)
      if (this.busy) return
      if (this.panel.rowId !== id) this.resetPanel()
      const seq = ++this.detailSeq, batchId = this.batchStore.selectedBatchId
      this.panel = { visible: true, rowId: id, loading: true, error: '', data: null }; this.pkgFile = null
      const key = this.workspaceKey
      this.syncQueryId(id)
      if (!batchId || !this.canBtn('internship.archive.view')) { this.panel.loading = false; this.panel.error = '请先选择有权查看的实习批次'; return }
      const res = await archiveApi.getDetail(id)
      if (seq !== this.detailSeq || key !== this.workspaceKey) return
      if (res.code !== 0) { this.panel.loading = false; this.panel.error = res.message || '归档详情加载失败'; return }
      // 旧详情合同没有批次信息，用当前批次有界台账确认对象归属。
      let inBatch = this.rows.some(row => String(row.id) === id)
      if (!inBatch && res.data.studentNo) {
        const proof = await archiveApi.getByStudent({ batchId, keyword: res.data.studentNo, page: 1, pageSize: 20 })
        if (seq !== this.detailSeq || key !== this.workspaceKey) return
        inBatch = proof.code === 0 && proof.data.list.some(row => String(row.id) === id)
      }
      this.panel.loading = false
      if (!inBatch || String(res.data.id) !== id) { this.panel.error = '无法确认该学生属于当前批次，请返回归档台账重新定位'; return }
      this.panel.data = res.data; this.pkgFile = res.data.latestPackage || null
      this.$nextTick?.(() => { const heading = this.$el?.querySelector('#archive-workspace-title'); heading?.focus({ preventScroll: true }); heading?.scrollIntoView({ block: 'start' }) })
    },
    goFix(item) {
      if (this.busy || !this.panel.data || !item?.path?.startsWith('/admin/internship/')) return
      const target = new URL(item.path, 'http://local.invalid')
      const pathMap = { '/admin/internship/insurances': '/admin/internship/insurance', '/admin/internship/process-reports': '/admin/internship/reports', '/admin/internship/visits': '/admin/internship/guidance' }
      let path = pathMap[target.pathname] || target.pathname
      const query = Object.fromEntries(target.searchParams)
      // 补项链接里的 id 是实习记录编号，不能用作协议、成绩或评价单编号。
      delete query.id
      if (path === '/admin/internship/evaluations') { path = item.code === 'enterpriseEval' ? '/admin/internship/enterprise-evals' : '/admin/internship/student-evals'; delete query.stage }
      if (path === '/admin/internship/agreements') { query.panel = 'audit-ledger'; query.status = ''; query.returnTo = this.$route.fullPath }
      if (path === '/admin/internship/compliance') {
        query.id = this.panel.rowId
        const tabs = { consent: 'consents', safety: 'safety', special: 'filings', emergency: 'incidents' }
        query.tab = tabs[query.panel] || 'overview'; delete query.panel
      } else if (path === '/admin/internship/enterprises') query.keyword = this.panel.data.enterpriseName || undefined
      else if (path !== '/admin/internship/positions') query.keyword = this.panel.data.studentName
      if (item.code === 'visit') query.view = 'visit'
      this.$router.push({ path, query: this.batchStore.withBatchQuery(query) })
    },
    acknowledgeLatest() {
      if (this.panel.loading || this.panel.error || !this.panel.data) return
      this.cd.visible = false; this.pending = null; this.actionConflict = false; this.actionError = ''
    },
    async runPreflight(r) {
      const id = String(r?.id || this.panel.data?.id || '')
      if (!id || id !== this.panel.rowId || !this.panel.data || this.busy || this.cd.visible || !this.canBtn('internship.archive.view')) return null
      const key = this.workspaceKey; this.actionError = ''
      this.preflightBusy = true
      const res = await archiveApi.preflight(id)
      if (key !== this.workspaceKey) return null
      this.preflightBusy = false
      if (res.code !== 0) {
        this.actionError = res.message || '归档预检失败'
        toast.error(this.actionError)
        return null
      }
      const data = { ...(this.panel.data || {}), ...res.data }
      this.panel.data = data
      this.pkgFile = data.latestPackage || this.pkgFile
      this.syncQueryId(id)
      this.lastReceipt = {
        actionLabel: '归档预检', objectLabel: `${data.studentName} · ${data.canArchive ? '可以归档' : '仍有归档阻断'}`,
        id, version: data.recordVersion,
        status: data.preflightReceipt?.status,
        statusLabel: data.canArchive ? '预检通过' : '预检阻断',
        auditText: `规则 ${data.ruleVersion} · FileVersion ${data.fileVersionSafety?.ready || 0}/${data.fileVersionSafety?.total || 0} 安全可用`,
        nextStep: data.canArchive ? '确认后提交归档；服务端会再次核验' : '按“去哪补”逐项处理后重新预检'
      }
      return data
    },
    async doArchive(r) {
      if (this.busy || this.actionConflict || r?.archived || !this.canBtn('internship.archive.execute')) return
      const data = await this.runPreflight(r)
      if (!data) return
      if (!data.canArchive) {
        toast.warning('预检未通过，已展开缺项与办理入口；未执行归档')
        return
      }
      this.pending = {
        id: String(data.id), kind: 'archive', scopeKey: this.scopeKey,
        expectedVersion: data.version ?? data.recordVersion,
        recordExpectedVersion: data.recordVersion
      }
      this.cd = { visible: true, title: '确认归档学生',
        content: `「${data.studentName}」已通过业务与文件安全预检。确认冻结当前材料版本、归档清单与已发布正式成绩？`,
        danger: false, confirmText: '确认归档', requireReason: false, submitting: false }
    },
    doRevoke(r) {
      if (this.busy || this.cd.visible || this.actionConflict || !r?.archived || !this.canBtn('internship.archive.revoke') || r.version == null || r.recordVersion == null) return
      this.actionError = ''
      this.pending = {
        id: String(r.id), kind: 'revoke', scopeKey: this.scopeKey, expectedVersion: r.version,
        recordExpectedVersion: r.recordVersion
      }
      this.cd = { visible: true, title: '撤销归档', content: `撤销「${r.studentName}」的归档，原因将写审计。`,
        danger: true, confirmText: '撤销归档', requireReason: true, submitting: false }
    },
    async onConfirm({ reason = '' }) {
      const p = this.pending, data = this.panel.data
      if (!p || !data || !this.cd.visible || this.busy || this.actionConflict || this.panel.error || p.scopeKey !== this.scopeKey || String(p.id) !== this.panel.rowId) return
      const code = p.kind === 'archive' ? 'internship.archive.execute' : 'internship.archive.revoke'
      if (!this.canBtn(code) || p.expectedVersion == null || p.recordExpectedVersion == null) return
      if ((p.kind === 'archive' && data.archived) || (p.kind === 'revoke' && !data.archived)) { this.actionConflict = true; this.actionError = '归档状态已改变，请核对最新结果'; return }
      if (p.recordExpectedVersion !== data.recordVersion || p.expectedVersion !== (data.version ?? data.recordVersion)) { this.actionError = '记录版本已改变，请重新核对'; this.actionConflict = true; return }
      reason = reason.trim()
      if (p.kind === 'revoke' && reason.length < 5) { this.actionError = '请填写至少 5 字的撤销原因'; return }
      const key = this.workspaceKey; this.keptReason = reason; this.actionError = ''
      this.cd.submitting = true
      const res = p.kind === 'archive'
        ? await archiveApi.archive(p.id, {
            force: false, expectedVersion: p.expectedVersion,
            recordExpectedVersion: p.recordExpectedVersion
          })
        : await archiveApi.revoke(p.id, {
            reason, expectedVersion: p.expectedVersion,
            recordExpectedVersion: p.recordExpectedVersion
          })
      if (key !== this.workspaceKey || p !== this.pending) return
      this.cd.submitting = false
      if (res.code !== 0) {
        this.actionConflict = true; this.actionError = res.message || '操作结果待核对，请勿重复提交'
        this.lastReceipt = {
          actionLabel: p.kind === 'archive' ? '归档未提交' : '撤销未提交',
          objectLabel: '服务端未确认写入成功', id: p.id, status: 'UNKNOWN',
          statusLabel: '请核对当前状态', auditText: res.message || '请求失败',
          nextStep: '已保留确认内容并重新读取服务端；请勿盲目重复提交'
        }
        toast.error(res.message || '操作失败；已重新读取服务端状态')
        await this.openDetailById(p.id)
        return
      }
      const receipt = res.data?.operationReceipt || {}
      this.lastReceipt = {
        actionLabel: p.kind === 'archive' ? '归档完成' : '撤销归档完成',
        objectLabel: p.kind === 'archive' ? '业务归档与 Manifest 已原子提交' : '归档、Manifest 与档案包已原子失效',
        id: p.id, version: receipt.recordVersion ?? res.data?.recordVersion,
        status: receipt.status || 'COMMITTED', statusLabel: '已提交',
        auditText: p.kind === 'archive'
          ? `Manifest r${receipt.manifestRevision} · ${receipt.fileVersionCount} 个文件版本`
          : `失效档案包 ${receipt.invalidatedPackageCount || 0} 个、Manifest ${receipt.revokedManifestCount || 0} 个`,
        nextStep: p.kind === 'archive' ? '可生成单生归档包并执行恢复校验' : '修正材料后重新预检'
      }
      this.cd.visible = false; this.pending = null; this.keptReason = ''; toast.success('操作成功，已写审计')
      await this.load()
      if (key !== this.workspaceKey) return
      // 工作区正在核验该行时，动作后刷新材料清单与留痕
      if (this.panel.visible && String(this.panel.rowId) === String(p.id)) this.openDetailById(p.id)
    },
    async buildPackage() {
      const id = this.panel.data?.id
      if (!id || !this.panel.data.archived || this.busy || !this.canBtn('internship.archive.package')) return
      const key = this.workspaceKey
      this.pkgBusy = true
      const res = await archiveApi.buildPackage(id)
      if (key !== this.workspaceKey) return
      this.pkgBusy = false
      if (res.code !== 0) return toast.error(res.message || '生成失败')
      this.pkgFile = res.data
      this.panel.data = { ...this.panel.data, packageReady: true, latestPackage: res.data }
      const receipt = res.data?.operationReceipt || {}
      this.lastReceipt = {
        actionLabel: '归档包生成', objectLabel: `${res.data.fileName} · ${res.data.fileCount || receipt.fileCount || 0} 个文件`,
        id: receipt.packageId || res.data.packageId, version: receipt.packageVersion || res.data.packageVersion,
        status: receipt.status || 'COMMITTED', statusLabel: '档案包就绪',
        auditText: `Manifest r${res.data.manifestRevision} · SHA-256 ${res.data.sha256}`,
        nextStep: '下载留存，或执行恢复校验验证行数与哈希'
      }
      toast.success('归档包已生成，可下载')
      return res.data
    },
    async downloadPackage() {
      if (!this.panel.data?.archived || this.busy || !this.canBtn('internship.archive.package')) return
      const pkg = this.pkgFile || this.panel.data?.latestPackage
      if (!pkg?.packageId) return toast.warning('尚无可下载的档案包，请先生成')
      const key = this.workspaceKey
      this.pkgBusy = true
      try {
        await archiveApi.downloadPackage(pkg.packageId, pkg.fileName || '实习归档.zip')
      } catch (e) {
        if (key === this.workspaceKey) toast.error(e?.message || '下载失败')
      }
      if (key === this.workspaceKey) this.pkgBusy = false
    },
    async verifyRestore() {
      if (this.busy || !this.panel.data?.archived || !this.canBtn('internship.archive.package')) return
      const pkg = this.pkgFile || this.panel.data?.latestPackage
      if (!pkg?.packageId) return toast.warning('请先生成归档包')
      const key = this.workspaceKey
      this.restoreBusy = true
      const res = await archiveApi.verifyRestore(pkg.packageId)
      if (key !== this.workspaceKey) return
      this.restoreBusy = false
      if (res.code !== 0) return toast.error(res.message || '恢复校验失败')
      const receipt = res.data?.operationReceipt || {}
      this.lastReceipt = {
        actionLabel: '恢复校验', objectLabel: '档案包可用于受控恢复',
        id: receipt.packageId, version: res.data.packageVersion,
        status: receipt.status || 'VERIFIED', statusLabel: '行数与哈希一致',
        auditText: `${receipt.rowCount} 行 · ${receipt.fileCount} 个文件 · SHA-256 ${receipt.packageSha256}`,
        nextStep: '校验仅验证可恢复性，未覆盖当前业务数据'
      }
      toast.success('恢复校验通过，行数与哈希一致')
    },
    async buildBatchPackage() {
      if (this.busy || this.loading || this.error || !this.canBtn('internship.archive.package')) return
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) return toast.warning('请先选择批次')
      const key = this.scopeKey
      const afterId = this.batchPackage?.hasMore ? this.batchPackage.nextAfterId : 0
      this.batchPkgBusy = true
      const res = await archiveApi.buildBatchPackage(batchId, { afterId, limit: 20 })
      if (key !== this.scopeKey) return
      this.batchPkgBusy = false
      if (res.code !== 0) return toast.error(res.message || '批次归档包生成失败')
      this.batchPackage = res.data
      const receipt = res.data?.operationReceipt || {}
      this.lastReceipt = {
        actionLabel: '批次归档包生成', objectLabel: `${res.data.rowCount} 名学生 · ${res.data.fileCount} 个冻结文件版本`,
        id: receipt.packageId, version: receipt.packageVersion,
        status: receipt.status || 'COMMITTED', statusLabel: '当前分片就绪',
        auditText: `SHA-256 ${res.data.sha256}`,
        nextStep: res.data.hasMore ? '先下载并恢复校验当前分片，再生成下一分片' : '批次全部分片已生成，可下载留存并恢复校验'
      }
      toast.success(res.data.hasMore ? '当前分片已生成，批次仍有下一分片' : '批次归档包已生成完毕')
    },
    async downloadBatchPackage() {
      if (this.busy || !this.canBtn('internship.archive.package')) return
      const pkg = this.batchPackage
      if (!pkg?.packageId) return
      const key = this.scopeKey
      this.batchPkgBusy = true
      try {
        await archiveApi.downloadBatchPackage(pkg.packageId, pkg.fileName || '实习批次归档.zip')
      } catch (e) {
        if (key === this.scopeKey) toast.error(e?.message || '批次归档包下载失败')
      }
      if (key === this.scopeKey) this.batchPkgBusy = false
    },
    async verifyBatchRestore() {
      if (this.busy || !this.canBtn('internship.archive.package')) return
      const pkg = this.batchPackage
      if (!pkg?.packageId) return
      const key = this.scopeKey
      this.batchRestoreBusy = true
      const res = await archiveApi.verifyRestore(pkg.packageId)
      if (key !== this.scopeKey) return
      this.batchRestoreBusy = false
      if (res.code !== 0) return toast.error(res.message || '批次恢复校验失败')
      const receipt = res.data?.operationReceipt || {}
      this.lastReceipt = {
        actionLabel: '批次恢复校验', objectLabel: '当前批次分片可用于受控恢复',
        id: receipt.packageId, version: res.data.packageVersion,
        status: receipt.status || 'VERIFIED', statusLabel: '行数与哈希一致',
        auditText: `${receipt.rowCount} 行 · ${receipt.fileCount} 个文件 · SHA-256 ${receipt.packageSha256}`,
        nextStep: pkg.hasMore ? '可生成下一分片；校验未覆盖当前业务数据' : '全部分片均应分别留存校验回执'
      }
      toast.success('批次分片恢复校验通过')
    },
    async goEmployment() {
      const id = this.panel.data?.id
      if (!id || !this.panel.data.archived || this.busy || !this.canBtn('internship.employment.view')) return
      const key = this.workspaceKey
      this.employmentBusy = true
      const res = await archiveApi.employmentTransition(id)
      if (key !== this.workspaceKey) return
      this.employmentBusy = false
      if (res.code !== 0) return toast.error(res.message || '就业衔接校验失败')
      this.$router.push(res.data.employmentPath)
    }
  }
}
</script>

<style scoped>
.tabs { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-light); }
.material-entry { display: flex; align-items: center; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-3); padding: var(--space-3) var(--space-4); border: 1px solid var(--warning-200, #fde68a); border-radius: var(--radius-lg, 12px); background: var(--warning-50, #fffbeb); color: var(--warning-800, #92400e); }
.material-entry > div { display: flex; flex-direction: column; gap: 3px; font-size: var(--font-size-sm); }
.material-entry span { color: var(--text-secondary); font-size: var(--font-size-xs); }
.tabs__btn { border: none; background: none; padding: var(--space-2) var(--space-3); cursor: pointer; color: var(--text-secondary); font-size: var(--font-size-sm); border-bottom: 2px solid transparent; }
.tabs__btn.is-active { color: var(--primary-700); border-bottom-color: var(--primary-600); font-weight: var(--font-weight-medium); }
.bar { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); flex-wrap: wrap; }
.batch-package-bar { padding: var(--space-3); border: 1px solid var(--border-light); border-radius: var(--radius-md, 10px); }
.batch-package-bar > div { display: grid; flex: 1; min-width: 260px; gap: 3px; }
.batch-package-bar span { color: var(--text-secondary); font-size: var(--font-size-xs); }
.bar__hint { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: auto; }
.chk { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--text-secondary); }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.miss { color: var(--danger-600); font-size: var(--font-size-xs); }
.miss-cell { display: inline-flex; align-items: center; height: 20px; padding: 0 8px; border-radius: 10px; font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); background: var(--danger-50, #fef2f2); color: var(--danger-600, #dc2626); border: 1px solid var(--danger-100, #fecaca); white-space: nowrap; }
.is-current { color: var(--primary-600, #2563eb); font-weight: var(--font-weight-semibold); }
.pct { display: flex; align-items: center; gap: var(--space-1); }
.pct__bar { width: 60px; height: 8px; background: var(--bg-subtle); border-radius: var(--radius-sm); overflow: hidden; }
.pct__fill { display: block; height: 100%; background: var(--warning-500, #f59e0b); }
.pct__fill.is-full { background: var(--success-500, #22c55e); }
.ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.hint { margin-top: var(--space-2); font-size: var(--font-size-xs); color: var(--text-tertiary); }
.wsp { margin-top: var(--space-3); border: 1px solid var(--border-light, #e5e7eb); border-radius: var(--radius-lg, 12px); background: var(--bg-card, #fff); padding: var(--space-4); box-shadow: var(--shadow-sm); }
.wsp__head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-bottom: var(--space-3); }
.wsp__title { font-weight: var(--font-weight-semibold); }
.wsp__close { margin-left: auto; }
.wsp__ops { display: flex; gap: var(--space-2); flex-wrap: wrap; }
.mat-list { display: flex; flex-direction: column; gap: var(--space-1); }
.mat-row { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-sm); padding: var(--space-1) var(--space-2); border-radius: var(--radius-sm); background: var(--success-50, #f0fdf4); color: var(--success-700); }
.mat-row.is-miss { background: var(--danger-50, #fef2f2); color: var(--danger-600); }
.mat-row__dot { font-weight: bold; width: 14px; text-align: center; }
.mat-row__label { display: grid; flex: 1; gap: 2px; }
.mat-row__label small { color: var(--text-secondary); font-size: var(--font-size-xs); font-weight: normal; }
.ready-line, .preflight-line { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3); border: 1px solid var(--success-200, #a7f3d0); border-radius: var(--radius-md, 10px); background: var(--success-50, #ecfdf5); }
.ready-line > div, .preflight-line > div { display: grid; flex: 1; gap: 3px; }
.ready-line small, .preflight-line span { color: var(--text-secondary); font-size: var(--font-size-xs); }
.preflight-line { margin-top: var(--space-3); border-color: var(--border-light); background: var(--bg-card, #fff); }
.tech-details { margin-top: var(--space-3); padding: var(--space-3); border: 1px dashed var(--border-light); border-radius: var(--radius-md, 10px); color: var(--text-secondary); }
.tech-details summary { cursor: pointer; font-weight: var(--font-weight-semibold); }
.tech-details dl { display: grid; gap: var(--space-2); margin: var(--space-3) 0 0; }
.tech-details dl div { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: var(--space-2); }
.tech-details dd { overflow-wrap: anywhere; margin: 0; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.student-cell { display: grid; gap: 5px; }
:deep(.dt__table) { min-width: 880px; }
.student-cell strong { font-size: 14px; font-weight: 600; }
.student-cell span { color: var(--text-secondary); font-size: 12px; }
.bar { padding: 14px 16px; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); }
.tabs { gap: 4px; margin-bottom: 16px; }
.tabs__btn { padding: 12px 16px; }
.tabs__btn:focus-visible { outline: 2px solid var(--primary-500); outline-offset: 2px; }
.wsp { margin-top: 0; padding: 24px; box-shadow: none; }
.wsp__title { margin: 0; font-size: 19px; scroll-margin-top: 170px; }
.wsp__title:focus { outline: none; }
.wsp__head { padding-bottom: 18px; border-bottom: 1px solid var(--border-base); }
.next-step { display: flex; gap: 12px; flex-wrap: wrap; padding: 14px 0; font-size: 13px; line-height: 1.7; color: var(--text-secondary); }
.next-step strong { color: var(--text-primary); }
.sec-t { font-size: 15px; color: var(--text-primary); margin: 24px 0 12px; font-weight: 600; }
.mat-list { border: 1px solid var(--border-base); border-radius: 10px; overflow: hidden; gap: 0; }
.mat-row.is-miss { padding: 14px; border-radius: 0; background: var(--bg-card); color: var(--text-primary); border-bottom: 1px solid var(--border-base); }
.mat-row:last-child { border-bottom: 0; }
.mat-row__label { min-width: 0; gap: 6px; line-height: 1.6; }
.mat-row__label strong { font-weight: 550; }
.preflight-line { flex-wrap: wrap; }
.unsafe-files { display: grid; gap: 10px; margin-top: 12px; padding: 14px; background: var(--warning-50, #fffbeb); border-radius: 8px; }
.unsafe-files > div { display: grid; gap: 5px; font-size: 12px; overflow-wrap: anywhere; }
.unsafe-files span { color: var(--text-secondary); }
.material-checklist { margin: 16px 0; font-size: 13px; color: var(--text-secondary); }
.material-checklist summary { cursor: pointer; padding: 8px 0; }
.material-checklist > div { display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--border-base); padding: 10px 0; }
.wsp__ops { padding-bottom: 8px; gap: 10px; }
.state.is-err { display: flex; justify-content: center; align-items: center; gap: 12px; flex-wrap: wrap; }
.is-err { color: var(--danger-600, #b42318); }
@media (max-width: 720px) {
  .wsp { padding: 16px; }
  .wsp__title { font-size: 17px; }
  .mat-row { flex-wrap: wrap; align-items: start; }
  .mat-row__label { flex-basis: calc(100% - 90px); }
  .mat-row > :last-child { margin-left: auto; }
  .preflight-line > div { flex-basis: 100%; }
  .tech-details dl div { grid-template-columns: minmax(0, 1fr); }
}
</style>
