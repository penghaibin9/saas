<template>
  <ModulePageShell
    title="教学任务"
    subtitle="按已发布并绑定年级的培养方案生成教学任务，分配授课教师、教师确认后提交审核"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton variant="primary" @click="showGen = !showGen">＋ 生成任务批次</AppButton>
    </template>

    <div class="mp-stack">
      <AppSectionCard v-if="showGen" title="生成教学任务批次">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item">
            学期
            <select v-model="gen.termId" class="aa-select">
              <option value="">选择学期…</option>
              <option v-for="t in terms" :key="t.termId" :value="t.termId">{{ t.yearCode }} 第 {{ t.termNo }} 学期</option>
            </select>
          </label>
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            批次名称
            <input v-model.trim="gen.batchName" class="aa-input" placeholder="选填，如 2026秋教学任务" maxlength="50" />
          </label>
          <AppButton variant="primary" :disabled="!gen.termId" :loading="generating" @click="doGenerate">生成（幂等）</AppButton>
        </div>
        <p class="mp-note">生成依据：状态为「已启用」且已绑定年级的培养方案。幂等——同学期重复生成不会重复建任务。</p>
      </AppSectionCard>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="还没有教学任务批次" description="先在「培养方案」发布并绑定年级，再来生成教学任务" />
      <DataTable v-else :columns="columns" :rows="rows" row-key="batchId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusColor(row.status)" dot>{{ statusLabel(row.status) }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="$router.push(`/admin/academic-affairs/teaching-tasks/${row.batchId}`)">分配 / 明细</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
/** 教学任务批次列表（/admin/academic-affairs/teaching-tasks）：GET/POST /academic-affairs/teaching-task-batches。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_BATCH_STATUS, taskBatchColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTaskBatchListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true, error: '', rows: [], terms: [],
      showGen: false, generating: false, gen: { termId: '', batchName: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'batchName', title: '批次名称' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  created() {
    // 「教学任务生成」菜单叶子直达本页并自动展开生成面板（?open=generate，Tier1 新增，复用本页不新建重复页面）
    if (this.$route && this.$route.query && this.$route.query.open === 'generate') this.showGen = true
    this.load()
    this.loadTerms()
  },
  methods: {
    statusColor: taskBatchColor,
    statusLabel(s) { return TASK_BATCH_STATUS[s] || s || '' },
    onPageChange(p) { this.pagination.page = p; this.load() },
    async loadTerms() {
      const res = await academicAffairsApi.getTerms({ page: 1, pageSize: 100 })
      if (res.code === 0) this.terms = res.data.list
    },
    async doGenerate() {
      if (this.generating || !this.gen.termId) return
      this.generating = true
      const res = await academicAffairsApi.generateTaskBatch({ termId: this.gen.termId, batchName: this.gen.batchName || undefined })
      this.generating = false
      if (res.code === 0) {
        toast.success('教学任务批次已生成')
        this.showGen = false
        this.gen = { termId: '', batchName: '' }
        this.load()
      } else {
        toast.error(res.message || '生成失败（需已发布并绑定年级的方案）')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTaskBatches({ page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) { this.rows = res.data.list; this.pagination.total = res.data.total }
      else { this.error = res.message }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form__item--grow { flex: 1; min-width: 220px; }
.aa-input, .aa-select { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
</style>
