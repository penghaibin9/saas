<template>
  <ModulePageShell
    title="正式评阅分配"
    subtitle="管理员先选择已通过正式定稿的学生，再分配独立评阅教师；指导教师自动从候选评阅人中回避"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="ra-layout">
      <section class="ra-card ra-list">
        <header class="ra-card__head">
          <div><strong>选择学生</strong><span>当前批次 · 后端真实数据范围</span></div>
          <button type="button" class="mp-btn" :disabled="loading" @click="loadStudents">刷新</button>
        </header>
        <div class="ra-search">
          <input v-model.trim="keyword" class="ie-in" placeholder="搜索学生姓名 / 学号" @keyup.enter="loadStudents" />
          <button type="button" class="mp-btn mp-btn--primary" :disabled="loading" @click="loadStudents">查询</button>
        </div>
        <ErrorState v-if="error" :description="error" @retry="loadStudents" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!students.length" title="当前条件下没有可见学生" description="请确认当前批次、数据范围或调整搜索条件。" />
        <div v-else class="ra-students">
          <button
            v-for="student in students" :key="student.id" type="button"
            :class="['ra-student', { 'is-active': current && String(current.id) === String(student.id) }]"
            @click="selectStudent(student)"
          >
            <span><b>{{ student.name || '未命名学生' }}</b><small>{{ student.studentNo || '未关联学号' }}</small></span>
            <span><small>{{ student.topicTitle || '未确认课题' }}</small><small>指导教师：{{ student.advisorName || '未分配' }}</small></span>
          </button>
        </div>
      </section>

      <section class="ra-card ra-assignment">
        <template v-if="current">
          <header class="ra-card__head">
            <div><strong>分配独立评阅教师</strong><span>{{ current.name }} · {{ current.studentNo || '未关联学号' }}</span></div>
          </header>
          <div class="ra-context">
            <div><span>课题</span><b>{{ current.topicTitle || '未确认课题' }}</b></div>
            <div><span>指导教师</span><b>{{ current.advisorName || '未分配' }}</b></div>
            <div><span>当前阶段</span><b>{{ current.stageLabel || current.stage || '—' }}</b></div>
          </div>
          <label class="ra-field">
            <span>独立评阅教师</span>
            <AppGraduationMentorPicker
              v-model="reviewerMentorId"
              :query="{
                qualificationStatus: 'QUALIFIED',
                valueMode: 'id',
                excludeMentorId: current.mentorId || '',
                excludeTeacherName: current.advisorName || ''
              }"
              placeholder="按姓名 / 工号搜索评阅教师"
            />
          </label>
          <p v-if="formError" class="ra-error">{{ formError }}</p>
          <div class="ra-actions">
            <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting || !reviewerMentorId" @click="assignReview">
              {{ submitting ? '正在分配…' : '分配正式评阅' }}
            </button>
            <button v-if="assigned" type="button" class="mp-btn" @click="openReviewCenter">进入统一评阅中心</button>
          </div>
          <p class="ra-note">系统只允许对“已通过正式定稿”的学生创建正式评阅任务，并由后端再次执行 SoD 校验：评阅人不得是该生指导教师。失败不会生成半条评阅记录。</p>
        </template>
        <EmptyState v-else title="请先选择学生" description="从左侧当前批次学生中选择一人后，再分配独立评阅教师。" />
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppGraduationMentorPicker } from '@/components/common'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { graduationDefenseGradeApi } from '@/modules/graduation/api/graduation-defense-grade.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationReviewAssignView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppGraduationMentorPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      batchStore: useGraduationBatchStore(),
      keyword: '', students: [], current: null,
      reviewerMentorId: '', loading: false, submitting: false,
      error: '', formError: '', assigned: false,
      loadToken: 0
    }
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.keyword = ''
      this.current = null
      this.reviewerMentorId = ''
      this.assigned = false
      this.loadStudents()
    }
  },
  created() { this.loadStudents() },
  beforeUnmount() { ++this.loadToken },
  methods: {
    async loadStudents() {
      const token = ++this.loadToken
      this.loading = true
      this.error = ''
      if (!this.batchStore.selectedBatchId) {
        this.students = []
        this.current = null
        this.loading = false
        this.error = '请先在顶部选择毕业设计批次'
        return
      }
      const res = await gdStudentApi.getStudents({
        keyword: this.keyword || undefined,
        batchId: this.batchStore.selectedBatchId,
        page: 1,
        pageSize: 50
      })
      if (token !== this.loadToken) return
      if (res.code === 0) {
        this.students = res.data?.list || []
        const requested = String(this.$route.query.studentId || '')
        const keep = this.current && this.students.find((item) => String(item.id) === String(this.current.id))
        const target = keep || (requested ? this.students.find((item) => String(item.id) === requested) : null)
        if (target) this.selectStudent(target)
        else if (this.current) this.current = null
      } else {
        this.students = []
        this.current = null
        this.error = res.message || '学生列表加载失败'
      }
      this.loading = false
    },
    selectStudent(student) {
      this.current = student
      this.reviewerMentorId = ''
      this.formError = ''
      this.assigned = false
      this.$router.replace({ query: { ...this.$route.query, batchId: this.batchStore.selectedBatchId || undefined, studentId: student.id } })
    },
    async assignReview() {
      if (!this.current || !this.reviewerMentorId || this.submitting) return
      this.submitting = true
      this.formError = ''
      const res = await graduationDefenseGradeApi.assignReview(this.current.id, null, this.reviewerMentorId)
      this.submitting = false
      if (res.code === 0) {
        this.assigned = true
        toast.success('正式评阅任务已分配')
      } else {
        this.assigned = false
        this.formError = res.message || '正式评阅任务分配失败'
      }
    },
    openReviewCenter() {
      this.$router.push({
        name: 'graduation-review-tasks',
        query: { batchId: this.batchStore.selectedBatchId || undefined, studentId: this.current?.id || undefined, source: 'review-assign' }
      })
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ra-layout{display:grid;grid-template-columns:minmax(320px,.9fr) minmax(420px,1.1fr);gap:14px;align-items:start}.ra-card{border:1px solid var(--border-light,#e2e8f0);border-radius:12px;background:#fff;padding:14px;min-width:0}.ra-card__head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.ra-card__head>div{display:grid;gap:3px}.ra-card__head strong{font-size:15px}.ra-card__head span,.ra-note{font-size:12px;color:var(--text-tertiary,#64748b)}.ra-search{display:flex;gap:8px;margin-bottom:12px}.ra-search .ie-in{flex:1}.ra-students{display:grid;gap:7px;max-height:620px;overflow:auto}.ra-student{width:100%;display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr);gap:10px;text-align:left;border:1px solid var(--border-light,#e2e8f0);border-radius:9px;background:#fff;padding:10px;cursor:pointer}.ra-student.is-active{border-color:var(--pri,#2563eb);background:var(--primary-50,#eff6ff)}.ra-student span{display:grid;gap:3px;min-width:0}.ra-student small{font-size:11px;color:var(--text-tertiary,#64748b);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ra-context{display:grid;gap:8px;margin-bottom:14px}.ra-context>div{display:grid;grid-template-columns:88px 1fr;gap:8px;padding:8px 0;border-bottom:1px dashed var(--border-light,#e2e8f0)}.ra-context span,.ra-field>span{font-size:12px;color:var(--text-tertiary,#64748b)}.ra-context b{font-size:13px}.ra-field{display:grid;gap:7px}.ra-error{margin:10px 0 0;padding:9px;border-radius:8px;background:#fef2f2;color:#b91c1c;font-size:12px}.ra-actions{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}.ra-note{margin:12px 0 0;line-height:1.6}.mp-btn{padding:7px 14px;border:1px solid var(--border-light,#d9dee8);border-radius:8px;background:#fff;cursor:pointer}.mp-btn--primary{background:var(--pri,#2563eb);border-color:var(--pri,#2563eb);color:#fff}.mp-btn:disabled{opacity:.55;cursor:not-allowed}@media(max-width:1100px){.ra-layout{grid-template-columns:1fr}.ra-students{max-height:420px}}
</style>
