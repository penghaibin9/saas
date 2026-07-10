<template>
  <ModulePageShell :title="`新增${typeMeta.label}`"
    subtitle="指导教师联系学生 / 现场巡访独立录入页 · 提交走真实接口并写审计 · 附件走文件中心"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="backToList">← 返回指导巡访列表</AppButton>
    </template>

    <section class="mp-card grf">
      <div class="grf__type">
        <span class="grf__type-lbl">记录类型</span>
        <AppQuickFilterChips :model-value="type" :options="typeOptions" @change="switchType" />
      </div>

      <AppForm ref="formRef" :model="form" :rules="rules" layout="horizontal" label-width="110px" @submit="doSubmit">
        <AppFormSection title="实习学生与方式" description="仅可对本人指导学生新增，越权将被后端拒绝并写审计">
          <AppFormItem label="实习学生" prop="internshipId" required>
            <AppStudentPicker
              v-model="form.internshipId"
              :remote-search="searchInternStudents"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <AppFormItem label="方式" prop="method">
            <AppSelect v-model="form.method" :options="methodOptions" />
          </AppFormItem>
        </AppFormSection>

        <template v-if="type === 'guidance'">
          <AppFormSection title="指导内容">
            <AppFormItem label="主题"><AppTextInput v-model="form.topic" placeholder="如：岗位适应 / 安全教育" /></AppFormItem>
            <AppFormItem label="指导内容" prop="content" required>
              <AppTextarea v-model="form.content" :rows="4" placeholder="记录本次指导的具体内容" />
            </AppFormItem>
            <AppFormItem label="问题类型"><AppTextInput v-model="form.problemType" placeholder="如：岗位不符 / 考勤异常 / 安全隐患" /></AppFormItem>
            <AppFormItem label="处理建议"><AppTextInput v-model="form.suggestion" placeholder="给学生/企业的处理建议" /></AppFormItem>
            <AppFormItem label="下次跟进日期"><AppDatePicker v-model="form.nextFollowDate" /></AppFormItem>
          </AppFormSection>
          <AppFormSection title="风险线索与联动" description="勾选后由后端联动风险台账 / 通知辅导员，并写审计">
            <AppFormItem label="联动动作">
              <AppCheckboxGroup v-model="form.guidanceFlags" :options="flagOptions" />
            </AppFormItem>
          </AppFormSection>
        </template>

        <template v-else>
          <AppFormSection title="巡访反馈">
            <AppFormItem label="企业反馈"><AppTextInput v-model="form.enterpriseFeedback" placeholder="企业对学生的反馈" /></AppFormItem>
            <AppFormItem label="学生反馈"><AppTextInput v-model="form.studentFeedback" placeholder="学生对岗位/实习的反馈" /></AppFormItem>
          </AppFormSection>
          <AppFormSection title="安全隐患与整改" description="填写安全隐患或整改要求后，该巡访自动进入「整改中」">
            <AppFormItem label="安全隐患"><AppTextInput v-model="form.safetyIssue" placeholder="填写后自动进入「整改中」" /></AppFormItem>
            <AppFormItem label="整改要求"><AppTextInput v-model="form.rectifyRequire" placeholder="填写后自动进入「整改中」" /></AppFormItem>
            <AppFormItem label="整改截止"><AppDatePicker v-model="form.rectifyDeadline" /></AppFormItem>
          </AppFormSection>
          <AppFormSection title="月度小结">
            <AppFormItem label="月度小结"><AppTextarea v-model="form.monthlyReport" :rows="3" placeholder="可选：本月巡访月报" /></AppFormItem>
          </AppFormSection>
        </template>

        <AppFormSection title="附件" description="可选 · 走文件中心真实上传，不伪造">
          <AppFormItem label="附件">
            <div class="grf__file-row">
              <input type="file" class="grf__file" @change="onFilePick" />
              <span v-if="form.fileId" class="grf__att">已上传：{{ attachName }}</span>
              <span v-else-if="uploadingFile" class="grf__att">上传中…</span>
            </div>
          </AppFormItem>
        </AppFormSection>

        <AppSubmitBar sticky :loading="submitting" submit-text="提交" cancel-text="取消并返回"
          @submit="onSubmitClick" @cancel="backToList">
          <template #info>提交成功后返回列表；越权提交将被后端拒绝并写审计。</template>
        </AppSubmitBar>
      </AppForm>
    </section>
  </ModulePageShell>
</template>

<script>
/**
 * 指导 / 巡访记录独立录入页（/admin/internship/guidance/new?type=guidance|visit）。
 * 由 GuidanceVisitView 的「＋ 新增记录」进入；原新增窄弹窗收口至此。
 * query.type 决定表单形态，顶部 chips 可切换并联动字段；提交走真实 createGuidance / createVisit。
 */
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppForm, AppFormSection, AppFormItem, AppSubmitBar, AppSelect, AppTextInput, AppTextarea,
  AppDatePicker, AppStudentPicker, AppCheckboxGroup, AppQuickFilterChips } from '@/components/common'
import { searchInternStudents } from './components/entityPickerAdapters'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { toast } from '@/utils/toast'

const TYPE_META = { guidance: { label: '指导记录' }, visit: { label: '巡访记录' } }
const METHODS = {
  guidance: [
    { value: 'ONSITE', label: '现场' }, { value: 'ONLINE', label: '线上' }, { value: 'PHONE', label: '电话' },
    { value: 'VIDEO', label: '视频' }, { value: 'ENTERPRISE_FEEDBACK', label: '企业导师反馈' }
  ],
  visit: [{ value: 'ONSITE', label: '现场' }, { value: 'ONLINE', label: '线上' }, { value: 'PHONE', label: '电话' }]
}
const LIST_PATH = '/admin/internship/guidance'

function emptyForm() {
  return { internshipId: '', method: 'ONSITE', topic: '', content: '', problemType: '', suggestion: '',
    nextFollowDate: '', guidanceFlags: [], enterpriseFeedback: '', studentFeedback: '',
    safetyIssue: '', rectifyRequire: '', rectifyDeadline: '', monthlyReport: '', fileId: '' }
}

export default {
  name: 'GuidanceRecordFormView',
  components: { ModulePageShell, AppButton, AppForm, AppFormSection, AppFormItem, AppSubmitBar,
    AppSelect, AppTextInput, AppTextarea, AppDatePicker, AppStudentPicker, AppCheckboxGroup, AppQuickFilterChips },
  data() {
    return {
      type: 'guidance',
      typeOptions: [{ label: '指导记录', value: 'guidance' }, { label: '巡访记录', value: 'visit' }],
      flagOptions: [{ label: '标记为风险线索', value: 'toRisk' }, { label: '通知辅导员', value: 'notifyCounselor' }],
      form: emptyForm(),
      attachName: '', uploadingFile: false, submitting: false,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    typeMeta() { return TYPE_META[this.type] },
    methodOptions() { return METHODS[this.type] },
    rules() {
      const r = { internshipId: [{ required: true, message: '请选择实习学生' }] }
      if (this.type === 'guidance') {
        r.content = [
          { required: true, message: '指导内容必填' },
          { validator: (v) => (String(v).trim() ? true : '指导内容必填') }
        ]
      }
      return r
    }
  },
  watch: {
    '$route.query.type': {
      immediate: true,
      handler(t) { this.applyType((t || 'guidance').toString()) }
    }
  },
  methods: {
    // 选择器远程搜索（岗位实习模块适配层，关键字与数据范围由后端裁定）
    searchInternStudents,
    applyType(t) {
      this.type = TYPE_META[t] ? t : 'guidance'
      // 方式选项随类型联动：当前值不在新选项内时回退到第一项
      if (!this.methodOptions.some((o) => o.value === this.form.method)) {
        this.form.method = this.methodOptions[0].value
      }
      if (this.$refs.formRef) this.$refs.formRef.clearValidate()
    },
    switchType(k) {
      if (k === this.type) return
      this.$router.replace({ query: { ...this.$route.query, type: k } })
    },
    backToList() {
      // 从列表进入时走历史返回（保留 tab/筛选/页码/选中）；深链直入时兜底到对应 tab 列表
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && (back === LIST_PATH || back.startsWith(LIST_PATH + '?'))) this.$router.back()
      else this.$router.push({ path: LIST_PATH, query: { panel: this.type } })
    },
    async onFilePick(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.uploadingFile = true
      const res = await guidanceVisitApi.uploadAttachment(file)
      this.uploadingFile = false
      if (res.code !== 0) return toast.error(res.message || '上传失败')
      this.form.fileId = res.data.fileId; this.attachName = res.data.fileName || file.name
      toast.success('附件已上传')
    },
    onSubmitClick() {
      // 统一走 AppForm 校验管道（校验通过后触发 @submit → doSubmit）
      if (this.$refs.formRef) this.$refs.formRef.onSubmit()
    },
    async doSubmit() {
      if (this.submitting) return
      const f = this.form
      const payload = this.type === 'guidance'
        ? { internshipId: f.internshipId, method: f.method, topic: f.topic, content: f.content,
            problemType: f.problemType, suggestion: f.suggestion, nextFollowDate: f.nextFollowDate,
            toRisk: f.guidanceFlags.includes('toRisk'), notifyCounselor: f.guidanceFlags.includes('notifyCounselor'),
            fileId: f.fileId }
        : { internshipId: f.internshipId, method: f.method, enterpriseFeedback: f.enterpriseFeedback,
            studentFeedback: f.studentFeedback, safetyIssue: f.safetyIssue, rectifyRequire: f.rectifyRequire,
            rectifyDeadline: f.rectifyDeadline, monthlyReport: f.monthlyReport, fileId: f.fileId }
      this.submitting = true
      const res = this.type === 'guidance'
        ? await guidanceVisitApi.createGuidance(payload)
        : await guidanceVisitApi.createVisit(payload)
      this.submitting = false
      if (res.code !== 0) return toast.error(res.message || '提交失败')
      toast.success('已保存并写审计')
      this.backToList()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.grf { padding: var(--space-5); max-width: 860px; }
.grf__type { display: flex; align-items: center; gap: var(--space-3); padding-bottom: var(--space-4); margin-bottom: var(--space-4); border-bottom: 1px solid var(--border-light); }
.grf__type-lbl { font-size: var(--font-size-sm); color: var(--text-secondary); }
.grf__file-row { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; min-height: 32px; }
.grf__file { font-size: var(--font-size-xs); }
.grf__att { font-size: var(--font-size-xs); color: var(--success-700); }
</style>
