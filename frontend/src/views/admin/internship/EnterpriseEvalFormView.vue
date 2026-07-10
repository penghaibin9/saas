<template>
  <ModulePageShell title="录入企业评价"
    subtitle="学校转录企业纸质评价独立录入页 · 来源标记「学校录入」· 提交走真实接口并写审计 · 扫描件走文件中心"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="backToList">← 返回企业评价列表</AppButton>
    </template>

    <section class="mp-card eef">
      <AppForm ref="formRef" :model="form" :rules="rules" layout="vertical" @submit="doSubmit">
        <AppFormSection title="实习学生" description="仅可对数据范围内实习学生录入，越权将被后端拒绝并写审计">
          <AppFormItem label="实习学生" prop="internshipId" required>
            <AppStudentPicker
              v-model="form.internshipId"
              :remote-search="searchInternStudents"
              placeholder="输入姓名或学号搜索实习学生"
              search-placeholder="按姓名 / 学号搜索"
              data-scope-hint="指导教师仅本人指导学生；管理员全校"
            />
          </AppFormItem>
          <AppFormItem label="企业导师姓名（来源可追溯）" prop="mentorName" required>
            <AppTextInput v-model="form.mentorName" placeholder="填写企业导师真实姓名" />
          </AppFormItem>
        </AppFormSection>

        <AppFormSection title="五维评分" description="五维评分均 0-100">
          <div class="eef__scores">
            <AppFormItem v-for="s in scoreDefs" :key="s.key" :label="s.label" :prop="s.key" class="eef__score">
              <AppNumberInput v-model="form[s.key]" :min="0" :max="100" />
            </AppFormItem>
          </div>
        </AppFormSection>

        <AppFormSection title="评语与建议">
          <AppFormItem label="综合评语"><AppTextarea v-model="form.overallComment" :rows="2" placeholder="企业对学生的综合评语" /></AppFormItem>
          <label class="eef__chk"><input v-model="form.recommendHire" type="checkbox" />建议录用</label>
        </AppFormSection>

        <AppFormSection title="评价扫描件" description="可选 · 企业签署，走文件中心真实上传，不伪造">
          <AppFormItem label="评价扫描件">
            <div class="eef__file-row">
              <input type="file" class="eef__file" @change="onFilePick" />
              <span v-if="form.fileId" class="eef__att">已上传：{{ attachName }}</span>
              <span v-else-if="uploadingFile" class="eef__att">上传中…</span>
            </div>
          </AppFormItem>
        </AppFormSection>

        <p class="eef__hint">五维评分均 0-100。学校录入的企业纸质评价来源标记为「学校录入」，请如实转录企业导师评价，勿代填虚构。</p>

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
 * 企业评价独立录入页（/admin/internship/enterprise-evals/new）。
 * 由 EnterpriseEvalView 的「＋ 录入企业评价」进入；原录入窄弹窗收口至此。
 * 字段与校验与原弹窗一致（学生 + 企业导师 + 五维评分 + 评语/建议录用 + 扫描件），
 * 提交走真实 enterpriseEvalApi.create，附件走 uploadAttachment（文件中心）。
 */
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppForm, AppFormSection, AppFormItem, AppSubmitBar, AppTextInput, AppNumberInput,
  AppTextarea, AppStudentPicker } from '@/components/common'
import { searchInternStudents } from './components/entityPickerAdapters'
import { enterpriseEvalApi } from '@/modules/internship/api/enterprise-eval.api'
import { toast } from '@/utils/toast'

const SCORES = [
  { key: 'attendanceScore', label: '出勤' }, { key: 'skillScore', label: '技能' },
  { key: 'attitudeScore', label: '态度' }, { key: 'collaborationScore', label: '协作' }, { key: 'safetyScore', label: '安全纪律' }
]
const LIST_PATH = '/admin/internship/enterprise-evals'

function emptyForm() {
  return { internshipId: '', mentorName: '', attendanceScore: null, skillScore: null,
    attitudeScore: null, collaborationScore: null, safetyScore: null, overallComment: '', recommendHire: false, fileId: '' }
}

export default {
  name: 'EnterpriseEvalFormView',
  components: { ModulePageShell, AppButton, AppForm, AppFormSection, AppFormItem, AppSubmitBar,
    AppTextInput, AppNumberInput, AppTextarea, AppStudentPicker },
  data() {
    return {
      scoreDefs: SCORES,
      form: emptyForm(),
      attachName: '', uploadingFile: false, submitting: false,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    rules() {
      const r = {
        internshipId: [{ required: true, message: '请选择实习学生' }],
        mentorName: [
          { required: true, message: '请填写企业导师姓名' },
          { validator: (v) => (String(v).trim() ? true : '请填写企业导师姓名') }
        ]
      }
      // 五维评分校验对齐原录入弹窗：必填且 0-100
      for (const s of SCORES) {
        r[s.key] = [
          { required: true, message: `${s.label}评分须为 0-100` },
          { validator: (v) => (v < 0 || v > 100 ? `${s.label}评分须为 0-100` : true) }
        ]
      }
      return r
    }
  },
  methods: {
    // 选择器远程搜索（岗位实习模块适配层，关键字与数据范围由后端裁定）
    searchInternStudents,
    backToList() {
      // 从列表进入时走历史返回（保留筛选/页码/选中）；深链直入时兜底到列表
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && (back === LIST_PATH || back.startsWith(LIST_PATH + '?'))) this.$router.back()
      else this.$router.push(LIST_PATH)
    },
    async onFilePick(e) {
      const file = e.target.files && e.target.files[0]
      if (!file) return
      this.uploadingFile = true
      const res = await enterpriseEvalApi.uploadAttachment(file)
      this.uploadingFile = false
      if (res.code !== 0) return toast.error(res.message || '上传失败')
      this.form.fileId = res.data.fileId; this.attachName = res.data.fileName || file.name
    },
    onSubmitClick() {
      // 统一走 AppForm 校验管道（校验通过后触发 @submit → doSubmit）
      if (this.$refs.formRef) this.$refs.formRef.onSubmit()
    },
    async doSubmit() {
      if (this.submitting) return
      const f = this.form
      const payload = { internshipId: f.internshipId, mentorName: f.mentorName,
        attendanceScore: f.attendanceScore, skillScore: f.skillScore, attitudeScore: f.attitudeScore,
        collaborationScore: f.collaborationScore, safetyScore: f.safetyScore,
        overallComment: f.overallComment, recommendHire: f.recommendHire, fileId: f.fileId }
      this.submitting = true
      const res = await enterpriseEvalApi.create(payload)
      this.submitting = false
      if (res.code !== 0) return toast.error(res.message || '提交失败')
      toast.success('已录入并写审计')
      this.backToList()
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.eef { padding: var(--space-5); max-width: 860px; }
.eef__scores { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.eef__score { width: calc(20% - var(--space-2)); min-width: 90px; }
.eef__chk { display: flex; align-items: center; gap: var(--space-1); font-size: var(--font-size-sm); color: var(--text-secondary); margin-bottom: var(--space-3); }
.eef__file-row { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; min-height: 32px; }
.eef__file { font-size: var(--font-size-xs); }
.eef__att { font-size: var(--font-size-xs); color: var(--success-700); }
.eef__hint { margin: var(--space-2) 0 var(--space-4); font-size: var(--font-size-xs); color: var(--text-tertiary); }
</style>
