<template>
  <!-- 计数徽标：count 有值时显示数字，dot 显示小圆点 -->
  <span
    v-if="isCounter"
    class="app-badge app-badge--counter"
    :class="[`app-badge--${type}`, { 'app-badge--dot': dot }]"
  >
    <template v-if="!dot">{{ displayCount }}</template>
  </span>
  <!-- 默认：文字胶囊标签（向后兼容原用法） -->
  <span v-else class="app-badge" :class="`app-badge--${type}`">
    <slot />
  </span>
</template>

<script>
/**
 * AppBadge —
 *  1) 文字胶囊标签（默认）：<AppBadge type="success">已通过</AppBadge>
 *  2) 计数/红点徽标：<AppBadge :count="8" type="danger" /> 或 <AppBadge dot type="danger" />
 * count 超过 max 显示 "max+"；count<=0 且非 showZero 时不渲染数字（dot 除外）。
 */
export default {
  name: 'AppBadge',
  props: {
    type: {
      type: String,
      default: 'neutral',
      validator: (v) => ['success', 'warning', 'danger', 'info', 'neutral'].includes(v)
    },
    count: { type: Number, default: null },
    max: { type: Number, default: 99 },
    dot: { type: Boolean, default: false },
    showZero: { type: Boolean, default: false }
  },
  computed: {
    isCounter() {
      return this.dot || this.count !== null
    },
    displayCount() {
      const c = this.count || 0
      if (c <= 0 && !this.showZero) return ''
      return c > this.max ? `${this.max}+` : String(c)
    }
  }
}
</script>

<style scoped>
.app-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 20px;
  padding: 0 var(--space-2);
  border-radius: var(--radius-full);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-medium);
  line-height: 1.2;
}
.app-badge--success {
  background: var(--success-50);
  color: var(--success-700);
}
.app-badge--warning {
  background: var(--warning-50);
  color: var(--warning-700);
}
.app-badge--danger {
  background: var(--danger-50);
  color: var(--danger-700);
}
.app-badge--info {
  background: var(--info-50);
  color: var(--info-700);
}
.app-badge--neutral {
  background: var(--gray-100);
  color: var(--text-secondary);
}
/* 计数徽标 */
.app-badge--counter {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  color: #fff;
  font-weight: var(--font-weight-medium);
  line-height: 1;
}
.app-badge--counter.app-badge--success { background: var(--success-500); }
.app-badge--counter.app-badge--warning { background: var(--warning-500); }
.app-badge--counter.app-badge--danger { background: var(--danger-500); }
.app-badge--counter.app-badge--info { background: var(--info-500); }
.app-badge--counter.app-badge--neutral { background: var(--gray-400); }
.app-badge--dot {
  min-width: 0;
  width: 8px;
  height: 8px;
  padding: 0;
  border-radius: var(--radius-full);
}
</style>
