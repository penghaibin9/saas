<template>
  <ModulePageShell
    title="教学任务工作台"
    subtitle="先看阻断项，再完成教师分配、本人确认、学院核对和教务终审"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton :disabled="loading" @click="load">刷新</AppButton>
      <AppButton variant="primary" @click="showGen = !showGen">＋ 生成任务批次</AppButton>
    </template>

    <div class="mp-stack">
      <section class="task-batch-overview">
        <article v-for="metric in metrics" :key="metric.label" class="task-batch-metric">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
          <small>{{ metric.note }}</small>
        </article>
      </section>

      <AppSectionCard v-if="showGen" title="生成教学任务批次">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item">
            学期
            <AppTermEntityPicker v-model="gen.termId" placeholder="选择学期" />
          </label>
          <label class="aa-cal-form__item aa-cal-form__item--grow">
            批次名称
            <input v-model.trim="gen.batchName" class="aa-input" placeholder="选填，如 2026秋教学任务" maxlength="50" />
          </label>
          <AppButton variant="primary" :disabled="!gen.termId" :loading="generating" @click="doGenerate">生成并检查</AppButton>
        </div>
        <p class="mp-note">系统只生成当前学期应开的课程；无法解析学期序号、培养方案或年级关系时会明确返回未生成原因，不会猜测生成。</p>
      </AppSectionCard>

      <section class="task-batch-filters">
        <label>学期
          <AppTermEntityPicker v-model="filters.termId" placeholder="全部学期" clearable @change="applyFilters" />
        </label>
        <label>批次状态
          <select v-model="filters.status" class="aa-select" @change="applyFilters">
            <option value="">全部状态</option>
            <option v-for="(label, key) in batchStatuses" :key="key" :value="key">{{ label }}</option>
          </select>
        </label>
        <label class="task-batch-filters__search">快速搜索
          <input v-model.trim="keyword" class="aa-input" placeholder="批次名称、下一步或阻断原因" />
        </label>
      </section>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!filteredRows.length" title="没有符合条件的教学任务批次" description="先发布并绑定培养方案，再生成当前学期教学任务" />
      <DataTable v-else :columns="columns" :rows="filteredRows" row-key="batchId" :pagination="pagination" @page-change="onPageChange">
        <template #cell-batch="{ row }">
          <div class="mp-cell-main">{{ row.batchName || `批次 ${row.batchId}` }}</div>
          <div class="mp-cell-sub">学期ID {{ row.termId }} · 共 {{ row.taskTotal ?? 0 }} 条任务</div>
        </template>
        <template #cell-progress="{ row }">
          <div class="task-progress-line"><span>分配</span><strong>{{ row.assignedRate ?? 0 }}%</strong></div>
          <div class="task-progress"><span :style="{ width: `${row.assignedRate || 0}%` }" /></div>
          <div class="task-progress-line is-secondary"><span>教师确认</span><strong>{{ row.teacherConfirmRate ?? 0 }}%</strong></div>
          <div class="task-progress"><span :style="{ width: `${row.teacherConfirmRate || 0}%` }" /></div>
        </template>
        <template #cell-blockers="{ row }">
          <div v-if="row.blockers?.length" class="task-batch-blockers">
            <span v-for="item in row.blockers.slice(0, 3)" :key="item.code">{{ item.message }}</span>
            <small v-if="row.blockers.length > 3">另有 {{ row.blockers.length - 3 }} 类问题</small>
          </div>
          <span v-else class="task-batch-ready">无阻断</span>
        </template>
        <template #cell-status="{ row }">
          <AppStatusTag :status="row.status" :type="statusColor(row.status)" dot />
        </template>
        <template #cell-next="{ row }">
          <div class="mp-cell-main">{{ row.nextAction?.label || '核对批次状态' }}</div>
          <div v-if="row.blockerCount" class="mp-cell-sub is-warning">共 {{ row.blockerCount }} 项阻断</div>
        </template>
        <template #cell-actions="{ row }">
          <button class="mp-link" @click="openBatch(row)">进入工作台</button>
        </template>
      </DataTable>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppTermEntityPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { TASK_BATCH_STATUS, taskBatchColor } from '@/modules/academicAffairs/constants/teaching'
import { toast } from '@/utils/toast'

export default {
  name: 'AaTaskBatchListView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppTermEntityPicker },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      showGen: false,
      generating: false,
      gen: { termId: '', batchName: '' },
      filters: { termId: '', status: '' },
      keyword: '',
      batchStatuses: TASK_BATCH_STATUS,
      pagination: { page: 1, pageSize: 20, total: 0 },
      columns: [
        { key: 'batch', title: '批次 / 规模' },
        { key: 'progress', title: '执行进度', width: '190px' },
        { key: 'blockers', title: '当前阻断' },
        { key: 'status', title: '批次状态', width: '130px' },
        { key: 'next', title: '下一步' },
        { key: 'actions', title: '操作', width: '110px' }
      ]
    }
  },
  computed: {
    metrics() {
      const rows = this.rows || []
      const totals = rows.reduce((sum, row) => sum + Number(row.taskTotal || 0), 0)
      const blockers = rows.reduce((sum, row) => sum + Number(row.blockerCount || 0), 0)
      const waiting = rows.reduce((sum, row) => sum + Number(row.waitingTeacherCount || 0), 0)
      const ready = rows.reduce((sum, row) => sum + Number(row.readyCount || 0), 0)
      return [
        { label: '当前批次', value: rows.length, note: '按当前数据范围展示' },
        { label: '教学任务', value: totals, note: '不含已并入合班记录' },
        { label: '待教师确认', value: waiting, note: '必须教师本人处理' },
        { label: '总阻断项', value: blockers, note: '处理完才能进入审核' },
        { label: '已就绪任务', value: ready, note: '可进入排课' }
      ]
    },
    filteredRows() {
      const keyword = this.keyword.toLowerCase()
      if (!keyword) return this.rows
      return this.rows.filter((row) => {
        const blockerText = (row.blockers || []).map((item) => item.message).join(' ')
        return [row.batchName, row.status, row.nextAction?.label, blockerText]
          .some((value) => String(value || '').toLowerCase().includes(keyword))
      })
    }
  },
  created() {
    if (this.$route?.query?.open === 'generate') this.showGen = true
    this.load()
  },
  methods: {
    statusColor: taskBatchColor,
    applyFilters() {
      this.pagination.page = 1
      this.load()
    },
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    openBatch(row) {
      this.$router.push(`/admin/academic-affairs/teaching-tasks/${row.batchId}`)
    },
    async doGenerate() {
      if (this.generating || !this.gen.termId) return
      this.generating = true
      const res = await academicAffairsApi.generateTaskBatch({
        termId: this.gen.termId,
        batchName: this.gen.batchName || undefined
      })
      this.generating = false
      if (res.code === 0) {
        toast.success('教学任务批次已生成，请继续处理阻断项')
        this.showGen = false
        this.gen = { termId: '', batchName: '' }
        this.load()
      } else toast.error(res.message || '生成失败，请核对培养方案和学期配置')
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getTaskBatches({
        termId: this.filters.termId || undefined,
        status: this.filters.status || undefined,
        page: this.pagination.page,
        pageSize: this.pagination.pageSize
      })
      if (res.code === 0) {
        this.rows = res.data?.list || []
        this.pagination.total = Number(res.data?.total || 0)
      } else this.error = res.message || '教学任务批次加载失败'
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.task-batch-overview { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.task-batch-metric { padding: 16px; border: 1px solid var(--gray-200); border-radius: 12px; background: #fff; }
.task-batch-metric span, .task-batch-metric small { display: block; color: var(--gray-500); font-size: 12px; }
.task-batch-metric strong { display: block; margin: 8px 0 5px; color: var(--gray-900); font-size: 24px; }
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--gray-700); }
.aa-cal-form__item--grow { flex: 1; min-width: 220px; }
.aa-input, .aa-select { height: 36px; padding: 0 10px; border: 1px solid var(--gray-300); border-radius: 7px; background: #fff; color: var(--gray-900); font-size: 13px; box-sizing: border-box; }
.task-batch-filters { display: flex; align-items: flex-end; gap: 14px; padding: 14px 16px; border: 1px solid var(--gray-200); border-radius: 12px; background: #fff; }
.task-batch-filters label { display: flex; flex-direction: column; gap: 6px; color: var(--gray-600); font-size: 12px; }
.task-batch-filters__search { flex: 1; }
.task-batch-filters__search .aa-input { width: 100%; }
.task-progress-line { display: flex; justify-content: space-between; color: var(--gray-700); font-size: 12px; }
.task-progress-line.is-secondary { margin-top: 8px; }
.task-progress { height: 5px; margin-top: 4px; border-radius: 3px; background: var(--gray-100); overflow: hidden; }
.task-progress span { display: block; height: 100%; border-radius: inherit; background: var(--primary-500); }
.task-batch-blockers { display: flex; flex-direction: column; gap: 4px; }
.task-batch-blockers span { color: var(--warning-700); font-size: 12px; }
.task-batch-blockers small { color: var(--gray-500); }
.task-batch-ready { color: var(--success-700); font-size: 12px; font-weight: 600; }
.mp-cell-sub.is-warning { color: var(--warning-700); }
@media (max-width: 1180px) { .task-batch-overview { grid-template-columns: repeat(3, 1fr); } }
@media (max-width: 760px) { .task-batch-overview { grid-template-columns: 1fr 1fr; } .task-batch-filters { flex-direction: column; align-items: stretch; } }
</style>
