<template>
  <view class="mobile-action-card" :class="{ 'is-disabled': disabled }" @click="onClick">
    <view v-if="$slots.icon || icon" class="mac-icon">
      <slot name="icon"><text>{{ icon }}</text></slot>
    </view>
    <view class="mac-body">
      <view class="mac-title-row">
        <text class="mac-title">{{ title }}</text>
        <MobileStatusTag v-if="status" :status="status" />
      </view>
      <text v-if="description" class="mac-desc">{{ description }}</text>
    </view>
    <view class="mac-right">
      <slot name="action">
        <button v-if="actionText" class="mac-btn" :disabled="disabled" @click.stop="onAction">
          {{ actionText }}
        </button>
        <text v-else class="mac-arrow">›</text>
      </slot>
    </view>
  </view>
</template>

<script>
import MobileStatusTag from './MobileStatusTag.vue'

/**
 * MobileActionCard 移动端行动卡片（服务入口 / 阶段主任务 / 快捷操作）
 * Props: title、description、icon（文本图标）、status（状态码）、
 *        actionText（主按钮文案，如“去打卡”“提交材料”）、disabled
 * Emits: click（点整卡）、action（点主按钮）
 * Slots: icon、action
 */
export default {
  name: 'MobileActionCard',
  components: { MobileStatusTag },
  props: {
    title: { type: String, required: true },
    description: { type: String, default: '' },
    icon: { type: String, default: '' },
    status: { type: String, default: '' },
    actionText: { type: String, default: '' },
    disabled: { type: Boolean, default: false }
  },
  emits: ['click', 'action'],
  methods: {
    onClick() {
      if (!this.disabled) this.$emit('click')
    },
    onAction() {
      if (!this.disabled) this.$emit('action')
    }
  }
}
</script>

<style scoped>
.mobile-action-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--card-padding-mobile);
  box-shadow: var(--shadow-card);
  min-height: var(--touch-target-min);
}
.mobile-action-card.is-disabled { opacity: 0.55; }
.mac-icon {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: var(--radius-md);
  background: var(--primary-50);
  color: var(--primary-600);
  font-size: var(--font-size-xl);
  display: flex;
  align-items: center;
  justify-content: center;
}
.mac-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: var(--space-1); }
.mac-title-row { display: flex; align-items: center; gap: var(--space-2); }
.mac-title { font-size: var(--font-size-md); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.mac-desc {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mac-right { flex-shrink: 0; }
.mac-btn {
  min-height: 36px;
  line-height: 36px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-md);
  border: none;
  background: var(--primary-600);
  color: var(--text-inverse);
  font-size: var(--font-size-base);
}
.mac-btn[disabled] { background: var(--gray-300); }
.mac-arrow { font-size: var(--font-size-2xl); color: var(--text-tertiary); }
</style>
