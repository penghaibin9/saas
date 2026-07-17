<template>
  <ModulePageShell
    title="教学评价 · 教务处控制台"
    :subtitle="'评教批次生命周期 · 学生匿名评教 · 结果分级 · 申诉两级审核'"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="aaev-tabs">
      <button v-for="t in tabs" :key="t.key" :class="['aaev-tab', { 'is-active': tab === t.key }]" @click="switchTab(t.key)">{{ t.label }}</button>
    </div>

    <div v-if="tab === 'batches'" class="mp-stack">
      <div class="aaev-bar"><AppButton variant="primary" size="small" @click="openCreate">新建评教批次</AppButton></div>
      <div class="aaev-layout">
        <ul class="aaev-list">
          <li v-for="b in rows" :key="b.batchId" :class="['aaev-item', { 'is-active': current && current.batchId === b.batchId }]" @click="select(b)">
            <span>{{ b.batchName }}</span>
            <StatusTag :type="bType(b.status)" :label="bLabel(b.status)" dot />
          </li>
        </ul>
        <div class="aaev-detail">
          <EmptyState v-if="!current" title="选择批次" description="从左侧选择评教批次管理生命周期" />
          <template v-else>
            <div class="aaev-head">
              <div><div class="aaev-title">{{ current.batchName }}</div><StatusTag :type="bType(current.status)" :label="bLabel(current.status)" dot /></div>
              <div class="aaev-actions">
                <AppButton v-if="current.status === 'DRAFT'" size="small" variant="ghost" @click="openGenTasks">生成应评任务</AppButton>
                <AppButton v-if="current.status === 'DRAFT'" size="small" variant="primary" @click="lc('publish', '发布')">发布</AppButton>
                <AppButton v-if="current.status === 'PUBLISHED'" size="small" variant="primary" @click="lc('open', '开放评教')">开放</AppButton>
                <AppButton v-if="current.status === 'OPEN'" size="small" variant="warning" @click="lc('closeScore', '关闭核算')">关闭核算</AppButton>
                <AppButton v-if="current.status === 'RESULT_READY'" size="small" variant="primary" @click="lc('publishResults', '发布结果')">发布结果</AppButton>
                <AppButton v-if="current.status === 'RESULT_READY'" size="small" variant="ghost" @click="lc('archive', '归档')">归档</AppButton>
              </div>
            </div>
            <div class="aaev-section-title">应评任务</div>
            <EmptyState v-if="!tasks.length" title="未生成应评任务" description="DRAFT 阶段从教学任务生成" />
            <DataTable v-else :columns="taskColumns" :rows="tasks" row-key="taskId">
              <template #cell-status="{ row }"><StatusTag :type="row.status === 'SUBMITTED' ? 'success' : 'primary'" :label="row.status" dot /></template>
            </DataTable>
            <template v-if="results.length">
              <div class="aaev-section-title">评价结果</div>
              <DataTable :columns="resultColumns" :rows="results" row-key="resultId">
                <template #cell-level="{ row }"><StatusTag :type="lvType(row.level)" :label="lvLabel(row.level)" dot /></template>
              </DataTable>
            </template>
          </template>
        </div>
      </div>
    </div>

    <div v-else class="mp-stack">
      <EmptyState v-if="!appeals.length" title="暂无申诉" description="教师对评价结果申诉后在此审核" />
      <DataTable v-else :columns="appealColumns" :rows="appeals" row-key="appealId">
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'RESOLVED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'primary'" :label="row.status" dot /></template>
        <template #cell-ops="{ row }">
          <button v-if="['SUBMITTED','COLLEGE_REVIEW'].includes(row.status)" class="mp-link" @click="reviewAppeal(row.appealId, 'RESOLVE')">受理</button>
          <button v-if="['SUBMITTED','COLLEGE_REVIEW'].includes(row.status)" class="mp-link is-danger" @click="rejectAppeal(row.appealId)">驳回</button>
        </template>
      </DataTable>
    </div>

    <AppDrawer :visible="createVisible" title="新建评教批次" @close="createVisible = false">
      <div class="aaev-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="form.batchName" placeholder="如 2024秋学生评教" :disabled="saving" /></AppFormItem>
        <AppFormItem label="学期 ID"><AppTextInput v-model="form.termId" placeholder="可空" :disabled="saving" /></AppFormItem>
        <AppInlineAlert type="info" description="问卷模板本期用默认客观5级量表；匿名默认开启（学生评教架构级不留身份）。" />
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="genVisible" title="生成应评任务" @close="genVisible = false">
      <div class="aaev-form">
        <AppFormItem label="评价来源">
          <AppSelect v-model="genType" :options="genTypeOptions" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="教学任务 ID（逗号分隔）" required><AppTextInput v-model="genRaw" placeholder="如 1,2,3" :disabled="saving" /></AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="genVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitGen">生成</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 教学评价 · 教务处控制台（/admin/academic-affairs/evaluation）：批次生命周期 + 结果分级 + 申诉。 */
import { ModulePageShell, DataTable, StatusTag, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppFormItem, AppSelect, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsEvaluationApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _BL = { DRAFT: '草稿', PUBLISHED: '已发布', OPEN: '评教中', CLOSED: '已关闭', RESULT_READY: '结果就绪', ARCHIVED: '已归档' }
const _LV = { EXCELLENT: '优秀', GOOD: '良好', PASS: '合格', NEED_IMPROVE: '需整改' }

export default {
  name: 'AaEvaluationConsoleView',
  components: { ModulePageShell, DataTable, StatusTag, EmptyState, AppButton, AppDrawer, AppTextInput, AppFormItem, AppSelect, AppConfirmDialog, AppInlineAlert },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'batches', tabs: [{ key: 'batches', label: '评教批次' }, { key: 'appeals', label: '申诉审核' }],
      rows: [], current: null, tasks: [], results: [], appeals: [],
      taskColumns: [{ key: 'courseName', title: '课程' }, { key: 'teacherName', title: '教师' }, { key: 'submittedCount', title: '已评' }, { key: 'status', title: '状态' }],
      resultColumns: [{ key: 'teacherName', title: '教师' }, { key: 'courseName', title: '课程' }, { key: 'studentAvg', title: '学生均分' }, { key: 'supervisorAvg', title: '督导' }, { key: 'peerAvg', title: '同行' }, { key: 'selfScore', title: '自评' }, { key: 'compositeScore', title: '综合分' }, { key: 'level', title: '等级' }],
      appealColumns: [{ key: 'teacherKey', title: '教师' }, { key: 'reason', title: '申诉理由' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      createVisible: false, form: { batchName: '', termId: '' }, formError: '',
      genVisible: false, genRaw: '', genType: 'STUDENT',
      genTypeOptions: [
        { label: '学生评教', value: 'STUDENT' }, { label: '教师自评', value: 'SELF' },
        { label: '同行评价', value: 'PEER' }, { label: '督导评价', value: 'SUPERVISOR' }
      ],
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    this.loadBatches()
    if (this.tab === 'appeals') this.loadAppeals()
  },
  methods: {
    bLabel(s) { return _BL[s] || s },
    bType(s) { return s === 'OPEN' ? 'success' : ['ARCHIVED', 'CLOSED'].includes(s) ? 'default' : s === 'RESULT_READY' ? 'warning' : 'primary' },
    lvLabel(l) { return _LV[l] || l || '—' },
    lvType(l) { return l === 'EXCELLENT' ? 'success' : l === 'NEED_IMPROVE' ? 'danger' : 'primary' },
    switchTab(k) { this.tab = k; if (k === 'appeals') this.loadAppeals() },
    async loadBatches() {
      const res = await api.listBatches({ pageSize: 100 })
      this.rows = res.code === 0 ? res.data.list : []
    },
    async select(b) {
      this.current = b
      const [t, r] = await Promise.all([api.listTasks(b.batchId), api.results(b.batchId, { pageSize: 200 })])
      this.tasks = t.code === 0 ? (t.data.items || []) : []
      this.results = r.code === 0 ? r.data.list : []
    },
    async loadAppeals() {
      const res = await api.listAppeals({ pageSize: 100 })
      this.appeals = res.code === 0 ? res.data.list : []
    },
    openCreate() { this.form = { batchName: '', termId: '' }; this.formError = ''; this.createVisible = true },
    async submitCreate() {
      if (!this.form.batchName) { this.formError = '批次名称必填'; return }
      this.saving = true
      const res = await api.createBatch({ batchName: this.form.batchName, termId: this.form.termId || undefined,
        template: { items: [{ q: '教学态度', type: 'scale5' }, { q: '教学效果', type: 'scale5' }] } })
      this.saving = false
      if (res.code === 0) { toast.success('已创建'); this.createVisible = false; this.loadBatches() } else this.formError = res.message
    },
    openGenTasks() { this.genRaw = ''; this.genType = 'STUDENT'; this.genVisible = true },
    async submitGen() {
      const ids = this.genRaw.split(',').map(s => s.trim()).filter(Boolean)
      if (!ids.length) { toast.error('请填教学任务 ID'); return }
      this.saving = true
      const res = await api.genTasks(this.current.batchId, ids, this.genType)
      this.saving = false
      if (res.code === 0) { toast.success(`已生成 ${res.data.taskCount} 条`); this.genVisible = false; this.select(this.current) } else toast.error(res.message)
    },
    lc(fn, label) {
      this.confirmTitle = label; this.confirmMessage = `确认对批次「${this.current.batchName}」执行「${label}」？`
      this.pendingAction = async () => {
        const res = await api[fn](this.current.batchId)
        if (res.code === 0) { toast.success(label + '成功'); await this.loadBatches(); const b = this.rows.find(x => x.batchId === this.current.batchId); if (b) await this.select(b) }
        else toast.error(res.message)
      }
      this.confirmVisible = true
    },
    async reviewAppeal(id, action) {
      const res = await api.reviewAppeal(id, action)
      if (res.code === 0) { toast.success('已受理'); this.loadAppeals() } else toast.error(res.message)
    },
    async rejectAppeal(id) {
      const reason = window.prompt('驳回原因（≥5字）')
      if (!reason || reason.trim().length < 5) { toast.error('原因至少5字'); return }
      const res = await api.reviewAppeal(id, 'REJECT', reason.trim())
      if (res.code === 0) { toast.success('已驳回'); this.loadAppeals() } else toast.error(res.message)
    },
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() }
  }
}
</script>

<style scoped>
.aaev-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; }
.aaev-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aaev-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aaev-bar { margin-bottom: 12px; }
.aaev-layout { display: grid; grid-template-columns: 280px 1fr; gap: 16px; }
.aaev-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaev-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aaev-item.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaev-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.aaev-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.aaev-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aaev-section-title { font-weight: 500; margin: 14px 0 8px; }
.aaev-form { display: flex; flex-direction: column; gap: 12px; }
</style>
