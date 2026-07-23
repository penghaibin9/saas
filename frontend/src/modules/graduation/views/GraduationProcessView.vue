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
          <li v-for="s in studentOptions" :key="s.id" class="gp-stu-item" :class="{ 'is-active': current && current.id === s.id }" tabindex="0" role="button" @click="selectStudent(s)" @keydown.enter.prevent="selectStudent(s)" @keydown.space.prevent="selectStudent(s)">
            <div class="mp-cell-main">{{ s.name }}</div>
            <div class="mp-cell-sub">{{ s.studentNo }} · {{ s.advisorName || '未分配导师' }} · {{ s.stageLabel }}</div>
          </li>
        </ul>
        <ErrorState v-if="sideError" :description="sideError" @retry="searchStudents" />
        <EmptyState v-else-if="!studentOptions.length" title="未找到学生" description="调整关键词重新搜索" />
      </div>

      <div class="gp-main">
          <section v-if="current" class="gp-context" aria-label="当前处理学生">
            <div class="gp-context__avatar">{{ (current.name || '学').slice(0, 1) }}</div>
            <div class="gp-context__identity">
              <strong>{{ current.name }}</strong>
              <span>{{ current.studentNo || '未关联学号' }} · {{ current.advisorName || '未分配指导教师' }}</span>
            </div>
            <div class="gp-context__stage">{{ current.stageLabel || '过程指导' }}</div>
          </section>
          <div class="gp-tabs">
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'taskbook' }" @click="switchTab('taskbook')">任务书</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'guidance' }" @click="switchTab('guidance')">指导记录</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'midterm' }" @click="switchTab('midterm')">中期检查</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'workflow' }" @click="switchTab('workflow')">规范流程</button>
          </div>

          <ErrorState v-if="loadError" :description="loadError" @retry="loadAll" />

          <!-- 规范流程是静态参考内容，不依赖选中学生；其余页签须先选学生 -->
          <EmptyState v-if="!current && tab !== 'workflow'" title="请先从左侧选择一名毕设学生" />

          <!-- 任务书 -->
          <div v-if="current && tab === 'taskbook'" class="gp-panel">
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
                <button v-if="taskbook.status !== 'CONFIRMED'" class="mp-btn mp-btn--primary" @click="doConfirmTaskbook">代学生确认</button>
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
          <div v-if="current && tab === 'guidance'" class="gp-panel">
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
          <div v-if="current && tab === 'midterm'" class="gp-panel">
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

          <!-- 规范流程：将毕业论文（设计）手册转化为系统可执行的关卡 -->
          <div v-if="tab === 'workflow'" class="gp-panel gp-workflow">
            <div class="gp-workflow__intro">
              <div>
                <div class="gm-section-title">毕业论文（设计）核心流程</div>
                <p>以选题到归档的八个关卡组织业务；每个关卡都明确责任人、交付材料和下一关准入条件。</p>
              </div>
              <span class="gp-workflow__badge">按批次规则执行</span>
            </div>
            <ol class="gp-workflow__steps">
              <li v-for="step in manualWorkflow" :key="step.key" class="gp-workflow__step">
                <span class="gp-workflow__order">{{ step.order }}</span>
                <div class="gp-workflow__body">
                  <div class="gp-workflow__head">
                    <strong>{{ step.title }}</strong>
                    <span>{{ step.owner }}</span>
                  </div>
                  <p><b>交付：</b>{{ step.deliverable }}</p>
                  <p><b>关卡：</b>{{ step.gate }}</p>
                </div>
                <button type="button" class="mp-link gp-workflow__go" @click="$router.push(step.route)">进入处理</button>
              </li>
            </ol>
            <div class="gp-workflow__gates">
              <div class="gm-section-title">执行原则</div>
              <ul>
                <li v-for="gate in manualGates" :key="gate">{{ gate }}</li>
              </ul>
            </div>
          </div>
      </div>
    </div>

    <!-- 首次进入本模块时的 4 步说明；「已看过」存后端偏好，顶栏「?」可重看 -->
    <AppPageGuide guide-key="graduation.gd-process" />
  </ModulePageShell>
</template>

<script>
/** 过程指导（/admin/graduation/process）：任务书下达/确认/变更 + 指导记录时间线 + 中期检查三档结论/整改闭环。 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDateDisplay } from '@/components/common/date'
import { AppPageGuide } from '@/components/common'
import { graduationTaskbookApi } from '@/modules/graduation/api/graduation-taskbook.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { GRADUATION_MANUAL_GATES, GRADUATION_MANUAL_WORKFLOW } from '@/modules/graduation/constants/graduationManualWorkflow'
import GraduationBatchStrip from './_shared/GraduationBatchStrip.vue'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationProcessView',
  components: { AppPageGuide, GraduationBatchStrip, ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      studentKeyword: '', studentOptions: [], current: null, tab: 'taskbook', submitting: false,
      sideError: '', loadError: '',
      taskbook: null, tbLoading: false,
      guidanceList: [], guidanceLoading: false,
      midterm: null, mtLoading: false,
      manualWorkflow: GRADUATION_MANUAL_WORKFLOW,
      manualGates: GRADUATION_MANUAL_GATES
    }
  },
  created() {
    this.tab = ['taskbook', 'guidance', 'midterm', 'workflow'].includes(this.$route.query.panel) ? this.$route.query.panel : 'taskbook'
    this.searchStudents()
  },
  watch: {
    // 应用内点左侧三级菜单（同路由不同 ?panel=）时组件被复用，必须监听 query 才能切页签
    '$route.query.panel'(p) {
      if (['taskbook', 'guidance', 'midterm', 'workflow'].includes(p) && p !== this.tab) this.tab = p
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
      const reason = window.prompt('管理员代确认须填写原因（不少于5字）', '学生线下已确认，代为录入')
      if (reason == null) return
      if (String(reason).trim().length < 5) { toast.error('代确认原因不少于5字'); return }
      const res = await graduationTaskbookApi.confirmTaskbook(this.current.id, { proxyReason: String(reason).trim() })
      if (res.code === 0) { toast.success('已代确认'); this.loadTaskbook() } else toast.error(res.message)
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
.gp-side { width: 280px; flex: none; padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.gp-main { flex: 1; min-width: 0; padding: var(--space-4); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md, 8px); background: var(--card, #fff); box-shadow: 0 1px 2px rgba(15, 23, 42, .03); }
.gp-stu-list { list-style: none; margin: var(--space-2) 0 0; padding: 0; max-height: 560px; overflow-y: auto; }
.gp-stu-item { padding: 9px 10px; border-radius: 8px; cursor: pointer; border: 1px solid transparent; transition: background .12s ease, border-color .12s ease; }
.gp-stu-item:hover { background: var(--bg2, #f8fafc); }
.gp-stu-item.is-active { background: var(--pri-bg, #eff6ff); border-color: var(--pri, #2563eb); }
.gp-stu-item:focus-visible, .gp-tabs__item:focus-visible { outline: 2px solid var(--primary-400, #60a5fa); outline-offset: -2px; }
.gp-context { display: flex; align-items: center; gap: var(--space-3); padding: 0 0 var(--space-3); margin-bottom: var(--space-1); border-bottom: 1px solid var(--border-light, #e2e8f0); }
.gp-context__avatar { display: grid; place-items: center; width: 36px; height: 36px; flex: 0 0 auto; border-radius: var(--radius-full); background: var(--primary-50, #eff6ff); color: var(--primary-700, #1d4ed8); font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); }
.gp-context__identity { display: grid; gap: 2px; min-width: 0; }
.gp-context__identity strong { color: var(--text-primary); font-size: var(--font-size-md); }
.gp-context__identity span { overflow: hidden; color: var(--text-tertiary); font-size: var(--font-size-xs); text-overflow: ellipsis; white-space: nowrap; }
.gp-context__stage { margin-left: auto; padding: 4px 8px; border-radius: var(--radius-full); color: var(--primary-700, #1d4ed8); background: var(--primary-50, #eff6ff); font-size: var(--font-size-xs); white-space: nowrap; }
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
.gp-workflow { max-width: 960px; }
.gp-workflow__intro { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); margin-bottom: var(--space-4); }
.gp-workflow__intro p { max-width: 680px; margin: 4px 0 0; color: var(--text-secondary, #475569); line-height: 1.6; }
.gp-workflow__badge { flex: none; padding: 4px 8px; border-radius: var(--radius-full); background: var(--primary-50, #eff6ff); color: var(--primary-700, #1d4ed8); font-size: var(--font-size-xs); }
.gp-workflow__steps { display: grid; gap: var(--space-2); margin: 0; padding: 0; list-style: none; counter-reset: none; }
.gp-workflow__step { display: grid; grid-template-columns: 36px minmax(0, 1fr) auto; gap: var(--space-3); align-items: start; padding: var(--space-3); border: 1px solid var(--border-light, #e2e8f0); border-radius: var(--radius-md); background: var(--gray-50, #f8fafc); }
.gp-workflow__order { display: grid; place-items: center; width: 32px; height: 32px; border-radius: var(--radius-full); background: var(--primary-100, #dbeafe); color: var(--primary-700, #1d4ed8); font-size: var(--font-size-xs); font-weight: var(--font-weight-bold); }
.gp-workflow__body { min-width: 0; }
.gp-workflow__head { display: flex; align-items: baseline; flex-wrap: wrap; gap: var(--space-2); }
.gp-workflow__head strong { color: var(--text-primary); }
.gp-workflow__head span { color: var(--text-tertiary, #64748b); font-size: var(--font-size-xs); }
.gp-workflow__body p { margin: 5px 0 0; color: var(--text-secondary, #475569); line-height: 1.55; }
.gp-workflow__body b { color: var(--text-primary, #0f172a); font-weight: var(--font-weight-medium); }
.gp-workflow__go { align-self: center; white-space: nowrap; }
.gp-workflow__gates { margin-top: var(--space-4); padding: var(--space-3); border-left: 3px solid var(--primary-400, #60a5fa); border-radius: 0 var(--radius-sm) var(--radius-sm) 0; background: var(--primary-50, #eff6ff); }
.gp-workflow__gates ul { display: grid; gap: 6px; margin: var(--space-2) 0 0; padding-left: 18px; color: var(--text-secondary, #475569); line-height: 1.5; }
@media (max-width: 960px) { .gp-layout { flex-direction: column; } .gp-side, .gp-main { width: 100%; box-sizing: border-box; } .gp-stu-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(185px, 1fr)); max-height: 260px; gap: var(--space-1); } }
@media (max-width: 640px) { .gp-main { padding: var(--space-3); } .gp-context__stage { display: none; } .gp-workflow__intro { flex-direction: column; } .gp-workflow__step { grid-template-columns: 32px minmax(0, 1fr); } .gp-workflow__go { grid-column: 2; justify-self: start; } }
</style>
