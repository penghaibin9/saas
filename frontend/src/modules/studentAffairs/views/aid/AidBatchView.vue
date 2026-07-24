<template>
  <AppPageShell
    title="认定批次管理"
    subtitle="家庭经济困难认定批次：学年 / 申请窗口 / 公示天数配置。发布后学生与辅导员方可受理申请。"
    role-name="学工处 / 资助老师"
    data-scope-name="资助范围（学工处全校）"
    watermark-purpose="困难认定批次管理"
  >
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="正在加载认定批次..." @retry="load"
                    @back="$router.push('/admin/student-affairs/aid')">
      <div class="sa-toolbar">
        <div class="sa-grid sa-grid--metrics">
          <AppMetricCard v-for="c in metricCards" :key="c.key" :title="c.label" :value="c.value" :accent="c.accent" />
        </div>
        <AppPermissionButton :allowed="canBtn('studentAffairs.aid.batch.manage')" code="studentAffairs.aid.batch.manage" :loading="saving" @click="openForm">
          建批次
        </AppPermissionButton>
      </div>

      <AppSectionCard v-if="formVisible" title="新建认定批次">
        <div class="bf-grid">
          <label class="bf-field"><span>批次名称 *</span>
            <input v-model.trim="form.batchName" class="bf-input" placeholder="如：2025-2026 学年家庭经济困难认定" /></label>
          <label class="bf-field"><span>学年 *</span>
            <input v-model.trim="form.schoolYear" class="bf-input" placeholder="如：2025-2026" /></label>
          <label class="bf-field"><span>公示天数</span>
            <input v-model.number="form.publicityDays" type="number" min="0" class="bf-input" placeholder="默认 5，快测可填 0" /></label>
          <label class="bf-field bf-field--check">
            <input v-model="form.publish" type="checkbox" /> <span>立即发布（开放受理）</span></label>
        </div>
        <p v-if="form.error" class="bf-error">{{ form.error }}</p>
        <div class="bf-actions">
          <button type="button" class="bf-btn" @click="formVisible = false">取消</button>
          <AppPermissionButton :allowed="canBtn('studentAffairs.aid.batch.manage')" code="studentAffairs.aid.batch.manage" :loading="saving" @click="save">保存</AppPermissionButton>
        </div>
      </AppSectionCard>

      <AppSectionCard title="批次列表">
        <DataTable v-if="batches.length" :columns="batchColumns" :rows="batches" row-key="batchId">
          <template #cell-name="{ row }"><span class="mp-cell-main">{{ row.batchName }}</span></template>
          <template #cell-schoolYear="{ row }">{{ row.schoolYear || '—' }}</template>
          <template #cell-status="{ row }"><StatusTag :type="statusType(row.status)" :label="statusLabel(row.status)" dot /></template>
          <template #cell-publicityDays="{ row }">{{ row.publicityDays != null ? row.publicityDays + ' 天' : '—' }}</template>
          <template #cell-window="{ row }">
            <span class="bf-window">
              <template v-if="row.applyStart || row.applyEnd">
                <AppDateDisplay :value="row.applyStart" mode="date" empty-text="…" />
                至
                <AppDateDisplay :value="row.applyEnd" mode="date" empty-text="…" />
              </template>
              <span v-else>—</span>
            </span>
          </template>
        </DataTable>
        <p v-else class="sa-empty">暂无认定批次，点右上「建批次」</p>
        <AppPagination v-model:page="pagination.page" v-model:pageSize="pagination.pageSize"
                       :total="pagination.total" @change="load" />
      </AppSectionCard>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { DataTable } from '@/components/business'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'


const BATCH_STATUS = { DRAFT: '草稿', OPEN: '开放中', REVIEWING: '评审中', PUBLICITY: '公示中', CLOSED: '已截止', ARCHIVED: '已归档' }
const BATCH_COLUMNS = [
  { key: 'name', title: '批次名称' },
  { key: 'schoolYear', title: '学年' },
  { key: 'status', title: '状态' },
  { key: 'publicityDays', title: '公示天数' },
  { key: 'window', title: '申请窗口' }
]

export default {
  name: 'AidBatchView',
  components: { AppDateDisplay, AppGlobalState, AppMetricCard, AppPageShell, AppPagination, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag, DataTable },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      batchColumns: BATCH_COLUMNS,
      loading: true, saving: false, errorMessage: '', batches: [], statsBatches: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      formVisible: false, form: { batchName: '', schoolYear: '', publicityDays: 5, publish: true, error: '' }
    }
  },
  computed: {
    pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') },
    metricCards() {
      const open = this.statsBatches.filter((b) => b.status === 'OPEN').length
      const closed = this.statsBatches.filter((b) => ['CLOSED', 'ARCHIVED'].includes(b.status)).length
      return [
        { key: 'all', label: '批次总数', value: this.pagination.total, accent: 'primary' },
        { key: 'open', label: '开放受理', value: open, accent: 'success' },
        { key: 'closed', label: '已截止/归档', value: closed, accent: 'warning' }
      ]
    }
  },
  mounted() { this.load() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    async load() {
      this.loading = true; this.errorMessage = ''
      const [pageRes, statsRes] = await Promise.all([
        studentAffairsApi.getAidBatches({ page: this.pagination.page, pageSize: this.pagination.pageSize }),
        // 独立于当前分页的全量口径（上限 200），仅用于统计卡；不影响列表本身的真实分页
        studentAffairsApi.getAidBatches({ pageSize: 200 })
      ])
      if (pageRes.code === 0 && pageRes.data) {
        this.batches = pageRes.data.items || []
        this.pagination.total = pageRes.data.total != null ? pageRes.data.total : this.batches.length
      } else {
        this.errorMessage = pageRes.message || '认定批次加载失败'
      }
      this.statsBatches = (statsRes.code === 0 && statsRes.data) ? (statsRes.data.items || []) : []
      this.loading = false
    },
    openForm() {
      this.form = { batchName: '', schoolYear: '', publicityDays: 5, publish: true, error: '' }
      this.formVisible = true
    },
    async save() {
      const m = this.form
      if (!m.batchName || !m.schoolYear) { m.error = '批次名称与学年必填'; return }
      m.error = ''
      this.saving = true
      const res = await studentAffairsApi.createAidBatch({
        batchName: m.batchName, schoolYear: m.schoolYear,
        publicityDays: Number(m.publicityDays) || 0, publish: !!m.publish
      })
      if (res.code === 0) {
        toast.success('批次已保存')
        this.formVisible = false
        this.pagination.page = 1
        await this.load()
      } else {
        m.error = res.message || '保存失败'
      }
      this.saving = false
    },
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
.sa-toolbar { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-4); margin-bottom: var(--space-4); flex-wrap: wrap; }
.sa-grid--metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); flex: 1; min-width: 320px; }
.bf-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); margin-bottom: var(--space-3); }
.bf-field { display: flex; flex-direction: column; gap: 6px; font-size: var(--font-size-sm); }
.bf-field--check { flex-direction: row; align-items: center; gap: var(--space-2); }
.bf-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 8px 12px; }
.bf-error { color: var(--danger-500, #dc2626); font-size: var(--font-size-sm); margin: 4px 0; }
.bf-actions { display: flex; gap: var(--space-3); justify-content: flex-end; }
.bf-btn { border: 1px solid var(--border-light); background: var(--bg-card); border-radius: var(--radius-md); padding: 8px 18px; cursor: pointer; }
.sa-empty { color: var(--text-tertiary); padding: var(--space-4); text-align: center; }
.bf-window { color: var(--text-secondary); font-size: var(--font-size-sm); }
@media (max-width: 960px) { .sa-grid--metrics { grid-template-columns: 1fr 1fr; } .bf-grid { grid-template-columns: 1fr; } }
@import '@/styles/module-page.css';
</style>
