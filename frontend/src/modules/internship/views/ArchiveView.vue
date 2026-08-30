<template>
  <ModulePageShell title="实习归档" subtitle="检查实习材料是否齐全，完成学生归档并查看批次统计结果 · 材料完整性检查 · 缺失提醒 · 按学生/批次/企业归档"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="goStats">实习统计</AppButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />
    <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

    <div v-if="panelMode === 'materials'" class="material-entry">
      <div>
        <strong>学生材料核验</strong>
        <span>已自动筛选材料不完整的学生；展开“核验”可查看缺项、审计留痕并完成归档。</span>
      </div>
      <AppButton variant="ghost" size="sm" @click="clearMaterialEntry">查看全部归档台账</AppButton>
    </div>

    <div class="tabs" role="tablist" aria-label="归档视图">
      <button v-for="t in tabs" :id="`archive-tab-${t.key}`" :key="t.key" type="button" role="tab"
        :aria-selected="tab === t.key" class="tabs__btn" :class="{ 'is-active': tab === t.key }"
        @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <!-- 按学生 -->
    <template v-if="tab === 'student'">
      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <label class="chk"><input v-model="onlyIncomplete" type="checkbox" @change="reload" />仅看待预检 / 未归档</label>
        <span class="bar__hint">数据范围内可见</span>
      </div>
      <div v-if="error" class="state is-err" role="alert">{{ error }} <button type="button" @click="load">重试</button></div>
      <template v-else>
        <DataTable :columns="studentColumns" :rows="rows" row-key="id" :loading="loading"
          :pagination="pagination" row-clickable @row-click="openDetail" @page-change="onPageChange">
          <template #cell-studentName="{ row }">
            <span :class="{ 'is-current': row.id === panel.rowId }">{{ row.studentName }}</span>
          </template>
          <template #cell-completeness="{ row }">
            <span v-if="row.readinessKnown" class="pct"><span class="pct__bar"><span class="pct__fill" :class="{ 'is-full': row.completeness >= 100 }" :style="{ width: row.completeness + '%' }"></span></span>{{ row.completeness }}%</span>
            <span v-else class="bar__hint">打开核验后计算</span>
          </template>
          <template #cell-missing="{ row }">
            <AppStatusTag v-if="!row.readinessKnown" type="default" size="sm">待预检</AppStatusTag>
            <AppStatusTag v-else-if="!row.missing.length" type="success" size="sm">齐全</AppStatusTag>
            <span v-else class="miss">{{ row.missing.join('、') }}</span>
          </template>
          <template #cell-archived="{ row }">
            <AppStatusTag :type="row.archived ? 'success' : 'default'">{{ row.archived ? '已归档' : '未归档' }}</AppStatusTag>
          </template>
          <template #cell-actions="{ row }">
            <div class="ops">
              <AppButton variant="ghost" size="sm" @click="openDetail(row)">核验</AppButton>
              <AppPermissionButton v-if="!row.archived" code="internship.archive.execute" :allowed="canBtn('internship.archive.execute')" variant="secondary" size="sm" @click="doArchive(row)">预检并归档</AppPermissionButton>
              <AppPermissionButton v-else code="internship.archive.manage" :allowed="canBtn('internship.archive.manage')" variant="ghost" size="sm" :danger="true" @click="doRevoke(row)">撤销归档</AppPermissionButton>
            </div>
          </template>
        </DataTable>

        <!-- 选中行完整性工作区（替代原「归档材料清单」居中弹窗） -->
        <div v-if="panel.visible" class="wsp" role="region" aria-labelledby="archive-workspace-title" aria-live="polite">
          <div class="wsp__head">
            <span id="archive-workspace-title" class="wsp__title">归档完整性核验{{ panelStudentLabel ? ' · ' + panelStudentLabel : '' }}</span>
            <template v-if="panel.data">
              <AppStatusTag :type="panel.data.archived ? 'success' : 'default'">{{ panel.data.archived ? '已归档' : '未归档' }}</AppStatusTag>
              <span v-if="panel.data.missing.length" class="miss-cell">缺 {{ panel.data.missing.length }} 项</span>
              <AppStatusTag v-else type="success" size="sm">材料齐全</AppStatusTag>
            </template>
            <AppButton class="wsp__close" variant="ghost" size="sm" @click="closePanel">收起</AppButton>
          </div>
          <div v-if="panel.loading" class="state">加载中…</div>
          <template v-else-if="panel.data">
            <AppDescriptionList :items="detailItems" :columns="2" />

            <div class="sec-t">① 缺什么 / 去哪补</div>
            <div v-if="panel.data.missingActions?.length" class="mat-list">
              <div v-for="m in panel.data.missingActions" :key="m.code" class="mat-row is-miss">
                <span class="mat-row__dot">!</span>
                <span class="mat-row__label"><strong>{{ m.label }}</strong><small>{{ m.reason || '尚未满足归档规则' }}</small></span>
                <AppButton variant="ghost" size="sm" @click="goFix(m)">{{ m.actionLabel }}</AppButton>
              </div>
            </div>
            <div v-else class="ready-line"><span>✓</span><div><strong>业务材料已满足归档规则</strong><small>提交前仍会重新核验文件安全状态与正式成绩版本</small></div></div>

            <div class="preflight-line">
              <div>
                <strong>文件安全预检</strong>
                <span v-if="panel.data.fileVersionSafety">{{ panel.data.fileVersionSafety.ready }}/{{ panel.data.fileVersionSafety.total }} 个当前版本安全可用</span>
                <span v-else>提交前由服务端同步 FileVersion 并核验扫描状态</span>
              </div>
              <AppStatusTag v-if="panel.data.fileVersionSafety" :type="panel.data.fileVersionSafety.unsafe ? 'danger' : 'success'" size="sm">
                {{ panel.data.fileVersionSafety.unsafe ? `阻断 ${panel.data.fileVersionSafety.unsafe} 项` : '安全门通过' }}
              </AppStatusTag>
              <AppButton variant="secondary" size="sm" :loading="preflightBusy" @click="runPreflight(panel.data)">重新预检</AppButton>
            </div>

            <div class="sec-t">② 归档状态与操作</div>
            <div class="wsp__ops">
              <AppPermissionButton v-if="!panel.data.archived" code="internship.archive.execute" :allowed="canBtn('internship.archive.execute')"
                variant="secondary" size="sm" :loading="preflightBusy" @click="doArchive(panel.data)">预检并提交归档</AppPermissionButton>
              <AppPermissionButton v-else code="internship.archive.manage" :allowed="canBtn('internship.archive.manage')" variant="ghost" size="sm"
                :danger="true" @click="doRevoke(panel.data)">撤销归档</AppPermissionButton>
              <template v-if="panel.data.archived">
                <AppPermissionButton v-if="!panel.data.packageReady" code="internship.archive.package" :allowed="canBtn('internship.archive.package')"
                  variant="secondary" size="sm" :loading="pkgBusy" @click="buildPackage">生成归档包</AppPermissionButton>
                <AppButton v-else variant="secondary" size="sm" :loading="pkgBusy" @click="downloadPackage">下载归档包 (zip)</AppButton>
                <AppButton v-if="panel.data.latestPackage || pkgFile" variant="ghost" size="sm" :loading="restoreBusy" @click="verifyRestore">恢复校验</AppButton>
                <AppButton variant="ghost" size="sm" :loading="employmentBusy" @click="goEmployment">衔接就业</AppButton>
              </template>
            </div>
            <p v-if="!panel.data.archived" class="hint">归档包需在「已归档」后生成；含 manifest + 材料清单 + 已有扫描件。</p>
            <p v-else class="hint">“恢复校验”只核对包内行数、文件数与 SHA-256，不会覆盖当前业务数据。</p>

            <details v-if="panel.data.latestPackage || pkgFile" class="tech-details">
              <summary>展开技术证据</summary>
              <dl>
                <div><dt>Package ID</dt><dd>{{ (pkgFile || panel.data.latestPackage).packageId }}</dd></div>
                <div><dt>文件数 / 行数</dt><dd>{{ (pkgFile || panel.data.latestPackage).fileCount }} / {{ (pkgFile || panel.data.latestPackage).rowCount }}</dd></div>
                <div><dt>SHA-256</dt><dd>{{ (pkgFile || panel.data.latestPackage).sha256 }}</dd></div>
              </dl>
            </details>

            <div class="sec-t">③ 归档留痕</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无归档记录" />
          </template>
        </div>
      </template>
    </template>

    <!-- 按批次 / 按企业 -->
    <template v-else>
      <div v-if="tab === 'batch'" class="bar batch-package-bar">
        <div>
          <strong>批次归档包</strong>
          <span>仅当当前数据范围内全部学生已归档时生成；每片最多 20 人，逐片保留独立回执。</span>
        </div>
        <AppPermissionButton code="internship.archive.package" :allowed="canBtn('internship.archive.package')"
          variant="secondary" size="sm" :loading="batchPkgBusy" @click="buildBatchPackage">
          {{ batchPackage?.hasMore ? '生成下一分片' : '生成批次归档包' }}
        </AppPermissionButton>
        <AppButton v-if="batchPackage" variant="ghost" size="sm" :loading="batchPkgBusy" @click="downloadBatchPackage">下载当前分片</AppButton>
        <AppButton v-if="batchPackage" variant="ghost" size="sm" :loading="batchRestoreBusy" @click="verifyBatchRestore">恢复校验</AppButton>
      </div>
      <DataTable :columns="aggColumns" :rows="aggRows" row-key="group" :loading="loading">
        <template #cell-avgCompleteness="{ row }">{{ row.avgCompleteness }}%</template>
        <template #cell-archiveRate="{ row }">{{ row.archiveRate }}%</template>
      </DataTable>
    </template>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="原因" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton,
  AppDescriptionList, AppAuditTrail, AppSearchBox } from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import ActionReceipt from './components/ActionReceipt.vue'
import { archiveApi } from '@/modules/internship/api/archive.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const STUDENT_COLUMNS = [
  { key: 'studentNo', title: '学号', width: '110px' }, { key: 'studentName', title: '姓名' },
  { key: 'advisorName', title: '指导教师' }, { key: 'enterpriseName', title: '企业' },
  { key: 'completeness', title: '完整度', width: '150px' }, { key: 'missing', title: '缺失材料' },
  { key: 'archived', title: '归档' }, { key: 'actions', title: '操作', width: '200px' }
]

export default {
  name: 'ArchiveView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, DataTable, AppButton, AppStatusTag, AppConfirmDialog,
    AppExportButton, AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox,
    ModuleSummaryStrip, ActionReceipt },
  data() {
    return {
      tab: 'student', panelMode: '',
      tabs: [{ key: 'student', label: '按学生' }, { key: 'batch', label: '按批次' }, { key: 'enterprise', label: '按企业' }],
      studentColumns: STUDENT_COLUMNS,
      rows: [], total: 0, page: 1, pageSize: 20, aggRows: [], loading: false, error: '',
      archiveStudentTotal: null,
      keyword: '', onlyIncomplete: false,
      // 选中行完整性工作区（替代原居中 modal）
      panel: { visible: false, rowId: '', loading: false, data: null },
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
        id: i, action: t.action, actor: t.operator,
        reason: t.detail && (t.detail.reason || t.detail.note || ''), at: t.occurredAt
      }))
    },
    summaryMetrics() {
      // 仅用「按学生」Tab 未筛选时的服务端 total；接口未返回缺失/已归档聚合数，不伪造
      if (this.loading || this.error) return []
      if (this.archiveStudentTotal == null) return []
      return [{ label: '应归档学生', value: this.archiveStudentTotal }]
    }
  },
  created() {
    this.applyRoutePanel(this.$route.query.panel)
    this.load()
    // 刷新恢复：route query.id 直接回到选中行工作区
    const qid = this.$route.query.id
    if (qid) this.openDetailById(String(qid))
  },
  watch: {
    '$route.query.panel'(value) {
      if (this.applyRoutePanel(value)) this.reload()
    },
    'batchStore.selectedBatchId'() {
      this.page = 1
      this.closePanel()
      this.batchPackage = null
      this.load()
    }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    goStats() { this.$router.push({ path: '/admin/internship/stats', query: this.batchStore.withBatchQuery() }) },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      return archiveApi.exportArchives({ keyword: this.keyword, batchId: this.batchStore.selectedBatchId })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    applyRoutePanel(value) {
      const next = value === 'materials' ? 'materials' : ''
      const changed = next !== this.panelMode
      this.panelMode = next
      if (next === 'materials') {
        this.tab = 'student'
        this.onlyIncomplete = true
        this.keyword = ''
      }
      return changed
    },
    clearMaterialEntry() {
      const query = { ...this.$route.query }
      delete query.panel
      this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
    },
    switchTab(k) { this.panelMode = ''; this.tab = k; this.page = 1; this.closePanel(); this.load() },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.aggRows = []; this.total = 0
        return
      }
      this.loading = true; this.error = ''
      if (this.tab === 'student') {
        const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
        if (this.onlyIncomplete) params.onlyPending = true
        const res = await archiveApi.getByStudent(params)
        this.loading = false
        if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
        this.rows = res.data.list; this.total = res.data.total
        // 无筛选时缓存服务端全量应归档人数，避免把筛选后小计当全量
        if (!this.keyword && !this.onlyIncomplete) this.archiveStudentTotal = res.data.total
      } else {
        const params = { batchId: this.batchStore.selectedBatchId }
        const res = this.tab === 'batch' ? await archiveApi.byBatch(params) : await archiveApi.byEnterprise(params)
        this.loading = false
        if (res.code !== 0) { this.error = res.message || '加载失败'; this.aggRows = []; return }
        this.aggRows = res.data || []
      }
    },
    syncQueryId(id) {
      const cur = String(this.$route.query.id ?? '')
      if (cur === (id || '')) return
      const query = { ...this.$route.query }
      if (id) query.id = id
      else delete query.id
      this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
    },
    closePanel() {
      this.panel = { visible: false, rowId: '', loading: false, data: null }
      this.pkgFile = null
      this.syncQueryId('')
    },
    openDetail(r) { this.openDetailById(r.id) },
    async openDetailById(id) {
      id = String(id)
      this.panel = { visible: true, rowId: id, loading: true, data: null }
      this.pkgFile = null
      this.syncQueryId(id)
      const res = await archiveApi.getDetail(id)
      if (!this.panel.visible || this.panel.rowId !== id) return
      this.panel.loading = false
      if (res.code !== 0) { toast.error(res.message || '加载失败'); this.closePanel(); return }
      this.panel.data = res.data
    },
    goFix(item) {
      if (item?.path) this.$router.push(item.path)
    },
    async runPreflight(r) {
      const id = String(r?.id || this.panel.data?.id || '')
      if (!id) return null
      this.preflightBusy = true
      const res = await archiveApi.preflight(id)
      this.preflightBusy = false
      if (res.code !== 0) {
        toast.error(res.message || '归档预检失败')
        return null
      }
      const data = { ...(this.panel.data || {}), ...res.data }
      this.panel = { visible: true, rowId: id, loading: false, data }
      this.pkgFile = data.latestPackage || this.pkgFile
      this.syncQueryId(id)
      this.lastReceipt = {
        actionLabel: '归档预检', objectLabel: `${data.studentName} · ${data.canArchive ? '可以归档' : `仍缺 ${data.missingActions?.length || 0} 项`}`,
        id, version: data.recordVersion,
        status: data.preflightReceipt?.status,
        statusLabel: data.canArchive ? '预检通过' : '预检阻断',
        auditText: `规则 ${data.ruleVersion} · FileVersion ${data.fileVersionSafety?.ready || 0}/${data.fileVersionSafety?.total || 0} 安全可用`,
        nextStep: data.canArchive ? '确认后提交归档；服务端会再次核验' : '按“去哪补”逐项处理后重新预检'
      }
      return data
    },
    async doArchive(r) {
      const data = await this.runPreflight(r)
      if (!data) return
      if (!data.canArchive) {
        toast.warning('预检未通过，已展开缺项与办理入口；未执行归档')
        return
      }
      this.pending = {
        id: data.id, kind: 'archive',
        expectedVersion: data.version ?? data.recordVersion,
        recordExpectedVersion: data.recordVersion
      }
      this.cd = { visible: true, title: '确认归档学生',
        content: `「${data.studentName}」已通过服务端业务与文件安全预检。确认冻结当前 FileVersion、Manifest 与已发布正式成绩？`,
        danger: false, confirmText: '确认归档', requireReason: false, submitting: false }
    },
    doRevoke(r) {
      this.pending = {
        id: r.id, kind: 'revoke', expectedVersion: r.version,
        recordExpectedVersion: r.recordVersion
      }
      this.cd = { visible: true, title: '撤销归档', content: `撤销「${r.studentName}」的归档，原因将写审计。`,
        danger: true, confirmText: '撤销归档', requireReason: true, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
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
      this.cd.submitting = false
      if (res.code !== 0) {
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
      this.cd.visible = false; toast.success('操作成功，已写审计')
      await this.load()
      // 工作区正在核验该行时，动作后刷新材料清单与留痕
      if (this.panel.visible && String(this.panel.rowId) === String(p.id)) this.openDetailById(p.id)
    },
    async buildPackage() {
      const id = this.panel.data?.id
      if (!id) return
      this.pkgBusy = true
      const res = await archiveApi.buildPackage(id)
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
      if (!this.panel.data?.id) return
      this.pkgBusy = true
      let pkg = this.pkgFile || this.panel.data?.latestPackage
      if (!pkg?.packageId) {
        pkg = await this.buildPackage()
        if (!pkg?.packageId) { this.pkgBusy = false; return }
      }
      try {
        await archiveApi.downloadPackage(pkg.packageId, pkg.fileName || '实习归档.zip')
      } catch (e) {
        toast.error(e?.message || '下载失败')
      }
      this.pkgBusy = false
    },
    async verifyRestore() {
      const pkg = this.pkgFile || this.panel.data?.latestPackage
      if (!pkg?.packageId) return toast.warning('请先生成归档包')
      this.restoreBusy = true
      const res = await archiveApi.verifyRestore(pkg.packageId)
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
      const batchId = this.batchStore.selectedBatchId
      if (!batchId) return toast.warning('请先选择批次')
      const afterId = this.batchPackage?.hasMore ? this.batchPackage.nextAfterId : 0
      this.batchPkgBusy = true
      const res = await archiveApi.buildBatchPackage(batchId, { afterId, limit: 20 })
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
      const pkg = this.batchPackage
      if (!pkg?.packageId) return
      this.batchPkgBusy = true
      try {
        await archiveApi.downloadBatchPackage(pkg.packageId, pkg.fileName || '实习批次归档.zip')
      } catch (e) {
        toast.error(e?.message || '批次归档包下载失败')
      }
      this.batchPkgBusy = false
    },
    async verifyBatchRestore() {
      const pkg = this.batchPackage
      if (!pkg?.packageId) return
      this.batchRestoreBusy = true
      const res = await archiveApi.verifyRestore(pkg.packageId)
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
      if (!id) return
      this.employmentBusy = true
      const res = await archiveApi.employmentTransition(id)
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
</style>
