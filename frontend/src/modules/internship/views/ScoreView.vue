<template>
  <ModulePageShell title="综合成绩" subtitle="实习成绩 · 五项权重核算 · 整批核对工作区 · 缺项不可发布"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppPermissionButton code="internship.score.manage" :allowed="canBtn('internship.score.manage')" variant="primary" @click="openCompute()">＋ 核算成绩</AppPermissionButton>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div class="stack">
      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

      <!-- 权重配置（真实 getConfig / saveConfig） -->
      <div class="cfg">
        <span class="cfg__t">五项权重配置</span>
        <div v-for="w in weightDefs" :key="w.key" class="cfg__item">
          <span>{{ w.label }}</span><AppNumberInput v-model="cfg[w.key]" :min="0" :max="100" size="sm" />
        </div>
        <div class="cfg__item"><span>及格线</span><AppNumberInput v-model="cfg.passLine" :min="0" :max="100" size="sm" /></div>
        <span class="cfg__sum" :class="{ 'is-bad': weightSum !== 100 }">合计 {{ weightSum }}/100</span>
        <AppPermissionButton code="internship.score.config" :allowed="canBtn('internship.score.config')" variant="secondary" size="sm" :loading="savingCfg" @click="saveConfig">保存配置</AppPermissionButton>
      </div>

      <!-- 快捷筛选行：状态（后端过滤）+ 仅看缺项（当前页内前端过滤） -->
      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
        <AppQuickFilterChips v-model="missingOnly" :options="missingOptions" allow-clear />
        <span v-if="missingOnly" class="bar__note">「仅看缺项」为当前页内筛选（接口暂不支持全量缺项过滤），本页命中 {{ displayRows.length }} 条</span>
      </div>

      <div v-if="error" class="state is-err">{{ error }} <button @click="load">重试</button></div>
      <template v-else>
        <DataTable :columns="columns" :rows="displayRows" row-key="id" :loading="loading"
          :pagination="pagination" row-clickable @row-click="openDetail" @page-change="onPageChange">
          <template #cell-studentName="{ row }">
            <span :class="{ 'is-current': row.id === panel.rowId }">{{ row.studentName }}</span>
          </template>
          <template #cell-checkinScore="{ row }">
            <span v-if="isMissing(row.checkinScore)" class="miss-cell">缺</span>
            <span v-else>{{ row.checkinScore }}</span>
          </template>
          <template #cell-weeklyScore="{ row }">
            <span v-if="isMissing(row.weeklyScore)" class="miss-cell">缺</span>
            <span v-else>{{ row.weeklyScore }}</span>
          </template>
          <template #cell-monthlyScore="{ row }">
            <span v-if="isMissing(row.monthlyScore)" class="miss-cell">缺</span>
            <span v-else>{{ row.monthlyScore }}</span>
          </template>
          <template #cell-enterpriseScore="{ row }">
            <span v-if="isMissing(row.enterpriseScore)" class="miss-cell">缺</span>
            <span v-else>{{ row.enterpriseScore }}</span>
          </template>
          <template #cell-schoolScore="{ row }">
            <span v-if="isMissing(row.schoolScore)" class="miss-cell">缺</span>
            <span v-else>{{ row.schoolScore }}</span>
          </template>
          <template #cell-total="{ row }">
            <b>{{ row.incomplete ? '—' : row.totalScore }}</b><span v-if="row.incomplete" class="miss-cell">缺项</span>
          </template>
          <template #cell-pass="{ row }">{{ row.incomplete ? '—' : (row.isPass ? '及格' : '不及格') }}</template>
          <template #cell-status="{ row }"><AppStatusTag :status="row.status">{{ row.statusLabel }}</AppStatusTag></template>
          <template #cell-actions="{ row }">
            <div class="ops">
              <AppButton variant="ghost" size="sm" @click="openDetail(row)">核对</AppButton>
              <AppPermissionButton v-if="canRecalc(row)" code="internship.score.manage" :allowed="canBtn('internship.score.manage')" variant="ghost" size="sm" @click="openCompute(row)">核算/重算</AppPermissionButton>
              <AppPermissionButton v-if="row.status === 'PENDING_REVIEW'" code="internship.score.publish" :allowed="canBtn('internship.score.publish')" variant="secondary" size="sm" :disabled="row.incomplete" @click="confirmAct(row, 'publish')">发布</AppPermissionButton>
              <AppPermissionButton v-if="row.status === 'PENDING_REVIEW'" code="internship.score.publish" :allowed="canBtn('internship.score.publish')" variant="ghost" size="sm" @click="confirmAct(row, 'return')">退回</AppPermissionButton>
              <AppPermissionButton v-if="row.status === 'PUBLISHED'" code="internship.score.publish" :allowed="canBtn('internship.score.publish')" variant="ghost" size="sm" :danger="true" @click="confirmAct(row, 'withdraw')">撤回</AppPermissionButton>
              <AppPermissionButton v-if="row.status === 'PUBLISHED'" code="internship.score.publish" :allowed="canBtn('internship.score.publish')" variant="ghost" size="sm" @click="confirmAct(row, 'archive')">归档</AppPermissionButton>
            </div>
          </template>
        </DataTable>
        <div v-if="missingOnly && !loading && rows.length && !displayRows.length" class="state">本页没有缺项记录，可翻页继续核对</div>
      </template>

      <!-- 选中行工作区：详情核对 / 行内核算（替代原居中弹窗） -->
      <div v-if="panel.visible" class="wsp">
        <div class="wsp__head">
          <span class="wsp__title">{{ panelTitle }}</span>
          <AppStatusTag v-if="panelRow" :status="panelRow.status">{{ panelRow.statusLabel }}</AppStatusTag>
          <span v-if="panelRow && panelRow.incomplete" class="miss-cell">{{ panelRow.incompleteReason || '缺项' }}</span>
          <AppButton class="wsp__close" variant="ghost" size="sm" @click="closePanel">收起</AppButton>
        </div>

        <template v-if="panel.mode === 'detail'">
          <div v-if="panel.loading" class="state">加载中…</div>
          <template v-else-if="panel.data">
            <AppDescriptionList :items="detailItems" :columns="2" />
            <div class="sec-t">核算/发布留痕</div>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
            <div v-if="panelRow && canRecalc(panelRow)" class="wsp__ops">
              <AppPermissionButton code="internship.score.manage" :allowed="canBtn('internship.score.manage')" variant="secondary" size="sm" @click="openCompute(panelRow)">转入核算</AppPermissionButton>
            </div>
          </template>
        </template>

        <template v-else>
          <AppFormItem v-if="panel.mode === 'create'" label="实习学生" required>
            <AppStudentPicker
              v-model="cForm.internshipId"
              :remote-search="searchInternStudents"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <div class="scores">
            <AppFormItem v-for="s in scoreInputs" :key="s.key" :label="s.label" class="score">
              <AppNumberInput v-model="cForm[s.key]" :min="0" :max="100" />
            </AppFormItem>
          </div>
          <p class="hint">各项 0-100。企业评价分留空时自动取「已通过企业评价」均分；缺项将标记且不可发布。权重取上方配置。</p>
          <div class="wsp__ops">
            <AppButton variant="ghost" @click="closePanel">取消</AppButton>
            <AppButton variant="primary" :loading="panel.submitting" @click="submitCompute(false)">核算</AppButton>
            <AppButton v-if="panel.mode === 'edit' && hasNextMissing" variant="secondary" :loading="panel.submitting" @click="submitCompute(true)">核算并跳下一缺项</AppButton>
          </div>
        </template>
      </div>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="原因" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppNumberInput, AppFormItem, AppStudentPicker } from '@/components/common'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { searchInternStudents } from './components/entityPickerAdapters'
import { scoreApi } from '@/modules/internship/api/score.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'

const WEIGHTS = [
  { key: 'checkinWeight', label: '打卡' }, { key: 'weeklyWeight', label: '周报' },
  { key: 'monthlyWeight', label: '月报' }, { key: 'enterpriseWeight', label: '企业' }, { key: 'schoolWeight', label: '学校' }
]
const SCORE_INPUTS = [
  { key: 'checkinScore', label: '打卡' }, { key: 'weeklyScore', label: '周报' },
  { key: 'monthlyScore', label: '月报总结' }, { key: 'enterpriseScore', label: '企业评价' }, { key: 'schoolScore', label: '学校评价' }
]
const COLUMNS = [
  { key: 'studentNo', title: '学号', width: '100px' }, { key: 'studentName', title: '姓名' },
  { key: 'checkinScore', title: '打卡' }, { key: 'weeklyScore', title: '周报' }, { key: 'monthlyScore', title: '月报' },
  { key: 'enterpriseScore', title: '企业评价' }, { key: 'schoolScore', title: '学校评价' },
  { key: 'total', title: '总分' }, { key: 'pass', title: '及格' }, { key: 'status', title: '状态' },
  { key: 'actions', title: '操作', width: '300px' }
]
const STATUS_MAP = { PENDING_CALC: '待核算', PENDING_REVIEW: '待复核', PUBLISHED: '已发布', WITHDRAWN: '已撤回', ARCHIVED: '已归档' }
const RECALC_STATUSES = ['PENDING_REVIEW', 'PENDING_CALC']
const DETAIL = [
  { key: 'studentName', label: '学生' }, { key: 'statusLabel', label: '状态' },
  { key: 'totalScore', label: '总分' }, { key: 'passLine', label: '及格线' },
  { key: 'checkinScore', label: '打卡分' }, { key: 'weeklyScore', label: '周报分' },
  { key: 'monthlyScore', label: '月报分' }, { key: 'enterpriseScore', label: '企业分' },
  { key: 'schoolScore', label: '学校分' }, { key: 'incompleteReason', label: '缺项' }
]

export default {
  name: 'ScoreView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, DataTable, ModuleSummaryStrip, AppButton, AppStatusTag, AppConfirmDialog, AppExportButton,
    AppPermissionButton, AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppNumberInput, AppFormItem, AppStudentPicker },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', missingOnly: '', columns: COLUMNS, weightDefs: WEIGHTS, scoreInputs: SCORE_INPUTS,
      statusOptions: Object.entries(STATUS_MAP).map(([value, label]) => ({ value, label })),
      missingOptions: [{ value: 'MISSING', label: '仅看缺项' }],
      cfg: { checkinWeight: 20, weeklyWeight: 20, monthlyWeight: 10, enterpriseWeight: 30, schoolWeight: 20, passLine: 60 },
      savingCfg: false,
      cForm: { internshipId: '', checkinScore: null, weeklyScore: null, monthlyScore: null, enterpriseScore: null, schoolScore: null },
      // 选中行工作区：mode = detail（核对）/ edit（行内核算）/ create（新核算）
      panel: { visible: false, mode: 'detail', rowId: '', loading: false, data: null, submitting: false },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    weightSum() { return WEIGHTS.reduce((a, w) => a + (Number(this.cfg[w.key]) || 0), 0) },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    displayRows() { return this.missingOnly ? this.rows.filter((r) => r.incomplete) : this.rows },
    summaryMetrics() {
      if (this.loading || this.error) return []
      const cur = this.statusOptions.find((o) => o.value === this.statusFilter)
      const missOnPage = this.rows.filter((r) => r.incomplete).length
      return [
        { label: '成绩记录 · ' + (cur ? cur.label : '全部'), value: this.total },
        { label: '本页缺项', value: missOnPage, tone: missOnPage ? 'warn' : 'good' }
      ]
    },
    panelRow() { return this.rows.find((r) => r.id === this.panel.rowId) || null },
    panelTitle() {
      if (this.panel.mode === 'create') return '核算成绩（选择学生）'
      const name = (this.panel.data && this.panel.data.studentName) || (this.panelRow && this.panelRow.studentName) || ''
      return (this.panel.mode === 'edit' ? '行内核算 · ' : '核对详情 · ') + name
    },
    hasNextMissing() {
      return this.rows.some((r) => r.incomplete && this.canRecalc(r) && r.id !== this.panel.rowId)
    },
    detailItems() { const d = this.panel.data || {}; return DETAIL.map((f) => ({ label: f.label, value: d[f.key] })) },
    auditRecords() {
      return (this.panel.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.reason || t.detail.comment || (t.detail.missing || []).join('、')), at: t.occurredAt
      }))
    }
  },
  created() { this.loadConfig(); this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    exportFn() { return scoreApi.exportScores({ keyword: this.keyword, status: this.statusFilter }) },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    async loadConfig() { const res = await scoreApi.getConfig(); if (res.code === 0) this.cfg = { ...this.cfg, ...res.data } },
    async saveConfig() {
      if (this.weightSum !== 100) return toast.error(`五项权重之和须为 100，当前 ${this.weightSum}`)
      this.savingCfg = true
      const res = await scoreApi.saveConfig(this.cfg)
      this.savingCfg = false
      if (res.code !== 0) return toast.error(res.message || '保存失败')
      toast.success('权重配置已保存')
    },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword }
      if (this.statusFilter) params.status = this.statusFilter
      const res = await scoreApi.getScores(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
    },
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    searchInternStudents,
    isMissing(v) { return v === null || v === undefined || v === '' },
    canRecalc(row) { return RECALC_STATUSES.includes(row.status) },
    closePanel() { this.panel = { visible: false, mode: 'detail', rowId: '', loading: false, data: null, submitting: false } },
    openCompute(row) {
      this.cForm = { internshipId: '', checkinScore: null, weeklyScore: null, monthlyScore: null, enterpriseScore: null, schoolScore: null }
      if (row && row.internId) {
        // 行内重算：学生锁定为该行，分数从当前行真实字段带出
        this.cForm.internshipId = row.internId
        for (const s of SCORE_INPUTS) this.cForm[s.key] = row[s.key] ?? null
        this.panel = { visible: true, mode: 'edit', rowId: row.id, loading: false, data: null, submitting: false }
      } else {
        this.panel = { visible: true, mode: 'create', rowId: '', loading: false, data: null, submitting: false }
      }
    },
    async submitCompute(goNext) {
      if (!this.cForm.internshipId) return toast.error('请选择实习学生')
      this.panel.submitting = true
      const body = { internshipId: this.cForm.internshipId }
      for (const s of SCORE_INPUTS) if (this.cForm[s.key] !== null && this.cForm[s.key] !== '') body[s.key] = this.cForm[s.key]
      const res = await scoreApi.compute(body)
      this.panel.submitting = false
      if (res.code !== 0) return toast.error(res.message || '核算失败')
      toast.success(res.data.incomplete ? `已核算（缺项：${res.data.incompleteReason}）` : `已核算，总分 ${res.data.total}`)
      const doneId = this.panel.mode === 'edit' ? this.panel.rowId : res.data.id
      await this.load()
      if (goNext) {
        const next = this.nextMissingRow(doneId)
        if (next) return this.openCompute(next)
        toast.info('本页已无其他可核算的缺项')
        this.closePanel()
      } else if (doneId) {
        this.openDetailById(doneId)
      } else {
        this.closePanel()
      }
    },
    nextMissingRow(afterId) {
      const eligible = (r) => r.incomplete && this.canRecalc(r) && r.id !== afterId
      const idx = this.rows.findIndex((r) => r.id === afterId)
      return this.rows.slice(idx + 1).find(eligible) || this.rows.slice(0, Math.max(idx, 0)).find(eligible) || null
    },
    openDetail(r) { this.openDetailById(r.id) },
    async openDetailById(id) {
      this.panel = { visible: true, mode: 'detail', rowId: id, loading: true, data: null, submitting: false }
      const res = await scoreApi.getDetail(id)
      if (!this.panel.visible || this.panel.rowId !== id || this.panel.mode !== 'detail') return
      this.panel.loading = false
      if (res.code !== 0) { toast.error(res.message || '加载失败'); this.closePanel(); return }
      this.panel.data = res.data
    },
    confirmAct(r, kind) {
      const map = {
        publish: { title: '发布成绩', content: `发布「${r.studentName}」的实习成绩（总分 ${r.totalScore}）？发布后学生可见。`, danger: false, confirmText: '发布', requireReason: false },
        return: { title: '退回重算', content: `退回「${r.studentName}」的成绩到待核算？`, danger: false, confirmText: '退回', requireReason: false },
        withdraw: { title: '撤回成绩', content: `撤回「${r.studentName}」的已发布成绩，原因将写审计。`, danger: true, confirmText: '撤回', requireReason: true },
        archive: { title: '归档成绩', content: `归档「${r.studentName}」的已发布成绩？`, danger: false, confirmText: '归档', requireReason: false }
      }[kind]
      this.pending = { id: r.id, kind }
      this.cd = { visible: true, ...map, submitting: false }
    },
    async onConfirm({ reason }) {
      const p = this.pending
      this.cd.submitting = true
      let res
      if (p.kind === 'publish') res = await scoreApi.publish(p.id)
      else if (p.kind === 'return') res = await scoreApi.returnRecalc(p.id, { reason })
      else if (p.kind === 'withdraw') res = await scoreApi.withdraw(p.id, { reason })
      else res = await scoreApi.archive(p.id)
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('操作成功，已写审计')
      await this.load()
      // 若工作区正在核对该行，动作后刷新留痕
      if (this.panel.visible && this.panel.mode === 'detail' && this.panel.rowId === p.id) this.openDetailById(p.id)
    }
  }
}
</script>

<style scoped>
.stack { display: flex; flex-direction: column; gap: var(--space-3); }
.cfg { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; padding: var(--space-3); background: var(--bg-subtle); border-radius: var(--radius-base); }
.cfg__t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); }
.cfg__item { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-xs); color: var(--text-secondary); }
.cfg__item :deep(.app-number-input) { width: 64px; }
.cfg__sum { font-size: var(--font-size-sm); color: var(--success-700); }
.cfg__sum.is-bad { color: var(--danger-600); }
.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.bar__note { font-size: var(--font-size-xs); color: var(--warning-700, #b45309); }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); }
.state.is-err { color: var(--danger-600); }
.miss-cell { display: inline-flex; align-items: center; height: 20px; padding: 0 8px; margin-left: 4px; border-radius: 10px; font-size: var(--font-size-xs); font-weight: var(--font-weight-semibold); background: var(--danger-bg, #fef2f2); color: var(--danger-600, #dc2626); border: 1px solid var(--danger-bd, #fecaca); white-space: nowrap; }
.miss-cell:first-child { margin-left: 0; }
.is-current { color: var(--pri, #2563eb); font-weight: var(--font-weight-semibold); }
.ops { display: flex; gap: var(--space-1); flex-wrap: wrap; }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-3) 0 var(--space-2); }
.hint { margin: var(--space-2) 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.scores { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.score { width: calc(20% - var(--space-2)); min-width: 92px; }
.wsp { border: 1px solid var(--card-b, #e5e7eb); border-radius: var(--radius-lg, 12px); background: var(--card, #fff); padding: var(--space-4); box-shadow: var(--s1); }
.wsp__head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; margin-bottom: var(--space-3); }
.wsp__title { font-weight: var(--font-weight-semibold); }
.wsp__close { margin-left: auto; }
.wsp__ops { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
</style>
