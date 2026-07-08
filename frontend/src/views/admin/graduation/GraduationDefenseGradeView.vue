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
        <EmptyState v-if="!studentOptions.length" title="未找到学生" />
      </div>

      <div class="gp-main">
        <template v-if="!current">
          <EmptyState title="请先从左侧选择一名毕设学生" />
        </template>
        <template v-else>
          <div class="gp-tabs">
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'plagiarism' }" @click="tab = 'plagiarism'">查重记录</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'review' }" @click="tab = 'review'">教师评阅</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'defense' }" @click="tab = 'defense'">答辩评分</button>
            <button class="gp-tabs__item" :class="{ 'is-active': tab === 'grade' }" @click="tab = 'grade'">成绩评定</button>
          </div>

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
              <input v-model="reviewerName" class="ie-in" placeholder="评阅人姓名" style="width:160px" />
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

    <AppDrawer v-model:visible="genericFormVisible" :title="genericFormTitle">
      <form class="ie-form" @submit.prevent="submitGenericForm">
        <template v-for="f in genericFormFields" :key="f.key">
          <label class="ie-fld ie-fld--full"><span class="ie-lbl">{{ f.label }} <i v-if="f.required">*</i></span>
            <textarea v-if="f.type === 'textarea'" v-model.trim="genericForm[f.key]" class="ie-in" rows="2" />
            <input v-else v-model="genericForm[f.key]" class="ie-in" />
          </label>
        </template>
        <p v-if="formError" class="ie-err">{{ formError }}</p>
        <div class="ie-actions">
          <button type="button" class="mp-btn" @click="genericFormVisible = false">取消</button>
          <button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">提交</button>
        </div>
      </form>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/** 答辩与成绩（/admin/graduation/defense-grade）：查重/评阅/答辩评分/成绩评定，按学生维度处理。 */
import { ModulePageShell, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import { AppDateDisplay } from '@/components/common/date'
import { graduationDefenseGradeApi } from '@/modules/graduation/api/graduation-defense-grade.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationDefenseGradeView',
  components: { ModulePageShell, StatusTag, LoadingState, EmptyState, AppDrawer, AppDateDisplay },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      studentKeyword: '', studentOptions: [], current: null, tab: 'plagiarism',
      plagiarismList: [], reviewList: [], scoreList: [], grade: null, gradeLoading: false,
      reviewerName: '',
      genericFormVisible: false, genericFormTitle: '', genericFormFields: [], genericForm: {}, genericFormAction: null,
      formError: '', submitting: false
    }
  },
  created() {
    const p = this.$route.query.panel
    if (['plagiarism', 'review', 'defense', 'grade'].includes(p)) this.tab = p
    this.searchStudents()
  },
  methods: {
    async searchStudents() {
      const res = await gdStudentApi.getStudents({ keyword: this.studentKeyword, pageSize: 20 })
      this.studentOptions = res.code === 0 ? res.data.list : []
    },
    selectStudent(s) { this.current = s; this.loadAll() },
    async loadAll() {
      await Promise.all([this.loadPlagiarism(), this.loadReview(), this.loadScores(), this.loadGrade()])
    },
    async loadPlagiarism() {
      const res = await graduationDefenseGradeApi.getPlagiarismList({ gdStudentId: this.current.id, pageSize: 50 })
      this.plagiarismList = res.code === 0 ? res.data.list : []
    },
    async loadReview() {
      const res = await graduationDefenseGradeApi.getReviewList({ gdStudentId: this.current.id, pageSize: 50 })
      this.reviewList = res.code === 0 ? res.data.list : []
    },
    async loadScores() {
      const res = await graduationDefenseGradeApi.getScoreList({ gdStudentId: this.current.id, pageSize: 50 })
      this.scoreList = res.code === 0 ? res.data.list : []
    },
    async loadGrade() {
      this.gradeLoading = true
      const res = await graduationDefenseGradeApi.getGrade(this.current.id)
      this.grade = res.code === 0 ? res.data : null
      this.gradeLoading = false
    },
    async doSubmitPlagiarism() {
      const res = await graduationDefenseGradeApi.submitPlagiarism(this.current.id)
      if (res.code === 0) { toast.success('已提交检测'); this.loadPlagiarism() } else toast.error(res.message)
    },
    openForm(title, fields, action) {
      this.genericFormTitle = title; this.genericFormFields = fields
      this.genericForm = {}; fields.forEach(f => { this.genericForm[f.key] = '' })
      this.genericFormAction = action; this.formError = ''; this.genericFormVisible = true
    },
    fillResult(p) {
      this.openForm('回填查重结果', [{ key: 'rate', label: '重复率(%)', required: true }, { key: 'reportUrl', label: '报告链接' }],
        async () => {
          const res = await graduationDefenseGradeApi.setPlagiarismResult(p.id, this.genericForm.rate, this.genericForm.reportUrl)
          if (res.code === 0) { toast.success('已回填'); this.loadPlagiarism() } else this.formError = res.message
        })
    },
    doDispute(p) {
      this.openForm('申请复查', [{ key: 'reason', label: '复查理由(≥5字)', required: true, type: 'textarea' }],
        async () => {
          const res = await graduationDefenseGradeApi.disputePlagiarism(p.id, this.genericForm.reason)
          if (res.code === 0) { toast.success('已提交复查申请'); this.loadPlagiarism() } else this.formError = res.message
        })
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
      this.openForm('提交评阅', [{ key: 'score', label: '评分(0-100)', required: true }, { key: 'opinion', label: '评阅意见', required: true, type: 'textarea' }],
        async () => {
          const res = await graduationDefenseGradeApi.submitReview(r.id, Number(this.genericForm.score), this.genericForm.opinion)
          if (res.code === 0) { toast.success('已提交'); this.loadReview() } else this.formError = res.message
        })
    },
    openReviewReturn(r) {
      this.openForm('退回重评', [{ key: 'reason', label: '退回原因(≥5字)', required: true, type: 'textarea' }],
        async () => {
          const res = await graduationDefenseGradeApi.returnReview(r.id, this.genericForm.reason)
          if (res.code === 0) { toast.success('已退回'); this.loadReview() } else this.formError = res.message
        })
    },
    openScoreEntry() {
      this.openForm('录入评委评分', [{ key: 'judgeName', label: '评委姓名', required: true }, { key: 'score', label: '评分(0-100)' }, { key: 'comment', label: '评语', type: 'textarea' }],
        async () => {
          const res = await graduationDefenseGradeApi.enterScore({ gdStudentId: this.current.id, judgeName: this.genericForm.judgeName, score: this.genericForm.score ? Number(this.genericForm.score) : undefined, comment: this.genericForm.comment })
          if (res.code === 0) { toast.success('已保存'); this.loadScores() } else this.formError = res.message
        })
    },
    async doConfirmScores() {
      const res = await graduationDefenseGradeApi.confirmScores(this.current.id)
      if (res.code === 0) { toast.success('已确认'); this.loadScores() } else toast.error(res.message)
    },
    openSecondDefense() {
      this.openForm('创建二次答辩', [{ key: 'reason', label: '原因(≥5字)', required: true, type: 'textarea' }],
        async () => {
          const res = await graduationDefenseGradeApi.createSecondDefense(this.current.id, this.genericForm.reason)
          if (res.code === 0) { toast.success('已创建二次答辩'); this.loadScores() } else this.formError = res.message
        })
    },
    openCalculate() {
      this.openForm('核算成绩', [{ key: 'advisorScore', label: '导师分', required: true }, { key: 'reviewerScore', label: '评阅分' }, { key: 'defenseScore', label: '答辩分', required: true }],
        async () => {
          const res = await graduationDefenseGradeApi.calculateGrade(this.current.id, {
            advisorScore: this.genericForm.advisorScore ? Number(this.genericForm.advisorScore) : undefined,
            reviewerScore: this.genericForm.reviewerScore ? Number(this.genericForm.reviewerScore) : undefined,
            defenseScore: this.genericForm.defenseScore ? Number(this.genericForm.defenseScore) : undefined
          })
          if (res.code === 0) { toast.success('已核算'); this.loadGrade() } else this.formError = res.message
        })
    },
    async doReview(action) {
      const res = await graduationDefenseGradeApi.reviewGrade(this.current.id, { action })
      if (res.code === 0) { toast.success('已复核'); this.loadGrade() } else toast.error(res.message)
    },
    openReturnGrade() {
      this.openForm('复核退回', [{ key: 'comment', label: '退回原因(≥5字)', required: true, type: 'textarea' }],
        async () => {
          const res = await graduationDefenseGradeApi.reviewGrade(this.current.id, { action: 'RETURN', comment: this.genericForm.comment })
          if (res.code === 0) { toast.success('已退回'); this.loadGrade() } else this.formError = res.message
        })
    },
    async doPublish() {
      const res = await graduationDefenseGradeApi.publishGrade(this.current.id)
      if (res.code === 0) { toast.success('已发布'); this.loadGrade() } else toast.error(res.message)
    },
    openWithdraw() {
      this.openForm('撤回成绩', [{ key: 'reason', label: '撤回原因(≥5字)', required: true, type: 'textarea' }],
        async () => {
          const res = await graduationDefenseGradeApi.withdrawGrade(this.current.id, this.genericForm.reason)
          if (res.code === 0) { toast.success('已撤回'); this.loadGrade() } else this.formError = res.message
        })
    },
    async submitGenericForm() {
      this.submitting = true
      try { await this.genericFormAction(); if (!this.formError) this.genericFormVisible = false } finally { this.submitting = false }
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
