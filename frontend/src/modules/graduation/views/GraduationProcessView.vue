<template>
  <ModulePageShell
    title="过程指导"
    subtitle="任务书 / 指导记录 / 中期检查 —— 按学生维度查看与处理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <GraduationBatchStrip />
    <div class="gp-layout">
      <div class="gp-side">
        <input v-model="studentKeyword" class="ie-in" placeholder="搜索学生姓名/学号" @input="searchStudents" />
        <ul class="gp-stu-list">
          <li v-for="s in studentOptions" :key="s.id" class="gp-stu-item" :class="{ 'is-active': current && current.id === s.id }" @click="selectStudent(s)">
            <div class="mp-cell-main">{{ s.name }}</div>
            <div class="mp-cell-sub">{{ s.studentNo }} · {{ s.advisorName || '未分配导师' }} · {{ s.stageLabel }}</div>
          </li>
        </ul>
        <ErrorState v-if="sideError" :description="sideError" @retry="searchStudents" />
        <EmptyState v-else-if="!studentOptions.length" title="未找到学生" description="调整关键词重新搜索" />
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

          <ErrorState v-if="loadError" :description="loadError" @retry="loadAll" />

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

  </ModulePageShell>
</template>

<script>
/** 过程指导（/admin/graduation/process）：任务书下达/确认/变更 + 指导记录时间线 + 中期检查三档结论/整改闭环。 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDateDisplay } from '@/components/common/date'
import { graduationTaskbookApi } from '@/modules/graduation/api/graduation-taskbook.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationProcessView',
  components: { GraduationBatchStrip, ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      studentKeyword: '', studentOptions: [], current: null, tab: 'taskbook', submitting: false,
      sideError: '', loadError: '',
      taskbook: null, tbLoading: false,
      guidanceList: [], guidanceLoading: false,
      midterm: null, mtLoading: false
    }
  },
  created() {
    this.tab = ['taskbook', 'guidance', 'midterm'].includes(this.$route.query.panel) ? this.$route.query.panel : 'taskbook'
    this.searchStudents()
  },
  watch: {
    // 应用内点左侧三级菜单（同路由不同 ?panel=）时组件被复用，必须监听 query 才能切页签
    '$route.query.panel'(p) {
      if (['taskbook', 'guidance', 'midterm'].includes(p) && p !== this.tab) this.tab = p
    }
  },
  methods: {
    async searchStudents() {
      this.sideError = ''
      const res = await gdStudentApi.getStudents({ keyword: this.studentKeyword, pageSize: 20 })
      if (res.code === 0) { this.studentOptions = res.data.list } else { this.studentOptions = []; this.sideError = res.message || '学生列表加载失败' }
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
      this.loadError = ''
      await Promise.all([this.loadTaskbook(), this.loadGuidance(), this.loadMidterm()])
    },
    async loadTaskbook() {
      this.tbLoading = true
      const res = await graduationTaskbookApi.getTaskbook(this.current.id)
      if (res.code === 0) { this.taskbook = res.data } else { this.taskbook = null; this.loadError = res.message || '任务书加载失败' }
      this.tbLoading = false
    },
    async loadGuidance() {
      this.guidanceLoading = true
      const res = await graduationTaskbookApi.getGuidanceList({ gdStudentId: this.current.id, pageSize: 50 })
      if (res.code === 0) { this.guidanceList = res.data.list } else { this.guidanceList = []; this.loadError = res.message || '指导记录加载失败' }
      this.guidanceLoading = false
    },
    async loadMidterm() {
      this.mtLoading = true
      const res = await graduationTaskbookApi.getMidterm(this.current.id)
      if (res.code === 0) { this.midterm = res.data } else { this.midterm = null; this.loadError = res.message || '中期检查加载失败' }
      this.mtLoading = false
    },
    processQuery(extra = {}) {
      return { panel: this.tab, ...extra }
    },
    openIssueTaskbook() {
      if (!this.current) return
      this.$router.push({
        path: `/admin/graduation/process/${this.current.id}/taskbook`,
        query: this.processQuery()
      })
    },
    openChangeTaskbook() {
      if (!this.current) return
      this.$router.push({
        path: `/admin/graduation/process/${this.current.id}/taskbook`,
        query: this.processQuery({ mode: 'change' })
      })
    },
    async doConfirmTaskbook() {
      const res = await graduationTaskbookApi.confirmTaskbook(this.current.id)
      if (res.code === 0) { toast.success('已确认'); this.loadTaskbook() } else toast.error(res.message)
    },
    openGuidanceCreate() {
      if (!this.current) return
      this.$router.push({
        path: `/admin/graduation/process/${this.current.id}/guidance`,
        query: this.processQuery()
      })
    },
    openMidtermCheck() {
      if (!this.current) return
      this.$router.push({
        path: `/admin/graduation/process/${this.current.id}/midterm`,
        query: this.processQuery()
      })
    },
    openRectifySubmit() {
      if (!this.current) return
      this.$router.push({
        path: `/admin/graduation/process/${this.current.id}/rectify`,
        query: this.processQuery()
      })
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
