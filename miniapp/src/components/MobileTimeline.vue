<template>
  <view class="mtl">
    <view
      v-for="(node, idx) in nodes"
      :key="node.id || idx"
      class="mtl__row"
      :class="{ 'is-current': node.current }"
    >
      <view class="mtl__rail">
        <view class="mtl__dot" :class="dotClass(node)" />
        <view v-if="idx < nodes.length - 1" class="mtl__line" :class="{ 'is-done': isDone(node) }" />
      </view>
      <view class="mtl__body">
        <view class="mtl__head">
          <text class="mtl__title">{{ node.title }}</text>
          <MobileStatusTag v-if="node.status" :status="node.status" />
        </view>
        <text v-if="node.desc" class="mtl__desc">{{ node.desc }}</text>
        <text v-if="node.time || node.deadline" class="mtl__time">
          {{ node.time || ('截止 ' + node.deadline) }}
        </text>
        <slot name="extra" :node="node" />
      </view>
    </view>
  </view>
</template>

<script>
/**
 * MobileTimeline 纵向时间线（迎新步骤 / 毕设节点 / 实习流程）
 * node: { id, title, status, desc, time, deadline, current }
 */
import MobileStatusTag from './MobileStatusTag.vue'
const DONE = ['COMPLETED', 'APPROVED', 'PUBLISHED', 'ARCHIVED']
export default {
  name: 'MobileTimeline',
  components: { MobileStatusTag },
  props: {
    nodes: { type: Array, default: () => [] }
  },
  methods: {
    isDone(node) {
      return DONE.includes(node.status)
    },
    dotClass(node) {
      if (this.isDone(node)) return 'is-done'
      if (node.current) return 'is-current'
      if (node.status === 'OVERDUE') return 'is-overdue'
      return 'is-pending'
    }
  }
}
</script>

<style scoped>
.mtl { display: flex; flex-direction: column; }
.mtl__row { display: flex; gap: var(--space-3); }
.mtl__rail { width: 16px; display: flex; flex-direction: column; align-items: center; }
.mtl__dot {
  width: 12px; height: 12px; border-radius: var(--radius-full);
  margin-top: 3px; flex-shrink: 0; border: 2px solid var(--gray-300); background: var(--bg-card);
}
.mtl__dot.is-done { background: var(--success-500); border-color: var(--success-500); }
.mtl__dot.is-current { background: var(--brand-primary); border-color: var(--brand-primary); box-shadow: 0 0 0 4px var(--primary-50); }
.mtl__dot.is-overdue { background: var(--danger-500); border-color: var(--danger-500); }
.mtl__dot.is-pending { background: var(--bg-card); border-color: var(--gray-300); }
.mtl__line { flex: 1; width: 2px; background: var(--border-base); margin: 2px 0; min-height: 14px; }
.mtl__line.is-done { background: var(--success-500); }
.mtl__body { flex: 1; min-width: 0; padding-bottom: var(--space-4); }
.mtl__head { display: flex; align-items: center; gap: var(--space-2); }
.mtl__title { font-size: var(--font-size-md); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.mtl__desc { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 2px; }
.mtl__time { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.mtl__row.is-current .mtl__title { color: var(--brand-primary); }
</style>
