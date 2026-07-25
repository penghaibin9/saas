<template>
  <div class="ibs">
    <span class="ibs__label">当前批次</span>
    <template v-if="store.batchLoading">
      <span class="ibs__text">正在读取…</span>
    </template>
    <!-- 失败且无缓存列表：纯错误态；有缓存列表时仍保留下拉，避免短暂故障后无法切批次 -->
    <template v-else-if="store.batchLoadFailed && !store.availableBatches.length">
      <span class="ibs__text ibs__text--err">{{ store.batchError || '批次服务加载失败' }}</span>
      <button type="button" class="mp-link" @click="reload">重试</button>
    </template>
    <template v-else-if="!store.availableBatches.length">
      <span class="ibs__text">暂无可用实习批次，请先创建并启用批次</span>
      <button type="button" class="mp-link" @click="$router.push('/admin/internship/batches')">去批次管理 →</button>
    </template>
    <template v-else>
      <select
        class="ibs__select"
        :value="store.selectedBatchId"
        aria-label="选择实习批次"
        @change="onSelect($event.target.value)"
      >
        <option v-if="store.needsExplicitSelect && !store.selectedBatchId" value="" disabled>请选择批次</option>
        <option v-for="b in store.availableBatches" :key="b.id" :value="String(b.id)">
          {{ b.batchName }}{{ b.status === 'RUNNING' ? '（进行中）' : '' }}{{ b.batchNo ? ` · ${b.batchNo}` : '' }}
        </option>
      </select>
      <span v-if="store.batchStatus === 'RUNNING'" class="ibs__tag">进行中</span>
      <span v-else-if="store.batchStatus" class="ibs__tag ibs__tag--muted">{{ statusLabel }}</span>
      <span v-if="store.startDate && store.endDate" class="ibs__meta">{{ store.startDate }} ~ {{ store.endDate }}</span>
      <span v-if="runningCount > 1" class="ibs__meta">进行中 {{ runningCount }} 个</span>
      <span v-if="store.needsExplicitSelect && !store.selectedBatchId" class="ibs__text ibs__text--err">请明确选择当前工作批次</span>
      <span v-if="store.invalidUrlBatch" class="ibs__text ibs__text--err">{{ store.batchError }}</span>
      <template v-if="store.batchLoadFailed">
        <span class="ibs__text ibs__text--err">{{ store.batchError || '批次列表刷新失败，已保留上次列表' }}</span>
        <button type="button" class="mp-link" @click="reload">重试</button>
      </template>
    </template>
  </div>
</template>

<script>
/**
 * InternshipBatchStrip — 真实批次选择器，读写 Pinia internshipBatch + URL query.batchId。
 * 仅做批次上下文，不做页面视觉重构。
 */
import { useInternshipBatchStore } from '@/stores/internshipBatch'

export default {
  name: 'InternshipBatchStrip',
  setup() {
    return { store: useInternshipBatchStore() }
  },
  computed: {
    runningCount() {
      return this.store.availableBatches.filter((b) => b.status === 'RUNNING').length
    },
    statusLabel() {
      const m = { DRAFT: '草稿', RUNNING: '进行中', CLOSED: '已结束', ARCHIVED: '已归档', VOIDED: '已作废' }
      return m[this.store.batchStatus] || this.store.batchStatus || '—'
    }
  },
  methods: {
    onSelect(id) {
      this.store.selectBatch(id)
      const q = { ...this.$route.query }
      if (id) q.batchId = id
      else delete q.batchId
      this.$router.replace({ query: q }).catch(() => {})
    },
    reload() {
      this.store.ensureLoaded({
        batchIdFromUrl: this.$route.query.batchId || '',
        force: true
      })
    }
  }
}
</script>

<style scoped>
.ibs {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--border-color, #e5e7eb);
  background: var(--surface-muted, #f8fafc);
  font-size: 13px;
}
.ibs__label { font-weight: 600; color: var(--text-secondary, #64748b); }
.ibs__select {
  min-width: 220px;
  max-width: 420px;
  padding: 4px 8px;
  border: 1px solid var(--border-color, #d1d5db);
  border-radius: 4px;
  background: #fff;
}
.ibs__text { color: var(--text-secondary, #64748b); }
.ibs__text--err { color: var(--danger-600, #dc2626); }
.ibs__meta { color: var(--text-tertiary, #94a3b8); }
.ibs__tag {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 4px;
  background: #dcfce7;
  color: #166534;
  font-size: 12px;
}
.ibs__tag--muted { background: #e2e8f0; color: #475569; }
</style>
