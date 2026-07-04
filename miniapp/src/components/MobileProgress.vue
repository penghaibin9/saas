<template>
  <view class="mprog">
    <view class="mprog__track">
      <view class="mprog__fill" :class="`is-${tone}`" :style="{ width: percent + '%' }" />
    </view>
    <text v-if="showText" class="mprog__text">{{ percent }}%</text>
  </view>
</template>

<script>
/** MobileProgress 进度条。tone: brand|success|warning|danger */
export default {
  name: 'MobileProgress',
  props: {
    value: { type: Number, default: 0 },
    tone: { type: String, default: 'brand' },
    showText: { type: Boolean, default: true }
  },
  computed: {
    percent() {
      return Math.max(0, Math.min(100, Math.round(this.value || 0)))
    }
  }
}
</script>

<style scoped>
.mprog { display: flex; align-items: center; gap: var(--space-2); }
.mprog__track { flex: 1; height: 8px; border-radius: var(--radius-full); background: var(--gray-100); overflow: hidden; }
.mprog__fill { height: 100%; border-radius: var(--radius-full); transition: width .3s; }
.mprog__fill.is-brand { background: var(--brand-primary); }
.mprog__fill.is-success { background: var(--success-500); }
.mprog__fill.is-warning { background: var(--warning-500); }
.mprog__fill.is-danger { background: var(--danger-500); }
.mprog__text { font-size: var(--font-size-xs); color: var(--text-secondary); min-width: 34px; text-align: right; }
</style>
