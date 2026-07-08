<template>
  <ModulePageShell
    title="过程指导"
    subtitle="任务书 / 指导记录 / 中期检查 —— 按学生维度查看与处理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="gp-layout">
      <div class="gp-side">
        <input v-model="studentKeyword" class="ie-in" placeholder="搜索学生姓名/学号" @input="searchStudents" />
        <ul class="gp-stu-list">
          <li v-for="s in studentOptions" :key="s.id" class="gp-stu-item" :class="{ 'is-active': current && current.id === s.id }" @click="selectStudent(s)">
            <div class="mp-cell-main">{{ s.name }}</div>
            <div class="mp-cell-sub">{{ s.studentNo }} · {{ s.advisorName || '未分配导师' }} · {{ s.stageLabel }}</div>
          </li>
        </ul>
        <EmptyState v-if="!studentOptions.length" title="未找到学生" description="调整关键词重新搜索" />
      </div>

      <div class="gp-main">
        <template v-if="!current">
          <EmptyState title="请先从左侧选择一名毕设学生" />
        </template>
        <template v-else>
          <div class="gp-tabs">
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'taskbook' }" @click="switchTab('taskbook')">任务书</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'guidance' }" @click="switchTab('guidance')">指导记录</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'midterm' }" @click="switchTab('midterm')">中期检查</button>
          </div>

          <!-- 任务书 -->
          <div v-if="tab === 'taskbook'" class="gp-panel">
            <LoadingState v-if="tbLoading" />
            <template v-else-if="taskbook && taskbook.exists">
              <div class="gp-kv"><span>状态</span><StatusTag :type="taskbook.statusTone" :label="taskbook.statusLabel" dot /></div>
              <div class="gp-kv"><span>版本</span><span>v{{ taskbook.taskbookVersion }}</span></div>
              <div class="gp-kv"><span>任务目标</span><span>{{ taskbook.objective }}</span></div>
              <div class="gp-kv"><span>任务内容</span><span>{{ taskbook.content }}</span></div>
              <div class="gp-kv"><span>进度计划</span><span>{{ taskbook.progressPlan || '—' }}</span></div>
              <div class="gp-kv"><span>成果要求</span><span>{{ taskbook.outcomeRequirement || '—' }}</span></div>
              <div class="gp-kv"><span>下达时间</span><AppDateDisplay :value="taskbook.issuedAt || taskbook.createdAt" mode="datetime" /></div>
              <div class="gp-kv"><span>截止时间</span><AppDateDisplay :value="taskbook.deadline" mode="deadline" /></div>
              <div class="ie-actions">
                <button v-if="taskbook.status !== 'CONFIRMED'" class="mp-btn mp-btn--primary" @click="doConfirmTaskbook">学生确认</button>
                <button v-if="taskbook.status === 'CONFIRMED'" class="mp-btn" @click="openChangeTaskbook">发起变更</button>
              </div>
              <div v-if="taskbook.history && taskbook.history.length" class="gp-history">
                <div class="gm-section-title">历史版本</div>
                <div v-for="h in taskbook.history" :key="h.version" class="gp-history-item">v{{ h.version }}：{{ h.objective }}</div>
              </div>
            </template>
            <template v-else>
              <EmptyState title="尚未下达任务书" description="点「下达任务书」为该生下达" />
              <div class="ie-actions"><button class="mp-btn mp-btn--primary" @click="openIssueTaskbook">下达任务书</button></div>
            </template>
          </div>

          <!-- 指导记录 -->
          <div v-if="tab === 'guidance'" class="gp-panel">
            <div class="ie-actions" style="justify-content: flex-start; margin-bottom: var(--space-3)"><button class="mp-btn mp-btn--primary" @click="openGuidanceCreate">＋ 新增指导记录</button></div>
            <LoadingState v-if="guidanceLoading" />
            <EmptyState v-else-if="!guidanceList.length" title="暂无指导记录" />
            <ul v-else class="gp-timeline">
              <li v-for="g in guidanceList" :key="g.id" class="gp-timeline-item">
                <div class="mp-cell-main"><AppDateDisplay :value="g.guidanceDate" mode="datetime" /> · {{ g.methodLabel }}</div>
                <div class="mp-cell-sub">{{ g.content }}</div>
                <div v-if="g.issues" class="gp-issue">问题：{{ g.issues }}</div>
              </li>
            </ul>
          </div>

          <!-- 中期检查 -->
          <div v-if="tab === 'midterm'" class="gp-panel">
            <LoadingState v-if="mtLoading" />
            <template v-else-if="midterm">
              <div class="gp-kv"><span>状态</span><StatusTag :type="midterm.statusTone" :label="midterm.statusLabel" dot /></div>
              <div v-if="midterm.conclusion" class="gp-kv"><span>结论</span><span>{{ midterm.conclusionLabel }}</span></div>
              <div v-if="midterm.checkComment" class="gp-kv"><span>检查意见</span><span>{{ midterm.checkComment }}</span></div>
              <div v-if="midterm.rectifyContent" class="gp-kv"><span>整改内容</span><span>{{ midterm.rectifyContent }}</span></div>
              <div class="gp-kv"><span>检查时间</span><AppDateDisplay :value="midterm.checkedAt || midterm.checkAt" mode="datetime" /></div>
              <div v-if="midterm.rectifyDeadline" class="gp-kv"><span>整改截止</span><AppDateDisplay :value="midterm.rectifyDeadline" mode="deadline" /></div>
              <div class="ie-actions">
                <button v-if="['PENDING', 'RECTIFIED_PASS', 'CHECKED_FAIL'].includes(midterm.status)" class="mp-btn mp-btn--primary" @click="openMidtermCheck">发起中期检查</button>
                <button v-if="midterm.status === 'RECTIFYING'" class="mp-btn" @click="openRectifySubmit">提交整改</button>
                <button v-if="midterm.status === 'RECTIFY_SUBMITTED'" class="mp-btn mp-btn--primary" @click="doReviewRectify('PASS')">整改复核通过</button>
                <button v-if="midterm.status === 'RECTIFY_SUBMITTED'" class="mp-btn mp-link--danger" @click="doReviewRectify('FAIL')">复核不通过</button>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>

    <!-- 下达/变更任务书 -->
    <AppDrawer v-model:visible="tbFormVisible" :title="tbFormMode === 'change' ? '变更任务书' : '下达任务书'">
      <form class="ie-form" @submit.prevent="submitTaskbookForm">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">任务目标 <i>*</i></span><textarea v-model.trim="tbForm.objective" class="ie-in" rows="2" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">任务内容 <i>*</i></span><textarea v-model.trim="tbForm.content" class="ie-in" rows="2" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">进度计划</span><textarea v-model.trim="tbForm.progressPlan" class="ie-in" rows="2" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">成果要求</span><textarea v-model.trim="tbForm.outcomeRequirement" class="ie-in" rows="2" /></label>
        <label v-if="tbFormMode === 'change'" class="ie-fld ie-fld--full"><span class="ie-lbl">变更原因（≥5字）<i>*</i></span><textarea v-model.trim="tbForm.reason" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="tbFormVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 新增指导记录 -->
    <AppDrawer v-model:visible="guidanceFormVisible" title="新增指导记录">
      <form class="ie-form" @submit.prevent="submitGuidanceForm">
        <label class="ie-fld"><span class="ie-lbl">指导方式</span>
          <select v-model="guidanceForm.method" class="ie-in"><option value="ONLINE">线上</option><option value="OFFLINE">线下</option></select>
        </label>
        <AppDateTimePicker v-model="guidanceForm.guidanceDate" class="ie-fld" label="指导时间" hint="默认当前时间" />
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">指导内容 <i>*</i></span><textarea v-model.trim="guidanceForm.content" class="ie-in" rows="2" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">发现的问题</span><textarea v-model.trim="guidanceForm.issues" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="guidanceFormVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 中期检查 -->
    <AppDrawer v-model:visible="mtFormVisible" title="发起中期检查">
      <form class="ie-form" @submit.prevent="submitMidtermCheck">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">结论 <i>*</i></span>
          <select v-model="mtForm.conclusion" class="ie-in">
            <option value="PASS">通过</option><option value="RECTIFY">限期整改</option><option value="FAIL">不通过</option>
          </select>
        </label>
        <AppDeadlinePicker v-if="mtForm.conclusion === 'RECTIFY'" v-model="mtForm.rectifyDeadline" class="ie-fld ie-fld--full" label="整改截止日期" hint="限期整改默认 23:59" />
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">检查意见</span><textarea v-model.trim="mtForm.comment" class="ie-in" rows="2" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="mtFormVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">提交</button>
        </div>
      </form>
    </AppDrawer>

    <!-- 提交整改 -->
    <AppDrawer v-model:visible="rectifyVisible" title="提交整改">
      <form class="ie-form" @submit.prevent="submitRectifyForm">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">整改内容 <i>*</i></span><textarea v-model.trim="rectifyContent" class="ie-in" rows="3" /></label>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="rectifyVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">提交</button>
        </div>
      </form>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 过程指导（/admin/graduation/process）：任务书下达/确认/变更 + 指导记录时间线 + 中期检查三档结论/整改闭环。 */
import { ModulePageShell, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import { AppDateTimePicker, AppDeadlinePicker, AppDateDisplay } from '@/components/common/date'
import { graduationTaskbookApi } from '@/modules/graduation/api/graduation-taskbook.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'
import { toDateTimeInputValue, daysFromNowDeadline } from '@/utils/dateUtils'

export default {
  name: 'GraduationProcessView',
  components: { ModulePageShell, StatusTag, LoadingState, EmptyState, AppDrawer, AppDateTimePicker, AppDeadlinePicker, AppDateDisplay },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      studentKeyword: '', studentOptions: [], current: null, tab: 'taskbook', submitting: false, formError: '',
      taskbook: null, tbLoading: false,
      guidanceList: [], guidanceLoading: false,
      midterm: null, mtLoading: false,
      tbFormVisible: false, tbFormMode: 'issue', tbForm: { objective: '', content: '', progressPlan: '', outcomeRequirement: '', reason: '' },
      guidanceFormVisible: false, guidanceForm: { method: 'ONLINE', guidanceDate: '', content: '', issues: '' },
      mtFormVisible: false, mtForm: { conclusion: 'PASS', comment: '', rectifyDeadline: '' },
      rectifyVisible: false, rectifyContent: ''
    }
  },
  created() {
    this.tab = ['taskbook', 'guidance', 'midterm'].includes(this.$route.query.panel) ? this.$route.query.panel : 'taskbook'
    this.searchStudents()
  },
  methods: {
    async searchStudents() {
      const res = await gdStudentApi.getStudents({ keyword: this.studentKeyword, pageSize: 20 })
      this.studentOptions = res.code === 0 ? res.data.list : []
    },
    selectStudent(s) {
      this.current = s
      this.loadAll()
    },
    switchTab(t) {
      this.tab = t
      this.$router.replace({ query: { ...this.$route.query, panel: t } })
    },
    async loadAll() {
      await Promise.all([this.loadTaskbook(), this.loadGuidance(), this.loadMidterm()])
    },
    async loadTaskbook() {
      this.tbLoading = true
      const res = await graduationTaskbookApi.getTaskbook(this.current.id)
      this.taskbook = res.code === 0 ? res.data : null
      this.tbLoading = false
    },
    async loadGuidance() {
      this.guidanceLoading = true
      const res = await graduationTaskbookApi.getGuidanceList({ gdStudentId: this.current.id, pageSize: 50 })
      this.guidanceList = res.code === 0 ? res.data.list : []
      this.guidanceLoading = false
    },
    async loadMidterm() {
      this.mtLoading = true
      const res = await graduationTaskbookApi.getMidterm(this.current.id)
      this.midterm = res.code === 0 ? res.data : null
      this.mtLoading = false
    },
    openIssueTaskbook() {
      this.tbFormMode = 'issue'
      this.tbForm = { objective: '', content: '', progressPlan: '', outcomeRequirement: '', reason: '' }
      this.formError = ''; this.tbFormVisible = true
    },
    openChangeTaskbook() {
      this.tbFormMode = 'change'
      this.tbForm = { objective: this.taskbook.objective, content: this.taskbook.content, progressPlan: this.taskbook.progressPlan, outcomeRequirement: this.taskbook.outcomeRequirement, reason: '' }
      this.formError = ''; this.tbFormVisible = true
    },
    async submitTaskbookForm() {
      this.formError = ''
      if (this.tbFormMode === 'change' && this.tbForm.reason.length < 5) { this.formError = '变更原因至少 5 字'; return }
      this.submitting = true
      try {
        const res = this.tbFormMode === 'change'
          ? await graduationTaskbookApi.changeTaskbook(this.current.id, this.tbForm)
          : await graduationTaskbookApi.issueTaskbook(this.current.id, this.tbForm)
        if (res.code === 0) { toast.success('已保存'); this.tbFormVisible = false; this.loadTaskbook() } else this.formError = res.message
      } finally { this.submitting = false }
    },
    async doConfirmTaskbook() {
      const res = await graduationTaskbookApi.confirmTaskbook(this.current.id)
      if (res.code === 0) { toast.success('已确认'); this.loadTaskbook() } else toast.error(res.message)
    },
    openGuidanceCreate() {
      this.guidanceForm = { method: 'ONLINE', guidanceDate: toDateTimeInputValue(new Date()), content: '', issues: '' }
      this.formError = ''; this.guidanceFormVisible = true
    },
    async submitGuidanceForm() {
      this.formError = ''
      if (!this.guidanceForm.content) { this.formError = '指导内容必填'; return }
      this.submitting = true
      try {
        const res = await graduationTaskbookApi.createGuidance(this.current.id, this.guidanceForm)
        if (res.code === 0) { toast.success('已记录'); this.guidanceFormVisible = false; this.loadGuidance() } else this.formError = res.message
      } finally { this.submitting = false }
    },
    openMidtermCheck() {
      this.mtForm = { conclusion: 'PASS', comment: '', rectifyDeadline: daysFromNowDeadline(7) }
      this.formError = ''; this.mtFormVisible = true
    },
    async submitMidtermCheck() {
      this.submitting = true
      try {
        const payload = {
          ...this.mtForm,
          rectifyDeadline: this.mtForm.rectifyDeadline
            ? (String(this.mtForm.rectifyDeadline).slice(0, 10))
            : ''
        }
        const res = await graduationTaskbookApi.checkMidterm(this.current.id, payload)
        if (res.code === 0) { toast.success('已提交'); this.mtFormVisible = false; this.loadMidterm() } else this.formError = res.message
      } finally { this.submitting = false }
    },
    openRectifySubmit() {
      this.rectifyContent = ''; this.formError = ''; this.rectifyVisible = true
    },
    async submitRectifyForm() {
      if (!this.rectifyContent) { this.formError = '整改内容必填'; return }
      this.submitting = true
      try {
        const res = await graduationTaskbookApi.submitRectification(this.current.id, this.rectifyContent)
        if (res.code === 0) { toast.success('已提交整改'); this.rectifyVisible = false; this.loadMidterm() } else this.formError = res.message
      } finally { this.submitting = false }
    },
    async doReviewRectify(action) {
      const res = await graduationTaskbookApi.reviewRectification(this.current.id, { action })
      if (res.code === 0) { toast.success('已复核'); this.loadMidterm() } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gp-layout { display: flex; gap: var(--space-4); align-items: flex-start; }
.gp-side { width: 280px; flex: none; }
.gp-main { flex: 1; min-width: 0; }
.gp-stu-list { list-style: none; margin: var(--space-2) 0 0; padding: 0; max-height: 560px; overflow-y: auto; }
.gp-stu-item { padding: 8px 10px; border-radius: 8px; cursor: pointer; border: 1px solid transparent; }
.gp-stu-item:hover { background: var(--bg2, #f8fafc); }
.gp-stu-item.is-active { background: var(--pri-bg, #eff6ff); border-color: var(--pri, #2563eb); }
.gp-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); }
.gp-tabs__item { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.gp-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.gp-panel { font-size: 13px; }
.gp-kv { display: flex; gap: var(--space-3); padding: 6px 0; border-bottom: 1px dashed var(--line, #eef1f6); }
.gp-kv > span:first-child { width: 90px; flex: none; color: var(--t3, #64748b); }
.gp-history { margin-top: var(--space-3); }
.gp-history-item { padding: 4px 0; color: var(--t3, #64748b); }
.gp-timeline { list-style: none; margin: 0; padding: 0; }
.gp-timeline-item { padding: 10px 0; border-bottom: 1px dashed var(--line, #eef1f6); }
.gp-issue { color: var(--danger, #dc2626); font-size: 12px; margin-top: 4px; }
.gm-section-title { font-size: 13px; font-weight: 600; margin-bottom: 6px; }
.ie-form { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); padding: var(--space-1) 0; }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-err { grid-column: 1 / -1; color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.mp-link--danger { color: var(--danger, #dc2626); border-color: var(--danger, #dc2626); }
</style>
