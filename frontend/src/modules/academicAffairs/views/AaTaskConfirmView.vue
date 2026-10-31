<template>
  <ModulePageShell title="教学任务确认" subtitle="学院先核对，校教务再终审；按当前责任岗位办理" :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName" show-subtitle-in-concise>
    <div class="task-workspace__filters"><label>学期<AppTermEntityPicker v-model="termId" clearable @change="query" /></label><label>批次状态<select v-model="status" @change="query"><option value="">全部状态</option><option value="DRAFT">准备与核对</option><option value="RETURNED">已退回学院</option><option value="COLLEGE_CONFIRMED">待校教务终审</option><option value="APPROVED">审核已完成</option></select></label><label>搜索批次<input v-model.trim="keyword" placeholder="批次名称" @keyup.enter="query" /></label><AppButton @click="query">查询</AppButton></div>
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <EmptyState v-else-if="!rows.length" title="当前范围暂无教学任务批次" description="从已发布培养方案生成后进入核对队列。" />
    <div v-else class="task-confirm-stack task-workspace">
      <div class="task-confirm-layout">
      <section class="task-confirm-queue" aria-label="责任队列">
        <h3>责任队列</h3>
        <button v-for="row in rows" :key="row.batchId" type="button" :class="{ active: selectedBatchId === String(row.batchId) }" @click="selectBatch(row)">
          <strong>{{ row.batchName }}</strong>
          <span>{{ row.termLabel || '学期待核对' }}</span>
          <AppStatusTag :type="taskBatchColor(row.status)" :label="statusLabel(row.status)" />
          <small>{{ row.nextAction?.label || '打开核对正式状态与阻断' }}</small>
        </button>
        <div class="task-confirm-pages">
          <button class="mp-link" :disabled="page === 1" @click="changePage(-1)">上一页</button>
          <span>{{ page }} / {{ Math.max(1, Math.ceil(total / 20)) }}</span>
          <button class="mp-link" :disabled="page * 20 >= total" @click="changePage(1)">下一页</button>
        </div>
      </section>
      <AaTaskDetailView v-if="selectedBatchId" :ctx="ctx" :selected-batch-id="selectedBatchId" />
      <EmptyState v-else title="选择需要核对的批次" description="先查看来源、教师确认状态和阻断证据，再办理当前节点。" />
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppTermEntityPicker } from '@/components/common'
import { academicAffairsApi } from '../api/academic-affairs.api'
import { TASK_BATCH_STATUS, taskBatchColor } from '../constants/teaching'
import AaTaskDetailView from './AaTaskDetailView.vue'

export default {
  name: 'AaTaskConfirmView',
  components: { AppButton, AppTermEntityPicker, ModulePageShell, LoadingState, ErrorState, EmptyState, AppStatusTag, AaTaskDetailView },
  props: { ctx: { type: Object, required: true } },
  data() { return { termId: '', status: '', keyword: '', loading: true, error: '', rows: [], revision: 0, page: 1, total: 0 } },
  computed: {
    selectedBatchId() { return String(this.$route.query.batchId || '') },
    queueQuery() { const q = this.$route.query; return JSON.stringify([q.termId, q.batchStatus, q.batchKeyword, q.queuePage]) }
  },
  created() { this.restoreQuery(); this.load() },
  watch: { queueQuery() { this.restoreQuery(); this.load() }, ctx() { this.revision++; this.rows = []; this.total = 0; this.load() } },
  beforeUnmount() { this.revision++ },
  methods: {
    restoreQuery() { const q = this.$route.query; this.termId = String(q.termId || ''); this.status = String(q.batchStatus || ''); this.keyword = String(q.batchKeyword || ''); this.page = Math.max(1, Number(q.queuePage) || 1) },
    async query() { const before = this.$route.fullPath; await this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, termId: this.termId || undefined, batchStatus: this.status || undefined, batchKeyword: this.keyword || undefined, batchId: undefined, status: undefined, keyword: undefined, page: undefined, queuePage: '1' } }); if (before === this.$route.fullPath) { this.page = 1; await this.load() } },
    taskBatchColor,
    statusLabel(value) { return TASK_BATCH_STATUS[value] || '状态待确认' },
    selectBatch(row) { this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, batchId: String(row.batchId), status: undefined, keyword: undefined, page: undefined, teachingTaskId: undefined } }) },
    changePage(delta) { return this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, queuePage: String(this.page + delta) } }) },
    async load() {
      const revision = ++this.revision
      this.loading = true; this.error = ''; this.rows = []; this.total = 0
      try {
        const result = await academicAffairsApi.getTaskBatches({ termId: this.termId || undefined, status: this.status || undefined, keyword: this.keyword || undefined, page: this.page, pageSize: 20 })
        if (revision !== this.revision) return
        if (result.code !== 0) { this.error = result.message || '核对队列读取失败，请重试。'; return }
        this.rows = result.data?.list || []; this.total = Number(result.data?.total || 0)
      } catch (error) { if (revision === this.revision) this.error = error.message || '网络连接失败，请重试。' }
      finally { if (revision === this.revision) this.loading = false }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
@import '../styles/teaching-task-workspace.css';
.task-confirm-layout :deep(.task-workbench__metrics) { display: none; }
.task-confirm-layout :deep(.mps__title) { font-size: 20px; }
.task-confirm-layout :deep(.task-workbench__hero) { padding: 14px; }
.task-confirm-layout { display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 16px; align-items: start; }
.task-confirm-stack { display: grid; gap: 16px; }
.task-confirm-queue { border: 1px solid var(--gray-200); border-radius: 10px; overflow: hidden; background: var(--bg-card); }
.task-confirm-queue { max-height: 65vh; overflow-y: auto; }
.task-confirm-layout :deep(.task-workbench__hero) { display: block; }
.task-confirm-layout :deep(.task-workbench__hero p) { margin-bottom: 0; }
.task-confirm-queue h3 { margin: 0; padding: 16px; font-size: 15px; }
.task-confirm-queue > button { display: flex; flex-direction: column; align-items: flex-start; gap: 9px; width: 100%; padding: 16px 13px; border: 0; border-top: 1px solid var(--gray-200); border-left: 3px solid transparent; background: transparent; color: var(--gray-800); text-align: left; cursor: pointer; }
.task-confirm-queue > button.active { border-left-color: var(--primary-600); background: var(--primary-50); }
.task-confirm-queue span, .task-confirm-queue small { font-size: 12px; color: var(--gray-500); }
.task-confirm-pages { display: flex; justify-content: space-between; gap: 8px; padding: 12px; }
@media (max-width: 1050px) { .task-confirm-layout { grid-template-columns: 1fr; } }
</style>
