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

    <div v-else-if="tab === 'studentEval'" class="mp-stack">
      <AppInlineAlert type="info" description="学生评教全部经小程序匿名提交（本轮不建小程序端），此处为教务处 PC 侧查看入口：按批次查看学生评教参评进度与课程明细，不提供提交能力。" />
      <AppFormItem label="选择批次">
        <AppSelect v-model="seBatchId" :options="batchOptions" placeholder="请选择评教批次" @change="loadStudentEval" />
      </AppFormItem>
      <EmptyState v-if="!seBatchId" title="请选择批次" description="选择后查看学生评教参评情况" />
      <template v-else>
        <div class="aaev-metrics">
          <div class="aaev-metric"><span class="aaev-metric-v">{{ seParticipation.total || 0 }}</span><span class="aaev-metric-l">应评课程数</span></div>
          <div class="aaev-metric"><span class="aaev-metric-v">{{ seParticipation.submitted || 0 }}</span><span class="aaev-metric-l">已有学生提交</span></div>
          <div class="aaev-metric"><span class="aaev-metric-v">{{ seParticipation.rate || 0 }}%</span><span class="aaev-metric-l">课程覆盖率</span></div>
        </div>
        <EmptyState v-if="!seTasks.length" title="暂无学生评教任务" description="批次 DRAFT 阶段从教学任务生成应评任务" />
        <DataTable v-else :columns="taskColumns" :rows="seTasks" row-key="taskId">
          <template #cell-status="{ row }"><StatusTag :type="row.status === 'SUBMITTED' ? 'success' : 'primary'" :label="row.status" dot /></template>
        </DataTable>
      </template>
    </div>

    <div v-else-if="['selfEval', 'peerEval', 'supervisorEval'].includes(tab)" class="mp-stack">
      <AppInlineAlert type="info" :description="roleTip" />
      <div class="aaev-section-title">我的待评任务</div>
      <EmptyState v-if="!myRoleRows.length" title="暂无待评任务" :description="`未查到分配给本人的${roleLabel}任务`" />
      <DataTable v-else :columns="myRoleColumns" :rows="myRoleRows" row-key="taskId">
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'SUBMITTED' ? 'success' : 'primary'" :label="row.status" dot /></template>
        <template #cell-ops="{ row }">
          <button v-if="row.status === 'PENDING' && row.batchStatus === 'OPEN'" class="mp-link" @click="openRoleSubmit(row)">提交评价</button>
        </template>
      </DataTable>
      <div class="aaev-section-title">教务处：生成应评任务</div>
      <div class="aaev-bar">
        <AppButton size="small" variant="primary" @click="openRoleGen">生成{{ roleLabel }}任务</AppButton>
      </div>
    </div>

    <div v-else-if="tab === 'evalStats'" class="mp-stack">
      <AppFormItem label="选择批次">
        <AppSelect v-model="stBatchId" :options="batchOptions" placeholder="请选择评教批次" @change="loadStatsTab" />
      </AppFormItem>
      <EmptyState v-if="!stBatchId" title="请选择批次" description="选择后查看结果分级与各评价类型参评率" />
      <template v-else>
        <div class="aaev-bar">
          <AppButton size="small" variant="secondary" :loading="exporting" @click="openExport('stats')">导出参评统计</AppButton>
          <AppButton size="small" variant="secondary" :loading="exporting" @click="openExport('results')">导出评价结果</AppButton>
        </div>
        <div class="aaev-metrics">
          <div class="aaev-metric"><span class="aaev-metric-v">{{ stData.resultCount || 0 }}</span><span class="aaev-metric-l">结果条数</span></div>
          <div class="aaev-metric"><span class="aaev-metric-v">{{ stData.overallAvg ?? '—' }}</span><span class="aaev-metric-l">学生评教总均分</span></div>
        </div>
        <div class="aaev-section-title">结果分级分布</div>
        <EmptyState v-if="!levelRows.length" title="暂无分级数据" description="批次关闭核算后生成" />
        <DataTable v-else :columns="levelColumns" :rows="levelRows" row-key="level" />
        <div class="aaev-section-title">按评价类型参评率</div>
        <EmptyState v-if="!participationRows.length" title="暂无参评数据" description="生成应评任务后统计" />
        <DataTable v-else :columns="participationColumns" :rows="participationRows" row-key="type" />
      </template>
    </div>

    <div v-else-if="tab === 'archive'" class="mp-stack">
      <div class="aaev-layout">
        <ul class="aaev-list">
          <EmptyState v-if="!archiveRows.length" title="暂无已归档批次" description="批次结果就绪后可归档，归档后只读" />
          <li v-for="b in archiveRows" :key="b.batchId" :class="['aaev-item', { 'is-active': archiveCurrent && archiveCurrent.batchId === b.batchId }]" @click="selectArchive(b)">
            <span>{{ b.batchName }}</span>
            <StatusTag type="default" label="已归档" dot />
          </li>
        </ul>
        <div class="aaev-detail">
          <EmptyState v-if="!archiveCurrent" title="选择归档批次" description="查看该批次的评价结果快照（只读）" />
          <template v-else>
            <div class="aaev-head">
              <div><div class="aaev-title">{{ archiveCurrent.batchName }}</div><StatusTag type="default" label="已归档" dot /></div>
              <div class="aaev-actions">
                <AppButton size="small" variant="secondary" :loading="exporting" @click="openExport('results', true)">导出结果</AppButton>
              </div>
            </div>
            <EmptyState v-if="!archiveResults.length" title="无评价结果" description="该批次未生成或未发布结果" />
            <DataTable v-else :columns="resultColumns" :rows="archiveResults" row-key="resultId">
              <template #cell-level="{ row }"><StatusTag :type="lvType(row.level)" :label="lvLabel(row.level)" dot /></template>
            </DataTable>
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
        <AppFormItem label="教学任务 ID（逗号分隔）" required><AppTextInput v-model="genRaw" placeholder="如 1,2,3" :disabled="saving" /></AppFormItem>
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="genVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitGen">生成</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="roleGenVisible" :title="`生成${roleLabel}任务`" @close="roleGenVisible = false">
      <div class="aaev-form">
        <AppFormItem label="选择批次（仅 DRAFT）" required>
          <AppSelect v-model="roleGenBatchId" :options="draftBatchOptions" placeholder="请选择草稿批次" />
        </AppFormItem>
        <AppFormItem :label="roleAssignLabel" required>
          <AppTextarea v-model="roleGenRaw" :rows="4" :placeholder="roleAssignPlaceholder" :disabled="saving" />
        </AppFormItem>
        <AppInlineAlert type="info" description="每行一条：教学任务ID,评价人工号（教师自评可省略评价人工号，默认=授课教师本人）。" />
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="roleGenVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitRoleGen">生成</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="roleSubmitVisible" :title="`提交${roleLabel}`" @close="roleSubmitVisible = false">
      <div class="aaev-form">
        <AppFormItem label="课程/对象"><span>{{ roleSubmitRow && roleSubmitRow.courseName }}（{{ roleSubmitRow && roleSubmitRow.teacherName }}）</span></AppFormItem>
        <AppFormItem label="客观评分（0-100）" required><AppNumberInput v-model="roleSubmitForm.objectiveScore" :min="0" :max="100" :disabled="saving" /></AppFormItem>
        <AppFormItem label="评语" required><AppTextarea v-model="roleSubmitForm.comment" :rows="3" placeholder="请输入评语" :disabled="saving" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving" @click="roleSubmitVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitRoleSubmit">提交</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="exportVisible" title="导出 xlsx" @close="exportVisible = false">
      <div class="aaev-form">
        <AppFormItem label="导出用途" required><AppTextInput v-model="exportPurpose" placeholder="如 学期教学质量归档核对（≥5字，写审计）" :disabled="exporting" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="exporting" @click="exportVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="exporting" @click="doExport">导出</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
/** 教学评价 · 教务处控制台（/admin/academic-affairs/evaluation）：批次生命周期 + 结果分级 + 申诉 +
 *  学生评教查看 + 教师自评/同行评价/督导评价（生成任务+本人提交）+ 评价统计 + 评价归档。 */
import { ModulePageShell, DataTable, StatusTag, EmptyState } from '@/components/business'
import { AppButton, AppDrawer } from '@/components/ui'
import { AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert } from '@/components/common'
import { academicAffairsApi, academicAffairsEvaluationApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

const _BL = { DRAFT: '草稿', PUBLISHED: '已发布', OPEN: '评教中', CLOSED: '已关闭', RESULT_READY: '结果就绪', ARCHIVED: '已归档' }
const _LV = { EXCELLENT: '优秀', GOOD: '良好', PASS: '合格', NEED_IMPROVE: '需整改' }
const _ROLE_TYPE = { selfEval: 'SELF', peerEval: 'PEER', supervisorEval: 'SUPERVISOR' }
const _ROLE_LABEL = { selfEval: '教师自评', peerEval: '同行评价', supervisorEval: '督导评价' }

export default {
  name: 'AaEvaluationConsoleView',
  components: { ModulePageShell, DataTable, StatusTag, EmptyState, AppButton, AppDrawer, AppTextInput, AppNumberInput, AppTextarea, AppSelect, AppFormItem, AppConfirmDialog, AppInlineAlert },
  data() {
    return {
      ctx: { currentRole: { roleName: '' }, dataScope: { scopeName: '' } },
      tab: 'batches',
      tabs: [
        { key: 'batches', label: '评教批次' },
        { key: 'studentEval', label: '学生评教' },
        { key: 'selfEval', label: '教师自评' },
        { key: 'peerEval', label: '同行评价' },
        { key: 'supervisorEval', label: '督导评价' },
        { key: 'evalStats', label: '评价统计' },
        { key: 'archive', label: '评价归档' },
        { key: 'appeals', label: '申诉审核' }
      ],
      rows: [], current: null, tasks: [], results: [], appeals: [],
      taskColumns: [{ key: 'courseName', title: '课程' }, { key: 'teacherName', title: '教师' }, { key: 'submittedCount', title: '已评' }, { key: 'status', title: '状态' }],
      resultColumns: [{ key: 'teacherName', title: '教师' }, { key: 'courseName', title: '课程' }, { key: 'studentAvg', title: '均分' }, { key: 'studentCount', title: '评价数' }, { key: 'level', title: '等级' }],
      appealColumns: [{ key: 'teacherKey', title: '教师' }, { key: 'reason', title: '申诉理由' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      createVisible: false, form: { batchName: '', termId: '' }, formError: '',
      genVisible: false, genRaw: '',
      saving: false, confirmVisible: false, confirmTitle: '', confirmMessage: '', pendingAction: null,
      // 学生评教（PC 查看）
      seBatchId: '', seTasks: [], seParticipation: {},
      // 教师自评/同行评价/督导评价
      myRoleRows: [], myRoleColumns: [{ key: 'courseName', title: '课程' }, { key: 'teacherName', title: '被评教师' }, { key: 'batchStatus', title: '批次状态' }, { key: 'status', title: '状态' }, { key: 'ops', title: '操作' }],
      roleGenVisible: false, roleGenBatchId: '', roleGenRaw: '',
      roleSubmitVisible: false, roleSubmitRow: null, roleSubmitForm: { objectiveScore: null, comment: '' },
      // 评价统计
      stBatchId: '', stData: {},
      levelColumns: [{ key: 'level', title: '等级' }, { key: 'count', title: '人数' }],
      participationColumns: [{ key: 'type', title: '评价类型' }, { key: 'total', title: '应评数' }, { key: 'submitted', title: '已评数' }, { key: 'rate', title: '参评率(%)' }],
      // 评价归档
      archiveRows: [], archiveCurrent: null, archiveResults: [],
      // 导出
      exportVisible: false, exportDomain: '', exportBid: '', exportPurpose: '', exporting: false
    }
  },
  computed: {
    batchOptions() { return this.rows.map((b) => ({ label: b.batchName, value: b.batchId })) },
    draftBatchOptions() { return this.rows.filter((b) => b.status === 'DRAFT').map((b) => ({ label: b.batchName, value: b.batchId })) },
    roleType() { return _ROLE_TYPE[this.tab] || '' },
    roleLabel() { return _ROLE_LABEL[this.tab] || '' },
    roleTip() {
      return this.tab === 'selfEval' ? '教师对本人教学的自我评价（轻量记录，非匿名）。教务处按教学任务生成任务后，教师本人在此提交。'
        : this.tab === 'peerEval' ? '同专业/同课程教师互评（轻量记录，非匿名）。教务处指定同行评价人后，被指定教师在此提交。'
          : '教学督导对授权范围内教师的评价（轻量记录，非匿名）。本项目暂未建独立督导角色/数据范围，评价人按登录身份与任务指定的评价人工号匹配核验（design gap，见二级施工包 D-07）。'
    },
    roleAssignLabel() { return this.tab === 'selfEval' ? '教学任务ID（每行一条，可选填评价人工号）' : '教学任务ID,评价人工号（每行一条，均必填）' },
    roleAssignPlaceholder() { return this.tab === 'selfEval' ? '1\n2,counselor01' : '1,peer01\n2,peer02' },
    levelRows() { return Object.entries(this.stData.byLevel || {}).map(([level, count]) => ({ level: _LV[level] || level, count })) },
    participationRows() {
      return Object.entries(this.stData.participation || {}).map(([type, v]) => ({ type, total: v.total, submitted: v.submitted, rate: v.rate }))
    }
  },
  async created() {
    const c = await academicAffairsApi.getContext()
    if (c.code === 0) this.ctx = c.data
    const q = this.$route && this.$route.query && this.$route.query.tab
    if (q && this.tabs.some((t) => t.key === q)) this.tab = q
    await this.loadBatches()
    this.afterTabLoad()
  },
  methods: {
    bLabel(s) { return _BL[s] || s },
    bType(s) { return s === 'OPEN' ? 'success' : ['ARCHIVED', 'CLOSED'].includes(s) ? 'default' : s === 'RESULT_READY' ? 'warning' : 'primary' },
    lvLabel(l) { return _LV[l] || l || '—' },
    lvType(l) { return l === 'EXCELLENT' ? 'success' : l === 'NEED_IMPROVE' ? 'danger' : 'primary' },
    switchTab(k) { this.tab = k; this.afterTabLoad() },
    afterTabLoad() {
      if (this.tab === 'appeals') this.loadAppeals()
      else if (['selfEval', 'peerEval', 'supervisorEval'].includes(this.tab)) this.loadMyRoleTasks()
      else if (this.tab === 'archive') this.loadArchive()
    },
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
    openGenTasks() { this.genRaw = ''; this.genVisible = true },
    async submitGen() {
      const ids = this.genRaw.split(',').map(s => s.trim()).filter(Boolean)
      if (!ids.length) { toast.error('请填教学任务 ID'); return }
      this.saving = true
      const res = await api.genTasks(this.current.batchId, ids)
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
    onConfirm() { const a = this.pendingAction; this.pendingAction = null; if (a) a() },

    // ── 学生评教（PC 查看） ──
    async loadStudentEval() {
      if (!this.seBatchId) return
      const [t, s] = await Promise.all([api.listTasks(this.seBatchId, { evaluatorType: 'STUDENT' }), api.stats(this.seBatchId)])
      this.seTasks = t.code === 0 ? (t.data.items || []) : []
      this.seParticipation = s.code === 0 ? (s.data.participation && s.data.participation.STUDENT) || {} : {}
    },

    // ── 教师自评/同行评价/督导评价 ──
    async loadMyRoleTasks() {
      const res = await api.myRoleTasks(this.roleType)
      this.myRoleRows = res.code === 0 ? (res.data.items || []) : []
    },
    openRoleGen() { this.roleGenBatchId = ''; this.roleGenRaw = ''; this.formError = ''; this.roleGenVisible = true },
    async submitRoleGen() {
      if (!this.roleGenBatchId) { this.formError = '请选择批次'; return }
      const lines = this.roleGenRaw.split('\n').map(s => s.trim()).filter(Boolean)
      if (!lines.length) { this.formError = '请至少填写一条'; return }
      const assignments = []
      for (const line of lines) {
        const [teachingTaskId, evaluatorKey] = line.split(',').map(s => (s || '').trim())
        if (!teachingTaskId) continue
        if (this.tab !== 'selfEval' && !evaluatorKey) { this.formError = `${this.roleLabel}每行必须填写评价人工号：${line}`; return }
        assignments.push({ teachingTaskId, evaluatorKey: evaluatorKey || undefined })
      }
      this.saving = true
      const res = await api.genRoleTasks(this.roleGenBatchId, this.roleType, assignments)
      this.saving = false
      if (res.code === 0) { toast.success(`已生成 ${res.data.taskCount} 条`); this.roleGenVisible = false; this.loadMyRoleTasks() } else this.formError = res.message
    },
    openRoleSubmit(row) { this.roleSubmitRow = row; this.roleSubmitForm = { objectiveScore: null, comment: '' }; this.formError = ''; this.roleSubmitVisible = true },
    async submitRoleSubmit() {
      if (this.roleSubmitForm.objectiveScore === null || this.roleSubmitForm.objectiveScore === '') { this.formError = '客观评分必填'; return }
      if (!this.roleSubmitForm.comment || !this.roleSubmitForm.comment.trim()) { this.formError = '评语必填'; return }
      this.saving = true
      const res = await api.submit({ taskId: this.roleSubmitRow.taskId, objectiveScore: Number(this.roleSubmitForm.objectiveScore), comment: this.roleSubmitForm.comment.trim() })
      this.saving = false
      if (res.code === 0) { toast.success('已提交'); this.roleSubmitVisible = false; this.loadMyRoleTasks() } else this.formError = res.message
    },

    // ── 评价统计 ──
    async loadStatsTab() {
      if (!this.stBatchId) return
      const res = await api.stats(this.stBatchId)
      this.stData = res.code === 0 ? res.data : {}
    },

    // ── 评价归档 ──
    async loadArchive() {
      const res = await api.archivedBatches({ pageSize: 100 })
      this.archiveRows = res.code === 0 ? res.data.list : []
    },
    async selectArchive(b) {
      this.archiveCurrent = b
      const r = await api.results(b.batchId, { pageSize: 200 })
      this.archiveResults = r.code === 0 ? r.data.list : []
    },

    // ── 导出 ──
    openExport(domain, fromArchive) {
      this.exportDomain = domain
      this.exportBid = fromArchive ? (this.archiveCurrent && this.archiveCurrent.batchId) : (this.tab === 'evalStats' ? this.stBatchId : this.seBatchId)
      if (!this.exportBid) { toast.error('请先选择批次'); return }
      this.exportPurpose = ''; this.formError = ''; this.exportVisible = true
    },
    async doExport() {
      if (!this.exportPurpose || this.exportPurpose.trim().length < 5) { this.formError = '用途至少5字'; return }
      this.exporting = true
      const res = await api.exportEvaluation(this.exportBid, this.exportDomain, this.exportPurpose.trim())
      this.exporting = false
      if (res.code === 0) {
        const url = URL.createObjectURL(res.data)
        const a = document.createElement('a'); a.href = url; a.download = `evaluation_${this.exportDomain}_${this.exportBid}.xlsx`; a.click()
        URL.revokeObjectURL(url)
        toast.success('已导出'); this.exportVisible = false
      } else this.formError = res.message
    }
  }
}
</script>

<style scoped>
.aaev-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 16px; flex-wrap: wrap; }
.aaev-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aaev-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aaev-bar { margin-bottom: 12px; display: flex; gap: 8px; }
.aaev-layout { display: grid; grid-template-columns: 280px 1fr; gap: 16px; }
.aaev-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aaev-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aaev-item.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-bg, #eff6ff); }
.aaev-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.aaev-title { font-size: 16px; font-weight: 600; margin-bottom: 4px; }
.aaev-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aaev-section-title { font-weight: 500; margin: 14px 0 8px; }
.aaev-form { display: flex; flex-direction: column; gap: 12px; }
.aaev-metrics { display: flex; gap: 24px; margin-bottom: 16px; }
.aaev-metric { display: flex; flex-direction: column; align-items: flex-start; }
.aaev-metric-v { font-size: 24px; font-weight: 700; color: var(--text-primary, #0f172a); }
.aaev-metric-l { font-size: 12px; color: var(--text-secondary, #64748b); }
</style>
