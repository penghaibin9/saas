<template>
  <section class="app-section-card" :class="{ 'is-compact': compact, 'is-flat': flat }">
    <header v-if="title || $slots.header || $slots['header-extra']" class="app-section-card__head">
      <div class="app-section-card__head-main">
        <span v-if="index" class="app-section-card__index">{{ index }}</span>
        <div class="app-section-card__titles">
          <h3 class="app-section-card__title">
            {{ title }}
            <AppHelpTooltip v-if="help" :content="help" />
          </h3>
          <p v-if="subtitle" class="app-section-card__subtitle">{{ subtitle }}</p>
        </div>
        <slot name="header" />
      </div>
      <div v-if="$slots['header-extra'] || collapsible" class="app-section-card__head-extra">
        <slot name="header-extra" />
        <button
          v-if="collapsible"
          type="button"
          class="app-section-card__toggle"
          :aria-expanded="!isCollapsed"
          :aria-label="isCollapsed ? '展开' : '收起'"
          @click="toggle"
        >{{ isCollapsed ? '展开 ▾' : '收起 ▴' }}</button>
      </div>
    </header>

    <div v-show="!isCollapsed" class="app-section-card__body" :class="{ 'is-nopad': noPadding }">
      <slot />
    </div>

    <footer v-if="$slots.footer && !isCollapsed" class="app-section-card__footer">
      <slot name="footer" />
    </footer>
  </section>
</template>

<script>
/**
 * AppSectionCard — 页面内区块卡片（标题 + 内容 + 可选页脚，商用后台标准区块）。
 * Props:
 *  - title / subtitle / index(序号徽标) / help(标题旁帮助气泡)
 *  - compact(紧凑密度) / flat(无边框阴影) / noPadding(内容区去内边距，放表格用)
 *  - collapsible(可折叠) / defaultCollapsed
 * Slots: header(标题右侧内联) / header-extra(右上操作区) / default(内容) / footer(页脚)
 * Emits: toggle(collapsed:boolean)
 */
import AppHelpTooltip from '../AppHelpTooltip.vue'

export default {
  name: 'AppSectionCard',
  components: { AppHelpTooltip },
  props: {
    title: { type: String, default: '' },
    subtitle: { type: String, default: '' },
    index: { type: String, default: '' },
    help: { type: String, default: '' },
    compact: { type: Boolean, default: false },
    flat: { type: Boolean, default: false },
    noPadding: { type: Boolean, default: false },
    collapsible: { type: Boolean, default: false },
    defaultCollapsed: { type: Boolean, default: false }
  },
  emits: ['toggle'],
  data() {
    return { isCollapsed: this.defaultCollapsed }
  },
  methods: {
    toggle() {
      this.isCollapsed = !this.isCollapsed
      this.$emit('toggle', this.isCollapsed)
    }
  }
}
</script>

<style scoped>
.app-section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  min-width: 0;
}
.app-section-card.is-flat {
  border-color: transparent;
  box-shadow: none;
  background: transparent;
}
.app-section-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}
.is-compact .app-section-card__head {
  padding: var(--space-3) var(--space-4);
}
.app-section-card__head-main {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  min-width: 0;
}
.app-section-card__index {
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-base);
  background: var(--primary-50);
  color: var(--primary-600);
  font-size: 11px;
  font-weight: var(--font-weight-bold);
}
.app-section-card__title {
  margin: 0;
  font-size: var(--font-size-md);
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.app-section-card__subtitle {
  margin: 2px 0 0;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.app-section-card__head-extra {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.app-section-card__toggle {
  border: none;
  background: none;
  color: var(--text-link);
  cursor: pointer;
  font-size: var(--font-size-xs);
}
.app-section-card__body {
  padding: var(--space-5);
}
.is-compact .app-section-card__body {
  padding: var(--space-4);
}
.app-section-card__body.is-nopad {
  padding: 0;
}
.app-section-card__footer {
  padding: var(--space-3) var(--space-5);
  border-top: 1px solid var(--border-light);
  background: var(--bg-subtle);
  border-radius: 0 0 var(--radius-md) var(--radius-md);
}
</style>
