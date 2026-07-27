<template>
  <ModulePageShell title="辅导员责任台账" subtitle="真实用户责任关系 · 主责、协同、临时代班与交接历史"
    :role-name="roleName" :data-scope-name="scopeHint">
    <div class="mp-stack">
      <section class="sa-summary-strip">
        <div class="sa-summary-strip__content">
          <span class="sa-summary-strip__eyebrow">当前责任关系</span>
          <h2 class="sa-summary-strip__title">先查空缺班级，再建立主责、协同或临时代班关系</h2>
          <p class="sa-summary-strip__text">责任关系决定辅导员可见学生和待办分派。主辅导员交接会结束旧主责关系并同步班级责任，历史记录继续保留。</p>
        </div>
        <div class="sa-summary-strip__actions">
          <AppPermissionButton :allowed="canBtn('studentAffairs.class.create')" code="studentAffairs.class.create" type="button" @click="openAssign">分配责任</AppPermissionButton>
        </div>
      </section>

      <div class="sa-workflow-strip" aria-label="辅导员责任管理流程">
        <div class="sa-workflow-step" data-step="1"><strong>查责任台账</strong><br>查看每名辅导员带班与学生规模</div>
        <div class="sa-workflow-step" data-step="2"><strong>补空缺班级</strong><br>优先为无主责班级建立责任关系</div>
        <div class="sa-workflow-step" data-step="3"><strong>维护责任类型</strong><br>区分主责、协同和临时代班</div>
        <div class="sa-workflow-step" data-step="4"><strong>交接留痕</strong><br>变更主责时保留原因、版本和历史</div>
      </div>

      <div class="tabs" role="tablist" aria-label="责任台账视图">
        <button v-for="item in tabs" :key="item.key" class="tab" :class="{ active: tab === item.key }"
          type="button" @click="switchTab(item.key)">{{ item.label }}</button>
      </div>
      <div class="toolbar sa-filter-bar">
        <div class="toolbar__filters">
          <AppClassPicker v-if="tab === 'assignments'" v-model="filters.classId" placeholder="全部班级"
            class="sa-filter-picker" @change="load" />
          <select v-if="tab === 'assignments'" v-model="filters.status" @change="load">
            <option value="">全部状态</option><option value="ACTIVE">有效</option><option value="ENDED">已结束</option>
          </select>
        </div>
        <AppPermissionButton :allowed="canBtn('studentAffairs.class.create')" code="studentAffairs.class.create" type="button" @click="openAssign">分配责任</AppPermissionButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDescription" />
      <DataTable v-else :columns="columns" :rows="rows" :row-key="rowKey" :pagination="pagination" @page-change="onPageChange">
        <template #cell-counselor="{ row }">
          <div class="mp-cell-main">{{ row.counselorName || row.name || '—' }}</div>
          <div v-if="row.loginName" class="mp-cell-sub">{{ row.loginName }}</div>
        </template>
        <template #cell-dutyType="{ row }"><AppStatusTag :status="row.dutyType" /></template>
        <template #cell-status="{ row }"><AppStatusTag :status="row.status" /></template>
        <template #cell-actions="{ row }">
          <div class="responsibility-actions">
            <button v-if="tab === 'assignments' && row.status === 'ACTIVE'" type="button" class="mp-link" @click="openHandover(row)">交接</button>
            <button v-if="tab === 'assignments' && row.status === 'ACTIVE'" type="button" class="mp-link danger" @click="openEnd(row)">结束</button>
          </div>
        </template>
      </DataTable>
      <p class="responsibility-note"><strong>影响说明：</strong>数据按当前角色与数据范围裁剪。主辅导员变更会结束旧主责关系并同步班级主辅导员；历史记录保留用于追溯。</p>
    </div>

    <div v-if="dialog.visible" class="overlay" @click.self="dialog.visible = false">
      <form class="dialog" @submit.prevent="submitDialog">
        <div class="dialog__head">
          <div>
            <span class="dialog__eyebrow">责任关系操作</span>
            <h3>{{ dialog.title }}</h3>
          </div>
          <button type="button" class="dialog__close" aria-label="关闭" @click="dialog.visible = false">×</button>
        </div>
        <p class="dialog__hint" v-if="dialog.mode === 'assign'">请选择班级、辅导员和责任类型。临时代班应填写明确截止日期。</p>
        <p class="dialog__hint" v-else-if="dialog.mode === 'handover'">交接会结束原主责关系并由新主辅导员承接学工责任，请核对双方身份和原因。</p>
        <p class="dialog__hint" v-else>结束后保留历史记录；若这是主辅导员，该班级会进入空缺台账。</p>
        <template v-if="dialog.mode === 'assign'">
          <label>班级<AppClassPicker v-model="form.classId" placeholder="搜索班级名称" /></label>
          <label>辅导员<AppTeacherPicker v-model="form.userId" placeholder="按姓名 / 工号搜索" /></label>
          <label>责任类型<select v-model="form.dutyType"><option value="PRIMARY">主辅导员</option><option value="CO">协同辅导员</option><option value="TEMP">临时代班</option></select></label>
          <div class="dialog__dates">
            <label>开始日期<input v-model="form.effectiveFrom" type="date"></label>
            <label>截止日期（临时代班必填）<input v-model="form.effectiveTo" type="date"></label>
          </div>
        </template>
        <template v-else-if="dialog.mode === 'handover'">
          <label>原辅导员<input :value="dialog.row.counselorName || dialog.row.name || '—'" disabled></label>
          <label>新主辅导员<AppTeacherPicker v-model="form.toUserId" placeholder="按姓名 / 工号搜索" /></label>
          <label>当前版本<input :value="dialog.row.version" disabled type="number"></label>
        </template>
        <label>原因<textarea v-model="form.reason" required maxlength="500" placeholder="说明分配、交接或结束责任关系的原因"></textarea></label>
        <p v-if="dialogError" class="dialog-error">{{ dialogError }}</p>
        <div class="actions"><button type="button" @click="dialog.visible = false">取消</button><button type="submit" :disabled="submitting">{{ submitting ? '提交中…' : '确认' }}</button></div>
      </form>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppPermissionButton, AppClassPicker, AppTeacherPicker } from '@/components/common'
import { counselorAssignmentApi } from '@/modules/studentAffairs/api/class.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'

const TABS = [{ key: 'ledger', label: '辅导员台账' }, { key: 'vacancies', label: '空缺班级' }, { key: 'assignments', label: '按班分配' }]
const COLS = {
  ledger: [{ key: 'counselor', title: '辅导员' }, { key: 'classCount', title: '带班数' }, { key: 'studentCount', title: '学生数' }, { key: 'primaryCount', title: '主责班级' }, { key: 'tempCount', title: '临时代班' }],
  vacancies: [{ key: 'className', title: '班级' }, { key: 'studentCount', title: '学生数' }, { key: 'status', title: '责任状态' }],
  assignments: [{ key: 'className', title: '班级' }, { key: 'counselor', title: '辅导员' }, { key: 'studentCount', title: '学生数' }, { key: 'dutyType', title: '责任类型' }, { key: 'status', title: '状态' }, { key: 'effectiveFrom', title: '生效时间' }, { key: 'effectiveTo', title: '截止时间' }, { key: 'actions', title: '操作' }]
}
const emptyForm = () => ({ classId: null, userId: null, dutyType: 'PRIMARY', effectiveFrom: '', effectiveTo: '', toUserId: null, reason: '' })
export default {
  name: 'CounselorAssignmentView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppPermissionButton, AppClassPicker, AppTeacherPicker },
  props: { ctx: { type: Object, default: null } },
  data: () => ({ tabs: TABS, tab: 'ledger', rows: [], loading: true, error: '', filters: { classId: '', status: '' }, pagination: { page: 1, pageSize: 20, total: 0 }, dialog: { visible: false, mode: '', title: '', row: null }, form: emptyForm(), dialogError: '', submitting: false }),
  computed: {
    columns() { return COLS[this.tab] }, rowKey() { return this.tab === 'ledger' ? 'userId' : (this.tab === 'vacancies' ? 'classId' : 'id') },
    roleName() { return this.ctx?.currentRole?.roleName || '学工处 / 学院学工 / 辅导员' },
    scopeHint() { return this.ctx?.dataScope?.name || '按数据范围裁剪' },
    emptyTitle() { return this.tab === 'vacancies' ? '当前没有空缺班级' : '暂无责任关系记录' },
    emptyDescription() { return this.tab === 'vacancies' ? '所有当前可见班级均有有效主辅导员。' : '可通过“分配责任”建立真实辅导员用户关系。' }
  },
  created() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.error = ''
      let res
      if (this.tab === 'ledger') res = await counselorAssignmentApi.ledger(this.pagination)
      else if (this.tab === 'vacancies') res = await counselorAssignmentApi.vacancies()
      else res = await counselorAssignmentApi.assignments({ ...this.pagination, classId: this.filters.classId || undefined, status: this.filters.status || undefined })
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; return }
      const data = res.data || {}; this.rows = data.list || data.items || []; this.pagination.total = data.total || this.rows.length
    },
    switchTab(tab) { this.tab = tab; this.pagination.page = 1; this.load() },
    onPageChange(page) { this.pagination.page = page; this.load() },
    openAssign() { this.form = emptyForm(); this.dialogError = ''; this.dialog = { visible: true, mode: 'assign', title: '分配辅导员责任', row: null } },
    openHandover(row) { this.form = emptyForm(); this.dialogError = ''; this.dialog = { visible: true, mode: 'handover', title: '辅导员交接', row } },
    openEnd(row) { this.form = emptyForm(); this.dialogError = ''; this.dialog = { visible: true, mode: 'end', title: '结束责任关系', row } },
    async submitDialog() {
      // 选择器回传的是字符串 id；后端要求整数，且原来的 required 校验随 input 一起去掉了，
      // 这里显式补上，避免"没选班级就点确认"变成一条看不懂的后端报错
      if (this.dialog.mode === 'assign' && !(this.form.classId && this.form.userId)) {
        this.dialogError = '请选择班级与辅导员'; return
      }
      if (this.dialog.mode === 'handover' && !this.form.toUserId) {
        this.dialogError = '请选择新主辅导员'; return
      }
      this.submitting = true; this.dialogError = ''; let res
      if (this.dialog.mode === 'assign') {
        res = await counselorAssignmentApi.assign({
          ...this.form, classId: Number(this.form.classId), userId: Number(this.form.userId)
        })
      }
      if (this.dialog.mode === 'handover') res = await counselorAssignmentApi.handover(this.dialog.row.classId, { fromUserId: Number(this.dialog.row.userId), toUserId: Number(this.form.toUserId), reason: this.form.reason, version: this.dialog.row.version })
      if (this.dialog.mode === 'end') res = await counselorAssignmentApi.end(this.dialog.row.id, { reason: this.form.reason, version: this.dialog.row.version })
      this.submitting = false
      if (res.code !== 0) { this.dialogError = res.message || '提交失败'; return }
      this.dialog.visible = false; this.load()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.tabs { display: flex; gap: var(--space-1); align-items: center; overflow-x: auto; padding: 4px; border: 1px solid var(--border-light); border-radius: var(--radius-lg); background: var(--bg-section); }
.tab { flex: 0 0 auto; border: 0; border-radius: var(--radius-md); background: transparent; padding: 8px 14px; color: var(--text-secondary); cursor: pointer; font-size: var(--font-size-sm); }
.tab.active { color: var(--primary-700); background: var(--bg-card); box-shadow: 0 1px 2px rgba(15, 23, 42, .08); font-weight: var(--font-weight-semibold); }
.toolbar { display:flex; justify-content:space-between; gap:var(--space-3); align-items:center; flex-wrap:wrap; }
.toolbar__filters { display: flex; gap: var(--space-2); align-items: center; flex-wrap: wrap; min-width: 0; }
.toolbar select { min-width: 130px; padding: 8px 10px; border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); }
.responsibility-actions { display: inline-flex; align-items: center; justify-content: flex-end; gap: 12px; flex-wrap: wrap; }
.responsibility-note { margin: 0; padding: var(--space-3); border-left: 3px solid var(--primary-300, #93c5fd); background: var(--primary-50, #eff6ff); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.65; }
.danger { color:var(--danger-600); }
.overlay { position:fixed; inset:0; z-index:50; background:rgba(15,23,42,.48); display:grid; place-items:center; padding: 16px; }
.dialog { width:min(560px,100%); max-height: min(760px, calc(100vh - 32px)); overflow-y: auto; padding:24px; border-radius:var(--radius-xl, 16px); background:white; display:grid; gap:14px; box-shadow: var(--shadow-xl, 0 24px 64px rgba(15,23,42,.22)); }
.dialog__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); padding-bottom: var(--space-3); border-bottom: 1px solid var(--border-light); }
.dialog__head h3 { margin: 3px 0 0; color: var(--text-primary); font-size: var(--font-size-lg); }
.dialog__eyebrow { color: var(--primary-700); font-size: var(--font-size-xs); font-weight: 600; }
.dialog__close { width: 32px; height: 32px; border: 0; border-radius: var(--radius-md); background: var(--bg-section); color: var(--text-tertiary); font-size: 22px; cursor: pointer; }
.dialog__hint { margin: 0; padding: 10px 12px; border: 1px solid var(--primary-100); border-radius: var(--radius-md); background: var(--primary-50); color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.dialog label { display:grid; gap:6px; color: var(--text-secondary); font-size: var(--font-size-sm); }
.dialog input,.dialog select,.dialog textarea { width:100%; box-sizing:border-box; padding:9px 10px; border: 1px solid var(--border-base); border-radius: var(--radius-md); font: inherit; }
.dialog textarea { min-height: 92px; resize: vertical; line-height: 1.55; }
.dialog__dates { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-3); }
.dialog-error { margin: 0; padding: 9px 11px; border-radius: var(--radius-md); background: var(--danger-50); color: var(--danger-700); font-size: var(--font-size-sm); }
.actions { display:flex; gap:var(--space-3); align-items:center; justify-content:flex-end; padding-top: var(--space-3); border-top: 1px solid var(--border-light); }
.actions button { min-width: 88px; padding: 8px 14px; border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--bg-card); cursor: pointer; }
.actions button[type='submit'] { border-color: var(--primary-600); background: var(--primary-600); color: #fff; }
@media (max-width: 640px) { .toolbar__filters, .toolbar__filters > * { width: 100%; } .dialog { padding: 16px; } .dialog__dates { grid-template-columns: 1fr; } .actions { align-items: stretch; flex-direction: column-reverse; } .actions button { width: 100%; } }
</style>
