<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="pageTitle"
    :subtitle="student ? `${student.name}（${student.studentNo}）` : ''"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="init" />
    <form v-else class="ie-form" @submit.prevent="submit">
      <template v-if="action === 'taskbook'">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">任务目标 <i>*</i></span><textarea v-model.trim="tbForm.objective" class="ie-in" rows="2" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">任务内容 <i>*</i></span><textarea v-model.trim="tbForm.content" class="ie-in" rows="2" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">进度计划</span><textarea v-model.trim="tbForm.progressPlan" class="ie-in" rows="2" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">成果要求</span><textarea v-model.trim="tbForm.outcomeRequirement" class="ie-in" rows="2" /></label>
        <label v-if="tbMode === 'change'" class="ie-fld ie-fld--full"><span class="ie-lbl">变更原因（≥5字）<i>*</i></span><textarea v-model.trim="tbForm.reason" class="ie-in" rows="2" /></label>
      </template>
      <template v-else-if="action === 'guidance'">
        <label class="ie-fld"><span class="ie-lbl">指导方式</span>
          <select v-model="guidanceForm.method" class="ie-in"><option value="ONLINE">线上</option><option value="OFFLINE">线下</option></select>
        </label>
        <AppDateTimePicker v-model="guidanceForm.guidanceDate" class="ie-fld" label="指导时间" hint="默认当前时间" />
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">指导内容 <i>*</i></span><textarea v-model.trim="guidanceForm.content" class="ie-in" rows="2" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">发现的问题</span><textarea v-model.trim="guidanceForm.issues" class="ie-in" rows="2" /></label>
      </template>
      <template v-else-if="action === 'midterm'">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">结论 <i>*</i></span>
          <select v-model="mtForm.conclusion" class="ie-in">
            <option value="PASS">通过</option><option value="RECTIFY">限期整改</option><option value="FAIL">不通过</option>
          </select>
        </label>
        <AppDeadlinePicker v-if="mtForm.conclusion === 'RECTIFY'" v-model="mtForm.rectifyDeadline" class="ie-fld ie-fld--full" label="整改截止日期" hint="限期整改默认 23:59" />
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">检查意见</span><textarea v-model.trim="mtForm.comment" class="ie-in" rows="2" /></label>
      </template>
      <template v-else-if="action === 'rectify'">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">整改内容 <i>*</i></span><textarea v-model.trim="rectifyContent" class="ie-in" rows="3" /></label>
      </template>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template v-if="!loading && !error" #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">保存</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { AppDateTimePicker, AppDeadlinePicker } from '@/components/common/date'
import { graduationTaskbookApi } from '@/modules/graduation/api/graduation-taskbook.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'
import { toDateTimeInputValue, daysFromNowDeadline } from '@/utils/dateUtils'

const ACTION_TITLES = {
  taskbook: '任务书',
  guidance: '新增指导记录',
  midterm: '发起中期检查',
  rectify: '提交整改'
}

export default {
  name: 'GraduationProcessActionView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, AppDateTimePicker, AppDeadlinePicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', student: null, action: 'taskbook', tbMode: 'issue',
      tbForm: { objective: '', content: '', progressPlan: '', outcomeRequirement: '', reason: '' },
      guidanceForm: { method: 'ONLINE', guidanceDate: '', content: '', issues: '' },
      mtForm: { conclusion: 'PASS', comment: '', rectifyDeadline: '' },
      rectifyContent: '',
      formError: '', submitting: false
    }
  },
  computed: {
    studentId() { return this.$route.params.studentId },
    pageTitle() {
      if (this.action === 'taskbook') return this.tbMode === 'change' ? '变更任务书' : '下达任务书'
      return ACTION_TITLES[this.action] || '过程指导'
    },
    backTo() {
      const panel = { taskbook: 'taskbook', guidance: 'guidance', midterm: 'midterm', rectify: 'midterm' }[this.action] || 'taskbook'
      return `/admin/graduation/process?panel=${panel}`
    }
  },
  created() { this.init() },
  methods: {
    async init() {
      this.loading = true
      this.error = ''
      const action = this.$route.params.action
      if (!['taskbook', 'guidance', 'midterm', 'rectify'].includes(action)) {
        this.error = '无效的操作类型'
        this.loading = false
        return
      }
      this.action = action
      const s = await gdStudentApi.getStudentDetail(this.studentId)
      if (s.code !== 0) { this.error = s.message; this.loading = false; return }
      this.student = s.data
      if (action === 'taskbook') {
        this.tbMode = this.$route.query.mode === 'change' ? 'change' : 'issue'
        if (this.tbMode === 'change') {
          const tb = await graduationTaskbookApi.getTaskbook(this.studentId)
          if (tb.code === 0 && tb.data?.exists) {
            this.tbForm = {
              objective: tb.data.objective, content: tb.data.content,
              progressPlan: tb.data.progressPlan, outcomeRequirement: tb.data.outcomeRequirement, reason: ''
            }
          }
        }
      } else if (action === 'guidance') {
        this.guidanceForm = { method: 'ONLINE', guidanceDate: toDateTimeInputValue(new Date()), content: '', issues: '' }
      } else if (action === 'midterm') {
        this.mtForm = { conclusion: 'PASS', comment: '', rectifyDeadline: daysFromNowDeadline(7) }
      }
      this.loading = false
    },
    async submit() {
      this.formError = ''
      this.submitting = true
      try {
        let res
        if (this.action === 'taskbook') {
          if (this.tbMode === 'change' && this.tbForm.reason.length < 5) {
            this.formError = '变更原因至少 5 字'
            return
          }
          res = this.tbMode === 'change'
            ? await graduationTaskbookApi.changeTaskbook(this.studentId, this.tbForm)
            : await graduationTaskbookApi.issueTaskbook(this.studentId, this.tbForm)
        } else if (this.action === 'guidance') {
          if (!this.guidanceForm.content) { this.formError = '指导内容必填'; return }
          res = await graduationTaskbookApi.createGuidance(this.studentId, this.guidanceForm)
        } else if (this.action === 'midterm') {
          const payload = {
            ...this.mtForm,
            rectifyDeadline: this.mtForm.rectifyDeadline ? String(this.mtForm.rectifyDeadline).slice(0, 10) : ''
          }
          res = await graduationTaskbookApi.checkMidterm(this.studentId, payload)
        } else if (this.action === 'rectify') {
          if (!this.rectifyContent) { this.formError = '整改内容必填'; return }
          res = await graduationTaskbookApi.submitRectification(this.studentId, this.rectifyContent)
        }
        if (res && res.code === 0) {
          toast.success('已保存')
          this.$router.push(this.backTo)
        } else if (res) this.formError = res.message
      } finally { this.submitting = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
