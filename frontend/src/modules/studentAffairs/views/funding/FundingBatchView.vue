<template>
  <AppPageShell
    title="资助批次管理"
    subtitle="在资助项目下建学年批次：申请窗口 / 公示天数 / 名额。发布后学生与辅导员方可申请。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（学工处全校）"
    watermark-purpose="资助批次管理"
  >
    <template #actions>
      <AppPermissionButton code="studentAffairs.funding.project.manage" :allowed="canBtn('studentAffairs.funding.project.manage')" :loading="saving" :disabled="!projects.length" @click="openForm">
        建批次
      </AppPermissionButton>
    </template>

    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载资助批次..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-grid sa-grid--metrics">
        <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
      </div>

      <p v-if="!projects.length" class="fb-hint">尚无资助项目，请先到「资助项目」建项目后再建批次。</p>

      <AppSectionCard title="批次列表">
        <DataTable v-if="batches.length" :columns="batchColumns" :rows="batches" row-key="batchId">
          <template #cell-project="{ row }"><span class="mp-cell-main">{{ projectName(row.projectId) }}</span> <em class="fb-type">{{ typeLabel(row.projectType) }}</em></template>
          <template #cell-schoolYear="{ row }">{{ row.schoolYear || '—' }}</template>
          <template #cell-quota="{ row }">{{ row.quota != null ? row.quota : '—' }}</template>
          <template #cell-publicityDays="{ row }">{{ row.publicityDays != null ? row.publicityDays + ' 天' : '—' }}</template>
          <template #cell-window="{ row }">
            <span class="fb-window">
              <template v-if="row.applyStart || row.applyEnd">
                <AppDateDisplay :value="row.applyStart" mode="date" empty-text="…" /> 至 <AppDateDisplay :value="row.applyEnd" mode="date" empty-text="…" />
              </template>
              <span v-else>—</span>
            </span>
          </template>
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" dot /></template>
        </DataTable>
        <p v-else class="sa-empty">暂无资助批次</p>
        <AppPagination v-if="total > pageSize || page > 1" class="fb-pager" v-model:page="page" v-model:pageSize="pageSize"
                       :total="total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>

    <!-- 新建资助批次 -->
    <AppDrawer v-model:visible="drawer.visible" title="新建资助批次">
      <div class="sa-form">
        <AppFormItem label="所属项目" required>
          <AppFundingProjectPicker v-model="drawer.form.projectId" :options="projectOptions" placeholder="（选择项目）" :disabled="saving" />
        </AppFormItem>
        <AppFormItem label="学年" required>
          <AppTextInput v-model="drawer.form.schoolYear" placeholder="如：2025-2026" :disabled="saving" />
        </AppFormItem>
        <div class="fb-grid2">
          <AppFormItem label="名额">
            <AppNumberInput v-model="drawer.form.quota" :min="0" placeholder="如：50" :disabled="saving" />
          </AppFormItem>
          <AppFormItem label="公示天数">
            <AppNumberInput v-model="drawer.form.publicityDays" :min="0" placeholder="默认 5，快测可填 0" :disabled="saving" />
          </AppFormItem>
        </div>
        <AppFormItem label="申请窗口" hint="选填，不填表示不限申请起止日期">
          <AppDateRangePicker v-model="drawer.form.applyWindow" mode="form" empty-label="不限" :show-shortcuts="false" :disabled="saving" />
        </AppFormItem>
        <label class="fb-check"><input v-model="drawer.form.publish" type="checkbox" :disabled="saving" /> <span>立即发布（开放申请）</span></label>
        <AppInlineAlert v-if="drawer.errorMessage" type="danger" :description="drawer.errorMessage" />
      </div>
      <template #footer>
        <button type="button" class="fb-btn" :disabled="saving" @click="drawer.visible = false">取消</button>
        <AppPermissionButton code="studentAffairs.funding.project.manage" :allowed="canBtn('studentAffairs.funding.project.manage')" :loading="saving" @click="save">保存</AppPermissionButton>
      </template>
    </AppDrawer>
  </AppPageShell>
</template>

<script>
import { AppDateDisplay, AppDateRangePicker, AppFormItem, AppGlobalState, AppInlineAlert, AppMetricCard,
        AppNumberInput, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard,
        AppStatusTag, AppFundingProjectPicker, AppTextInput } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { toast } from '@/utils/toast'

const BATCH_STATUS = { DRAFT: '草稿', OPEN: '开放中', REVIEWING: '评审中', PUBLICITY: '公示中', ANNOUNCED: '已公布', CLOSED: '已截止', ARCHIVED: '已归档' }
const BATCH_COLUMNS = [
  { key: 'project', title: '所属项目' },
  { key: 'schoolYear', title: '学年' },
  { key: 'quota', title: '名额' },
  { key: 'publicityDays', title: '公示天数' },
  { key: 'window', title: '申请窗口' },
  { key: 'status', title: '状态' }
]

function freshForm() {
  return { projectId: '', schoolYear: '', quota: null, publicityDays: 5, publish: true, applyWindow: { start: '', end: '' } }
}

export default {
  name: 'FundingBatchView',
  components: { AppDateDisplay, AppDateRangePicker, AppDrawer, AppFormItem, AppGlobalState, AppInlineAlert,
               AppMetricCard, AppNumberInput, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard,
               AppFundingProjectPicker, AppTextInput, StatusTag: AppStatusTag, DataTable },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      batchColumns: BATCH_COLUMNS,
      loading: true, saving: false, errorMessage: '', batches: [], projects: [], statusCounts: null,
      page: 1, pageSize: 20, total: 0,
      drawer: { visible: false, form: freshForm(), errorMessage: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      return [
        { key: 'all', label: '批次总数', value: this.total, accent: 'primary' },
        { key: 'open', label: '开放申请', value: this.statusCounts === null ? '—' : (this.statusCounts.OPEN || 0), accent: 'success' },
        { key: 'proj', label: '在用项目', value: '—', accent: 'warning' }
      ]
    },
    projectOptions() {
      return this.projects.map((p) => ({ label: `${p.projectName}（${this.typeLabel(p.projectType)}）`, value: p.projectId }))
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.errorMessage = ''
      const [bs, ps] = await Promise.all([
        studentAffairsApi.getFundingBatches({ page: this.page, pageSize: this.pageSize }),
        studentAffairsApi.getFundingProjects({ pageSize: 200 })
      ])
      if (bs.code === 0 && bs.data) {
        this.batches = bs.data.items || []
        this.total = bs.data.total != null ? bs.data.total : this.batches.length
        this.statusCounts = bs.data.statusCounts || null
        this.projects = (ps.code === 0 && ps.data) ? (ps.data.items || []) : []
      } else {
        this.errorMessage = bs.message || '资助批次加载失败'
      }
      this.loading = false
    },
    openForm() {
      this.drawer.form = freshForm()
      if (this.projects[0]) this.drawer.form.projectId = this.projects[0].projectId
      this.drawer.errorMessage = ''
      this.drawer.visible = true
    },
    async save() {
      const f = this.drawer.form
      if (!f.projectId || !f.schoolYear) { this.drawer.errorMessage = '所属项目与学年必填'; return }
      this.drawer.errorMessage = ''
      this.saving = true
      const body = { projectId: f.projectId, schoolYear: f.schoolYear, publicityDays: Number(f.publicityDays) || 0, publish: !!f.publish }
      if (f.quota != null && f.quota !== '') body.quota = Number(f.quota)
      if (f.applyWindow.start) body.applyStart = f.applyWindow.start
      if (f.applyWindow.end) body.applyEnd = f.applyWindow.end
      const res = await studentAffairsApi.createFundingBatch(body)
      if (res.code === 0) {
        toast.success('批次已保存')
        this.drawer.visible = false
        this.page = 1
        await this.load()
      } else {
        this.drawer.errorMessage = res.message || '保存失败'
      }
      this.saving = false
    },
    projectName(id) { const p = this.projects.find((x) => x.projectId === id); return p ? p.projectName : ('项目#' + id) },
    typeLabel(t) { return ({ SCHOLARSHIP: '奖学金', GRANT: '助学金', WORK_STUDY: '勤工助学', LOAN: '助学贷款' })[t] || t || '' },
    statusLabel(s) { return BATCH_STATUS[s] || s || '—' },
    statusType(s) {
      if (s === 'OPEN') return 'success'
      if (['REVIEWING', 'PUBLICITY'].includes(s)) return 'processing'
      if (['CLOSED', 'ARCHIVED'].includes(s)) return 'default'
      return 'warning'
    }
  }
}
</script>

<style scoped>
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); margin-bottom: var(--space-4); }
.fb-hint { color: var(--text-tertiary); font-size: var(--font-size-sm); margin-bottom: var(--space-3); }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.fb-type { color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.fb-window { color: var(--text-secondary); font-size: var(--font-size-sm); }
.fb-pager { margin-top: var(--space-4); }
.sa-form { display: flex; flex-direction: column; gap: var(--space-1); }
.fb-grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }
.fb-check { display: flex; align-items: center; gap: var(--space-2); font-size: var(--font-size-base); color: var(--text-secondary); cursor: pointer; margin: var(--space-1) 0 var(--space-3); }
.fb-btn { height: 34px; padding: 0 var(--space-4); border-radius: var(--radius-base); border: 1px solid var(--border-base); background: var(--bg-card); color: var(--text-secondary); font-size: var(--font-size-base); cursor: pointer; }
.fb-btn:hover { border-color: var(--border-dark); }
.fb-btn:disabled { opacity: 0.6; cursor: not-allowed; }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } .fb-grid2 { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
