<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="activePreset.title"
    :subtitle="pageSubtitle"
    :eyebrow="activePreset.eyebrow"
    :purpose="activePreset.purpose"
    :status-text="formStatusText"
    status-tone="warning"
    :back-to="backTo"
    :busy="submitting"
    @blocked-back="onBlockedBack"
  >
    <template #context>
      <div class="dgf-context">
        <span><b>学生</b>{{ student ? `${student.name} · ${student.studentNo}` : '正在读取' }}</span>
        <span><b>批次</b>{{ batchLabel }}</span>
        <span><b>记录</b>{{ recordLabel }}</span>
      </div>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="init" />
    <form v-else class="ie-form dgf-form" @submit.prevent="submit">
      <section class="dgf-command ie-fld--full" aria-label="当前职责与写入对象">
        <div>
          <span>{{ activePreset.roleLabel }}</span>
          <strong>{{ activePreset.command }}</strong>
          <p>{{ activePreset.contract }}</p>
        </div>
        <b>{{ activePreset.riskLabel }}</b>
      </section>

      <section v-if="formKey === 'scoreEntry'" class="dgf-actor ie-fld--full" aria-label="当前登录评委">
        <div>
          <span>当前登录评委</span>
          <strong>{{ actorName || '身份未确认' }}</strong>
          <small>评分人来自登录身份与答辩组席位，不能在页面中修改。</small>
        </div>
        <StatusTag :type="actorName ? 'success' : 'danger'" :label="actorName ? '身份已锁定' : '禁止提交'" dot />
      </section>

      <section class="dgf-fields ie-fld--full">
        <header>
          <div><span>本次填写</span><strong>{{ activePreset.sectionTitle }}</strong></div>
          <small>提交时锁定学生、批次、记录和表单草稿</small>
        </header>
        <div class="dgf-fields__body">
          <template v-for="field in formFields" :key="field.key">
            <label v-if="field.type === 'checkbox'" class="dgf-check ie-fld--full" :for="fieldId(field)">
              <input
                :id="fieldId(field)"
                v-model="form[field.key]"
                type="checkbox"
                class="ie-check"
                :disabled="submitting"
                :aria-describedby="field.hint ? hintId(field) : undefined"
              />
              <span>
                <strong>{{ field.label }}</strong>
                <small v-if="field.hint" :id="hintId(field)">{{ field.hint }}</small>
              </span>
            </label>
            <div v-else class="ie-fld ie-fld--full">
              <label class="ie-lbl" :for="fieldId(field)">{{ field.label }} <i v-if="field.required">*</i></label>
              <textarea
                v-if="field.type === 'textarea'"
                :id="fieldId(field)"
                v-model.trim="form[field.key]"
                class="ie-in"
                rows="4"
                :disabled="submitting"
                :aria-describedby="field.hint ? hintId(field) : undefined"
                :placeholder="field.placeholder || ''"
                @input="formError = ''"
              ></textarea>
              <input
                v-else
                :id="fieldId(field)"
                v-model="form[field.key]"
                class="ie-in"
                :type="field.inputType || 'text'"
                :inputmode="field.inputMode || undefined"
                :min="field.min"
                :max="field.max"
                :readonly="field.readonly"
                :disabled="submitting"
                :aria-describedby="field.hint ? hintId(field) : undefined"
                :placeholder="field.placeholder || ''"
                @input="formError = ''"
              />
              <p v-if="field.hint" :id="hintId(field)" class="ie-hint">{{ field.hint }}</p>
              <AppTemplateChips v-if="field.chips && !submitting" :options="field.chips" @pick="(value) => onPickChip(field, value)" />
            </div>
          </template>
        </div>
      </section>

      <p v-if="formError" class="ie-err" role="alert">{{ formError }}</p>
    </form>

    <template v-if="!loading && !error" #aside>
      <section class="dgf-aside-card">
        <span>提交前检查</span>
        <ul>
          <li v-if="formKey === 'scoreEntry'" :class="{ done: Boolean(actorName) }">
            <b>{{ actorName ? '✓' : '!' }}</b><div><strong>登录评委身份</strong><small>{{ actorName || '尚未确认' }}</small></div>
          </li>
          <li v-for="item in completionItems" :key="item.key" :class="{ done: item.done }">
            <b>{{ item.done ? '✓' : item.order }}</b><div><strong>{{ item.label }}</strong><small>{{ item.hint }}</small></div>
          </li>
        </ul>
      </section>
      <details class="dgf-next">
        <summary>提交后的流转</summary>
        <ol><li v-for="item in activePreset.nextSteps" :key="item">{{ item }}</li></ol>
      </details>
    </template>

    <template v-if="!loading && !error" #footer>
      <button type="button" class="mp-btn" :disabled="submitting" @click="cancel">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitDisabled" @click="submit">
        {{ submitting ? '正在提交…' : activePreset.submitLabel }}
      </button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState, StatusTag } from '@/components/business'
import { AppTemplateChips } from '@/components/common'
import { graduationDefenseGradeApi } from '@/modules/graduation/api/graduation-defense-grade.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { getAuthContext } from '@/security/auth/auth.context'
import { matchPermission } from '@/config/navPlan'
import {
  graduationActionErrorMessage,
  graduationConflictMessage,
  isGraduationConflictResponse
} from '@/modules/graduation/utils/form-state'
import { toast } from '@/utils/toast'

const DEFENSE_COMMENT_CHIPS = ['选题有实际意义，完成度高', '回答问题思路清晰', '论文结构完整，工作量饱满', '部分问题回答不够深入']
const ADVISOR_SCORE_CHIPS = [
  { label: '优秀 92', value: 92 }, { label: '良好 83', value: 83 },
  { label: '中等 75', value: 75 }, { label: '及格 65', value: 65 }
]
const RETURN_PATHS = {
  'graduation-plagiarism-ledger': '/admin/graduation/plagiarism-ledger',
  'graduation-review-tasks': '/admin/graduation/review-tasks',
  'graduation-defense-scoring': '/admin/graduation/defense-scoring',
  'graduation-defense-confirmation': '/admin/graduation/defense-confirmation',
  'graduation-grade-ledger': '/admin/graduation/grade-ledger'
}
const PANEL_PATHS = {
  plagiarism: '/admin/graduation/plagiarism-ledger',
  review: '/admin/graduation/review-tasks',
  defense: '/admin/graduation/defense-scoring',
  grade: '/admin/graduation/grade-ledger'
}
const SAFE_PREFIX = '/admin/graduation/'
const GRADE_CONTEXT_FORMS = new Set(['calculate', 'returnGrade', 'withdraw'])
const RECORD_CONTEXT_FORMS = new Set(['plagiarismResult', 'dispute', 'reviewSubmit', 'reviewReturn'])
const FORM_PERMISSIONS = {
  plagiarismResult: 'graduationDesign.plagiarism.result',
  dispute: 'graduationDesign.plagiarism.start',
  reviewSubmit: 'graduationDesign.review.submit',
  reviewReturn: 'graduationDesign.review.return',
  scoreEntry: 'graduationDesign.defense.score',
  secondDefense: 'graduationDesign.defense.secondRound',
  calculate: 'graduationDesign.grade.calculate',
  returnGrade: 'graduationDesign.grade.review',
  withdraw: 'graduationDesign.grade.withdraw'
}

const FORM_PRESETS = {
  plagiarismResult: {
    title: '回填查重结果', eyebrow: '成果与查重', roleLabel: '查重管理员职责',
    purpose: '将第三方查重结果绑定当前正式成果记录。', command: '回填当前查重记录',
    contract: '后续准入只认服务器规则和正式成果版本。', riskLabel: '绑定当前记录', sectionTitle: '查重结果', submitLabel: '确认回填',
    fields: [
      { key: 'rate', label: '重复率（%）', required: true, inputType: 'number', inputMode: 'decimal', min: 0, max: 100, hint: '填写第三方查重系统返回的真实百分比。' },
      { key: 'reportUrl', label: '报告链接', placeholder: 'https://…', hint: '填写学校允许访问的查重报告地址。' }
    ],
    nextSteps: ['保存查重结果', '服务器重新判断阈值', '答辩准入读取最新状态']
  },
  dispute: {
    title: '申请查重复查', eyebrow: '成果与查重', roleLabel: '指导教师职责',
    purpose: '为当前查重记录提交可追溯的复查理由。', command: '提交复查申请',
    contract: '申请期间原查重结果继续有效。', riskLabel: '原结果保留', sectionTitle: '复查依据', submitLabel: '提交复查申请',
    fields: [{ key: 'reason', label: '复查理由', required: true, type: 'textarea', placeholder: '说明复查原因，不少于 5 个字。' }],
    nextSteps: ['生成待审核申请', '授权角色审核', '更新查重状态与审计']
  },
  reviewSubmit: {
    title: '提交正式评阅', eyebrow: '成果与评阅', roleLabel: '评阅教师职责',
    purpose: '对分配给本人的正式评阅任务提交评分和意见。', command: '提交当前评阅任务',
    contract: '评阅分进入成绩来源，不修改导师分或答辩分。', riskLabel: '当前评阅任务', sectionTitle: '评阅结论', submitLabel: '提交正式评阅',
    fields: [
      { key: 'score', label: '评阅评分（0–100）', required: true, inputType: 'number', inputMode: 'decimal', min: 0, max: 100 },
      { key: 'opinion', label: '评阅意见', required: true, type: 'textarea', placeholder: '写明成果质量、问题和结论。' }
    ],
    nextSteps: ['评阅任务完成', '成绩台账读取评阅分', '学生端按权限查看反馈']
  },
  reviewReturn: {
    title: '退回重新评阅', eyebrow: '成果与评阅', roleLabel: '评阅管理职责',
    purpose: '退回当前评阅任务并保留原记录。', command: '要求重新评阅',
    contract: '管理角色不能替评阅教师补填新结论。', riskLabel: '历史保留', sectionTitle: '退回原因', submitLabel: '确认退回重评',
    fields: [{ key: 'reason', label: '退回原因', required: true, type: 'textarea', placeholder: '说明退回原因，不少于 5 个字。' }],
    nextSteps: ['任务回到待处理', '评阅教师重新核验版本', '再次提交评阅']
  },
  scoreEntry: {
    title: '录入本人答辩评分', eyebrow: '答辩与成绩', roleLabel: '答辩评委职责',
    purpose: '当前登录评委只提交本人对该学生本轮答辩的评分或缺席事实。', command: '提交本人评分',
    contract: '评分人来自认证身份；秘书确认与评委评分严格分离。', riskLabel: '仅本人评分', sectionTitle: '本轮评分', submitLabel: '提交本人评分',
    fields: [
      { key: 'absent', label: '本人缺席', type: 'checkbox', hint: '缺席时必须填写原因，评分留空。' },
      { key: 'absentReason', label: '缺席原因', placeholder: '仅缺席时填写' },
      { key: 'score', label: '答辩评分（0–100）', inputType: 'number', inputMode: 'decimal', min: 0, max: 100, hint: '非缺席时必填。' },
      { key: 'comment', label: '答辩评语', type: 'textarea', chips: DEFENSE_COMMENT_CHIPS, placeholder: '写明答辩表现和改进建议。' }
    ],
    nextSteps: ['保存本人评分或缺席事实', '等待其他评委完成', '秘书在完整后确认本轮']
  },
  secondDefense: {
    title: '发起二次答辩', eyebrow: '答辩与成绩', roleLabel: '答辩管理职责',
    purpose: '保留原答辩记录并创建新的答辩轮次。', command: '创建二次答辩轮次',
    contract: '新轮次不会覆盖第一次答辩。', riskLabel: '新增轮次', sectionTitle: '发起依据', submitLabel: '创建二次答辩',
    fields: [{ key: 'reason', label: '发起原因', required: true, type: 'textarea', placeholder: '说明原因，不少于 5 个字。' }],
    nextSteps: ['创建新轮次', '重新安排时间地点和评委', '发布后通知相关人员']
  },
  calculate: {
    title: '核算毕业设计成绩', eyebrow: '答辩与成绩', roleLabel: '成绩管理员职责',
    purpose: '基于导师分、正式评阅分和已确认答辩分核算综合成绩。', command: '核算当前学生成绩',
    contract: '评阅分和答辩分来自服务器，只读。', riskLabel: '来源项须齐全', sectionTitle: '成绩来源', submitLabel: '确认核算',
    fields: [
      { key: 'advisorScore', label: '导师分', required: true, inputType: 'number', inputMode: 'decimal', min: 0, max: 100, chips: ADVISOR_SCORE_CHIPS },
      { key: 'reviewerScore', label: '评阅分（服务器汇总）', readonly: true },
      { key: 'defenseScore', label: '答辩分（服务器汇总）', required: true, readonly: true }
    ],
    nextSteps: ['按批次权重核算', '进入待复核', '复核后发布']
  },
  returnGrade: {
    title: '成绩复核退回', eyebrow: '答辩与成绩', roleLabel: '成绩复核职责',
    purpose: '退回当前成绩版本并保留复核意见。', command: '要求重新核算',
    contract: '来源分必须回原业务环节处理。', riskLabel: '原版本保留', sectionTitle: '复核意见', submitLabel: '确认退回',
    fields: [{ key: 'comment', label: '退回原因', required: true, type: 'textarea', placeholder: '说明原因，不少于 5 个字。' }],
    nextSteps: ['成绩回到可核算状态', '核对来源项', '重新核算并复核']
  },
  withdraw: {
    title: '撤回已发布成绩', eyebrow: '答辩与成绩', roleLabel: '成绩管理员职责',
    purpose: '有原因、有留痕地撤回已发布成绩。', command: '撤回当前成绩版本',
    contract: '撤回后必须重新核算、复核和发布。', riskLabel: '高风险操作', sectionTitle: '撤回依据', submitLabel: '确认撤回成绩',
    fields: [{ key: 'reason', label: '撤回原因', required: true, type: 'textarea', placeholder: '说明原因，不少于 5 个字。' }],
    nextSteps: ['变为撤回状态', '学生端同步状态', '重新核算、复核并发布']
  }
}

const EMPTY_PRESET = {
  title: '毕业设计操作', eyebrow: '毕业设计', roleLabel: '当前角色职责', purpose: '处理当前学生的毕业设计业务。',
  command: '提交当前操作', contract: '以服务端状态机为准。', riskLabel: '待确认', sectionTitle: '业务内容', submitLabel: '提交', fields: [], nextSteps: []
}

export default {
  name: 'GraduationDefenseGradeFormView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, StatusTag, AppTemplateChips },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', student: null, formKey: '', formFields: [], form: {}, formError: '',
      submitting: false, recordId: '', commandSnapshot: null, actorName: ''
    }
  },
  computed: {
    studentId() { return this.$route.params.studentId || this.$route.query.studentId },
    permissionPatterns() { return Array.isArray(this.ctx?.permissionPatterns) ? this.ctx.permissionPatterns : [] },
    activePreset() { return FORM_PRESETS[this.formKey] || EMPTY_PRESET },
    safeReturnTo() {
      const raw = Array.isArray(this.$route.query.returnTo) ? this.$route.query.returnTo[0] : this.$route.query.returnTo
      const value = String(raw || '').trim()
      return value.startsWith(SAFE_PREFIX) ? value : ''
    },
    backTo() {
      if (this.safeReturnTo) return this.safeReturnTo
      const panel = this.$route.query.panel || 'plagiarism'
      const path = RETURN_PATHS[this.$route.query.returnRoute] || PANEL_PATHS[panel] || PANEL_PATHS.plagiarism
      const query = new URLSearchParams()
      for (const key of ['batchId', 'studentId', 'panel', 'view', 'queue', 'missingType', 'status', 'source']) {
        const value = this.$route.query[key]
        if (value != null && value !== '') query.set(key, String(value))
      }
      return query.toString() ? `${path}?${query}` : path
    },
    pageSubtitle() {
      return this.student ? `${this.student.name}（${this.student.studentNo}）· ${this.activePreset.roleLabel}` : '正在读取当前学生和业务上下文'
    },
    batchLabel() { return String(this.$route.query.batchId || this.student?.batchName || '当前批次') },
    recordLabel() { return this.recordId ? `记录 ${this.recordId}` : '按当前学生办理' },
    formStatusText() { return this.submitting ? '提交中' : this.formError ? '请修正' : '待提交' },
    completionItems() {
      return this.formFields.map((field, index) => ({
        key: field.key, order: index + 1, label: field.label, done: this.fieldCompleted(field), hint: field.required ? '必填或由服务器提供' : '按实际情况填写'
      }))
    },
    submitDisabled() {
      if (this.submitting) return true
      if (this.formKey === 'scoreEntry' && !this.actorName) return true
      return this.formFields.some((field) => field.required && !this.fieldCompleted(field))
    }
  },
  created() { this.init() },
  beforeRouteLeave(_to, _from, next) {
    if (this.submitting) {
      toast.info('当前毕业设计操作正在等待服务器回执，请完成后再离开')
      next(false)
      return
    }
    next()
  },
  methods: {
    canOpenForm(formKey) {
      const permissionKey = FORM_PERMISSIONS[formKey]
      return Boolean(permissionKey && matchPermission(this.permissionPatterns, permissionKey))
    },
    fieldId(field) { return `gd-${this.formKey || 'form'}-${field.key}` },
    hintId(field) { return `${this.fieldId(field)}-hint` },
    onBlockedBack() { toast.info('当前操作正在提交，请勿重复点击或切换页面') },
    cancel() { if (!this.submitting) this.$router.push(this.backTo) },
    fieldCompleted(field) {
      if (field.type === 'checkbox') return true
      const value = this.form[field.key]
      return value !== '' && value != null
    },
    onPickChip(field, value) {
      this.form[field.key] = field.type === 'textarea' ? (this.form[field.key] ? `${this.form[field.key]}\n${value}` : String(value)) : value
      this.formError = ''
    },
    captureEditableDraft() {
      return Object.fromEntries(this.formFields.filter((field) => !field.readonly).map((field) => [field.key, this.form[field.key]]))
    },
    restoreEditableDraft(draft = {}) {
      for (const field of this.formFields) if (!field.readonly && Object.prototype.hasOwnProperty.call(draft, field.key)) this.form[field.key] = draft[field.key]
    },
    validateBeforeSubmit() {
      if (this.formKey === 'scoreEntry' && !this.actorName) return '无法确认当前登录评委身份，请重新登录后再评分'
      for (const field of this.formFields) {
        if (field.required && !this.fieldCompleted(field)) return `请填写${field.label.replace(/（.*?）|\(.*?\)/g, '')}`
        if (field.inputType === 'number' && this.form[field.key] !== '' && this.form[field.key] != null) {
          const value = Number(this.form[field.key])
          if (!Number.isFinite(value)) return `${field.label}必须是有效数字`
          if (field.min != null && value < Number(field.min)) return `${field.label}不能小于 ${field.min}`
          if (field.max != null && value > Number(field.max)) return `${field.label}不能大于 ${field.max}`
        }
      }
      if (['dispute', 'reviewReturn', 'secondDefense', 'withdraw'].includes(this.formKey) && String(this.form.reason || '').trim().length < 5) return '原因必须填写且不少于 5 个字'
      if (this.formKey === 'returnGrade' && String(this.form.comment || '').trim().length < 5) return '退回原因必须填写且不少于 5 个字'
      if (this.formKey === 'reviewSubmit' && String(this.form.opinion || '').trim().length < 2) return '评阅意见至少填写 2 个字'
      if (this.formKey === 'scoreEntry') {
        if (this.form.absent && !String(this.form.absentReason || '').trim()) return '评委缺席时必须填写缺席原因'
        if (!this.form.absent && (this.form.score === '' || this.form.score == null)) return '非缺席评委必须填写评分'
      }
      return ''
    },
    async loadStudentContext() {
      const student = await gdStudentApi.getStudentDetail(this.studentId)
      if (student.code !== 0) return student
      const routeBatchId = String(this.$route.query.batchId || '')
      const studentBatchId = String(student.data?.batchId || '')
      if (routeBatchId && studentBatchId && routeBatchId !== studentBatchId) return { code: 409, message: '当前批次与学生上下文不一致，请返回后重新选择学生' }
      this.student = student.data
      return student
    },
    async refreshConflictTruth() {
      if (this.formKey === 'calculate') {
        const grade = await graduationDefenseGradeApi.getGrade(this.studentId)
        if (grade.code === 0) {
          const source = grade.data.sourceScores || {}
          this.form.reviewerScore = source.reviewerScore ?? ''
          this.form.defenseScore = source.defenseScore ?? ''
        }
      }
      await this.loadStudentContext()
    },
    async init() {
      this.loading = true
      this.error = ''
      this.formError = ''
      this.formKey = this.$route.query.formKey || ''
      this.recordId = this.$route.query.recordId || ''
      const auth = getAuthContext()
      this.actorName = String(auth.displayName || auth.username || '').trim()
      if (!this.studentId) { this.error = '缺少学生标识，请返回后重新选择学生'; this.loading = false; return }
      const preset = FORM_PRESETS[this.formKey]
      if (!preset) { this.error = '无效的表单类型'; this.loading = false; return }
      if (!this.canOpenForm(this.formKey)) { this.error = '当前角色无权执行该毕业设计操作，请返回对应工作区'; this.loading = false; return }
      if (RECORD_CONTEXT_FORMS.has(this.formKey) && !this.recordId) { this.error = '缺少业务记录标识，请返回对应工作区重新选择记录'; this.loading = false; return }
      if (this.formKey === 'scoreEntry' && !this.actorName) { this.error = '无法确认当前登录评委身份，请重新登录后再评分'; this.loading = false; return }

      this.formFields = preset.fields
      this.form = {}
      preset.fields.forEach((field) => { this.form[field.key] = field.type === 'checkbox' ? false : '' })

      let grade = null
      if (GRADE_CONTEXT_FORMS.has(this.formKey)) {
        grade = await graduationDefenseGradeApi.getGrade(this.studentId)
        if (grade.code !== 0) { this.error = grade.message || '当前成绩上下文不可用'; this.loading = false; return }
      }
      const student = await this.loadStudentContext()
      if (student.code !== 0) { this.error = student.message || '学生上下文加载失败'; this.loading = false; return }

      if (this.formKey === 'calculate') {
        const source = grade.data.sourceScores || {}
        this.form.advisorScore = grade.data.advisorScore ?? ''
        this.form.reviewerScore = source.reviewerScore ?? ''
        this.form.defenseScore = source.defenseScore ?? ''
        if (source.reviewerScore == null || source.defenseScore == null) this.error = '请先完成教师评阅与答辩评分确认'
      }
      this.loading = false
    },
    async submit() {
      if (this.submitting) return
      this.formError = ''
      if (!this.canOpenForm(this.formKey)) { this.formError = '当前角色无权执行该毕业设计操作'; return }
      const validation = this.validateBeforeSubmit()
      if (validation) { this.formError = validation; return }
      const snapshot = Object.freeze({
        formKey: this.formKey,
        studentId: String(this.studentId),
        recordId: String(this.recordId || ''),
        batchId: String(this.$route.query.batchId || ''),
        actorName: this.actorName,
        form: Object.freeze({ ...this.form }),
        backTo: this.backTo
      })
      this.commandSnapshot = snapshot
      this.submitting = true
      try {
        let res
        const sid = snapshot.studentId
        const f = snapshot.form
        if (snapshot.formKey === 'plagiarismResult') res = await graduationDefenseGradeApi.setPlagiarismResult(snapshot.recordId, f.rate, f.reportUrl)
        else if (snapshot.formKey === 'dispute') res = await graduationDefenseGradeApi.disputePlagiarism(snapshot.recordId, f.reason)
        else if (snapshot.formKey === 'reviewSubmit') res = await graduationDefenseGradeApi.submitReview(snapshot.recordId, Number(f.score), f.opinion)
        else if (snapshot.formKey === 'reviewReturn') res = await graduationDefenseGradeApi.returnReview(snapshot.recordId, f.reason)
        else if (snapshot.formKey === 'scoreEntry') {
          res = await graduationDefenseGradeApi.enterScore({
            gdStudentId: sid,
            judgeName: snapshot.actorName,
            score: f.absent ? undefined : Number(f.score),
            comment: f.comment,
            absent: Boolean(f.absent),
            absentReason: f.absent ? f.absentReason : undefined
          })
        } else if (snapshot.formKey === 'secondDefense') res = await graduationDefenseGradeApi.createSecondDefense(sid, f.reason)
        else if (snapshot.formKey === 'calculate') {
          res = await graduationDefenseGradeApi.calculateGrade(sid, {
            advisorScore: f.advisorScore ? Number(f.advisorScore) : undefined,
            reviewerScore: f.reviewerScore ? Number(f.reviewerScore) : undefined,
            defenseScore: f.defenseScore ? Number(f.defenseScore) : undefined
          })
        } else if (snapshot.formKey === 'returnGrade') res = await graduationDefenseGradeApi.reviewGrade(sid, { action: 'RETURN', comment: f.comment })
        else if (snapshot.formKey === 'withdraw') res = await graduationDefenseGradeApi.withdrawGrade(sid, f.reason)

        if (res?.code === 0) {
          toast.success(`${this.activePreset.title}已提交`)
          this.$router.push(snapshot.backTo)
        } else if (res && isGraduationConflictResponse(res)) {
          const draft = this.captureEditableDraft()
          await this.refreshConflictTruth()
          this.restoreEditableDraft(draft)
          this.formError = graduationConflictMessage(res)
        } else if (res) this.formError = graduationActionErrorMessage(res)
      } catch (error) {
        this.formError = error?.message || '操作未完成，请稍后重试'
      } finally {
        this.submitting = false
        this.commandSnapshot = null
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.dgf-context{display:flex;min-width:0;gap:6px}.dgf-context span{display:grid;min-width:145px;gap:1px;padding:6px 8px;border:1px solid var(--border-light);border-radius:8px;background:#fff;color:var(--text-secondary);font-size:10px}.dgf-context b{color:var(--text-tertiary);font-size:9px}.dgf-form{gap:10px}.dgf-command,.dgf-actor{display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:10px;padding:10px 12px;border:1px solid var(--primary-100);border-radius:9px;background:var(--primary-50)}.dgf-command>div,.dgf-actor>div{display:grid;gap:1px}.dgf-command span,.dgf-actor span{color:var(--primary-600);font-size:9px;font-weight:700;letter-spacing:.06em}.dgf-command strong,.dgf-actor strong{color:var(--text-primary);font-size:12px}.dgf-command p,.dgf-actor small{margin:0;color:var(--text-secondary);font-size:9px;line-height:1.45}.dgf-command>b{padding:4px 7px;border-radius:999px;background:var(--warning-50);color:var(--warning-800);font-size:9px;white-space:nowrap}.dgf-actor{border-color:var(--success-100,#d1fae5);background:var(--success-50,#ecfdf5)}.dgf-fields{overflow:hidden;border:1px solid var(--border-light);border-radius:9px;background:#fff}.dgf-fields>header{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:8px 10px;border-bottom:1px solid var(--border-light);background:var(--gray-50)}.dgf-fields>header>div{display:grid;gap:1px}.dgf-fields>header span,.dgf-fields>header small{color:var(--text-tertiary);font-size:9px}.dgf-fields>header strong{font-size:11px}.dgf-fields__body{display:grid;gap:10px;padding:10px}.dgf-check{display:flex;align-items:flex-start;gap:8px;padding:8px;border:1px solid var(--border-light);border-radius:8px;background:var(--gray-50)}.dgf-check span{display:grid;gap:1px}.dgf-check strong{font-size:10px}.dgf-check small{color:var(--text-tertiary);font-size:9px}.dgf-aside-card,.dgf-next{padding:10px;border:1px solid var(--border-light);border-radius:9px;background:#fff}.dgf-aside-card>span{font-size:11px;font-weight:700}.dgf-aside-card ul,.dgf-next ol{display:grid;gap:6px;margin:7px 0 0;padding:0;list-style:none}.dgf-aside-card li{display:flex;gap:7px;font-size:9px}.dgf-aside-card li>b{display:grid;width:20px;height:20px;flex:none;place-items:center;border-radius:50%;background:var(--gray-100);color:var(--text-tertiary);font-size:8px}.dgf-aside-card li.done>b{background:var(--success-50);color:var(--success-700)}.dgf-aside-card li div{display:grid;gap:1px}.dgf-aside-card li strong{font-size:9px}.dgf-aside-card li small{color:var(--text-tertiary);font-size:8px}.dgf-next summary{cursor:pointer;color:var(--text-primary);font-size:10px;font-weight:700}.dgf-next ol{counter-reset:next}.dgf-next li{display:flex;gap:6px;color:var(--text-secondary);font-size:9px}.dgf-next li::before{counter-increment:next;content:counter(next);display:grid;width:17px;height:17px;flex:none;place-items:center;border-radius:5px;background:var(--primary-50);color:var(--primary-700);font-size:8px}.mp-btn{padding:7px 15px;border:1px solid var(--line,#d9dee8);border-radius:8px;background:#fff;cursor:pointer;font-size:12px}.mp-btn--primary{border-color:var(--pri,#2563eb);background:var(--pri,#2563eb);color:#fff}.mp-btn:disabled{cursor:not-allowed;opacity:.5}@media(max-width:760px){.dgf-command,.dgf-actor{grid-template-columns:1fr}}
</style>
