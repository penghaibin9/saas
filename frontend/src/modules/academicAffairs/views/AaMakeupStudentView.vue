<template>
  <ModulePageShell title="重修 · 免修申请" subtitle="从本人正式成绩和课程版本发起申请，禁止手工输入课程名称">
    <div class="aamks-tabs">
      <button :class="['aamks-tab', { 'is-active': tab === 'retake' }]" @click="switchTab('retake')">我的重修</button>
      <button :class="['aamks-tab', { 'is-active': tab === 'exemption' }]" @click="switchTab('exemption')">我的免修</button>
    </div>

    <AppInlineAlert
      v-if="options.identityDebtCount"
      type="warning"
      :title="`${options.identityDebtCount}条历史成绩暂不可办理`"
      description="这些成绩缺少课程ID、课程版本或修读次数，请联系教务处完成身份治理。"
    />

    <AppSectionCard :title="tab === 'retake' ? '提交重修报名' : '提交免修申请'">
      <div class="aamks-form">
        <label class="aamks-field">
          <span>{{ tab === 'retake' ? '挂科成绩' : '目标课程版本' }}</span>
          <select v-if="tab === 'retake'" v-model="form.gradeId" class="aamks-select" :disabled="saving">
            <option value="">请选择当前有效挂科成绩</option>
            <option v-for="item in options.retakeOptions" :key="item.gradeId" :value="item.gradeId">
              {{ optionLabel(item, true) }}
            </option>
          </select>
          <select v-else v-model="form.courseId" class="aamks-select" :disabled="saving">
            <option value="">请选择课程具体版本</option>
            <option v-for="item in options.exemptionOptions" :key="item.courseId" :value="item.courseId">
              {{ optionLabel(item, false) }}
            </option>
          </select>
        </label>
        <label class="aamks-field">
          <span>申请理由</span>
          <AppTextarea v-model="form.reason" placeholder="选填；说明本次申请情况" :disabled="saving" />
        </label>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
        <AppInlineAlert
          v-if="tab === 'exemption'"
          type="info"
          description="免修终审通过后生成计学分、不计分数的正式成绩；材料附件由学校启用后按要求上传。"
        />
        <div class="aamks-actions">
          <AppButton variant="primary" :loading="saving" :disabled="!canSubmit" @click="submitApply">提交申请</AppButton>
        </div>
      </div>
    </AppSectionCard>

    <LoadingState v-if="loading" />
    <EmptyState v-else-if="!rows.length" :title="tab === 'retake' ? '暂无重修申请' : '暂无免修申请'" description="上方选择正式成绩或课程版本后提交" />
    <ul v-else class="aamks-list">
      <li v-for="row in rows" :key="row.applyId || row.exemptionId">
        <div>
          <div class="mp-cell-main">{{ row.courseName }}</div>
          <div class="mp-cell-sub">{{ row.termCode || '' }}<template v-if="row.retakeCount"> · 第{{ row.retakeCount }}次重修</template></div>
        </div>
        <StatusTag :type="stType(row.status)" :label="row.status" dot />
      </li>
    </ul>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppTextarea, AppInlineAlert, AppSectionCard } from '@/components/common'
import { academicAffairsMakeupApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { gradeIdentityApi } from '@/modules/academicAffairs/api/grade-identity.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaMakeupStudentView',
  components: { ModulePageShell, StatusTag, LoadingState, EmptyState, AppButton, AppTextarea, AppInlineAlert, AppSectionCard },
  data() {
    return {
      tab: 'retake', loading: true, rows: [], loadingOptions: false,
      options: { retakeOptions: [], exemptionOptions: [], identityDebtCount: 0 },
      form: { gradeId: '', courseId: '', reason: '', materialFileIds: [] },
      formError: '', saving: false
    }
  },
  computed: {
    canSubmit() {
      return !this.saving && (this.tab === 'retake' ? Boolean(this.form.gradeId) : Boolean(this.form.courseId))
    }
  },
  created() { this.reload(); this.loadOptions() },
  methods: {
    stType(status) { return ['APPROVED', 'ENROLLED', 'FINISHED'].includes(status) ? 'success' : status === 'REJECTED' ? 'danger' : 'primary' },
    optionLabel(item, includeAttempt) {
      const identity = `${item.courseCode || '无代码'} v${item.courseVersion || '?'}`
      const attempt = includeAttempt ? ` · 第${item.attemptNo || '?'}次修读 · ${item.score ?? '—'}分` : ''
      return `${item.courseName} · ${identity}${attempt}`
    },
    switchTab(key) {
      this.tab = key
      this.form = { gradeId: '', courseId: '', reason: '', materialFileIds: [] }
      this.formError = ''
      this.reload()
    },
    async loadOptions() {
      if (this.loadingOptions) return
      this.loadingOptions = true
      const res = await gradeIdentityApi.myMakeupOptions()
      this.loadingOptions = false
      if (res.code === 0) this.options = res.data || this.options
      else toast.error(res.message || '加载课程身份候选失败')
    },
    async reload() {
      this.loading = true
      const res = this.tab === 'retake' ? await api.retakeMy() : await api.exemptionMy()
      this.rows = res.code === 0 ? (res.data.items || []) : []
      this.loading = false
    },
    async submitApply() {
      if (!this.canSubmit) return
      this.formError = ''
      this.saving = true
      const body = this.tab === 'retake'
        ? { gradeId: Number(this.form.gradeId), reason: this.form.reason.trim() }
        : {
            courseId: Number(this.form.courseId),
            reason: this.form.reason.trim(),
            materialFileIds: this.form.materialFileIds
          }
      const res = this.tab === 'retake' ? await api.retakeApply(body) : await api.exemptionApply(body)
      this.saving = false
      if (res.code === 0) {
        toast.success('已提交')
        this.form = { gradeId: '', courseId: '', reason: '', materialFileIds: [] }
        await Promise.all([this.reload(), this.loadOptions()])
      } else this.formError = res.message || '提交失败'
    }
  }
}
</script>

<style scoped>
.aamks-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-color, #e5e7eb); margin-bottom: 12px; }
.aamks-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-secondary, #64748b); border-bottom: 2px solid transparent; }
.aamks-tab.is-active { color: var(--primary-color, #2563eb); border-bottom-color: var(--primary-color, #2563eb); font-weight: 600; }
.aamks-form { display: grid; gap: 14px; }
.aamks-field { display: grid; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aamks-select { min-height: 38px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 7px; background: #fff; }
.aamks-actions { display: flex; justify-content: flex-end; }
.aamks-list { list-style: none; margin: 12px 0 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.aamks-list li { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; background: var(--fill-light, #f8fafc); border-radius: 8px; }
</style>
