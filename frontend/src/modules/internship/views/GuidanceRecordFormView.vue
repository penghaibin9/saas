<template>
  <ModulePageShell :title="`新增${typeMeta.label}`"
    subtitle="记录本次沟通与处理建议，保存后查看详情并继续跟进。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" :disabled="submitting" @click="backToList">返回指导巡访</AppButton>
    </template>

    <section class="mp-card grf">
      <div v-if="submitError" class="grf__error" role="alert">{{ submitError }}</div>
      <div class="grf__type">
        <span class="grf__type-lbl">记录类型</span>
        <AppQuickFilterChips :model-value="type" :options="typeOptions" @change="switchType" />
      </div>

      <AppForm ref="formRef" :model="form" :rules="rules" layout="horizontal" label-width="110px" @submit="doSubmit">
        <fieldset class="grf__fields" :disabled="submitting">
        <AppFormSection title="学生与指导方式">
          <AppFormItem label="实习学生" prop="internshipId" required>
            <AppInternshipStudentPicker
              v-model="form.internshipId"
              :key="batchStore.selectedBatchId" :query="{ batchId: batchStore.selectedBatchId }"
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
          <AppFormSection title="后续跟进" description="有风险需持续处理时标记线索，需协同时通知辅导员。">
            <AppFormItem label="联动动作">
              <AppCheckboxGroup v-model="form.guidanceFlags" :options="flagOptions" />
            </AppFormItem>
          </AppFormSection>
        </template>

        <template v-else>
          <AppFormSection title="巡访反馈">
            <AppFormItem label="企业反馈">
              <AppTextInput v-model="form.enterpriseFeedback" placeholder="企业对学生的反馈" />
              <AppTemplateChips class="grf__chips" :options="VISIT_GUIDANCE" size="compact" @pick="(v) => pickInto('enterpriseFeedback', v)" />
            </AppFormItem>
            <AppFormItem label="学生反馈">
              <AppTextInput v-model="form.studentFeedback" placeholder="学生对岗位/实习的反馈" />
              <AppTemplateChips class="grf__chips" :options="VISIT_STATUS" size="compact" @pick="(v) => pickInto('studentFeedback', v)" />
            </AppFormItem>
          </AppFormSection>
          <AppFormSection title="安全隐患与整改" description="填写安全隐患或整改要求后，该巡访自动进入「整改中」">
            <AppFormItem label="安全隐患">
              <AppTextInput v-model="form.safetyIssue" placeholder="仅填写实际发现的问题；未发现隐患请留空" />
            </AppFormItem>
            <AppFormItem label="整改要求"><AppTextInput v-model="form.rectifyRequire" placeholder="填写后自动进入「整改中」" /></AppFormItem>
            <AppFormItem label="整改截止"><AppDatePicker v-model="form.rectifyDeadline" /></AppFormItem>
          </AppFormSection>
          <AppFormSection title="月度小结">
            <AppFormItem label="月度小结"><AppTextarea v-model="form.monthlyReport" :rows="3" placeholder="可选：本月巡访月报" /></AppFormItem>
          </AppFormSection>
        </template>

        <AppFormSection title="相关材料" description="选填，可上传沟通或巡访佐证材料。">
          <AppFormItem label="附件">
            <div class="grf__file-row">
              <input type="file" aria-label="上传相关材料" :disabled="uploadingFile || submitting" class="grf__file" @change="onFilePick" />
              <span v-if="uploadingFile" class="grf__att">上传中，请稍候…</span>
              <span v-else-if="form.fileId" class="grf__att">已上传：{{ attachName }}</span>

            </div>
          </AppFormItem>
        </AppFormSection>

        </fieldset>
        <AppSubmitBar sticky :loading="submitting" :disabled="uploadingFile || !batchStore.selectedBatchId" :submit-text="`保存${typeMeta.label}`" cancel-text="取消并返回"
          @submit="onSubmitClick" @cancel="backToList">
          <template #info>{{ uploadingFile ? '附件上传中，完成后即可保存' : '保存后查看记录详情，继续跟进或登记下一条' }}</template>
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
  AppDatePicker, AppInternshipStudentPicker, AppCheckboxGroup, AppQuickFilterChips, AppTemplateChips } from '@/components/common'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { toast } from '@/utils/toast'
import { VISIT_STATUS, VISIT_GUIDANCE } from '@/modules/internship/constants/presetPrompts'

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
    AppSelect, AppTextInput, AppTextarea, AppDatePicker, AppInternshipStudentPicker, AppCheckboxGroup, AppQuickFilterChips, AppTemplateChips },
  data() {
    return {
      VISIT_STATUS, VISIT_GUIDANCE,
      type: 'guidance',
      typeOptions: [{ label: '指导记录', value: 'guidance' }, { label: '巡访记录', value: 'visit' }],
      flagOptions: [{ label: '标记为风险线索', value: 'toRisk' }, { label: '通知辅导员', value: 'notifyCounselor' }],
      form: emptyForm(),
      attachName: '', uploadingFile: false, submitting: false, submitError: '', uploadSequence: 0,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
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
  beforeUnmount() { this.uploadSequence++; this.form = emptyForm() },
  watch: {
    'batchStore.selectedBatchId'() {
      this.uploadSequence++; this.form = emptyForm(); this.attachName = ''
      this.uploadingFile = false; this.submitting = false; this.submitError = ''
    },
    '$route.query.type': {
      immediate: true,
      handler(t) { this.applyType((t || 'guidance').toString()) }
    }
  },
  methods: {
    // 选择器远程搜索（岗位实习模块适配层，关键字与数据范围由后端裁定）
    pickInto(field, text) {
      if (!text || this.submitting) return
      const cur = (this.form[field] || '').trim()
      this.form[field] = cur ? cur + '；' + text : text
    },
    applyType(t) {
      this.type = TYPE_META[t] ? t : 'guidance'
      // 方式选项随类型联动：当前值不在新选项内时回退到第一项
      if (!this.methodOptions.some((o) => o.value === this.form.method)) {
        this.form.method = this.methodOptions[0].value
      }
      if (this.$refs.formRef) this.$refs.formRef.clearValidate()
    },
    switchType(k) {
      if (k === this.type || this.submitting || this.uploadingFile) return
      this.$router.replace({ query: { ...this.$route.query, type: k } })
    },
    backToList() {
      if (this.submitting) return
      // 从列表进入时走历史返回（保留 tab/筛选/页码/选中）；深链直入时兜底到对应 tab 列表
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && (back === LIST_PATH || back.startsWith(LIST_PATH + '?'))) this.$router.back()
      else this.$router.push({ path: LIST_PATH, query: this.batchStore.withBatchQuery({ panel: this.type }) })
    },
    async onFilePick(e) {
      const file = e.target.files && e.target.files[0]
      if (!file || this.uploadingFile || this.submitting) return
      const sequence = ++this.uploadSequence
      const form = this.form
      this.submitError = ''
      this.uploadingFile = true
      const res = await guidanceVisitApi.uploadAttachment(file)
      if (sequence !== this.uploadSequence || form !== this.form) return
      this.uploadingFile = false
      e.target.value = ''
      if (res.code !== 0) { this.submitError = res.message || '附件上传失败，请重新选择文件'; return }
      this.form.fileId = res.data.fileId; this.attachName = res.data.fileName || file.name
      toast.success('附件已上传')
    },
    onSubmitClick() {
      // 统一走 AppForm 校验管道（校验通过后触发 @submit → doSubmit）
      if (this.$refs.formRef) this.$refs.formRef.onSubmit()
    },
    async doSubmit() {
      if (this.submitting || this.uploadingFile) return
      this.submitError = ''
      if (!this.batchStore.selectedBatchId) { this.submitError = '请先选择实习批次'; return }
      const f = this.form
      if (!f.internshipId) { this.submitError = '请选择实习学生'; return }
      if (this.type === 'guidance' && !f.content.trim()) { this.submitError = '请填写指导内容'; return }
      const type = this.type
      const queryBefore = this.batchStore.withBatchQuery({ ...this.$route.query })
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
      if (this.form !== f) return
      this.submitting = false
      if (res.code !== 0) { this.submitError = res.message || '保存失败，已保留填写内容'; return }
      window.__SAAS_DIRTY_FORM_GUARD__?.markSaved()
      toast.success('记录已保存')
      const query = { ...queryBefore, panel: type, id: String(res.data.id), receipt: 'created' }
      delete query.type
      this.$router.push({
        path: LIST_PATH,
        query
      })
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.grf { padding: var(--space-5); max-width: 980px; }
.grf__fields { border: 0; padding: 0; margin: 0; min-width: 0; }
.grf__error { padding: 12px 16px; margin-bottom: 16px; border: 1px solid var(--danger-200, #fecdca); border-radius: 8px; background: var(--danger-50, #fff4f2); color: var(--danger-700, #b42318); }
.grf__type { display: flex; align-items: center; gap: var(--space-3); padding-bottom: var(--space-4); margin-bottom: var(--space-4); border-bottom: 1px solid var(--border-light); }
.grf__type-lbl { font-size: var(--font-size-sm); color: var(--text-secondary); }
.grf__file-row { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; min-height: 32px; }
.grf__file { font-size: var(--font-size-xs); }
.grf__att { font-size: var(--font-size-xs); color: var(--success-700); }
.grf__chips { margin-top: var(--space-2); }
</style>
