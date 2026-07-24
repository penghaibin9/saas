<template>
  <div class="gbs">
    <span class="gbs__label">当前批次</span>
    <template v-if="store.batchLoading">
      <span class="gbs__text">正在读取…</span>
    </template>
    <template v-else-if="store.batchError">
      <span class="gbs__text gbs__text--err">{{ store.batchError }}</span>
      <button type="button" class="mp-link" @click="reload">重试</button>
    </template>
    <template v-else-if="!store.availableBatches.length">
      <span class="gbs__text">暂无可用毕设批次，请先创建并启用毕设批次</span>
      <button type="button" class="mp-link" @click="$router.push('/admin/graduation/batches?panel=list')">去毕设批次 →</button>
      <slot />
    </template>
    <template v-else>
      <select
        class="gbs__select"
        :value="store.selectedBatchId"
        aria-label="选择毕设批次"
        @change="onSelect($event.target.value)"
      >
        <option v-if="store.needsExplicitSelect && !store.selectedBatchId" value="" disabled>请选择批次</option>
        <option v-for="b in store.availableBatches" :key="b.id" :value="String(b.id)">
          {{ b.batchName }}{{ b.status === 'RUNNING' ? '（进行中）' : '' }}{{ b.gradeYear ? ` · ${b.gradeYear}` : '' }}
        </option>
      </select>
      <StatusTag v-if="store.batchStatus === 'RUNNING'" type="processing" label="进行中" dot />
      <StatusTag v-else-if="store.batchStatus" type="default" :label="statusLabel" dot />
      <span v-if="store.gradeYear" class="gbs__meta">{{ store.gradeYear }}</span>
      <span v-if="runningCount > 1" class="gbs__meta">进行中 {{ runningCount }} 个</span>
      <span v-if="store.needsExplicitSelect && !store.selectedBatchId" class="gbs__text gbs__text--err">请明确选择当前工作批次</span>
      <slot />
    </template>
  </div>
</template>

<script>
/**
 * GraduationBatchStrip — 真实批次选择器，读写 Pinia graduationBatch + URL query.batchId。
 */
import { StatusTag } from '@/components/business'
import { useGraduationBatchStore } from '@/stores/graduationBatch'

export default {
  name: 'GraduationBatchStrip',
  components: { StatusTag },
  setup() {
    return { store: useGraduationBatchStore() }
  },
  computed: {
    runningCount() {
      return this.store.availableBatches.filter((b) => b.status === 'RUNNING').length
    },
    statusLabel() {
      const m = { DRAFT: '草稿', RUNNING: '进行中', CLOSED: '已关闭', ARCHIVED: '已归档' }
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
.gbs {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding: var(--space-2) var(--space-3);
  background: var(--gray-50, #f8fafc);
  border: 1px solid var(--border-light, #e2e8f0);
  border-radius: var(--radius-md, 8px);
  font-size: var(--font-size-sm, 13px);
}
.gbs__label {
  color: var(--text-tertiary, #64748b);
  flex: none;
}
.gbs__select {
  min-width: 220px;
  max-width: 420px;
  padding: 4px 8px;
  border: 1px solid var(--border-base, #cbd5e1);
  border-radius: 6px;
  background: #fff;
  font-size: inherit;
  color: var(--text-primary, #0f172a);
  font-weight: 600;
}
.gbs__meta {
  color: var(--text-secondary, #475569);
}
.gbs__text {
  color: var(--text-secondary, #475569);
}
.gbs__text--err {
  color: var(--danger, #dc2626);
}
.mp-link {
  border: none;
  background: none;
  color: var(--brand-primary, #2563eb);
  cursor: pointer;
  font-size: inherit;
  padding: 0;
}
</style>
