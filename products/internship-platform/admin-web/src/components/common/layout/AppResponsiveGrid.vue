<template>
  <div class="app-responsive-grid" :style="gridStyle">
    <slot />
  </div>
</template>

<script>
/**
 * AppResponsiveGrid — 响应式栅格（卡片墙 / 指标卡 / 表单双列，自动按容器宽度换行）。
 * Props:
 *  - minColWidth: 每列最小宽度(px)，容器变窄自动减少列数（默认 240）
 *  - cols: 固定列数（传了就用固定列，忽略 minColWidth）
 *  - gap: 间距，接受 token 名或 px（默认 var(--space-4)）
 * 纯布局，无业务。
 */
export default {
  name: 'AppResponsiveGrid',
  props: {
    minColWidth: { type: Number, default: 240 },
    cols: { type: Number, default: 0 },
    gap: { type: String, default: 'var(--space-4)' }
  },
  computed: {
    gridStyle() {
      const template = this.cols > 0
        ? `repeat(${this.cols}, minmax(0, 1fr))`
        : `repeat(auto-fill, minmax(min(${this.minColWidth}px, 100%), 1fr))`
      return { 'grid-template-columns': template, gap: this.gap }
    }
  }
}
</script>

<style scoped>
.app-responsive-grid {
  display: grid;
  min-width: 0;
}
</style>
