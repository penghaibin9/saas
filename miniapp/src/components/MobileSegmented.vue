<template>
  <scroll-view class="mseg" scroll-x :show-scrollbar="false">
    <view class="mseg__inner">
      <view
        v-for="item in items"
        :key="item.key"
        class="mseg__item"
        :class="{ 'is-active': item.key === modelValue }"
        @click="$emit('update:modelValue', item.key)"
      >
        <text>{{ item.label }}</text>
        <text v-if="item.badge" class="mseg__badge">{{ item.badge }}</text>
      </view>
    </view>
  </scroll-view>
</template>

<script>
/** MobileSegmented 横向分段/标签切换（支持角标、可横滑） */
export default {
  name: 'MobileSegmented',
  props: {
    items: { type: Array, default: () => [] }, // [{key,label,badge}]
    modelValue: { type: String, default: '' }
  },
  emits: ['update:modelValue']
}
</script>

<style scoped>
.mseg { width: 100%; white-space: nowrap; }
.mseg__inner { display: inline-flex; gap: var(--space-2); padding: 2px 0; }
.mseg__item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 7px var(--space-4);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  border: 1px solid var(--border-base);
}
.mseg__item.is-active {
  background: var(--brand-primary);
  color: #fff;
  border-color: var(--brand-primary);
}
.mseg__badge {
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: var(--radius-full);
  background: var(--danger-500);
  color: #fff;
  font-size: 10px;
  line-height: 16px;
  text-align: center;
}
.mseg__item.is-active .mseg__badge { background: rgba(255,255,255,0.28); }
</style>
