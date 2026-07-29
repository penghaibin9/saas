<template>
  <view class="aia" :class="`is-${normalizedType}`" role="alert">
    <view class="aia__body">
      <text v-if="title" class="aia__title">{{ title }}</text>
      <text v-if="description" class="aia__description">{{ description }}</text>
      <slot />
    </view>
    <text v-if="closable" class="aia__close" @click="$emit('close')">×</text>
  </view>
</template>

<script>
const TYPES = ['info', 'success', 'warning', 'danger']

export default {
  name: 'AppInlineAlert',
  emits: ['close'],
  props: {
    type: { type: String, default: 'info' },
    title: { type: String, default: '' },
    description: { type: String, default: '' },
    closable: { type: Boolean, default: false }
  },
  computed: {
    normalizedType() {
      const value = String(this.type || 'info').toLowerCase()
      return TYPES.includes(value) ? value : 'info'
    }
  }
}
</script>

<style scoped>
.aia {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  margin: var(--space-3) 0;
  padding: var(--space-3);
  border: 1px solid var(--info-100);
  border-radius: var(--radius-md);
  background: var(--info-50);
  color: var(--info-700);
  box-sizing: border-box;
}
.aia.is-success { border-color: var(--success-100); background: var(--success-50); color: var(--success-700); }
.aia.is-warning { border-color: var(--warning-100); background: var(--warning-50); color: var(--warning-700); }
.aia.is-danger { border-color: var(--danger-100); background: var(--danger-50); color: var(--danger-700); }
.aia__body { flex: 1; min-width: 0; }
.aia__title { display: block; margin-bottom: var(--space-1); font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); }
.aia__description { display: block; font-size: var(--font-size-sm); line-height: var(--line-height-base); }
.aia__close { min-width: var(--touch-target-min); min-height: var(--touch-target-min); margin: calc(var(--space-2) * -1); display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xl); }
</style>
