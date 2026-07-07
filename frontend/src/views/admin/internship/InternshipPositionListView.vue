<template>
  <ModulePageShell
    title="岗位库"
    :subtitle="'共 ' + total + ' 个岗位 · 岗位关联企业 · 黑名单/停用企业不可上架'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbarActions" @action="onToolbar" />
    </template>

    <div class="mp-stack">
      <AdvancedFilter v-model="filters" :fields="filterFields" @search="search" @reset="reset" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
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
          <StatusTag :type="row.statusTone" :label="row.statusLabel" dot />
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
        <label v-if="!editing" class="ie-fld ie-fld--full"><span class="ie-lbl">所属企业 <i>*</i></span>
          <select v-model="form.companyId" class="ie-in" @change="onCompanyChange">
            <option value="">请选择企业</option>
            <option v-for="e in enterpriseOpts" :key="e.id" :value="e.id" :disabled="e.blacklist || e.coopStatus === 'BLACKLIST'">{{ e.name }}{{ e.blacklist ? '（黑名单）' : (e.coopStatus !== 'ACTIVE' ? '（非合作中）' : '') }}</option>
          </select>
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">岗位名称 <i>*</i></span><input v-model.trim="form.title" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">专业要求</span><input v-model.trim="form.majorRequirement" class="ie-in" placeholder="不填=不限" /></label>
        <label class="ie-fld"><span class="ie-lbl">年级要求</span><input v-model.trim="form.gradeRequirement" class="ie-in" placeholder="如 2024级" /></label>
        <label class="ie-fld"><span class="ie-lbl">工作地点</span><input v-model.trim="form.workLocation" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">薪资</span><input v-model.trim="form.salaryRange" class="ie-in" placeholder="如 3k-4k" /></label>
        <label class="ie-fld"><span class="ie-lbl">补贴</span><input v-model.trim="form.subsidy" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">容量 <i>*</i></span><input v-model.number="form.headcount" type="number" min="1" class="ie-in" /></label>
        <label v-if="!editing" class="ie-fld"><span class="ie-lbl">企业导师</span>
          <select v-model="form.mentorContactId" class="ie-in">
            <option value="">不指定</option>
            <option v-for="m in mentorOpts" :key="m.id" :value="m.id">{{ m.name }}</option>
          </select>
        </label>
        <label class="ie-fld"><span class="ie-lbl">批次（预留）</span><input class="ie-in" value="待实习批次模块联调" disabled /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">备注</span><textarea v-model.trim="form.remark" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="editVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">{{ submitting ? '提交中…' : '保存' }}</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 导入 -->
    <AppDrawer v-model:visible="importVisible" title="导入岗位（CSV 粘贴）">
      <div class="ie-form">
        <p class="ie-hint">每行一个，逗号分隔：<b>岗位名称,企业名称,专业要求,工作地点,容量</b>（企业名称须已在企业库）</p>
        <textarea v-model="importText" class="ie-in" rows="6" placeholder="示例：前端实习生,华信智能科技有限公司,软件技术,上海,3" />
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="dryRunImport">预校验</button>
          <button type="button" class="mp-btn mp-btn--primary" :disabled="!importChecked || submitting" @click="confirmImport">确认导入</button>
        </div>
        <div v-if="importResult" class="ie-imp">
          <p>共 {{ importResult.total }} 行 · 通过 <b class="ie-ok">{{ importResult.validRows }}</b> · 失败 <b class="ie-bad">{{ importResult.invalidRows }}</b></p>
          <ul v-if="importResult.errors.length" class="ie-imp__errs"><li v-for="(e, i) in importResult.errors" :key="i">第 {{ e.rowNo }} 行 · {{ e.field }}：{{ e.message }}</li></ul>
          <p v-else class="ie-ok">全部通过，可确认导入。</p>
        </div>
      </div>
    </AppDrawer>

    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/** 岗位库列表（/admin/internship/positions）：筛选 + 增改抽屉(企业/导师选择) + 状态机 + 风险标记 + 真导入导出。 */
import { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { positionApi } from '@/modules/internship/api/position.api'
import { POSITION_STATUS } from '@/mocks/internship/position.mock'
import { toast } from '@/utils/toast'

const EMPTY_FILTERS = () => ({ keyword: '', status: '', companyId: '', risk: '' })
const EMPTY_FORM = () => ({ companyId: '', title: '', majorRequirement: '', gradeRequirement: '', workLocation: '', salaryRange: '', subsidy: '', headcount: 1, mentorContactId: '', remark: '' })

export default {
  name: 'InternshipPositionListView',
  components: { ModulePageShell, ModuleToolbar, AdvancedFilter, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppDrawer, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', submitting: false,
      rows: [], total: 0, page: 1, pageSize: 10, filters: EMPTY_FILTERS(),
      enterpriseOpts: [], mentorOpts: [],
      editVisible: false, editing: null, form: EMPTY_FORM(), formError: '',
      importVisible: false, importText: '', importChecked: false, importResult: null,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null, row: null },
      columns: [
        { key: 'position', title: '岗位 / 企业' },
        { key: 'require', title: '专业 / 年级' },
        { key: 'workLocation', title: '工作地点' },
        { key: 'salaryRange', title: '薪资' },
        { key: 'capacity', title: '已分配/容量' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '230px' }
      ]
    }
  },
  computed: {
    statusOpts() { return POSITION_STATUS },
    filterFields() {
      return [
        { key: 'keyword', label: '关键词', type: 'text', placeholder: '岗位 / 企业 / 专业' },
        { key: 'status', label: '状态', type: 'select', options: this.statusOpts },
        { key: 'companyId', label: '企业', type: 'select', options: this.enterpriseOpts.map((e) => ({ value: e.id, label: e.name })) },
        { key: 'risk', label: '风险', type: 'select', options: [{ value: 'true', label: '仅风险岗位' }] }
      ]
    },
    toolbarActions() {
      return [{ key: 'create', label: '＋ 新增岗位', variant: 'primary' }, { key: 'import', label: '导入' }, { key: 'export', label: '导出' }]
    }
  },
  async created() {
    const e = await positionApi.getEnterpriseOptions()
    if (e.code === 0) this.enterpriseOpts = e.data
    this.load()
  },
  methods: {
    async load() {
      this.loading = true; this.error = ''
      const res = await positionApi.getPositions({ ...this.filters, page: this.page, pageSize: this.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.total = res.data.total } else this.error = res.message
      this.loading = false
    },
    search() { this.page = 1; this.load() },
    reset() { this.filters = EMPTY_FILTERS(); this.page = 1; this.load() },
    turnPage(p) { this.page = p; this.load() },
    onToolbar(key) {
      if (key === 'create') { this.editing = null; this.form = EMPTY_FORM(); this.mentorOpts = []; this.formError = ''; this.editVisible = true }
      if (key === 'import') { this.importText = ''; this.importResult = null; this.importChecked = false; this.importVisible = true }
      if (key === 'export') this.doExport()
    },
    async onCompanyChange() {
      this.form.mentorContactId = ''
      this.mentorOpts = []
      if (!this.form.companyId) return
      const res = await positionApi.getEnterpriseMentors(this.form.companyId)
      if (res.code === 0) this.mentorOpts = res.data
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
    },
    _parse() {
      return this.importText.split('\n').map((l) => l.trim()).filter(Boolean).map((l) => {
        const [title, company, major, location, headcount] = l.split(',').map((x) => (x || '').trim())
        return { title, company, major, location, headcount }
      })
    },
    async dryRunImport() {
      const rows = this._parse()
      if (!rows.length) return toast.error('请粘贴至少一行')
      const res = await positionApi.importPositionsDryRun(rows)
      if (res.code === 0) { this.importResult = res.data; this.importChecked = res.data.invalidRows === 0 } else toast.error(res.message)
    },
    async confirmImport() {
      const res = await positionApi.importPositionsConfirm(this._parse())
      if (res.code === 0) { toast.success(`已导入 ${res.data.created} 个岗位（草稿）`); this.importVisible = false; this.load() } else toast.error(res.message)
    },
    async doExport() {
      const res = await positionApi.exportPositions({ ...this.filters })
      if (res.code !== 0) return toast.error(res.message)
      const blob = new Blob(['﻿' + res.data.content], { type: 'text/csv;charset=utf-8' })
      const url = URL.createObjectURL(blob); const a = document.createElement('a')
      a.href = url; a.download = res.data.filename || '岗位库导出.csv'; a.click(); URL.revokeObjectURL(url)
      toast.success(`已导出 ${res.data.rowCount} 个岗位（已写审计）`)
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
.ie-ok { color: var(--success, #16a34a); } .ie-bad { color: var(--danger, #dc2626); }
</style>
