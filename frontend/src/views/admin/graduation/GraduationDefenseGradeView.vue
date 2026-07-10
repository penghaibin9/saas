<template>
  <ModulePageShell
    title="答辩与成绩"
    subtitle="查重 / 教师评阅 / 答辩评分 / 成绩评定 —— 按学生维度查看与处理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="gp-layout">
      <div class="gp-side">
        <input v-model="studentKeyword" class="ie-in" placeholder="搜索学生姓名/学号" @input="searchStudents" />
        <ul class="gp-stu-list">
          <li v-for="s in studentOptions" :key="s.id" class="gp-stu-item" :class="{ 'is-active': current && current.id === s.id }" @click="selectStudent(s)">
            <div class="mp-cell-main">{{ s.name }}</div>
            <div class="mp-cell-sub">{{ s.studentNo }} · {{ s.advisorName || '未分配导师' }}</div>
          </li>
        </ul>
        <ErrorState v-if="sideError" :description="sideError" @retry="searchStudents" />
        <EmptyState v-else-if="!studentOptions.length" title="未找到学生" />
      </div>

      <div class="gp-main">
        <template v-if="!current">
          <EmptyState title="请先从左侧选择一名毕设学生" />
        </template>
        <template v-else>
          <div class="gp-tabs">
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'plagiarism' }" @click="switchTab('plagiarism')">查重记录</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'review' }" @click="switchTab('review')">教师评阅</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'defense' }" @click="switchTab('defense')">答辩评分</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'grade' }" @click="switchTab('grade')">成绩评定</button>
          </div>

          <ErrorState v-if="loadError" :description="loadError" @retry="loadAll" />

          <!-- 查重 -->
          <div v-if="tab === 'plagiarism'" class="gp-panel">
            <div class="ie-actions" style="justify-content: flex-start; margin-bottom: var(--space-3)"><button class="mp-btn mp-btn--primary" @click="doSubmitPlagiarism">发起查重</button></div>
            <ul class="gp-timeline">
              <li v-for="p in plagiarismList" :key="p.id" class="gp-timeline-item">
                <div class="mp-cell-main"><AppDateDisplay :value="p.submitAt" mode="datetime" /> · <StatusTag :type="p.overThreshold ? 'danger' : 'success'" :label="p.status === 'DONE' ? (p.rate || '—') : p.statusLabel" dot /></div>
                <div v-if="p.status === 'CHECKING'" class="mp-cell-sub"><button class="mp-link" @click="fillResult(p)">回填结果</button></div>
                <div v-if="p.overThreshold && !p.disputeStatus" class="mp-cell-sub"><button class="mp-link" @click="doDispute(p)">申请复查</button></div>
                <div v-if="p.disputeStatus === 'PENDING'" class="mp-cell-sub">复查申请：{{ p.disputeReason }}
                  <button class="mp-link" @click="doDisputeReview(p, 'APPROVE')">通过</button>
                  <button class="mp-link mp-link--danger" @click="doDisputeReview(p, 'REJECT')">驳回</button>
                </div>
              </li>
            </ul>
            <EmptyState v-if="!plagiarismList.length" title="暂无查重记录" />
          </div>

          <!-- 评阅 -->
          <div v-if="tab === 'review'" class="gp-panel">
            <div class="ie-actions" style="justify-content: flex-start; margin-bottom: var(--space-3)">
              <AppMentorPicker v-model="reviewerName" :remote-search="searchReviewers" placeholder="搜索评阅教师（自动回避该生导师）" style="width: 260px" />
              <button class="mp-btn mp-btn--primary" @click="doAssignReview">分配评阅</button>
            </div>
            <ul class="gp-timeline">
              <li v-for="r in reviewList" :key="r.id" class="gp-timeline-item">
                <div class="mp-cell-main">{{ r.reviewerName }} · <StatusTag :type="r.statusTone" :label="r.statusLabel" dot /></div>
                <div v-if="r.opinion" class="mp-cell-sub">评分 {{ r.score }} · {{ r.opinion }}</div>
                <div class="ie-actions" style="justify-content:flex-start;margin-top:4px">
                  <button v-if="['ASSIGNED', 'REVIEWING', 'RETURNED'].includes(r.status)" class="mp-link" @click="openReviewSubmit(r)">提交评阅</button>
                  <button v-if="r.status === 'COMPLETED'" class="mp-link" @click="openReviewReturn(r)">退回重评</button>
                </div>
              </li>
            </ul>
            <EmptyState v-if="!reviewList.length" title="暂无评阅任务" />
          </div>

          <!-- 答辩评分 -->
          <div v-if="tab === 'defense'" class="gp-panel">
            <div class="ie-actions" style="justify-content: flex-start; margin-bottom: var(--space-3)"><button class="mp-btn mp-btn--primary" @click="openScoreEntry">录入评委评分</button></div>
            <ul class="gp-timeline">
              <li v-for="d in scoreList" :key="d.id" class="gp-timeline-item">
                <div class="mp-cell-main">{{ d.judgeName }}（第{{ d.roundNo }}轮）· {{ d.absent ? '缺席' : d.score }} · <StatusTag :type="d.status === 'CONFIRMED' ? 'success' : 'warning'" :label="d.statusLabel" dot /></div>
              </li>
            </ul>
            <EmptyState v-if="!scoreList.length" title="暂无评分记录" />
            <div class="ie-actions">
              <button class="mp-btn" @click="doConfirmScores">确认本轮成绩</button>
              <button class="mp-btn" @click="openSecondDefense">创建二次答辩</button>
            </div>
          </div>

          <!-- 成绩 -->
          <div v-if="tab === 'grade'" class="gp-panel">
            <LoadingState v-if="gradeLoading" />
            <template v-else-if="grade">
              <div class="gp-kv"><span>状态</span><StatusTag :type="grade.statusTone" :label="grade.statusLabel" dot /></div>
              <div class="gp-kv"><span>导师分</span><span>{{ grade.advisorScore ?? '—' }}</span></div>
              <div class="gp-kv"><span>评阅分</span><span>{{ grade.reviewerScore ?? '—' }}</span></div>
              <div class="gp-kv"><span>答辩分</span><span>{{ grade.defenseScore ?? '—' }}</span></div>
              <div class="gp-kv"><span>综合分</span><span>{{ grade.totalScore ?? '—' }}（{{ grade.gradeLevel }}）</span></div>
              <div class="gp-kv"><span>发布时间</span><AppDateDisplay :value="grade.publishedAt" mode="datetime" /></div>
              <div class="ie-actions">
                <button v-if="['DRAFT', 'WITHDRAWN'].includes(grade.status)" class="mp-btn mp-btn--primary" @click="openCalculate">核算成绩</button>
                <button v-if="grade.status === 'CALCULATED' && !grade.reviewedAt" class="mp-btn" @click="doReview('APPROVE')">复核通过</button>
                <button v-if="grade.status === 'CALCULATED' && !grade.reviewedAt" class="mp-btn" @click="openReturnGrade">复核退回</button>
                <button v-if="grade.status === 'CALCULATED' && grade.reviewedAt" class="mp-btn mp-btn--primary" @click="doPublish">发布成绩</button>
                <button v-if="grade.status === 'PUBLISHED'" class="mp-btn mp-link--danger" @click="openWithdraw">撤回</button>
              </div>
            </template>
          </div>
        </template>
      </div>
    </div>

  </ModulePageShell>
</template>

<script>
/** 答辩与成绩（/admin/graduation/defense-grade）：查重/评阅/答辩评分/成绩评定，按学生维度处理。 */
import { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppDateDisplay } from '@/components/common/date'
import { graduationDefenseGradeApi } from '@/modules/graduation/api/graduation-defense-grade.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { graduationMentorApi } from '@/modules/graduation/api/graduation-mentor.api'
import { AppMentorPicker } from '@/components/common'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationDefenseGradeView',
  components: { ModulePageShell, StatusTag, LoadingState, ErrorState, EmptyState, AppDateDisplay, AppMentorPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      studentKeyword: '', studentOptions: [], current: null, tab: 'plagiarism',
      sideError: '', loadError: '',
      plagiarismList: [], reviewList: [], scoreList: [], grade: null, gradeLoading: false,
      reviewerName: '',
      submitting: false
    }
  },
  created() {
    const p = this.$route.query.panel
    if (['plagiarism', 'review', 'defense', 'grade'].includes(p)) this.tab = p
    this.searchStudents()
  },
  watch: {
    // 应用内点左侧三级菜单（同路由不同 ?panel=）时组件被复用，必须监听 query 才能切页签
    '$route.query.panel'(p) {
      if (['plagiarism', 'review', 'defense', 'grade'].includes(p) && p !== this.tab) this.tab = p
    }
  },
  methods: {
    /** 页签切换同步到 URL，保证刷新/分享/左侧菜单高亮一致 */
    switchTab(t) {
      this.tab = t
      if (this.$route.query.panel !== t) this.$router.replace({ query: { ...this.$route.query, panel: t } })
    },
    /** 评阅教师远程搜索：排除该生指导教师（SoD），最终由后端再次校验 */
    async searchReviewers(keyword) {
      const res = await graduationMentorApi.getMentors({ keyword, qualificationStatus: 'QUALIFIED', pageSize: 20 })
      if (res.code !== 0) throw new Error(res.message || '搜索失败')
      const advisor = this.current && this.current.advisorName
      return res.data.list.map((m) => ({
        label: m.teacherName === advisor ? `${m.teacherName}（该生导师 · 回避）` : `${m.teacherName}（${m.capacityText || m.collegeName || '教师'}）`,
        value: m.teacherName,
        disabled: m.teacherName === advisor
      }))
    },
    async searchStudents() {
      this.sideError = ''
      const res = await gdStudentApi.getStudents({ keyword: this.studentKeyword, pageSize: 20 })
      if (res.code === 0) { this.studentOptions = res.data.list } else { this.studentOptions = []; this.sideError = res.message || '学生列表加载失败' }
    },
    selectStudent(s) { this.current = s; this.loadAll() },
    async loadAll() {
      this.loadError = ''
      await Promise.all([this.loadPlagiarism(), this.loadReview(), this.loadScores(), this.loadGrade()])
    },
    async loadPlagiarism() {
      const res = await graduationDefenseGradeApi.getPlagiarismList({ gdStudentId: this.current.id, pageSize: 50 })
      if (res.code === 0) { this.plagiarismList = res.data.list } else { this.plagiarismList = []; this.loadError = res.message || '查重记录加载失败' }
    },
    async loadReview() {
      const res = await graduationDefenseGradeApi.getReviewList({ gdStudentId: this.current.id, pageSize: 50 })
      if (res.code === 0) { this.reviewList = res.data.list } else { this.reviewList = []; this.loadError = res.message || '评阅记录加载失败' }
    },
    async loadScores() {
      const res = await graduationDefenseGradeApi.getScoreList({ gdStudentId: this.current.id, pageSize: 50 })
      if (res.code === 0) { this.scoreList = res.data.list } else { this.scoreList = []; this.loadError = res.message || '评分记录加载失败' }
    },
    async loadGrade() {
      this.gradeLoading = true
      const res = await graduationDefenseGradeApi.getGrade(this.current.id)
      if (res.code === 0) { this.grade = res.data } else { this.grade = null; this.loadError = res.message || '成绩加载失败' }
      this.gradeLoading = false
    },
    async doSubmitPlagiarism() {
      const res = await graduationDefenseGradeApi.submitPlagiarism(this.current.id)
      if (res.code === 0) { toast.success('已提交检测'); this.loadPlagiarism() } else toast.error(res.message)
    },
    openForm(formKey, recordId = '') {
      if (!this.current) return
      this.$router.push({
        path: '/admin/graduation/defense-grade/form',
        query: {
          formKey,
          recordId: recordId || undefined,
          studentId: this.current.id,
          panel: this.tab
        }
      })
    },
    fillResult(p) {
      this.openForm('plagiarismResult', p.id)
    },
    doDispute(p) {
      this.openForm('dispute', p.id)
    },
    async doDisputeReview(p, action) {
      const res = await graduationDefenseGradeApi.reviewDispute(p.id, action, action === 'REJECT' ? '维持原查重结果' : '核实无误')
      if (res.code === 0) { toast.success('已审核'); this.loadPlagiarism() } else toast.error(res.message)
    },
    async doAssignReview() {
      if (!this.reviewerName) return toast.error('请填写评阅人姓名')
      const res = await graduationDefenseGradeApi.assignReview(this.current.id, this.reviewerName)
      if (res.code === 0) { toast.success('已分配'); this.reviewerName = ''; this.loadReview() } else toast.error(res.message)
    },
    openReviewSubmit(r) {
      this.openForm('reviewSubmit', r.id)
    },
    openReviewReturn(r) {
      this.openForm('reviewReturn', r.id)
    },
    openScoreEntry() {
      this.openForm('scoreEntry')
    },
    async doConfirmScores() {
      const res = await graduationDefenseGradeApi.confirmScores(this.current.id)
      if (res.code === 0) { toast.success('已确认'); this.loadScores() } else toast.error(res.message)
    },
    openSecondDefense() {
      this.openForm('secondDefense')
    },
    openCalculate() {
      this.openForm('calculate')
    },
    async doReview(action) {
      const res = await graduationDefenseGradeApi.reviewGrade(this.current.id, { action })
      if (res.code === 0) { toast.success('已复核'); this.loadGrade() } else toast.error(res.message)
    },
    openReturnGrade() {
      this.openForm('returnGrade')
    },
    async doPublish() {
      const res = await graduationDefenseGradeApi.publishGrade(this.current.id)
      if (res.code === 0) { toast.success('已发布'); this.loadGrade() } else toast.error(res.message)
    },
    openWithdraw() {
      this.openForm('withdraw')
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
.gp-tabs { display: flex; gap: var(--space-1); border-bottom: 1px solid var(--line, #e2e8f0); margin-bottom: var(--space-3); flex-wrap: wrap; }
.gp-tabs__item { padding: 8px 14px; border: none; background: none; cursor: pointer; font-size: 13px; color: var(--t2, #475569); border-bottom: 2px solid transparent; }
.gp-tabs__item.is-active { color: var(--pri, #2563eb); border-bottom-color: var(--pri, #2563eb); font-weight: 600; }
.gp-panel { font-size: 13px; }
.gp-kv { display: flex; gap: var(--space-3); padding: 6px 0; border-bottom: 1px dashed var(--line, #eef1f6); }
.gp-kv > span:first-child { width: 90px; flex: none; color: var(--t3, #64748b); }
.gp-timeline { list-style: none; margin: 0; padding: 0; }
.gp-timeline-item { padding: 10px 0; border-bottom: 1px dashed var(--line, #eef1f6); }
.mp-link--danger { color: var(--danger, #dc2626); }
.ie-form { display: grid; grid-template-columns: 1fr; gap: var(--space-3); padding: var(--space-1) 0; }
.ie-fld { display: flex; flex-direction: column; gap: 4px; }
.ie-fld--full { grid-column: 1 / -1; }
.ie-lbl { font-size: 12px; color: var(--t2, #475569); }
.ie-lbl i { color: var(--danger, #dc2626); font-style: normal; }
.ie-in { width: 100%; padding: 7px 10px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; font-size: 13px; box-sizing: border-box; }
.ie-err { color: var(--danger, #dc2626); font-size: 12px; margin: 0; }
.ie-actions { display: flex; justify-content: flex-end; gap: var(--space-2); margin-top: var(--space-3); }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
