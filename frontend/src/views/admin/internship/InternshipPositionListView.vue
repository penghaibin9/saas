<template>
  <ModulePageShell
    title="企业与岗位"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppExportButton v-if="activePanel !== 'stats'" :export-fn="exportFn">⬇ 导出 Excel 台账</AppExportButton>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div v-if="activePanel === 'stats' && posStats" class="mp-stats">
      <div class="mp-stat"><div class="mp-stat__val">{{ posStats.total }}</div><div class="mp-stat__lbl">岗位总数</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ posStats.riskCount }}</div><div class="mp-stat__lbl">风险岗位</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ posStats.publishedCapacity }}</div><div class="mp-stat__lbl">已上架容量</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ posStats.publishedAllocated }}</div><div class="mp-stat__lbl">已分配</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ posStats.capacityUtilization }}%</div><div class="mp-stat__lbl">容量利用率</div></div>
      <div class="mp-stat"><div class="mp-stat__val">{{ posStats.unlimitedMajorCount }}</div><div class="mp-stat__lbl">不限专业(上架)</div></div>
    </div>

    <div class="mp-stack">
      <AdvancedFilter v-if="activePanel !== 'stats'" v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <template v-else-if="activePanel === 'stats' && posStats">
        <div class="ip-block">
          <h3 class="ip-h">按状态</h3>
          <DataTable :columns="statStatusCols" :rows="posStats.byStatus || []" row-key="status" :pagination="null" />
        </div>
        <div class="ip-block">
          <h3 class="ip-h">按专业要求（已上架）</h3>
          <EmptyState v-if="!(posStats.byMajor || []).length" title="暂无已上架岗位" description="上架岗位后可按专业要求聚合统计" />
          <DataTable v-else :columns="statMajorCols" :rows="posStats.byMajor || []" row-key="major" :pagination="null" />
        </div>
      </template>
      <EmptyState v-else-if="!rows.length" title="暂无岗位" description="可「＋ 新增岗位」或「导入」补充岗位库（岗位须先有企业）" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="id" :pagination="{ page, pageSize, total }" @page-change="turnPage">
        <template #cell-position="{ row }">
          <div class="mp-cell-main">{{ row.title }}<span v-if="row.riskFlag" class="ip-risk">⚠风险</span></div>
          <div class="mp-cell-sub">{{ row.companyName }}</div>
        </template>
        <template #cell-require="{ row }">
          <div class="mp-cell-sub">{{ row.majorRequirement || '不限专业' }}</div>
          <div class="mp-cell-sub">{{ row.gradeRequirement || '不限年级' }}</div>
        </template>
        <template #cell-capacity="{ row }">{{ row.allocatedCount }}/{{ row.headcount }}</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="row.statusTone" dot>{{ row.statusLabel }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push('/admin/internship/positions/' + row.id)">详情</button>
          <button v-if="row.status === 'DRAFT'" class="mp-link" style="margin-left: var(--space-2)" @click="askStatus(row, 'SUBMIT')">提交</button>
          <button v-else-if="['PENDING', 'OFFLINE', 'SUSPENDED'].includes(row.status)" class="mp-link" style="margin-left: var(--space-2)" @click="askStatus(row, 'PUBLISH')">上架</button>
          <button v-else-if="row.status === 'PUBLISHED'" class="mp-link" style="margin-left: var(--space-2)" @click="askStatus(row, 'OFFLINE')">下架</button>
          <button v-if="row.status !== 'ARCHIVED' && row.status !== 'RISK'" class="mp-link mp-link--danger" style="margin-left: var(--space-2)" @click="askRisk(row, true)">标记风险</button>
          <button v-if="row.status === 'RISK'" class="mp-link" style="margin-left: var(--space-2)" @click="askRisk(row, false)">解除风险</button>
        </template>
      </DataTable>
    </div>

    <!-- 新增 / 编辑 -->
    <AppDrawer v-model:visible="editVisible" :title="editing ? '编辑岗位' : '新增岗位'">
      <form class="ie-form" @submit.prevent="submitEdit">
        <!-- Picker 不能包在 <label> 里：label 激活会把点击转发给选择器内部按钮 -->
        <div v-if="!editing" class="ie-fld ie-fld--full"><span class="ie-lbl">所属企业 <i>*</i></span>
          <AppCompanyPicker
            v-model="form.companyId"
            :remote-search="searchEnterprises"
            :options="companyPresetOpts"
            placeholder="输入企业名称搜索"
            search-placeholder="按企业名称搜索"
            data-scope-hint="仅合作企业 · 黑名单/非合作中企业上架时由后端拦截"
            @update:model-value="onCompanyChange"
          />
        </div>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">岗位名称 <i>*</i></span><input v-model.trim="form.title" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">专业要求</span><input v-model.trim="form.majorRequirement" class="ie-in" placeholder="不填=不限" /></label>
        <label class="ie-fld"><span class="ie-lbl">年级要求</span><input v-model.trim="form.gradeRequirement" class="ie-in" placeholder="如 2024级" /></label>
        <label class="ie-fld"><span class="ie-lbl">工作地点</span><input v-model.trim="form.workLocation" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">薪资</span><input v-model.trim="form.salaryRange" class="ie-in" placeholder="如 3k-4k" /></label>
        <label class="ie-fld"><span class="ie-lbl">补贴</span><input v-model.trim="form.subsidy" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">容量 <i>*</i></span><input v-model.number="form.headcount" type="number" min="1" class="ie-in" /></label>
        <div v-if="!editing" class="ie-fld"><span class="ie-lbl">企业导师</span>
          <AppMentorPicker
            v-model="form.mentorContactId"
            :options="mentorOpts"
            placeholder="选择企业导师（可不指定）"
            search-placeholder="按导师姓名过滤"
            data-scope-hint="先选择所属企业，再选择该企业的导师"
          />
        </div>
        <label class="ie-fld"><span class="ie-lbl">批次（预留）</span><input class="ie-in" value="按当前实习批次自动关联" disabled /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><textarea v-model.trim="form.remark" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="editVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">{{ submitting ? '提交中…' : '保存' }}</button>
        </div>
      </form>
    </AppDrawer>

    <AppExcelImportDrawer
      v-model:visible="importVisible"
      title="导入岗位"
      template-name="岗位导入模板.xlsx"
      :required-fields="['岗位名称', '关联企业']"
      :preview-fields="['title', 'company', 'major', 'location', 'headcount']"
      :download-template-fn="() => positionApi.downloadPositionTemplate()"
      :upload-fn="(file) => positionApi.importPositionsXlsx(file)"
      :confirm-fn="({ rows }) => positionApi.importPositionsConfirm(rows)"
      :download-errors-fn="({ rows, errors }) => positionApi.downloadPositionImportErrors(rows, errors)"
      @imported="onImported"
    />

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 岗位库列表（/admin/internship/positions）：筛选 + 增改抽屉(企业/导师选择) + 状态机 + 风险标记 + 真导入导出。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppExportButton, AppStatusTag, AppCompanyPicker, AppMentorPicker } from '@/components/common'
import { AppExcelImportDrawer } from '@/components/common/excel'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { searchEnterprises } from './components/entityPickerAdapters'
import { positionApi } from '@/modules/internship/api/position.api'
import { POSITION_STATUS } from '@/modules/internship/constants/position.constants'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', companyId: '', risk: '' })
const EMPTY_FORM = () => ({ companyId: '', title: '', majorRequirement: '', gradeRequirement: '', workLocation: '', salaryRange: '', subsidy: '', headcount: 1, mentorContactId: '', remark: '' })
const POSITION_PANEL_PRESETS = {
  list: () => EMPTY_FILTERS(),
  detail: () => EMPTY_FILTERS(),
  requirement: () => EMPTY_FILTERS(),
  capacity: () => ({ ...EMPTY_FILTERS(), status: 'PUBLISHED' }),
  publish: () => ({ ...EMPTY_FILTERS(), status: 'PENDING' }),
  offline: () => ({ ...EMPTY_FILTERS(), status: 'PUBLISHED' }),
  risk: () => ({ ...EMPTY_FILTERS(), risk: 'true' }),
  archive: () => ({ ...EMPTY_FILTERS(), status: 'ARCHIVED' }),
  stats: () => EMPTY_FILTERS()
}
const POSITION_PANEL_HINTS = {
  list: '岗位关联企业 · 黑名单/停用企业不可上架',
  detail: '点击行「详情」进入岗位详情页',
  requirement: '关注「专业/年级」列 · 新建/编辑可维护要求',
  capacity: '已上架岗位 · 关注「已分配/容量」列',
  publish: '待审核岗位 · 行内可「上架」',
  offline: '已上架岗位 · 行内可「下架」',
  risk: '仅风险岗位 · 可「解除风险」',
  archive: '已归档岗位台账',
  stats: '岗位库真实统计 · 状态分布 / 专业分布 / 容量利用率'
}

export default {
  name: 'InternshipPositionListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, AppStatusTag, AppExportButton, AppExcelImportDrawer, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog, AppCompanyPicker, AppMentorPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      positionApi,
      loading: true, error: '', submitting: false, activePanel: 'list',
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      enterpriseOpts: [], mentorOpts: [], posStats: null,
      editVisible: false, editing: null, form: EMPTY_FORM(), formError: '',
      importVisible: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      columns: [
        { key: 'position', title: '岗位 / 企业' },
        { key: 'require', title: '专业 / 年级' },
        { key: 'workLocation', title: '工作地点' },
        { key: 'salaryRange', title: '薪资' },
        { key: 'capacity', title: '已分配/容量' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '230px' }
      ],
      statStatusCols: [{ key: 'label', title: '状态' }, { key: 'count', title: '数量' }],
      statMajorCols: [
        { key: 'major', title: '专业要求' },
        { key: 'count', title: '岗位数' },
        { key: 'capacity', title: '容量' },
        { key: 'allocated', title: '已分配' }
      ]
    }
  },
  computed: {
    statusOpts() { return POSITION_STATUS },
    companyPresetOpts() {
      // 编辑态回显：把当前岗位所属企业预置进选择器本地选项缓存（合法本地预置，不是一次性全量加载）
      if (!this.editing || !this.editing.companyId) return []
      return [{ label: this.editing.companyName, value: this.editing.companyId }]
    },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '岗位 / 企业 / 专业' },
        { key: 'status', label: '状态', type: 'select', options: this.statusOpts },
        { key: 'companyId', label: '企业', type: 'select', options: this.enterpriseOpts.map((e) => ({ value: e.id, label: e.name })) },
        { key: 'risk', label: '风险', type: 'select', options: [{ value: 'true', label: '仅风险岗位' }] }
      ]
    },
    toolbarActions() {
      if (this.activePanel === 'stats') {
        return [{ key: 'refreshStats', label: '刷新统计', variant: 'primary' }]
      }
      return [{ key: 'create', label: '＋ 新增岗位', variant: 'primary' }, { key: 'import', label: '导入' }]
    },
    pageSubtitle() {
      const hint = POSITION_PANEL_HINTS[this.activePanel] || POSITION_PANEL_HINTS.list
      if (this.activePanel === 'stats' && this.posStats) {
        return `${hint} · 共 ${this.posStats.total} 个岗位`
      }
      return `共 ${this.total} 个岗位 · ${hint}`
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'list').toString())
      }
    }
  },
  async created() {
    const e = await positionApi.getEnterpriseOptions()
    if (e.code === 0) this.enterpriseOpts = e.data
  },
  methods: {
    // 选择器远程搜索（岗位实习模块适配层，后端裁定关键字与数据范围）
    searchEnterprises,
    applyPanel(panel) {
      const key = POSITION_PANEL_PRESETS[panel] ? panel : 'list'
      this.activePanel = key
      this.filters = (POSITION_PANEL_PRESETS[key] || POSITION_PANEL_PRESETS.list)()
      this.page = 1
      this.load()
    },
    async load() {
      this.loading = true; this.error = ''
      if (this.activePanel === 'stats') {
        const res = await positionApi.getPositionStats()
        if (res.code === 0) { this.posStats = res.data; this.rows = []; this.total = 0 }
        else this.error = res.message
        this.loading = false
        return
      }
      this.posStats = null
      const p = { ...this.filters, page: this.page, pageSize: this.pageSize }
      if (p.risk === '') delete p.risk
      const res = await positionApi.getPositions(p)
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) {
      if (key === 'create') { this.editing = null; this.form = EMPTY_FORM(); this.mentorOpts = []; this.formError = ''; this.editVisible = true }
      if (key === 'import') { this.importVisible = true }
      if (key === 'refreshStats') this.load()
    },
    exportFn() {
      return positionApi.exportPositions({ ...this.filters })
    },
    onImported(data) {
      toast.success(`已导入 ${data.created || 0} 个岗位（草稿）`)
      this.load()
    },
    async onCompanyChange() {
      // 企业变更：清空导师选择并联动加载该企业导师小列表（本地过滤即可，非一次性全量预载）
      this.form.mentorContactId = ''
      this.mentorOpts = []
      if (!this.form.companyId) return
      const res = await positionApi.getEnterpriseMentors(this.form.companyId)
      if (res.code === 0) this.mentorOpts = (res.data || []).map((m) => ({ label: m.name, value: m.id }))
    },
    async submitEdit() {
      this.formError = ''
      if (!this.editing && !this.form.companyId) { this.formError = '请选择所属企业'; return }
      if (!this.form.title) { this.formError = '岗位名称必填'; return }
      if (!this.form.headcount || this.form.headcount < 1) { this.formError = '容量至少 1'; return }
      this.submitting = true
      try {
        const res = this.editing ? await positionApi.updatePosition(this.editing.id, this.form) : await positionApi.createPosition(this.form)
        if (res.code === 0) { toast.success('已保存并写入留痕'); this.editVisible = false; this.load() } else this.formError = res.message
      } finally { this.submitting = false }
    },
    askStatus(row, action) {
      const map = { SUBMIT: { t: '提交审核', c: '确认提交', type: 'primary' }, PUBLISH: { t: '上架岗位', c: '确认上架', type: 'primary' }, OFFLINE: { t: '下架岗位', c: '确认下架', type: 'warning' } }
      const m = map[action]
      this.confirm = { visible: true, title: m.t, message: `确认对「${row.title}」执行「${m.t}」？${action === 'PUBLISH' ? '（黑名单/非合作中企业将被拒）' : ''}`, type: m.type, confirmText: m.c, requireReason: false, action: 'STATUS_' + action, row }
    },
    askRisk(row, on) {
      this.confirm = { visible: true, title: on ? '标记风险岗位' : '解除风险', message: on ? `确认将「${row.title}」标记为风险岗位？` : `确认解除「${row.title}」的风险标记？（回到已下架）`, type: on ? 'danger' : 'primary', confirmText: on ? '确认标记' : '确认解除', requireReason: on, reasonLabel: '风险说明', action: on ? 'RISK_ON' : 'RISK_OFF', row }
    },
    async onConfirm({ reason } = {}) {
      const { action, row } = this.confirm
      this.submitting = true
      try {
        let res
        if (action.startsWith('STATUS_')) res = await positionApi.setPositionStatus(row.id, { action: action.slice(7), reason: reason || '' })
        else if (action === 'RISK_ON') res = await positionApi.markPositionRisk(row.id, { on: true, note: reason || '' })
        else if (action === 'RISK_OFF') res = await positionApi.markPositionRisk(row.id, { on: false })
        if (res && res.code === 0) { toast.success('已更新并写入留痕'); this.confirm.visible = false; this.load() } else if (res) toast.error(res.message)
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ip-risk { margin-left: var(--space-2); font-size: 11px; color: var(--danger, #dc2626); }
.mp-link--danger { color: var(--danger, #dc2626); }
.ie-form { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); padding: var(--space-1) 0; }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-hint { grid-column: 1 / -1; font-size: 12px; color: var(--t3, #64748b); margin: 0; }
.ie-actions { grid-column: 1 / -1; display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-2); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.ie-imp { grid-column: 1 / -1; font-size: 12px; }
.ie-imp__errs { margin: 4px 0 0; padding-left: 18px; color: var(--danger, #dc2626); }
.ie-xlsx { grid-column: 1 / -1; padding: 10px 12px; border: 1px dashed var(--line, #d9dee8); border-radius: 8px; font-size: 13px; background: var(--bg-subtle, #f8fafc); }
.ie-ok { color: var(--success, #16a34a); } .ie-bad { color: var(--danger, #dc2626); }
.mp-stats { display: flex; flex-wrap: wrap; gap: var(--space-3); margin-bottom: var(--space-4); }
.mp-stat { min-width: 120px; padding: var(--space-3) var(--space-4); background: #fff; border: 1px solid var(--line, #d9dee8); border-radius: 8px; }
.mp-stat__val { font-size: 20px; font-weight: 600; }
.mp-stat__lbl { color: var(--t2, #475569); font-size: 12px; margin-top: 4px; }
.ip-block { margin-bottom: var(--space-4); }
.ip-h { margin: 0 0 var(--space-2); font-size: 14px; }
</style>
