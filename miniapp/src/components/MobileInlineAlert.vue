<template>
  <view class="mobile-inline-alert" :class="`is-${type}`">
    <text class="mia-icon">{{ icon }}</text>
    <view class="mia-content">
      <text v-if="title" class="mia-title">{{ title }}</text>
      <view class="mia-desc">
        <slot><text>{{ description }}</text></slot>
      </view>
      <view v-if="$slots.actions" class="mia-actions">
        <slot name="actions" />
      </view>
    </view>
    <text v-if="closable" class="mia-close" @click="$emit('close')">×</text>
  </view>
</template>

<script>
/**
 * MobileInlineAlert 移动端行内提示
 * 依据 V2.1 §11.3/§11.4：退回提示不可关闭（closable 默认 false），
 * 首屏必须直接展示老师意见，不允许让学生自己找。
 * Props: type: info|success|warning|danger、title、description、closable
 * Emits: close
 * Slots: default、actions（如“查看原因 / 去修改”按钮）
 */
const ICONS = { info: 'ℹ', success: '✓', warning: '!', danger: '!' }

export default {
  name: 'MobileInlineAlert',
  props: {
    type: {
      type: String,
      default: 'info',
      validator: (v) => ['info', 'success', 'warning', 'danger'].includes(v)
    },
    title: { type: String, default: '' },
    description: { type: String, default: '' },
    closable: { type: Boolean, default: false }
  },
  emits: ['close'],
  computed: {
    icon() {
      return ICONS[this.type]
    }
  }
}
</script>

<style scoped>
.mobile-inline-alert {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3) var(--card-padding-mobile);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  line-height: var(--line-height-base);
}
.is-info { background: var(--info-50); color: var(--info-700); }
.is-success { background: var(--success-50); color: var(--success-700); }
.is-warning { background: var(--warning-50); color: var(--warning-700); }
.is-danger { background: var(--danger-50); color: var(--danger-700); }
.mia-icon {
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  color: var(--text-inverse);
  font-size: var(--font-size-xs);
  text-align: center;
  line-height: 18px;
  flex-shrink: 0;
  margin-top: 2px;
}
.is-info .mia-icon { background: var(--info-500); }
.is-success .mia-icon { background: var(--success-500); }
.is-warning .mia-icon { background: var(--warning-500); }
.is-danger .mia-icon { background: var(--danger-500); }
.mia-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: var(--space-1); }
.mia-title { font-weight: var(--font-weight-medium); }
.mia-desc { color: var(--text-secondary); font-size: var(--font-size-sm); }
.mia-actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.mia-close { font-size: var(--font-size-lg); color: var(--text-tertiary); padding: 0 var(--space-1); }
</style>
