<template>
  <view class="sq card" v-if="currentItem">
    <view class="sq__head">
      <view class="flex-1">
        <text class="sq__title">{{ title }}</text>
        <text class="sq__progress">第 {{ currentIndex + 1 }} / {{ items.length }} 条</text>
      </view>
      <text class="sq__open" @click="$emit('open', currentItem)">查看对象</text>
    </view>

    <view class="sq__window" aria-label="连续处理窗口">
      <text
        v-for="entry in windowItems"
        :key="entry.index"
        class="sq__step"
        :class="{ 'is-current': entry.index === currentIndex, 'is-done': entry.index < currentIndex }"
      >{{ entry.index + 1 }}</text>
    </view>

    <MobileInlineAlert
      v-if="conflict"
      type="warning"
      title="对象已发生变化"
      description="连续处理已停止。请先刷新当前对象，以服务器最新状态为准。"
    />

    <view class="sq__body">
      <slot :item="currentItem" :index="currentIndex" :blocked="conflict || loading" />
    </view>

    <view class="sq__foot">
      <text class="sq__hint">单对象处理完成并回读成功后才进入下一条</text>
      <button
        v-if="actionLabel"
        class="btn btn-primary"
        :disabled="loading || conflict"
        @click="$emit('action', currentItem, null)"
      >{{ loading ? '处理中…' : actionLabel }}</button>
      <button
        v-else-if="allowManualNext"
        class="btn btn-ghost"
        :disabled="loading || conflict || currentIndex >= items.length - 1"
        @click="$emit('next')"
      >下一条</button>
    </view>
  </view>
</template>

<script>
const WINDOW_RADIUS = 2

export default {
  name: 'MobileSequentialQueue',
  props: {
    title: { type: String, default: '连续处理' },
    items: { type: Array, default: () => [] },
    currentIndex: { type: Number, default: 0 },
    loading: { type: Boolean, default: false },
    actionLabel: { type: String, default: '' },
    allowManualNext: { type: Boolean, default: false },
    conflict: { type: Boolean, default: false }
  },
  emits: ['open', 'action', 'next'],
  computed: {
    currentItem() {
      const index = Math.max(0, Math.min(Number(this.currentIndex) || 0, this.items.length - 1))
      return this.items[index] || null
    },
    windowItems() {
      if (!this.items.length) return []
      const center = Math.max(0, Math.min(Number(this.currentIndex) || 0, this.items.length - 1))
      let start = Math.max(0, center - WINDOW_RADIUS)
      let end = Math.min(this.items.length, center + WINDOW_RADIUS + 1)
      const desired = WINDOW_RADIUS * 2 + 1
      if (end - start < desired) {
        start = Math.max(0, end - desired)
        end = Math.min(this.items.length, start + desired)
      }
      return this.items.slice(start, end).map((item, offset) => ({ item, index: start + offset }))
    }
  }
}
</script>

<style scoped>
.sq { display: flex; flex-direction: column; gap: var(--space-3); border: 1px solid var(--teacher-500); }
.sq__head { display: flex; align-items: center; gap: var(--space-2); }
.sq__title { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.sq__progress { display: block; margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.sq__open { flex-shrink: 0; font-size: var(--font-size-sm); color: var(--teacher-700); }
.sq__window { display: flex; justify-content: center; gap: 6px; }
.sq__step { width: 26px; height: 26px; border-radius: var(--radius-full); display: flex; align-items: center; justify-content: center; background: var(--gray-100); color: var(--text-tertiary); font-size: var(--font-size-xs); }
.sq__step.is-current { background: var(--teacher-600); color: #fff; font-weight: var(--font-weight-semibold); }
.sq__step.is-done { background: var(--success-50); color: var(--success-700); }
.sq__body { min-width: 0; }
.sq__foot { display: flex; flex-direction: column; gap: var(--space-2); }
.sq__hint { font-size: 10px; color: var(--text-tertiary); text-align: center; }
</style>
