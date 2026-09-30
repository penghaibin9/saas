<template>
  <ModulePageShell
    title="导师评分"
    subtitle="给你指导、论文定稿已通过的学生打导师分；综合成绩由管理员按 导师 / 评阅 / 答辩 三项核算"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="as-layout">
      <section class="as-card as-list">
        <header class="as-card__head">
          <div><strong>选择学生</strong><span>当前批次 · 只列论文定稿已通过的学生</span></div>
          <AppButton :disabled="loading" @click="loadStudents">刷新</AppButton>
        </header>
        <div class="as-search">
          <input v-model.trim="keyword" class="ie-in" placeholder="搜索学生姓名 / 学号" @keyup.enter="loadStudents" />
          <AppButton variant="primary" :disabled="loading" @click="loadStudents">查询</AppButton>
        </div>
        <ErrorState v-if="error" :description="error" @retry="loadStudents" />
        <LoadingState v-else-if="loading" />
        <EmptyState
          v-else-if="!students.length"
          title="当前没有可以打导师分的学生"
          description="这里只显示你指导的、论文定稿已经通过的学生。定稿通过后学生会出现在这里。"
        />
        <div v-else class="as-students">
          <button
            v-for="student in students" :key="student.id" type="button"
            :class="['as-student', { 'is-active': current && String(current.id) === String(student.id) }]"
            @click="selectStudent(student)"
          >
            <span><b>{{ student.name || '未命名学生' }}</b><small>{{ student.studentNo || '未关联学号' }}</small></span>
            <span><small>{{ student.topicTitle || '未确认课题' }}</small></span>
          </button>
        </div>
      </section>

      <section class="as-card as-form">
        <template v-if="current">
          <header class="as-card__head">
            <div><strong>{{ current.name }} 的导师分</strong><span>{{ current.studentNo || '未关联学号' }} · {{ current.topicTitle || '未确认课题' }}</span></div>
          </header>
          <LoadingState v-if="gradeLoading" />
          <template v-else>
            <div class="as-context">
              <div><span>当前导师分</span><b>{{ grade && grade.advisorScore != null ? grade.advisorScore : '还没打' }}</b></div>
              <div><span>成绩状态</span><b>{{ grade ? (grade.statusLabel || grade.status) : '—' }}</b></div>
            </div>
            <p v-if="published" class="as-warn">成绩已经发布，导师分不能再改。如确实要改，请联系管理员先撤回成绩。</p>
            <template v-else>
              <label class="as-field">
                <span>导师分（0–100 的整数）</span>
                <input v-model="score" class="ie-in" type="number" inputmode="numeric" min="0" max="100" step="1" placeholder="例如 88" />
              </label>
              <div class="as-chips">
                <button v-for="n in CHIPS" :key="n" type="button" class="as-chip" @click="score = String(n)">{{ n }}</button>
              </div>
              <label class="as-field">
                <span>评语（选填）</span>
                <textarea v-model.trim="comment" class="ie-in" rows="3" maxlength="500" placeholder="对学生毕设过程的简要评价" />
              </label>
              <p v-if="willReset" class="as-warn">该生的综合成绩已经核算过，修改导师分后会退回“待核算”，需要管理员重新核算。</p>
              <p v-if="formError" class="as-error">{{ formError }}</p>
              <div class="as-actions">
                <AppButton variant="primary" :disabled="submitting || !scoreValid" @click="submit">
                  {{ submitting ? '正在保存…' : '保存导师分' }}
                </AppButton>
                <AppButton v-if="students.length > 1" @click="selectNext">选下一位学生</AppButton>
              </div>
            </template>
          </template>
        </template>
        <EmptyState v-else title="请先选择学生" description="从左侧选择一位学生后，填写导师分。" />
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { AppButton } from '@/components/ui'
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { graduationDefenseGradeApi } from '@/modules/graduation/api/graduation-defense-grade.api'
import { useGraduationBatchStore } from '@/stores/graduationBatch'
import { toast } from '@/utils/toast'

const CHIPS = [95, 90, 85, 80, 75, 70, 60]

export default {
  name: 'GraduationAdvisorScoreView',
  components: { AppButton, ModulePageShell, LoadingState, ErrorState, EmptyState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      CHIPS,
      batchStore: useGraduationBatchStore(),
      keyword: '', students: [], current: null, grade: null,
      score: '', comment: '',
      loading: false, gradeLoading: false, submitting: false,
      error: '', formError: '', loadToken: 0, gradeToken: 0
    }
  },
  computed: {
    published() { return this.grade?.status === 'PUBLISHED' },
    scoreValid() {
      const text = String(this.score ?? '').trim()
      if (!/^\d{1,3}$/.test(text)) return false
      const n = Number(text)
      return n >= 0 && n <= 100
    },
    willReset() {
      return ['CALCULATED', 'REVIEWED'].includes(this.grade?.status)
        && this.scoreValid && Number(this.score) !== this.grade?.advisorScore
    }
  },
  watch: {
    'batchStore.selectedBatchId'() {
      this.keyword = ''
      this.current = null
      this.grade = null
      this.loadStudents()
    }
  },
  created() { this.loadStudents() },
  beforeUnmount() { ++this.loadToken; ++this.gradeToken },
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
        finalStatus: 'APPROVED',
        gdIdentity: 'GD_MENTOR'
      })
      if (token !== this.loadToken) return
      if (res.code === 0) {
        this.students = res.data?.list || []
        const requested = String(this.$route.query.studentId || '')
        const keep = this.current && this.students.find((item) => String(item.id) === String(this.current.id))
        const target = keep || (requested ? this.students.find((item) => String(item.id) === requested) : null)
          || (this.students.length === 1 && !this.keyword ? this.students[0] : null)
        if (target) this.selectStudent(target)
        else if (this.current) this.current = null
      } else {
        this.students = []
        this.current = null
        this.error = res.message || '学生列表加载失败'
      }
      this.loading = false
    },
    async selectStudent(student) {
      this.current = student
      this.grade = null
      this.score = ''
      this.comment = ''
      this.formError = ''
      this.$router.replace({ query: { ...this.$route.query, batchId: this.batchStore.selectedBatchId || undefined, studentId: student.id } })
      await this.loadGrade()
    },
    async loadGrade() {
      const token = ++this.gradeToken
      const id = this.current?.id
      if (!id) return
      this.gradeLoading = true
      const res = await graduationDefenseGradeApi.getGrade(id)
      if (token !== this.gradeToken || String(this.current?.id) !== String(id)) return
      this.gradeLoading = false
      if (res.code === 0) {
        this.grade = res.data || null
        if (this.grade?.advisorScore != null) this.score = String(this.grade.advisorScore)
      } else {
        this.grade = null
        this.formError = res.message || '成绩状态加载失败'
      }
    },
    async submit() {
      if (!this.current || !this.scoreValid || this.submitting) return
      this.submitting = true
      this.formError = ''
      const res = await graduationDefenseGradeApi.submitAdvisorScore(this.current.id, {
        score: Number(this.score), comment: this.comment || undefined
      })
      this.submitting = false
      if (res.code === 0) {
        this.grade = res.data || this.grade
        toast.success(`${this.current.name} 的导师分已保存：${Number(this.score)} 分`)
      } else {
        this.formError = res.message || '导师分保存失败'
      }
    },
    selectNext() {
      const index = this.students.findIndex((item) => String(item.id) === String(this.current?.id))
      const next = this.students[(index + 1) % this.students.length]
      if (next) this.selectStudent(next)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.as-layout{display:grid;grid-template-columns:minmax(320px,.9fr) minmax(420px,1.1fr);gap:14px;align-items:start}.as-card{border:1px solid var(--border-light,#e2e8f0);border-radius:12px;background:#fff;padding:14px;min-width:0}.as-card__head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}.as-card__head>div{display:grid;gap:3px}.as-card__head strong{font-size:15px}.as-card__head span{font-size:12px;color:var(--text-tertiary,#64748b)}.as-search{display:flex;gap:8px;margin-bottom:12px}.as-search .ie-in{flex:1}.as-students{display:grid;gap:7px;max-height:620px;overflow:auto}.as-student{width:100%;display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.2fr);gap:10px;text-align:left;border:1px solid var(--border-light,#e2e8f0);border-radius:9px;background:#fff;padding:10px;cursor:pointer}.as-student.is-active{border-color:var(--pri,#2563eb);background:var(--primary-50,#eff6ff)}.as-student span{display:grid;gap:3px;min-width:0}.as-student small{font-size:11px;color:var(--text-tertiary,#64748b);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.as-context{display:grid;gap:8px;margin-bottom:14px}.as-context>div{display:grid;grid-template-columns:88px 1fr;gap:8px;padding:8px 0;border-bottom:1px dashed var(--border-light,#e2e8f0)}.as-context span,.as-field>span{font-size:12px;color:var(--text-tertiary,#64748b)}.as-context b{font-size:13px}.as-field{display:grid;gap:7px;margin-bottom:10px}.as-chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}.as-chip{padding:4px 12px;border:1px solid var(--border-light,#d9dee8);border-radius:999px;background:#fff;cursor:pointer;font-size:12px}.as-warn{margin:10px 0;padding:9px;border-radius:8px;background:#fffbeb;color:#92400e;font-size:12px}.as-error{margin:10px 0 0;padding:9px;border-radius:8px;background:#fef2f2;color:#b91c1c;font-size:12px}.as-actions{display:flex;gap:8px;margin-top:14px;flex-wrap:wrap}.mp-btn{padding:7px 14px;border:1px solid var(--border-light,#d9dee8);border-radius:8px;background:#fff;cursor:pointer}.mp-btn--primary{background:var(--pri,#2563eb);border-color:var(--pri,#2563eb);color:#fff}.mp-btn:disabled{opacity:.55;cursor:not-allowed}@media(max-width:1100px){.as-layout{grid-template-columns:1fr}.as-students{max-height:420px}}
</style>
