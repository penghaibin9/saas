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
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">任务目标 <i>*</i></span>
          <textarea v-model.trim="tbForm.objective" class="ie-in" rows="2" placeholder="设计并实现一个功能完整的×××系统，满足实际业务需求…" />
          <AppTemplateChips :options="TASKBOOK_OBJECTIVE_CHIPS" @pick="(t) => (tbForm.objective = tbForm.objective ? tbForm.objective + '\n' + t : t)" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">任务内容 <i>*</i></span>
          <textarea v-model.trim="tbForm.content" class="ie-in" rows="2" />
          <AppTemplateChips :options="TASKBOOK_CONTENT_CHIPS" @pick="(t) => (tbForm.content = tbForm.content ? tbForm.content + '\n' + t : t)" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">进度计划</span>
          <textarea v-model.trim="tbForm.progressPlan" class="ie-in" rows="2" />
          <AppTemplateChips :options="TASKBOOK_PROGRESS_CHIPS" @pick="(t) => (tbForm.progressPlan = tbForm.progressPlan ? tbForm.progressPlan + '\n' + t : t)" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">成果要求</span>
          <textarea v-model.trim="tbForm.outcomeRequirement" class="ie-in" rows="2" />
          <AppTemplateChips :options="TASKBOOK_REQUIREMENT_CHIPS" @pick="(t) => (tbForm.outcomeRequirement = tbForm.outcomeRequirement ? tbForm.outcomeRequirement + '\n' + t : t)" />
        </label>
        <label v-if="tbMode === 'change'" class="ie-fld ie-fld--full"><span class="ie-lbl">变更原因（≥5字）<i>*</i></span>
          <textarea v-model.trim="tbForm.reason" class="ie-in" rows="2" />
          <AppTemplateChips :options="TASKBOOK_REASON_CHIPS" @pick="(t) => (tbForm.reason = tbForm.reason ? tbForm.reason + '\n' + t : t)" />
        </label>
      </template>
      <template v-else-if="action === 'guidance'">
        <label class="ie-fld"><span class="ie-lbl">指导方式</span>
          <select v-model="guidanceForm.method" class="ie-in"><option value="ONLINE">线上</option><option value="OFFLINE">线下</option></select>
        </label>
        <AppDateTimePicker v-model="guidanceForm.guidanceDate" class="ie-fld" label="指导时间" hint="默认当前时间" />
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">指导内容 <i>*</i></span>
          <textarea v-model.trim="guidanceForm.content" class="ie-in" rows="2" placeholder="详细记录本次指导内容、建议…" />
          <AppTemplateChips :options="GUIDANCE_CONTENT_CHIPS" @pick="(t) => (guidanceForm.content = guidanceForm.content ? guidanceForm.content + '\n' + t : t)" />
        </label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">发现的问题</span><textarea v-model.trim="guidanceForm.issues" class="ie-in" rows="2" /></label>
      </template>
      <template v-else-if="action === 'midterm'">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">结论 <i>*</i></span>
          <select v-model="mtForm.conclusion" class="ie-in">
            <option value="PASS">通过</option><option value="RECTIFY">限期整改</option><option value="FAIL">不通过</option>
          </select>
        </label>
        <AppDeadlinePicker v-if="mtForm.conclusion === 'RECTIFY'" v-model="mtForm.rectifyDeadline" class="ie-fld ie-fld--full" label="整改截止日期" hint="限期整改默认 23:59" />
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">检查意见</span>
          <textarea v-model.trim="mtForm.comment" class="ie-in" rows="2" />
          <AppTemplateChips :options="MIDTERM_COMMENT_CHIPS" @pick="(t) => (mtForm.comment = mtForm.comment ? mtForm.comment + '\n' + t : t)" />
        </label>
      </template>
      <template v-else-if="action === 'rectify'">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">整改内容 <i>*</i></span>
          <textarea v-model.trim="rectifyContent" class="ie-in" rows="3" />
          <AppTemplateChips :options="RECTIFY_CONTENT_CHIPS" @pick="(t) => (rectifyContent = rectifyContent ? rectifyContent + '\n' + t : t)" />
        </label>
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
import { AppTemplateChips } from '@/components/common'
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

const TASKBOOK_OBJECTIVE_CHIPS = [
  '设计并实现一个功能完整的×××系统，满足实际业务需求。',
  '研究×××关键技术，提出改进方案并通过实验验证。',
  '调研×××领域现状，设计并开发×××原型系统。'
]
const TASKBOOK_CONTENT_CHIPS = [
  '1. 完成需求分析与系统设计；2. 完成数据库设计与后端开发；3. 完成前端界面开发；4. 编写论文并通过答辩。',
  '1. 调研相关技术；2. 完成系统方案设计；3. 编码实现并测试；4. 撰写学位论文。'
]
const TASKBOOK_REQUIREMENT_CHIPS = [
  '严格按学校规范撰写论文，字数不少于8000字；每周汇报进展；按时参加中期检查和答辩。',
  '完成系统功能设计并测试，提交完整源代码及文档；论文格式符合规范。'
]
const TASKBOOK_PROGRESS_CHIPS = [
  '第1-2周：调研选题，完成开题报告；第3-8周：完成系统设计与开发；第9-12周：测试优化；第13-15周：撰写论文；第16周：答辩。'
]
const GUIDANCE_CONTENT_CHIPS = [
  '检查开题报告初稿，指导文献综述方向，要求细化研究方法。',
  '审阅论文初稿，就结构框架、研究方法和写作规范提出修改意见。',
  '检查系统功能实现进度，针对存在的技术问题给出解决方向。',
  '中期检查，汇报进展，提出下阶段重点和完成时间节点。',
  '就答辩PPT制作和答辩技巧进行辅导，模拟答辩环节。'
]
const TASKBOOK_REASON_CHIPS = [
  '学生更换研究方向，原任务书内容不再适用',
  '指导教师根据实际进展调整任务范围',
  '企业合作项目变更，需调整任务书要求'
]
const MIDTERM_COMMENT_CHIPS = [
  '进度按计划完成，质量达到要求',
  '进度有所滞后，需加快后续工作',
  '态度端正，能按要求推进，建议注意细节'
]
const RECTIFY_CONTENT_CHIPS = [
  '问题：×××；整改措施：×××；预期完成时间：×××'
]

export default {
  name: 'GraduationProcessActionView',
  components: { GraduationFormPageShell, LoadingState, ErrorState, AppDateTimePicker, AppDeadlinePicker, AppTemplateChips },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      TASKBOOK_OBJECTIVE_CHIPS, TASKBOOK_CONTENT_CHIPS, TASKBOOK_REQUIREMENT_CHIPS, TASKBOOK_PROGRESS_CHIPS, GUIDANCE_CONTENT_CHIPS,
      TASKBOOK_REASON_CHIPS, MIDTERM_COMMENT_CHIPS, RECTIFY_CONTENT_CHIPS,
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
