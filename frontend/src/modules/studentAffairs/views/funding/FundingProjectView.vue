<template>
  <AppPageShell
    title="资助项目管理"
    subtitle="奖学金 / 助学金项目定义：金额、名额与准入条件。项目下再建学年批次开放申请。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（学工处全校）"
    watermark-purpose="资助项目管理"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.funding.project.manage" :allowed="canBtn('studentAffairs.funding.project.manage')" :loading="saving" @click="openForm">
        建项目
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载资助项目..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

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
        <!-- 资助项目是学校级项目目录（数量级远小于申请/发放台账），后端 /funding/projects 虽支持 page/pageSize，
             但项目总数统计卡依赖一次性拉取的完整列表；实际项目数不会达到需要分页浏览的规模，暂不引入 AppPagination。 -->
      </AppSectionCard>
    </AppGlobalState>

    <!-- 新建资助项目 -->
    <AppDrawer v-model:visible="drawer.visible" title="新建资助项目">
      <div class="sa-form">
        <AppFormItem label="项目名称" required>
          <AppTextInput v-model="drawer.form.projectName" placeholder="如：国家励志奖学金" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="项目类型" required>
          <AppSelect v-model="drawer.form.projectType" :options="projectTypeOptions" :disabled="saving" />
        </AppFormItem>
        <div class="pf-grid2">
          <AppFormItem label="金额（元）">
            <AppNumberInput v-model="drawer.form.amount" :min="0" placeholder="如：3300" :disabled="saving" />
          </AppFormItem>
          <AppFormItem label="名额">
            <AppNumberInput v-model="drawer.form.quota" :min="0" placeholder="如：50" :disabled="saving" />
          </AppFormItem>
        </div>
        <AppInlineAlert v-if="drawer.errorMessage" type="danger" :description="drawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="pf-btn" :disabled="saving" @click="drawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.funding.project.manage" :allowed="canBtn('studentAffairs.funding.project.manage')" :loading="saving" @click="save">保存</AppPermissionButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import { AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppNumberInput, AppPageShell,
        AppPermissionButton, AppSectionCard, AppSelect, AppStatusTag, AppTextInput } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'

const TYPES = [
  { key: '', label: '全部' },
  { key: 'SCHOLARSHIP', label: '奖学金' },
  { key: 'GRANT', label: '助学金' }
]
const PROJECT_TYPE_OPTIONS = [{ label: '奖学金', value: 'SCHOLARSHIP' }, { label: '助学金', value: 'GRANT' }]

function freshForm() {
  return { projectName: '', projectType: 'GRANT', amount: null, quota: null }
}

export default {
  name: 'FundingProjectView',
  components: { AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard, AppNumberInput,
               AppPageShell, AppPermissionButton, AppSectionCard, AppSelect, AppTextInput, StatusTag: AppStatusTag },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, saving: false, errorMessage: '', projects: [], activeType: '', typeFilters: TYPES,
      projectTypeOptions: PROJECT_TYPE_OPTIONS,
      drawer: { visible: false, form: freshForm(), errorMessage: '' }
    }
  },
  computed: {
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
    canBtn(code) { return canCode(this.ctx, code) },
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
      this.drawer.form = freshForm()
      this.drawer.errorMessage = ''
      this.drawer.visible = true
    },
    async save() {
      const f = this.drawer.form
      if (!f.projectName) { this.drawer.errorMessage = '项目名称必填'; return }
      this.drawer.errorMessage = ''
      this.saving = true
      const body = { projectName: f.projectName, projectType: f.projectType }
      if (f.amount != null && f.amount !== '') body.amount = Number(f.amount)
      if (f.quota != null && f.quota !== '') body.quota = Number(f.quota)
      const res = await studentAffairsApi.createFundingProject(body)
      if (res.code === 0) {
        toast.success('项目已创建')
        this.drawer.visible = false
        await this.load()
      } else {
        this.drawer.errorMessage = res.message || '创建失败'
      }
      this.saving = false
    },
    setType(k) { this.activeType = k },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[t] || t }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.pf-filters { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.pf-chip { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-full); padding: 4px 14px; font-size: var(--font-size-sm); cursor: pointer; }
.pf-chip.is-on { background: var(--color-primary); color: #fff; border-color: var(--color-primary); }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.sa-form { display: flex; flex-direction: column; gap: var(--space-1); }
.pf-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }
.pf-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.pf-btn:hover { border-color: var(--border-dark); }
.pf-btn:disabled { opacity: 0.6; cursor: not-allowed; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } .pf-grid2 { grid-template-columns: 1fr; } }
</style>
