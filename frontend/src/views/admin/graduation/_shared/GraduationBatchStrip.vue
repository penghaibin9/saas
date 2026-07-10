<template>
  <div class="gbs">
    <span class="gbs__label">当前批次</span>
    <template v-if="state === 'loading'">
      <span class="gbs__text">正在读取…</span>
    </template>
    <template v-else-if="state === 'ready'">
      <span class="gbs__name">{{ batch.batchName }}</span>
      <StatusTag type="processing" label="进行中" dot />
      <span v-if="batch.gradeYear" class="gbs__meta">{{ batch.gradeYear }} 届</span>
      <span v-if="extraRunning > 0" class="gbs__meta">另有 {{ extraRunning }} 个进行中批次</span>
      <slot />
    </template>
    <template v-else-if="state === 'empty'">
      <span class="gbs__text">暂无进行中的毕设批次，请先创建并启用毕设批次</span>
      <button type="button" class="mp-link" @click="$router.push('/admin/graduation/batches?panel=list')">去毕设批次 →</button>
      <slot />
    </template>
    <template v-else>
      <span class="gbs__text gbs__text--err">批次信息读取失败</span>
      <button type="button" class="mp-link" @click="reload">重试</button>
    </template>
  </div>
</template>

<script>
/**
 * GraduationBatchStrip — 毕设中心各二级模块落点页顶部的「当前批次」上下文条。
 * 数据来源：graduationBatchApi.getBatches({ status: 'RUNNING' })，真实后端，不 mock。
 * 模块级缓存一次请求，同一次会话内各落点页共享，避免每页重复打接口；「重试」会强制刷新。
 * 插槽：页面可追加自己的真实状态摘要（如待审阅数），本组件不造任何假指标。
 */
import { StatusTag } from '@/components/business'
import { graduationBatchApi } from '@/modules/graduation/api/graduation-batch.api'

let runningCache = null

export default {
  name: 'GraduationBatchStrip',
  components: { StatusTag },
  data() {
    return { state: 'loading', batch: null, extraRunning: 0 }
  },
  created() {
    this.load()
  },
  methods: {
    async load(force = false) {
      this.state = 'loading'
      if (force || !runningCache) {
        runningCache = graduationBatchApi.getBatches({ status: 'RUNNING', page: 1, pageSize: 1 })
      }
      const res = await runningCache
      if (res.code !== 0) {
        runningCache = null
        this.state = 'error'
        return
      }
      const list = (res.data && res.data.list) || []
      if (!list.length) {
        this.state = 'empty'
        this.batch = null
        this.extraRunning = 0
        return
      }
      this.batch = list[0]
      this.extraRunning = Math.max(0, (res.data.total || 1) - 1)
      this.state = 'ready'
    },
    reload() {
      this.load(true)
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
.gbs__name {
  font-weight: var(--font-weight-semibold, 600);
  color: var(--text-primary, #0f172a);
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
