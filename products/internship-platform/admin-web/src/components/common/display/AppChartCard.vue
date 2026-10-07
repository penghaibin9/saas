<template>
  <section class="app-chart-card">
    <header class="app-chart-card__head">
      <div class="app-chart-card__titles">
        <h3 class="app-chart-card__title">{{ title }}</h3>
        <p v-if="subtitle" class="app-chart-card__subtitle">{{ subtitle }}</p>
      </div>
      <div class="app-chart-card__toolbar"><slot name="toolbar" /></div>
    </header>

    <div class="app-chart-card__body" :style="{ minHeight: minHeight + 'px' }">
      <div v-if="loading" class="app-chart-card__state">
        <span class="app-chart-card__spinner" /> 加载图表…
      </div>
      <div v-else-if="empty" class="app-chart-card__state is-empty">{{ emptyText }}</div>
      <slot v-else />
    </div>

    <footer v-if="$slots.footer" class="app-chart-card__footer"><slot name="footer" /></footer>
  </section>
</template>

<script>
/**
 * AppChartCard —（partial 部分完成）图表卡片容器。
 *
 * ⚠️ 现状：不强绑任何图表库（避免引入重依赖）。本组件只提供统一的「标题 + 工具条 + 图表槽 +
 *    加载/空状态 + 页脚」外壳；真实图表由调用方在默认插槽内渲染（项目已有图表库时接入，否则先留空）。
 *    未接图表前标 partial，不能当成熟图表组件对外宣称。
 *
 * Props: title / subtitle / loading / empty / emptyText / minHeight(px)
 * Slots: toolbar（右上，如时间范围切换）/ default（图表本体）/ footer（图例/说明）
 */
export default {
  name: 'AppChartCard',
  props: {
    title: { type: String, default: '' },
    subtitle: { type: String, default: '' },
    loading: { type: Boolean, default: false },
    empty: { type: Boolean, default: false },
    emptyText: { type: String, default: '暂无图表数据' },
    minHeight: { type: Number, default: 220 }
  }
}
</script>

<style scoped>
.app-chart-card {
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-card);
  overflow: hidden;
}
.app-chart-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5);
  border-bottom: 1px solid var(--border-light);
}
.app-chart-card__title { margin: 0; font-size: var(--font-size-md); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.app-chart-card__subtitle { margin: 2px 0 0; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.app-chart-card__toolbar { display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0; }
.app-chart-card__body { padding: var(--space-5); position: relative; }
.app-chart-card__state {
  display: flex; align-items: center; justify-content: center; gap: var(--space-2);
  height: 100%; min-height: inherit; color: var(--text-tertiary); font-size: var(--font-size-sm);
}
.app-chart-card__state.is-empty { border: 1px dashed var(--border-base); border-radius: var(--radius-base); background: var(--bg-subtle); }
.app-chart-card__spinner {
  width: 16px; height: 16px; border: 2px solid var(--primary-100); border-top-color: var(--primary-500);
  border-radius: var(--radius-full); animation: acc-spin 0.7s linear infinite;
}
@keyframes acc-spin { to { transform: rotate(360deg); } }
.app-chart-card__footer { padding: var(--space-3) var(--space-5); border-top: 1px solid var(--border-light); background: var(--bg-subtle); }
</style>
