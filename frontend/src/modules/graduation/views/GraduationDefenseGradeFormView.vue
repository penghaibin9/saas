<template>
  <GraduationFormPageShell
    :ctx="ctx"
    :title="formTitle"
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
        <span><b>当前学生</b>{{ student ? `${student.name} · ${student.studentNo}` : '正在读取' }}</span>
        <span><b>当前批次</b>{{ batchLabel }}</span>
        <span><b>业务记录</b>{{ recordLabel }}</span>
      </div>
    </template>

    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="init" />
    <form v-else class="ie-form dgf-form" @submit.prevent="submit">
      <section class="dgf-command ie-fld--full" aria-label="本次操作职责">
        <div>
          <span>{{ activePreset.roleLabel }}</span>
          <strong>{{ activePreset.command }}</strong>
          <p>{{ activePreset.contract }}</p>
        </div>
        <b>{{ activePreset.riskLabel }}</b>
      </section>

      <section class="dgf-fields ie-fld--full">
        <header>
          <div>
            <span>本次填写</span>
            <strong>{{ activePreset.sectionTitle }}</strong>
          </div>
          <small>提交时锁定学生、批次、记录和当前表单草稿</small>
        </header>
        <div class="dgf-fields__body">
          <template v-for="field in formFields" :key="field.key">
            <label v-if="field.type === 'checkbox'" class="dgf-check ie-fld--full">
              <input v-model="form[field.key]" type="checkbox" class="ie-check" :disabled="submitting" />
              <span>
                <strong>{{ field.label }}</strong>
                <small>{{ field.hint || '勾选后按对应业务规则处理。' }}</small>
              </span>
            </label>
            <label v-else class="ie-fld ie-fld--full">
              <span class="ie-lbl">{{ field.label }} <i v-if="field.required">*</i></span>
              <textarea
                v-if="field.type === 'textarea'"
                v-model.trim="form[field.key]"
                class="ie-in"
                rows="4"
                :disabled="submitting"
                :placeholder="field.placeholder || ''"
                @input="formError = ''"
              ></textarea>
              <input
                v-else
                v-model="form[field.key]"
                class="ie-in"
                :type="field.inputType || 'text'"
                :inputmode="field.inputMode || undefined"
                :min="field.min"
                :max="field.max"
                :readonly="field.readonly"
                :disabled="submitting"
                :placeholder="field.placeholder || ''"
                @input="formError = ''"
              />
              <p v-if="field.hint" class="ie-hint">{{ field.hint }}</p>
              <AppTemplateChips v-if="field.chips && !submitting" :options="field.chips" @pick="(value) => onPickChip(field, value)" />
            </label>
          </template>
        </div>
      </section>

      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </form>

    <template v-if="!loading && !error" #aside>
      <section class="dgf-aside-card">
        <span>提交前检查</span>
        <ul>
          <li v-for="item in completionItems" :key="item.key" :class="{ done: item.done }">
            <b>{{ item.done ? '✓' : item.order }}</b>
            <div><strong>{{ item.label }}</strong><small>{{ item.hint }}</small></div>
          </li>
        </ul>
      </section>

      <section class="dgf-aside-card is-next">
        <span>提交后的真实流转</span>
        <ol>
          <li v-for="item in activePreset.nextSteps" :key="item">{{ item }}</li>
        </ol>
      </section>

      <section class="dgf-warning">
        <strong>{{ activePreset.warningTitle }}</strong>
        <p>{{ activePreset.warning }}</p>
      </section>
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
import { LoadingState, ErrorState } from '@/components/business'
import { AppTemplateChips } from '@/components/common'
import { graduationDefenseGradeApi } from '@/modules/graduation/api/graduation-defense-grade.api'
import { gdStudentApi } from '@/modules/graduation/api/graduation-student.api'
import { matchPermission } from '@/config/navPlan'
import {
  graduationActionErrorMessage,
  graduationConflictMessage,
  isGraduationConflictResponse
} from '@/modules/graduation/utils/form-state'
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
    title: '回填查重结果', eyebrow: '成果与查重 · 结果回填', roleLabel: '查重管理员职责',
    purpose: '把第三方查重结果绑定到当前学生的正式成果记录，供后续答辩准入状态机核验。',
    command: '回填当前查重记录的重复率与报告来源',
    contract: '重复率只作为服务器状态机输入；页面不能自行决定学生是否准入答辩。',
    riskLabel: '绑定当前查重记录', sectionTitle: '查重结果', submitLabel: '确认回填',
    fields: [
      { key: 'rate', label: '重复率（%）', required: true, inputType: 'number', inputMode: 'decimal', min: 0, max: 100, hint: '填写第三方查重系统返回的真实百分比。' },
      { key: 'reportUrl', label: '报告链接', placeholder: 'https://…', hint: '仅填写学校允许访问的查重报告地址；最终可见范围仍由服务端控制。' }
    ],
    nextSteps: ['服务器保存查重结果', '重新判断查重是否超阈值', '答辩准入读取最新查重状态'],
    warningTitle: '不能在前端放行', warning: '即使重复率看起来合格，后续准入仍必须以服务端规则和当前正式成果版本为准。'
  },
  dispute: {
    title: '申请查重复查', eyebrow: '成果与查重 · 复查申请', roleLabel: '指导教师职责',
    purpose: '针对当前查重记录提出可追溯的复查理由，原查重结果在复查完成前保持不变。',
    command: '为当前查重记录提交复查申请',
    contract: '复查申请必须绑定原记录；不会覆盖原报告，也不会自动改变答辩准入。',
    riskLabel: '原结果继续有效', sectionTitle: '复查依据', submitLabel: '提交复查申请',
    fields: [{ key: 'reason', label: '复查理由', required: true, type: 'textarea', placeholder: '说明需要复查的具体原因，不少于 5 个字。', hint: '建议写明报告异常位置、版本或数据依据。' }],
    nextSteps: ['生成待审核复查申请', '授权角色审核复查', '审核后更新查重状态和审计留痕'],
    warningTitle: '申请不等于通过', warning: '提交复查后，原结果仍参与状态机判断，直到授权角色完成审核。'
  },
  reviewSubmit: {
    title: '提交正式评阅', eyebrow: '成果与评阅 · 正式写入', roleLabel: '评阅教师职责',
    purpose: '对分配给本人的正式评阅任务提交评分与意见，结果绑定当前评阅记录。',
    command: '提交当前评阅任务的评分和文字意见',
    contract: '评阅任务与指导关系保持独立；写入后进入成绩来源汇总。',
    riskLabel: '仅当前评阅任务', sectionTitle: '评阅结论', submitLabel: '提交正式评阅',
    fields: [
      { key: 'score', label: '评阅评分（0–100）', required: true, inputType: 'number', inputMode: 'decimal', min: 0, max: 100, hint: '评分会成为成绩核算的真实来源项。' },
      { key: 'opinion', label: '评阅意见', required: true, type: 'textarea', placeholder: '写明成果质量、主要问题和结论。', hint: '意见会进入学生反馈和后续审计。' }
    ],
    nextSteps: ['评阅任务进入已完成状态', '成绩台账读取评阅分', '学生端按权限查看评阅反馈'],
    warningTitle: '不能替代导师或答辩分', warning: '本次只写正式评阅任务，不修改导师评分、答辩评分或成果 FileVersion。'
  },
  reviewReturn: {
    title: '退回重新评阅', eyebrow: '成果与评阅 · 退回重评', roleLabel: '评阅管理职责',
    purpose: '把已完成或异常的正式评阅任务退回重评，并保留原评阅记录与退回原因。',
    command: '退回当前评阅记录并要求重新评阅',
    contract: '退回不会删除历史评阅；新的评阅仍需由具有权限的评阅教师提交。',
    riskLabel: '历史记录保留', sectionTitle: '退回原因', submitLabel: '确认退回重评',
    fields: [{ key: 'reason', label: '退回原因', required: true, type: 'textarea', placeholder: '说明退回重评的业务原因，不少于 5 个字。' }],
    nextSteps: ['当前评阅任务回到待处理', '评阅教师重新核验成果版本', '再次提交评分和意见'],
    warningTitle: '不能代替评阅教师', warning: '管理角色只能退回任务，不能在本页替评阅教师补填新的评阅结论。'
  },
  scoreEntry: {
    title: '录入本人答辩评分', eyebrow: '答辩与成绩 · 评委评分', roleLabel: '答辩评委职责',
    purpose: '评委只提交本人对当前学生本轮答辩的评分或缺席事实。',
    command: '提交本人评分，不确认其他评委结果',
    contract: '秘书确认与评委评分严格分离；本页不能代其他评委补分。',
    riskLabel: '仅本人评分', sectionTitle: '本轮答辩评分', submitLabel: '提交本人评分',
    fields: [
      { key: 'judgeName', label: '评委姓名', required: true, placeholder: '填写当前登录评委姓名', hint: '服务端仍会按当前身份和答辩组关系校验。' },
      { key: 'absent', label: '本评委缺席', type: 'checkbox', hint: '缺席时必须填写原因，评分留空。' },
      { key: 'absentReason', label: '缺席原因', placeholder: '仅缺席时填写' },
      { key: 'score', label: '答辩评分（0–100）', inputType: 'number', inputMode: 'decimal', min: 0, max: 100, hint: '非缺席时必填。' },
      { key: 'comment', label: '答辩评语', type: 'textarea', chips: DEFENSE_COMMENT_CHIPS, placeholder: '写明答辩表现和改进建议。' }
    ],
    nextSteps: ['服务器保存本人评分或缺席事实', '等待其他评委完成本轮评分', '秘书仅在完整后确认本轮'],
    warningTitle: '职责严格分离', warning: '评委不能确认整轮成绩，秘书也不能通过本页代替评委提交评分。'
  },
  secondDefense: {
    title: '发起二次答辩', eyebrow: '答辩与成绩 · 二次答辩', roleLabel: '答辩管理职责',
    purpose: '在原答辩记录保留的前提下，为当前学生创建新的答辩轮次。',
    command: '基于原答辩结果创建二次答辩轮次',
    contract: '新轮次不会覆盖第一次答辩；时间、评委和学生通知仍需后续编排。',
    riskLabel: '新增轮次', sectionTitle: '发起依据', submitLabel: '创建二次答辩',
    fields: [{ key: 'reason', label: '发起原因', required: true, type: 'textarea', placeholder: '说明为什么需要二次答辩，不少于 5 个字。' }],
    nextSteps: ['创建新的答辩轮次', '重新安排时间、地点和评委', '发布后通知学生与相关教师'],
    warningTitle: '不会自动发布', warning: '创建轮次后仍必须完成编排、回避检查和正式发布。'
  },
  calculate: {
    title: '核算毕业设计成绩', eyebrow: '答辩与成绩 · 成绩核算', roleLabel: '成绩管理员职责',
    purpose: '基于导师分、正式评阅分和已确认答辩分生成当前学生的综合成绩。',
    command: '核算当前学生的成绩来源项',
    contract: '评阅分和答辩分来自服务器汇总，只读；页面只允许录入或确认导师分。',
    riskLabel: '来源项必须齐全', sectionTitle: '成绩来源', submitLabel: '确认核算',
    fields: [
      { key: 'advisorScore', label: '导师分', required: true, inputType: 'number', inputMode: 'decimal', min: 0, max: 100, chips: ADVISOR_SCORE_CHIPS, hint: '导师分会与另外两项按批次规则核算。' },
      { key: 'reviewerScore', label: '评阅分（服务器汇总）', readonly: true, hint: '来自已完成正式评阅，不能在本页修改。' },
      { key: 'defenseScore', label: '答辩分（服务器汇总）', required: true, readonly: true, hint: '来自秘书已确认的完整评分轮次。' }
    ],
    nextSteps: ['服务端按批次权重核算综合分', '成绩进入待复核状态', '复核通过后才允许发布'],
    warningTitle: '不能跳过来源项', warning: '评阅或答辩未完成时，必须回到对应工作区处理，不能在本页手工补齐。'
  },
  returnGrade: {
    title: '成绩复核退回', eyebrow: '答辩与成绩 · 复核退回', roleLabel: '成绩复核职责',
    purpose: '把已核算成绩退回重新处理，保留原成绩版本和复核意见。',
    command: '退回当前成绩版本并要求重新核算',
    contract: '退回原因进入审计；原成绩版本保留，不直接修改来源分。',
    riskLabel: '原版本保留', sectionTitle: '复核意见', submitLabel: '确认退回',
    fields: [{ key: 'comment', label: '退回原因', required: true, type: 'textarea', placeholder: '说明需要重新核算的具体原因，不少于 5 个字。' }],
    nextSteps: ['成绩回到可重新核算状态', '核对导师/评阅/答辩来源项', '重新核算并再次复核'],
    warningTitle: '不能直接改分', warning: '复核角色只能退回，来源分必须回到原业务环节处理。'
  },
  withdraw: {
    title: '撤回已发布成绩', eyebrow: '答辩与成绩 · 成绩撤回', roleLabel: '成绩管理员职责',
    purpose: '对已发布成绩执行有原因、有留痕的撤回，学生端可见状态随服务器结果更新。',
    command: '撤回当前已发布成绩版本',
    contract: '撤回后不能静默修改；必须重新核算、复核并发布新的有效状态。',
    riskLabel: '高风险写操作', sectionTitle: '撤回依据', submitLabel: '确认撤回成绩',
    fields: [{ key: 'reason', label: '撤回原因', required: true, type: 'textarea', placeholder: '说明撤回原因，不少于 5 个字。' }],
    nextSteps: ['已发布成绩变为撤回状态', '学生端同步最新状态', '重新核算、复核并发布'],
    warningTitle: '撤回影响学生可见结果', warning: '提交前确认对象和原因；网络结果不确定时先回台账核对，不能盲目重复提交。'
  }
}

const EMPTY_PRESET = {
  title: '毕业设计操作', eyebrow: '毕业设计 · 业务办理', roleLabel: '当前角色职责',
  purpose: '处理当前学生的毕业设计业务。', command: '提交当前操作', contract: '以服务端状态机为准。',
  riskLabel: '待确认', sectionTitle: '业务内容', submitLabel: '提交', fields: [], nextSteps: [],
  warningTitle: '操作提醒', warning: '请确认当前学生和业务上下文。'
}

export default {
  name: 'GraduationDefenseGradeFormView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, AppTemplateChips },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      student: null,
      formKey: '',
      formTitle: '',
      formFields: [],
      form: {},
      formError: '',
      submitting: false,
      recordId: '',
      commandSnapshot: null
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
      const suffix = query.toString()
      return suffix ? `${path}?${suffix}` : path
    },
    pageSubtitle() {
      if (!this.student) return '正在读取当前学生和业务上下文'
      return `${this.student.name}（${this.student.studentNo}）· ${this.activePreset.roleLabel}`
    },
    batchLabel() { return String(this.$route.query.batchId || this.student?.batchName || '当前批次') },
    recordLabel() { return this.recordId ? `记录 ${this.recordId}` : '按当前学生办理' },
    formStatusText() {
      if (this.submitting) return '提交中'
      if (this.formError) return '请修正'
      return '待提交'
    },
    completionItems() {
      return this.formFields.map((field, index) => ({
        key: field.key,
        order: index + 1,
        label: field.label,
        done: this.fieldCompleted(field),
        hint: field.required ? '必填或由服务器提供' : '按实际情况填写'
      }))
    },
    submitDisabled() {
      return this.submitting || this.formFields.some((field) => field.required && !this.fieldCompleted(field))
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
    onBlockedBack() {
      toast.info('当前操作正在提交，请勿重复点击或切换页面')
    },
    cancel() {
      if (!this.submitting) this.$router.push(this.backTo)
    },
    fieldCompleted(field) {
      if (field.type === 'checkbox') return true
      const value = this.form[field.key]
      return value !== '' && value != null
    },
    onPickChip(field, value) {
      this.form[field.key] = field.type === 'textarea'
        ? (this.form[field.key] ? `${this.form[field.key]}\n${value}` : String(value))
        : value
      this.formError = ''
    },
    captureEditableDraft() {
      return Object.fromEntries(
        this.formFields.filter((field) => !field.readonly).map((field) => [field.key, this.form[field.key]])
      )
    },
    restoreEditableDraft(draft = {}) {
      for (const field of this.formFields) {
        if (!field.readonly && Object.prototype.hasOwnProperty.call(draft, field.key)) this.form[field.key] = draft[field.key]
      }
    },
    validateBeforeSubmit() {
      for (const field of this.formFields) {
        if (field.required && !this.fieldCompleted(field)) return `请填写${field.label.replace(/（.*?）|\(.*?\)/g, '')}`
        if (field.inputType === 'number' && this.form[field.key] !== '' && this.form[field.key] != null) {
          const value = Number(this.form[field.key])
          if (!Number.isFinite(value)) return `${field.label}必须是有效数字`
          if (field.min != null && value < Number(field.min)) return `${field.label}不能小于 ${field.min}`
          if (field.max != null && value > Number(field.max)) return `${field.label}不能大于 ${field.max}`
        }
      }
      if (['dispute', 'reviewReturn', 'secondDefense', 'withdraw'].includes(this.formKey)) {
        const key = this.formKey === 'reviewReturn' ? 'reason' : 'reason'
        if (String(this.form[key] || '').trim().length < 5) return '原因必须填写且不少于 5 个字'
      }
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
      if (routeBatchId && studentBatchId && routeBatchId !== studentBatchId) {
        return { code: 409, message: '当前批次与学生上下文不一致，请返回后重新选择学生' }
      }
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
      if (!this.studentId) {
        this.error = '缺少学生标识，请返回后重新选择学生'
        this.loading = false
        return
      }
      const preset = FORM_PRESETS[this.formKey]
      if (!preset) {
        this.error = '无效的表单类型'
        this.loading = false
        return
      }
      if (!this.canOpenForm(this.formKey)) {
        this.error = '当前角色无权执行该毕业设计操作，请返回对应工作区'
        this.loading = false
        return
      }
      if (RECORD_CONTEXT_FORMS.has(this.formKey) && !this.recordId) {
        this.error = '缺少业务记录标识，请返回对应工作区重新选择记录'
        this.loading = false
        return
      }
      this.formTitle = preset.title
      this.formFields = preset.fields
      this.form = {}
      preset.fields.forEach((field) => { this.form[field.key] = field.type === 'checkbox' ? false : '' })

      let grade = null
      if (GRADE_CONTEXT_FORMS.has(this.formKey)) {
        grade = await graduationDefenseGradeApi.getGrade(this.studentId)
        if (grade.code !== 0) {
          this.error = grade.message || '当前成绩上下文不可用'
          this.loading = false
          return
        }
      }
      const student = await this.loadStudentContext()
      if (student.code !== 0) {
        this.error = student.message || '学生上下文加载失败'
        this.loading = false
        return
      }

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
      if (!this.canOpenForm(this.formKey)) {
        this.formError = '当前角色无权执行该毕业设计操作'
        return
      }
      const validation = this.validateBeforeSubmit()
      if (validation) {
        this.formError = validation
        return
      }
      const snapshot = Object.freeze({
        formKey: this.formKey,
        studentId: String(this.studentId),
        recordId: String(this.recordId || ''),
        batchId: String(this.$route.query.batchId || ''),
        form: Object.freeze({ ...this.form }),
        backTo: this.backTo
      })
      this.commandSnapshot = snapshot
      this.submitting = true
      try {
        let res
        const sid = snapshot.studentId
        const f = snapshot.form
        if (snapshot.formKey === 'plagiarismResult') {
          res = await graduationDefenseGradeApi.setPlagiarismResult(snapshot.recordId, f.rate, f.reportUrl)
        } else if (snapshot.formKey === 'dispute') {
          res = await graduationDefenseGradeApi.disputePlagiarism(snapshot.recordId, f.reason)
        } else if (snapshot.formKey === 'reviewSubmit') {
          res = await graduationDefenseGradeApi.submitReview(snapshot.recordId, Number(f.score), f.opinion)
        } else if (snapshot.formKey === 'reviewReturn') {
          res = await graduationDefenseGradeApi.returnReview(snapshot.recordId, f.reason)
        } else if (snapshot.formKey === 'scoreEntry') {
          res = await graduationDefenseGradeApi.enterScore({
            gdStudentId: sid,
            judgeName: f.judgeName,
            score: f.absent ? undefined : Number(f.score),
            comment: f.comment,
            absent: Boolean(f.absent),
            absentReason: f.absent ? f.absentReason : undefined
          })
        } else if (snapshot.formKey === 'secondDefense') {
          res = await graduationDefenseGradeApi.createSecondDefense(sid, f.reason)
        } else if (snapshot.formKey === 'calculate') {
          res = await graduationDefenseGradeApi.calculateGrade(sid, {
            advisorScore: f.advisorScore ? Number(f.advisorScore) : undefined,
            reviewerScore: f.reviewerScore ? Number(f.reviewerScore) : undefined,
            defenseScore: f.defenseScore ? Number(f.defenseScore) : undefined
          })
        } else if (snapshot.formKey === 'returnGrade') {
          res = await graduationDefenseGradeApi.reviewGrade(sid, { action: 'RETURN', comment: f.comment })
        } else if (snapshot.formKey === 'withdraw') {
          res = await graduationDefenseGradeApi.withdrawGrade(sid, f.reason)
        }
        if (res && res.code === 0) {
          toast.success(`${this.activePreset.title}已提交`)
          this.$router.push(snapshot.backTo)
        } else if (res && isGraduationConflictResponse(res)) {
          const draft = this.captureEditableDraft()
          await this.refreshConflictTruth()
          this.restoreEditableDraft(draft)
          this.formError = graduationConflictMessage(res)
        } else if (res) {
          this.formError = graduationActionErrorMessage(res)
        }
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

.dgf-context {
  display: flex;
  min-width: 0;
  gap: 8px;
}

.dgf-context span {
  display: grid;
  min-width: 155px;
  gap: 2px;
  padding: 7px 10px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  background: var(--bg-card, #fff);
  color: var(--text-secondary, #475569);
  font-size: 11px;
}

.dgf-context b {
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
  font-weight: 600;
}

.dgf-form {
  gap: 12px;
}

.dgf-command {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid var(--primary-100, #dbeafe);
  border-radius: 10px;
  background: linear-gradient(120deg, var(--primary-50, #eff6ff), var(--bg-card, #fff));
}

.dgf-command > div {
  display: grid;
  gap: 2px;
}

.dgf-command span {
  color: var(--primary-600, #2563eb);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: .08em;
}

.dgf-command strong {
  color: var(--text-primary, #0f172a);
  font-size: 13px;
}

.dgf-command p {
  margin: 0;
  color: var(--text-secondary, #475569);
  font-size: 10px;
  line-height: 1.5;
}

.dgf-command > b {
  padding: 5px 9px;
  border-radius: 999px;
  background: var(--warning-50, #fffbeb);
  color: var(--warning-800, #92400e);
  font-size: 10px;
  white-space: nowrap;
}

.dgf-fields {
  overflow: hidden;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 10px;
  background: var(--bg-card, #fff);
}

.dgf-fields > header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--border-light, #e8edf5);
  background: var(--bg-subtle, #f8fafc);
}

.dgf-fields > header > div {
  display: grid;
  gap: 1px;
}

.dgf-fields > header span,
.dgf-fields > header small {
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
}

.dgf-fields > header strong {
  color: var(--text-primary, #0f172a);
  font-size: 12px;
}

.dgf-fields__body {
  display: grid;
  gap: 12px;
  padding: 12px;
}

.dgf-check {
  display: flex;
  align-items: flex-start;
  gap: 9px;
  padding: 10px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 8px;
  background: var(--bg-subtle, #f8fafc);
}

.dgf-check input {
  margin-top: 2px;
}

.dgf-check span {
  display: grid;
  gap: 2px;
}

.dgf-check strong {
  color: var(--text-primary, #0f172a);
  font-size: 11px;
}

.dgf-check small {
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
}

.dgf-aside-card,
.dgf-warning {
  padding: 12px;
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: 10px;
  background: var(--bg-card, #fff);
}

.dgf-aside-card > span {
  color: var(--text-primary, #0f172a);
  font-size: 12px;
  font-weight: 700;
}

.dgf-aside-card ul,
.dgf-aside-card ol {
  display: grid;
  gap: 8px;
  margin: 9px 0 0;
  padding: 0;
  list-style: none;
}

.dgf-aside-card li {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  color: var(--text-secondary, #475569);
  font-size: 10px;
}

.dgf-aside-card ul li > b {
  display: grid;
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  place-items: center;
  border-radius: 50%;
  background: var(--gray-100, #f1f5f9);
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
}

.dgf-aside-card ul li.done > b {
  background: var(--success-50, #ecfdf5);
  color: var(--success-700, #047857);
}

.dgf-aside-card li div {
  display: grid;
  gap: 1px;
}

.dgf-aside-card li strong {
  color: var(--text-primary, #0f172a);
  font-size: 10px;
}

.dgf-aside-card li small {
  color: var(--text-tertiary, #64748b);
  font-size: 9px;
}

.dgf-aside-card.is-next ol {
  counter-reset: next;
}

.dgf-aside-card.is-next li::before {
  counter-increment: next;
  content: counter(next);
  display: grid;
  flex: 0 0 auto;
  width: 19px;
  height: 19px;
  place-items: center;
  border-radius: 6px;
  background: var(--primary-50, #eff6ff);
  color: var(--primary-700, #1d4ed8);
  font-size: 9px;
  font-weight: 700;
}

.dgf-warning {
  border-color: var(--warning-200, #fde68a);
  background: var(--warning-50, #fffbeb);
}

.dgf-warning strong {
  color: var(--warning-800, #92400e);
  font-size: 11px;
}

.dgf-warning p {
  margin: 4px 0 0;
  color: var(--warning-700, #a16207);
  font-size: 10px;
  line-height: 1.5;
}

.mp-btn {
  padding: 7px 16px;
  border: 1px solid var(--line, #d9dee8);
  border-radius: 8px;
  background: #fff;
  cursor: pointer;
  font-size: 13px;
}

.mp-btn--primary {
  border-color: var(--pri, #2563eb);
  background: var(--pri, #2563eb);
  color: #fff;
}

.mp-btn:disabled {
  cursor: not-allowed;
  opacity: .5;
}

@media (max-width: 760px) {
  .dgf-command {
    grid-template-columns: 1fr;
  }
}
</style>
