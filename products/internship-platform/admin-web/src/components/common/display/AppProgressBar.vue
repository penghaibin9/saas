<template>
  <div class="app-progress" :class="[`is-${size}`]">
    <div class="app-progress__track">
      <div
        class="app-progress__fill"
        :class="[`is-${resolvedStatus}`, { 'is-striped': striped }]"
        :style="{ width: clampedValue + '%' }"
        role="progressbar"
        :aria-valuenow="clampedValue"
        aria-valuemin="0"
        aria-valuemax="100"
      />
    </div>
    <span v-if="showText" class="app-progress__text" :class="`is-${resolvedStatus}`">
      <slot>{{ clampedValue }}%</slot>
    </span>
  </div>
</template>

<script>
/**
 * AppProgressBar — 线性进度条（导入进度、完成率、提交进度）。
 * Props: value(0-100) / status(auto|normal|success|warning|danger) / showText / striped / size(normal|compact)
 * status=auto 时：>=100 success，>=80 normal，>=40 warning，<40 danger（可被显式 status 覆盖）。
 */
export default {
  name: 'AppProgressBar',
  props: {
    value: { type: Number, default: 0 },
    status: { type: String, default: 'normal' },
    showText: { type: Boolean, default: true },
    striped: { type: Boolean, default: false },
    size: { type: String, default: 'normal', validator: (v) => ['normal', 'compact'].includes(v) }
  },
  computed: {
    clampedValue() {
      return Math.min(100, Math.max(0, Math.round(this.value)))
    },
    resolvedStatus() {
      if (this.status !== 'auto') return this.status
      const v = this.clampedValue
      if (v >= 100) return 'success'
      if (v >= 80) return 'normal'
      if (v >= 40) return 'warning'
      return 'danger'
    }
  }
}
</script>

<style scoped>
.app-progress {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.app-progress__track {
  flex: 1;
  height: 8px;
  border-radius: var(--radius-full);
  background: var(--gray-100);
  overflow: hidden;
}
.app-progress.is-compact .app-progress__track { height: 6px; }
.app-progress__fill {
  height: 100%;
  border-radius: var(--radius-full);
  transition: width 0.3s ease;
  background: var(--primary-500);
}
.app-progress__fill.is-success { background: var(--success-500); }
.app-progress__fill.is-warning { background: var(--warning-500); }
.app-progress__fill.is-danger { background: var(--danger-500); }
.app-progress__fill.is-striped {
  background-image: linear-gradient(45deg, rgba(255,255,255,0.25) 25%, transparent 25%, transparent 50%, rgba(255,255,255,0.25) 50%, rgba(255,255,255,0.25) 75%, transparent 75%, transparent);
  background-size: 16px 16px;
  animation: ap-move 0.8s linear infinite;
}
@keyframes ap-move { to { background-position: 16px 0; } }
.app-progress__text {
  flex-shrink: 0;
  min-width: 38px;
  text-align: right;
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
.app-progress__text.is-success { color: var(--success-600); }
.app-progress__text.is-warning { color: var(--warning-700); }
.app-progress__text.is-danger { color: var(--danger-600); }
</style>
