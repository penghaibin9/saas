<template>
  <fieldset class="app-form-section" :class="{ 'is-compact': compact }" :disabled="disabled">
    <legend v-if="title" class="app-form-section__legend">
      <span class="app-form-section__bar" aria-hidden="true" />
      <span class="app-form-section__title">{{ title }}</span>
      <span v-if="description" class="app-form-section__desc">{{ description }}</span>
      <span v-if="$slots.extra" class="app-form-section__extra"><slot name="extra" /></span>
    </legend>
    <div class="app-form-section__body">
      <slot />
    </div>
  </fieldset>
</template>

<script>
/**
 * AppFormSection — 表单分组（长表单按业务分段：基本信息 / 联系方式 / 附件等）。
 * disabled 会通过原生 fieldset 一次性禁用整段内的表单控件。
 * Props: title / description / compact / disabled。Slots: extra（标题右侧）/ default（字段）
 */
export default {
  name: 'AppFormSection',
  props: {
    title: { type: String, default: '' },
    description: { type: String, default: '' },
    compact: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false }
  }
}
</script>

<style scoped>
.app-form-section {
  border: none;
  margin: 0 0 var(--space-5);
  padding: 0;
  min-width: 0;
}
.app-form-section__legend {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  width: 100%;
  padding: 0;
  margin-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-light);
  padding-bottom: var(--space-2);
}
.is-compact .app-form-section__legend { margin-bottom: var(--space-3); }
.app-form-section__bar {
  width: 3px;
  height: 14px;
  border-radius: var(--radius-full);
  background: var(--primary-600);
  flex-shrink: 0;
}
.app-form-section__title {
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}
.app-form-section__desc {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.app-form-section__extra { margin-left: auto; }
</style>
