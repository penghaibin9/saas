<template>
  <ModulePageShell title="录入企业评价"
    subtitle="转录企业导师纸质评价，提交后交由其他授权审核人确认。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" :disabled="submitting" @click="backToList">返回企业评价</AppButton>
    </template>

    <section class="mp-card eef">
      <AppForm ref="formRef" :model="form" :rules="rules" layout="vertical" @submit="doSubmit">
        <p v-if="submitError" class="eef__error" role="alert">{{ submitError }}</p>
        <fieldset class="eef__fields" :disabled="submitting">
        <AppFormSection title="评价对象" description="选择当前批次处于考核中的实习学生。">
          <AppFormItem label="实习学生" prop="internshipId" required>
            <AppInternshipStudentPicker
              v-model="form.internshipId"
              :key="batchStore.selectedBatchId" :query="{ batchId: batchStore.selectedBatchId, status: 'ASSESSING' }"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <AppFormItem label="企业导师姓名" prop="mentorName" required>
            <AppTextInput v-model="form.mentorName" placeholder="填写企业导师真实姓名" />
          </AppFormItem>
        </AppFormSection>

        <AppFormSection title="五维评分" description="按纸质评价逐项填写，范围为 0–100 分的整数。">
          <div class="eef__scores">
            <AppFormItem v-for="s in scoreDefs" :key="s.key" :label="s.label" :prop="s.key" class="eef__score" required>
              <AppNumberInput v-model="form[s.key]" :min="0" :max="100" />
            </AppFormItem>
          </div>
          <p class="eef__average">五维平均分 <strong>{{ averageScore }}</strong><span v-if="averageScore !== '待填写'"> 分</span></p>
        </AppFormSection>

        <AppFormSection title="评语与建议">
          <AppFormItem label="综合评语">
            <AppTextarea v-model="form.overallComment" :rows="2" placeholder="企业对学生的综合评语" />
            <AppTemplateChips class="eef__chips" :options="ENTERPRISE_EVAL_COMMENT" size="compact" @pick="onPickComment" />
          </AppFormItem>
          <label class="eef__chk"><input v-model="form.recommendHire" type="checkbox" />建议录用</label>
        </AppFormSection>

        <AppFormSection title="评价扫描件" description="学校代录须上传企业纸质评价，供审核人对照。">
          <AppFormItem label="评价扫描件" prop="fileId" required>
            <div class="eef__file-row">
              <input type="file" class="eef__file" aria-label="上传企业评价扫描件" :disabled="uploadingFile || submitting" @change="onFilePick" />
              <span v-if="uploadingFile" class="eef__att">上传中，请稍候…</span>
              <span v-else-if="form.fileId" class="eef__att">已上传：{{ attachName }}</span>
            </div>
          </AppFormItem>
        </AppFormSection>

        </fieldset>

        <AppSubmitBar sticky :loading="submitting" :disabled="uploadingFile || !batchStore.selectedBatchId" submit-text="提交评价并查看" cancel-text="取消"
          @submit="onSubmitClick" @cancel="backToList">
          <template #info>{{ uploadingFile ? '扫描件上传完成后可提交' : '来源：学校录入 · 提交后等待独立审核' }}</template>
        </AppSubmitBar>
      </AppForm>
    </section>
  </ModulePageShell>
</template>

<script>
/**
 * 企业评价独立录入页（/admin/internship/enterprise-evals/new）。
 * 由 EnterpriseEvalView 的「＋ 录入企业评价」进入；原录入窄弹窗收口至此。
 * 字段与校验与原弹窗一致（学生 + 企业导师 + 五维评分 + 评语/建议录用 + 扫描件），
 * 提交走真实 enterpriseEvalApi.create，附件走 uploadAttachment（文件中心）。
 */
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppForm, AppFormSection, AppFormItem, AppSubmitBar, AppTextInput, AppNumberInput,
  AppTextarea, AppInternshipStudentPicker, AppTemplateChips } from '@/components/common'
import { enterpriseEvalApi, uploadAttachment } from '@/modules/internship/api/enterprise-eval.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { ENTERPRISE_EVAL_COMMENT } from '@/modules/internship/constants/presetPrompts'

const SCORES = [
  { key: 'attendanceScore', label: '出勤' }, { key: 'skillScore', label: '技能' },
  { key: 'attitudeScore', label: '态度' }, { key: 'collaborationScore', label: '协作' }, { key: 'safetyScore', label: '安全纪律' }
]
const LIST_PATH = '/admin/internship/enterprise-evals'
const validScore = value => value !== null && value !== '' && Number.isInteger(Number(value)) && Number(value) >= 0 && Number(value) <= 100

function emptyForm() {
  return { internshipId: '', mentorName: '', attendanceScore: null, skillScore: null,
    attitudeScore: null, collaborationScore: null, safetyScore: null, overallComment: '', recommendHire: false, fileId: '' }
}

export default {
  name: 'EnterpriseEvalFormView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, AppButton, AppForm, AppFormSection, AppFormItem, AppSubmitBar,
    AppTextInput, AppNumberInput, AppTextarea, AppInternshipStudentPicker, AppTemplateChips },
  data() {
    return {
      ENTERPRISE_EVAL_COMMENT,
      scoreDefs: SCORES,
      form: emptyForm(),
      attachName: '', uploadingFile: false, submitting: false, submitError: '', uploadSequence: 0,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    averageScore() {
      return SCORES.every(s => validScore(this.form[s.key])) ? (SCORES.reduce((sum, s) => sum + Number(this.form[s.key]), 0) / 5).toFixed(1) : '待填写'
    },
    rules() {
      const r = {
        internshipId: [{ required: true, message: '请选择实习学生' }],
        fileId: [{ required: true, message: '请上传企业纸质评价扫描件' }],
        mentorName: [
          { required: true, message: '请填写企业导师姓名' },
          { validator: (v) => (String(v).trim() ? true : '请填写企业导师姓名') }
        ]
      }
      // 五维评分校验对齐原录入弹窗：必填且 0-100
      for (const s of SCORES) {
        r[s.key] = [
          { required: true, message: `${s.label}评分须为 0-100` },
          { validator: (v) => validScore(v) || `${s.label}评分须为 0–100 的整数` }
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
      this.$refs.formRef?.clearValidate()
    }
  },
  methods: {
    // 选择器远程搜索（岗位实习模块适配层，关键字与数据范围由后端裁定）
    onPickComment(text) {
      if (!text || this.submitting) return
      const cur = (this.form.overallComment || '').trim()
      this.form.overallComment = cur ? cur + '；' + text : text
    },
    backToList() {
      if (this.submitting) return
      // 从列表进入时走历史返回（保留筛选/页码/选中）；深链直入时兜底到列表
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && (back === LIST_PATH || back.startsWith(LIST_PATH + '?'))) this.$router.back()
      else this.$router.push({ path: LIST_PATH, query: this.batchStore.withBatchQuery({}) })
    },
    async onFilePick(e) {
      const file = e.target.files && e.target.files[0]
      if (!file || this.uploadingFile || this.submitting) return
      const form = this.form, sequence = ++this.uploadSequence
      this.submitError = ''
      this.uploadingFile = true
      const res = await uploadAttachment(file)
      if (form !== this.form || sequence !== this.uploadSequence) return
      this.uploadingFile = false
      e.target.value = ''
      if (res.code !== 0) { this.submitError = res.message || '扫描件上传失败，请重试'; return }
      this.form.fileId = res.data.fileId; this.attachName = res.data.fileName || file.name
    },
    async onSubmitClick() {
      if (this.submitting || this.uploadingFile || !this.$refs.formRef) return
      const form = this.form, formRef = this.$refs.formRef
      const { valid } = await formRef.validate()
      if (form !== this.form) return
      if (valid) return this.doSubmit()
      await this.$nextTick()
      const field = formRef.$el.querySelector('.app-form-item.is-error')
      field?.scrollIntoView({ block: 'center' })
      field?.querySelector('input, textarea, select, button, [tabindex="0"]')?.focus({ preventScroll: true })
    },
    async doSubmit() {
      if (this.submitting || this.uploadingFile) return
      this.submitError = ''
      if (!canCode(this.ctx, 'internship.eval.enterprise.manage')) { this.submitError = '当前账号无企业评价录入权限'; return }
      if (!this.batchStore.selectedBatchId) { this.submitError = '请先选择实习批次'; return }
      const f = this.form
      if (!f.internshipId || !f.mentorName.trim()) { this.submitError = '请选择学生并填写企业导师姓名'; return }
      if (!SCORES.every(s => validScore(f[s.key]))) { this.submitError = '五项评分均须为 0–100 的整数'; return }
      if (!f.fileId) { this.submitError = '请上传企业纸质评价扫描件'; return }
      const batchId = this.batchStore.selectedBatchId
      const payload = { internshipId: f.internshipId, mentorName: f.mentorName,
        attendanceScore: f.attendanceScore, skillScore: f.skillScore, attitudeScore: f.attitudeScore,
        collaborationScore: f.collaborationScore, safetyScore: f.safetyScore,
        overallComment: f.overallComment, recommendHire: f.recommendHire, fileId: f.fileId }
      this.submitting = true
      const res = await enterpriseEvalApi.create(payload)
      if (f !== this.form || batchId !== this.batchStore.selectedBatchId) return
      this.submitting = false
      if (res.code !== 0) { this.submitError = res.message || '提交失败，已保留填写内容'; return }
      window.__SAAS_DIRTY_FORM_GUARD__?.markSaved()
      toast.success('企业评价已提交，等待独立审核')
      this.$router.push({ path: LIST_PATH, query: this.batchStore.withBatchQuery({ id: String(res.data.id), reviewStatus: 'PENDING' }) })
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.eef { padding: var(--space-5); max-width: 980px; }
.eef__fields { border: 0; padding: 0; margin: 0; min-width: 0; }
.eef__error { color: var(--danger-700); background: var(--danger-50); padding: 12px 16px; border-radius: 8px; }
.eef__average { margin: 0; padding: 10px 14px; background: var(--primary-50, #eff6ff); border-radius: 8px; color: var(--text-secondary); font-size: 13px; }
.eef__average strong { margin-left: 10px; color: var(--primary-700); font-size: 20px; }
.eef__scores { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.eef__score { width: calc(20% - var(--space-2)); min-width: 90px; }
.eef__chk { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: var(--space-3); }
.eef__chips { margin-top: var(--space-2); }
.eef__file-row { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; min-height: 32px; }
.eef__file { font-size: var(--font-size-xs); }
.eef__att { font-size: var(--font-size-xs); color: var(--success-700); }
.eef__file { max-width: 100%; }
@media (max-width: 600px) { .eef__score { width: calc(50% - var(--space-2)); }.eef :deep(.app-submit-bar) { flex-wrap: wrap; }.eef :deep(.app-submit-bar__info) { flex-basis: 100%; } }
@media (max-height: 700px) { .eef :deep(.app-submit-bar.is-sticky) { position: static; } }
</style>
