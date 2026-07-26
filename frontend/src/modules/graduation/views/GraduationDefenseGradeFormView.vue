<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="formTitle"
    :subtitle="student ? `${student.name}（${student.studentNo}）` : ''"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="init" />
    <form v-else class="ie-form" @submit.prevent="submit">
      <template v-for="f in formFields" :key="f.key">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">{{ f.label }} <i v-if="f.required">*</i></span>
          <textarea v-if="f.type === 'textarea'" v-model.trim="form[f.key]" class="ie-in" rows="2" />
          <input v-else-if="f.type === 'checkbox'" v-model="form[f.key]" type="checkbox" class="ie-check" />
          <input v-else v-model="form[f.key]" class="ie-in" :readonly="f.readonly" />
          <AppTemplateChips v-if="f.chips" :options="f.chips" @pick="(v) => onPickChip(f, v)" />
        </label>
      </template>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>
    <template v-if="!loading && !error" #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">提交</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { AppTemplateChips } from '@/components/common'
import { graduationDefenseGradeApi } from '@/modules/graduation/api/graduation-defense-grade.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { toast } from '@/utils/toast'

const DEFENSE_COMMENT_CHIPS = [
  '选题有实际意义，完成度高',
  '回答问题思路清晰',
  '论文结构完整，工作量饱满',
  '部分问题回答不够深入'
]
const ADVISOR_SCORE_CHIPS = [
  { label: '优秀 92', value: 92 },
  { label: '良好 83', value: 83 },
  { label: '中等 75', value: 75 },
  { label: '及格 65', value: 65 }
]

const FORM_PRESETS = {
  plagiarismResult: {
    title: '回填查重结果',
    fields: [{ key: 'rate', label: '重复率(%)', required: true }, { key: 'reportUrl', label: '报告链接' }]
  },
  dispute: {
    title: '申请复查',
    fields: [{ key: 'reason', label: '复查理由(≥5字)', required: true, type: 'textarea' }]
  },
  reviewSubmit: {
    title: '提交评阅',
    fields: [{ key: 'score', label: '评分(0-100)', required: true }, { key: 'opinion', label: '评阅意见', required: true, type: 'textarea' }]
  },
  reviewReturn: {
    title: '退回重评',
    fields: [{ key: 'reason', label: '退回原因(≥5字)', required: true, type: 'textarea' }]
  },
  scoreEntry: {
    title: '录入评委评分',
    fields: [
      { key: 'judgeName', label: '评委姓名', required: true },
      { key: 'absent', label: '评委缺席', type: 'checkbox' },
      { key: 'absentReason', label: '缺席原因（缺席时必填）' },
      { key: 'score', label: '评分(0-100，缺席时留空)' },
      { key: 'comment', label: '评语', type: 'textarea', chips: DEFENSE_COMMENT_CHIPS }
    ]
  },
  secondDefense: {
    title: '创建二次答辩',
    fields: [{ key: 'reason', label: '原因(≥5字)', required: true, type: 'textarea' }]
  },
  calculate: {
    title: '核算成绩',
    fields: [
      { key: 'advisorScore', label: '导师分', required: true, chips: ADVISOR_SCORE_CHIPS },
      { key: 'reviewerScore', label: '评阅分（自动汇总）', readonly: true },
      { key: 'defenseScore', label: '答辩分（自动汇总）', required: true, readonly: true }
    ]
  },
  returnGrade: {
    title: '复核退回',
    fields: [{ key: 'comment', label: '退回原因(≥5字)', required: true, type: 'textarea' }]
  },
  withdraw: {
    title: '撤回成绩',
    fields: [{ key: 'reason', label: '撤回原因(≥5字)', required: true, type: 'textarea' }]
  }
}

export default {
  name: 'GraduationDefenseGradeFormView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, AppTemplateChips },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', student: null,
      formKey: '', formTitle: '', formFields: [], form: {},
      formError: '', submitting: false, recordId: ''
    }
  },
  computed: {
    studentId() { return this.$route.params.studentId || this.$route.query.studentId },
    backTo() {
      const panel = this.$route.query.panel || 'plagiarism'
      const batch = this.$route.query.batchId ? `&batchId=${encodeURIComponent(this.$route.query.batchId)}` : ''
      return `/admin/graduation/defense-grade?panel=${panel}${batch}`
    }
  },
  created() { this.init() },
  methods: {
    onPickChip(f, value) {
      this.form[f.key] = f.type === 'textarea'
        ? (this.form[f.key] ? this.form[f.key] + '\n' + value : String(value))
        : value
    },
    async init() {
      this.loading = true
      this.error = ''
      this.formKey = this.$route.query.formKey || ''
      this.recordId = this.$route.query.recordId || ''
      if (!this.studentId) { this.error = '缺少学生标识，请返回后重新选择学生'; this.loading = false; return }
      const preset = FORM_PRESETS[this.formKey]
      if (!preset) { this.error = '无效的表单类型'; this.loading = false; return }
      this.formTitle = preset.title
      this.formFields = preset.fields
      this.form = {}
      preset.fields.forEach((f) => { this.form[f.key] = f.type === 'checkbox' ? false : '' })
      const s = await gdStudentApi.getStudentDetail(this.studentId)
      if (s.code !== 0) { this.error = s.message; this.loading = false; return }
      this.student = s.data
      if (this.formKey === 'calculate') {
        const grade = await graduationDefenseGradeApi.getGrade(this.studentId)
        if (grade.code !== 0) { this.error = grade.message; this.loading = false; return }
        const source = grade.data.sourceScores || {}
        this.form.advisorScore = grade.data.advisorScore ?? ''
        this.form.reviewerScore = source.reviewerScore ?? ''
        this.form.defenseScore = source.defenseScore ?? ''
        if (source.reviewerScore == null || source.defenseScore == null) {
          this.error = '请先完成教师评阅与答辩评分确认'
        }
      }
      this.loading = false
    },
    async submit() {
      this.formError = ''
      this.submitting = true
      try {
        let res
        const sid = this.studentId
        const f = this.form
        if (this.formKey === 'plagiarismResult') {
          res = await graduationDefenseGradeApi.setPlagiarismResult(this.recordId, f.rate, f.reportUrl)
        } else if (this.formKey === 'dispute') {
          res = await graduationDefenseGradeApi.disputePlagiarism(this.recordId, f.reason)
        } else if (this.formKey === 'reviewSubmit') {
          res = await graduationDefenseGradeApi.submitReview(this.recordId, Number(f.score), f.opinion)
        } else if (this.formKey === 'reviewReturn') {
          res = await graduationDefenseGradeApi.returnReview(this.recordId, f.reason)
        } else if (this.formKey === 'scoreEntry') {
          if (f.absent && !String(f.absentReason || '').trim()) {
            this.formError = '评委缺席时必须填写缺席原因'
            return
          }
          if (!f.absent && (f.score === '' || f.score == null)) {
            this.formError = '非缺席评委必须填写评分'
            return
          }
          res = await graduationDefenseGradeApi.enterScore({
            gdStudentId: sid, judgeName: f.judgeName,
            score: f.absent ? undefined : Number(f.score), comment: f.comment,
            absent: !!f.absent, absentReason: f.absent ? f.absentReason : undefined
          })
        } else if (this.formKey === 'secondDefense') {
          res = await graduationDefenseGradeApi.createSecondDefense(sid, f.reason)
        } else if (this.formKey === 'calculate') {
          res = await graduationDefenseGradeApi.calculateGrade(sid, {
            advisorScore: f.advisorScore ? Number(f.advisorScore) : undefined,
            reviewerScore: f.reviewerScore ? Number(f.reviewerScore) : undefined,
            defenseScore: f.defenseScore ? Number(f.defenseScore) : undefined
          })
        } else if (this.formKey === 'returnGrade') {
          res = await graduationDefenseGradeApi.reviewGrade(sid, { action: 'RETURN', comment: f.comment })
        } else if (this.formKey === 'withdraw') {
          res = await graduationDefenseGradeApi.withdrawGrade(sid, f.reason)
        }
        if (res && res.code === 0) {
          toast.success('已提交')
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
