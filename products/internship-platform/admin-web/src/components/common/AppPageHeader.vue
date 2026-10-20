<template>
  <div class="app-page-header">
    <div class="app-page-header__main">
      <button v-if="showBack" type="button" class="app-page-header__back" @click="$emit('back')">
        ←
      </button>
      <div class="app-page-header__text">
        <div class="app-page-header__title-row">
          <h1 class="app-page-header__title">{{ title }}</h1>
          <slot name="tags" />
        </div>
        <p v-if="description" class="app-page-header__desc">{{ description }}</p>
      </div>
    </div>
    <div v-if="$slots.actions" class="app-page-header__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script>
/**
 * AppPageHeader 页面标题头
 * Props: title、description、showBack
 * Emits: back
 * Slots: tags（标题旁状态标签区）、actions（右侧主操作按钮区）
 */
export default {
  name: 'AppPageHeader',
  props: {
    title: { type: String, required: true },
    description: { type: String, default: '' },
    showBack: { type: Boolean, default: false }
  },
  emits: ['back']
}
</script>

<style scoped>
.app-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}
.app-page-header__main {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  min-width: 0;
}
.app-page-header__back {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-base);
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-lg);
  cursor: pointer;
  flex-shrink: 0;
}
.app-page-header__back:hover {
  border-color: var(--primary-500);
  color: var(--primary-600);
}
.app-page-header__title-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}
.app-page-header__title {
  margin: 0;
  font-size: var(--font-size-3xl);
  font-weight: var(--font-weight-semibold);
  color: var(--gray-900);
  line-height: 1.3;
}
.app-page-header__desc {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-base);
  color: var(--text-secondary);
}
.app-page-header__actions {
  display: flex;
  gap: var(--space-3);
  flex-shrink: 0;
}
</style>
