<template>
  <div class="app-section-header" :class="{ 'is-compact': compact }">
    <div class="app-section-header__main">
      <span v-if="index" class="app-section-header__index">{{ index }}</span>
      <div class="app-section-header__text">
        <h2 class="app-section-header__title">
          {{ title }}
          <slot name="title-extra" />
        </h2>
        <p v-if="subtitle" class="app-section-header__subtitle">{{ subtitle }}</p>
      </div>
    </div>
    <div v-if="$slots.extra" class="app-section-header__extra">
      <slot name="extra" />
    </div>
  </div>
</template>

<script>
export default {
  name: 'AppSectionHeader',
  props: {
    index: { type: String, default: '' },
    title: { type: String, required: true },
    subtitle: { type: String, default: '' },
    compact: { type: Boolean, default: false }
  }
}
</script>

<style scoped>
.app-section-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.app-section-header.is-compact {
  align-items: center;
}
.app-section-header__main {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  min-width: 0;
}
.app-section-header__index {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-md);
  background: var(--primary-50);
  color: var(--primary-600);
  font-size: 11px;
  font-weight: var(--font-weight-bold);
}
.app-section-header__title {
  margin: 0;
  color: var(--text-primary);
  font-size: var(--font-size-lg);
  font-weight: var(--font-weight-bold);
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.app-section-header__subtitle {
  margin: 2px 0 0;
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
}
.app-section-header__extra {
  flex-shrink: 0;
}
</style>
