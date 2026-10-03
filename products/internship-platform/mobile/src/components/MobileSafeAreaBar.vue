<template>
  <view class="mobile-safe-area-bar" :class="{ 'is-transparent': transparent }">
    <view class="mobile-safe-area-bar__content">
      <slot />
    </view>
  </view>
</template>

<script>
/**
 * MobileSafeAreaBar 底部安全区固定操作栏
 * 依据 V2.1 §4.4：所有移动端底部固定操作必须适配 safe-area，
 * 打卡、提交等底部主按钮必须放入本组件，禁止被全面屏/手势导航遮挡。
 * Props:
 *  - transparent: 是否透明背景（默认白底 + 上边框 + 上阴影）
 * Slots: default（放置底部按钮，按钮高度应 ≥ var(--touch-target-min) 44px）
 */
export default {
  name: 'MobileSafeAreaBar',
  props: {
    transparent: { type: Boolean, default: false }
  }
}
</script>

<style scoped>
.mobile-safe-area-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: var(--z-bar);
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
  box-shadow: var(--shadow-bar);
  /* 安全区适配（冻结验收点）：16px 基础内边距 + 系统安全区 */
  padding-bottom: constant(safe-area-inset-bottom); /* iOS < 11.2 兜底 */
  padding-bottom: calc(16px + env(safe-area-inset-bottom));
}
.mobile-safe-area-bar.is-transparent {
  background: transparent;
  border-top: none;
  box-shadow: none;
}
.mobile-safe-area-bar__content {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--page-padding-mobile) 0;
  min-height: var(--touch-target-min);
}
</style>
