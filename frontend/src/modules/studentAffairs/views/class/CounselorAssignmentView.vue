<template>
  <ModulePageShell title="辅导员责任台账" subtitle="真实用户责任关系 · 主责、协同、临时代班与交接历史"
    :role-name="roleName" :data-scope-name="scopeHint">
    <div class="mp-stack">
      <div class="tabs" role="tablist">
        <button v-for="item in tabs" :key="item.key" class="tab" :class="{ active: tab === item.key }"
          type="button" @click="switchTab(item.key)">{{ item.label }}</button>
      </div>
      <div class="toolbar">
        <AppSearchBox v-if="tab === 'assignments'" v-model="filters.classId" placeholder="班级 ID（可选）" @search="load" />
        <select v-if="tab === 'assignments'" v-model="filters.status" @change="load">
          <option value="">全部状态</option><option value="ACTIVE">有效</option><option value="ENDED">已结束</option>
        </select>
        <AppPermissionButton :allowed="canBtn('studentAffairs.class.create')" code="studentAffairs.class.create" type="button" @click="openAssign">分配责任</AppPermissionButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="emptyTitle" :description="emptyDescription" />
      <DataTable v-else :columns="columns" :rows="rows" :row-key="rowKey" :pagination="pagination" @page-change="onPageChange">
        <template #cell-counselor="{ row }">
          <div class="mp-cell-main">{{ row.counselorName || row.name || '—' }}</div>
          <div v-if="row.userId" class="mp-cell-sub">用户 ID：{{ row.userId }}</div>
        </template>
        <template #cell-dutyType="{ row }"><AppStatusTag :status="row.dutyType" /></template>
        <template #cell-status="{ row }"><AppStatusTag :status="row.status" /></template>
        <template #cell-actions="{ row }">
          <button v-if="tab === 'assignments' && row.status === 'ACTIVE'" type="button" class="mp-link" @click="openHandover(row)">交接</button>
          <button v-if="tab === 'assignments' && row.status === 'ACTIVE'" type="button" class="mp-link danger" @click="openEnd(row)">结束</button>
        </template>
      </DataTable>
      <p class="mp-note">数据按当前角色与数据范围裁剪。主辅导员变更会结束旧主责关系并同步班级主辅导员；历史记录保留用于追溯。</p>
    </div>

    <div v-if="dialog.visible" class="overlay" @click.self="dialog.visible = false">
      <form class="dialog" @submit.prevent="submitDialog">
        <h3>{{ dialog.title }}</h3>
        <template v-if="dialog.mode === 'assign'">
          <label>班级 ID<input v-model.number="form.classId" required min="1" type="number"></label>
          <label>辅导员用户 ID<input v-model.number="form.userId" required min="1" type="number"></label>
          <label>责任类型<select v-model="form.dutyType"><option value="PRIMARY">主辅导员</option><option value="CO">协同辅导员</option><option value="TEMP">临时代班</option></select></label>
          <label>开始日期<input v-model="form.effectiveFrom" type="date"></label>
          <label>截止日期（临时代班必填）<input v-model="form.effectiveTo" type="date"></label>
        </template>
        <template v-else-if="dialog.mode === 'handover'">
          <label>原辅导员<input :value="dialog.row.counselorName + '（' + dialog.row.userId + '）'" disabled></label>
          <label>新主辅导员用户 ID<input v-model.number="form.toUserId" required min="1" type="number"></label>
          <label>当前版本<input :value="dialog.row.version" disabled type="number"></label>
        </template>
        <template v-else><p>结束后保留历史记录；若这是主辅导员，该班级会进入空缺台账。</p></template>
        <label>原因<textarea v-model="form.reason" required maxlength="500"></textarea></label>
        <p v-if="dialogError" class="danger">{{ dialogError }}</p>
        <div class="actions"><button type="button" @click="dialog.visible = false">取消</button><button type="submit" :disabled="submitting">{{ submitting ? '提交中…' : '确认' }}</button></div>
      </form>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSearchBox, AppStatusTag, AppPermissionButton } from '@/components/common'
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
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppStatusTag, AppPermissionButton, AppSearchBox },
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
      this.submitting = true; this.dialogError = ''; let res
      if (this.dialog.mode === 'assign') res = await counselorAssignmentApi.assign(this.form)
      if (this.dialog.mode === 'handover') res = await counselorAssignmentApi.handover(this.dialog.row.classId, { fromUserId: Number(this.dialog.row.userId), toUserId: this.form.toUserId, reason: this.form.reason, version: this.dialog.row.version })
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
.tabs,.toolbar,.actions { display:flex; gap:var(--space-3); align-items:center; flex-wrap:wrap; }
.tab { border:0; background:transparent; padding:var(--space-2) var(--space-3); cursor:pointer; }
.tab.active { color:var(--primary-600); border-bottom:2px solid var(--primary-600); font-weight:var(--font-weight-semibold); }
.toolbar { justify-content:space-between; } .danger { color:var(--danger-600); }
.overlay { position:fixed; inset:0; z-index:50; background:rgba(0,0,0,.45); display:grid; place-items:center; }
.dialog { width:min(520px,calc(100vw - 32px)); padding:24px; border-radius:8px; background:white; display:grid; gap:12px; }
.dialog label { display:grid; gap:6px; } .dialog input,.dialog select,.dialog textarea { width:100%; box-sizing:border-box; padding:8px; }
.actions { justify-content:flex-end; } .danger { color:var(--danger-600); }
</style>
