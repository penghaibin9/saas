<template>
  <AppPageShell
    title="资助项目管理"
    subtitle="奖学金 / 助学金项目定义：金额、名额与准入条件。项目下再建学年批次开放申请。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（学工处全校）"
    watermark-purpose="资助项目管理"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载资助项目..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton code="studentAffairs.funding.project.manage" :loading="saving" @click="openForm">
          建项目
        </AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="新建资助项目">
        <div class="pf-grid">
          <label class="pf-field"><span>项目名称 *</span>
            <AppTextInput v-model="form.projectName" placeholder="如：国家励志奖学金" /></label>
          <label class="pf-field"><span>项目类型 *</span>
            <AppSelect v-model="form.projectType" :options="PROJECT_TYPE_OPTIONS" placeholder="" /></label>
          <label class="pf-field"><span>金额（元）</span>
            <AppNumberInput v-model="form.amount" :min="0" placeholder="如：3300" /></label>
          <label class="pf-field"><span>名额</span>
            <AppNumberInput v-model="form.quota" :min="0" placeholder="如：50" /></label>
        </div>
        <p v-if="form.error" class="pf-error">{{ form.error }}</p>
        <div class="pf-actions">
          <button type="button" class="pf-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton code="studentAffairs.funding.project.manage" :loading="saving" @click="save">保存</AppPermissionButton>
        </div>
      </AppSectionCard>

      <AppSectionCard title="项目列表">
        <div class="pf-filters">
          <button v-for="f in typeFilters" :key="f.key" type="button" class="pf-chip"
                  :class="{ 'is-on': activeType === f.key }" @click="setType(f.key)">{{ f.label }}</button>
        </div>
        <table class="sa-table">
          <thead><tr><th>项目名称</th><th>类型</th><th>金额</th><th>名额</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="p in filtered" :key="p.projectId">
              <td><strong>{{ p.projectName }}</strong></td>
              <td>{{ typeLabel(p.projectType) }}</td>
              <td>{{ p.amount != null ? ('¥' + p.amount) : '—' }}</td>
              <td>{{ p.quota != null ? p.quota : '—' }}</td>
              <td><StatusTag :type="p.status === 'ENABLED' ? 'success' : 'default'" :label="p.status === 'ENABLED' ? '启用' : '停用'" dot /></td>
            </tr>
            <tr v-if="!filtered.length"><td colspan="5" class="sa-empty">暂无资助项目，点右上「建项目」</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton, AppSectionCard,
  AppSelect, AppStatusTag, AppTextInput
} from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const TYPES = [
  { key: '', label: '全部' },
  { key: 'SCHOLARSHIP', label: '奖学金' },
  { key: 'GRANT', label: '助学金' }
]
const PROJECT_TYPE_OPTIONS = [{ value: 'SCHOLARSHIP', label: '奖学金' }, { value: 'GRANT', label: '助学金' }]

export default {
  name: 'FundingProjectView',
  components: {
    AppGlobalState, AppMetricCard, AppNumberInput, AppPageShell, AppPermissionButton, AppSectionCard,
    AppSelect, StatusTag: AppStatusTag, AppTextInput
  },
  data() {
    return {
      loading: true, saving: false, errorMessage: '', projects: [], activeType: '', typeFilters: TYPES,
      formVisible: false, form: { projectName: '', projectType: 'GRANT', amount: null, quota: null, error: '' }
    }
  },
  computed: {
    PROJECT_TYPE_OPTIONS: () => PROJECT_TYPE_OPTIONS,
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    filtered() { return this.activeType ? this.projects.filter((p) => p.projectType === this.activeType) : this.projects },
    metricCards() {
      const enabled = this.projects.filter((p) => p.status === 'ENABLED').length
      const grant = this.projects.filter((p) => p.projectType === 'GRANT').length
      return [
        { key: 'all', label: '项目总数', value: this.projects.length, accent: 'primary' },
        { key: 'en', label: '启用中', value: enabled, accent: 'success' },
        { key: 'gr', label: '助学金项目', value: grant, accent: 'warning' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const res = await studentAffairsApi.getFundingProjects({ pageSize: 200 })
      if (res.code === 0 && res.data) {
        this.projects = res.data.items || []
      } else {
        this.errorMessage = res.message || '资助项目加载失败'
      }
      this.loading = false
    },
    openForm() {
      this.form = { projectName: '', projectType: 'GRANT', amount: null, quota: null, error: '' }
      this.formVisible = true
    },
    async save() {
      const m = this.form
      const projectName = (m.projectName || '').trim()
      if (!projectName) { m.error = '项目名称必填'; return }
      m.error = ''
      this.saving = true
      const body = { projectName, projectType: m.projectType }
      if (m.amount != null && m.amount !== '') body.amount = Number(m.amount)
      if (m.quota != null && m.quota !== '') body.quota = Number(m.quota)
      const res = await studentAffairsApi.createFundingProject(body)
      if (res.code === 0) {
        toast.success('项目已创建')
        this.formVisible = false
        await this.load()
      } else {
        m.error = res.message || '创建失败'
      }
      this.saving = false
    },
    setType(k) { this.activeType = k },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[t] || t }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.pf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-3); }
.pf-field { display: flex; flex-direction: column; gap: 6px; font-size: var(--font-size-sm); }
.pf-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 8px 12px; }
.pf-error { color: var(--danger-500, #dc2626); font-size: var(--font-size-sm); margin: 4px 0; }
.pf-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.pf-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 8px 18px; cursor: pointer; }
.pf-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.pf-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.pf-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } .pf-grid { grid-template-columns: 1fr; } }
</style>
