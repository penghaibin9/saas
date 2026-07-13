<template>
  <AppPageShell
    title="资助批次管理"
    subtitle="在资助项目下建学年批次：申请窗口 / 公示天数 / 名额。发布后学生与辅导员方可申请。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（学工处全校）"
    watermark-purpose="资助批次管理"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载资助批次..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton code="studentAffairs.funding.project.manage" :loading="saving" :disabled="!projects.length" @click="openForm">
          建批次
        </AppPermissionButton>
      </div>

      <p v-if="!projects.length" class="fb-hint">尚无资助项目，请先到「资助项目」建项目后再建批次。</p>

      <AppSectionCard v-if="formVisible" title="新建资助批次">
        <div class="fb-grid">
          <label class="fb-field"><span>所属项目 *</span>
            <select v-model="form.projectId" class="fb-input">
              <option value="">（选择项目）</option>
              <option v-for="p in projects" :key="p.projectId" :value="p.projectId">
                {{ p.projectName }}（{{ typeLabel(p.projectType) }}）
              </option>
            </select></label>
          <label class="fb-field"><span>学年 *</span>
            <input v-model.trim="form.schoolYear" class="fb-input" placeholder="如：2025-2026" /></label>
          <label class="fb-field"><span>名额</span>
            <input v-model.number="form.quota" type="number" min="0" class="fb-input" placeholder="如：50" /></label>
          <label class="fb-field"><span>公示天数</span>
            <input v-model.number="form.publicityDays" type="number" min="0" class="fb-input" placeholder="默认 5，快测可填 0" /></label>
          <label class="fb-field bf-check"><input v-model="form.publish" type="checkbox" /> <span>立即发布（开放申请）</span></label>
        </div>
        <p v-if="form.error" class="fb-error">{{ form.error }}</p>
        <div class="fb-actions">
          <button type="button" class="fb-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton code="studentAffairs.funding.project.manage" :loading="saving" @click="save">保存</AppPermissionButton>
        </div>
      </AppSectionCard>

      <AppSectionCard title="批次列表">
        <table class="sa-table">
          <thead><tr><th>所属项目</th><th>学年</th><th>名额</th><th>公示天数</th><th>申请窗口</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="b in batches" :key="b.batchId">
              <td><strong>{{ projectName(b.projectId) }}</strong> <em class="fb-type">{{ typeLabel(b.projectType) }}</em></td>
              <td>{{ b.schoolYear || '—' }}</td>
              <td>{{ b.quota != null ? b.quota : '—' }}</td>
              <td>{{ b.publicityDays != null ? b.publicityDays + ' 天' : '—' }}</td>
              <td class="fb-window">{{ windowText(b) }}</td>
              <td><StatusTag :type="statusType(b.status)" :label="statusLabel(b.status)" dot /></td>
            </tr>
            <tr v-if="!batches.length"><td colspan="6" class="sa-empty">暂无资助批次</td></tr>
          </tbody>
        </table>
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const BATCH_STATUS = { DRAFT: '草稿', OPEN: '开放中', REVIEWING: '评审中', PUBLICITY: '公示中', ANNOUNCED: '已公布', CLOSED: '已截止', ARCHIVED: '已归档' }

export default {
  name: 'FundingBatchView',
  components: { AppGlobalState, AppMetricCard, AppPageShell, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag },
  data() {
    return {
      loading: true, saving: false, errorMessage: '', batches: [], projects: [],
      formVisible: false, form: { projectId: '', schoolYear: '', quota: null, publicityDays: 5, publish: true, error: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const open = this.batches.filter((b) => b.status === 'OPEN').length
      return [
        { key: 'all', label: '批次总数', value: this.batches.length, accent: 'primary' },
        { key: 'open', label: '开放申请', value: open, accent: 'success' },
        { key: 'proj', label: '在用项目', value: this.projects.length, accent: 'warning' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [bs, ps] = await Promise.all([
        studentAffairsApi.getFundingBatches({ pageSize: 200 }),
        studentAffairsApi.getFundingProjects({ pageSize: 200 })
      ])
      if (bs.code === 0 && bs.data) {
        this.batches = bs.data.items || []
        this.projects = (ps.code === 0 && ps.data) ? (ps.data.items || []) : []
      } else {
        this.errorMessage = bs.message || '资助批次加载失败'
      }
      this.loading = false
    },
    openForm() {
      this.form = { projectId: this.projects[0] ? this.projects[0].projectId : '', schoolYear: '', quota: null, publicityDays: 5, publish: true, error: '' }
      this.formVisible = true
    },
    async save() {
      const m = this.form
      if (!m.projectId || !m.schoolYear) { m.error = '所属项目与学年必填'; return }
      m.error = ''
      this.saving = true
      const body = { projectId: m.projectId, schoolYear: m.schoolYear, publicityDays: Number(m.publicityDays) || 0, publish: !!m.publish }
      if (m.quota != null && m.quota !== '') body.quota = Number(m.quota)
      const res = await studentAffairsApi.createFundingBatch(body)
      if (res.code === 0) {
        toast.success('批次已保存')
        this.formVisible = false
        await this.load()
      } else {
        m.error = res.message || '保存失败'
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
    },
    windowText(b) {
      const a = (b.applyStart || '').slice(0, 10); const z = (b.applyEnd || '').slice(0, 10)
      if (!a && !z) return '—'
      return `${a || '…'} 至 ${z || '…'}`
    }
  }
}
</script>

<style scoped>
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.fb-hint { color: var(--text-tertiary); font-size: var(--font-size-sm); margin-bottom: var(--space-3); }
.fb-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-3); }
.fb-field { display: flex; flex-direction: column; gap: 6px; font-size: var(--font-size-sm); }
.bf-check { flex-direction: row; align-items: center; gap: var(--space-2); }
.fb-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 8px 12px; }
.fb-error { color: var(--danger-500, #dc2626); font-size: var(--font-size-sm); margin: 4px 0; }
.fb-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.fb-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 8px 18px; cursor: pointer; }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-3); text-align: left; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.fb-type { color: var(--text-tertiary); font-size: var(--font-size-xs); font-style: normal; }
.fb-window { color: var(--text-secondary); font-size: var(--font-size-sm); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } .fb-grid { grid-template-columns: 1fr; } }
</style>
