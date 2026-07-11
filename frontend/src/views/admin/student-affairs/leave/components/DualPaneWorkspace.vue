<template>
  <div class="dpw" :style="{ '--dpw-aside': asideWidth + 'px' }">
    <aside class="dpw__aside">
      <div v-if="asideTitle" class="dpw__aside-head">
        <span class="dpw__aside-title">{{ asideTitle }}</span>
        <span v-if="asideCount !== null" class="dpw__aside-count">{{ asideCount }}</span>
      </div>
      <div class="dpw__aside-body">
        <slot name="aside" />
      </div>
      <div v-if="$slots['aside-foot']" class="dpw__aside-foot">
        <slot name="aside-foot" />
      </div>
    </aside>
    <section class="dpw__main">
      <slot />
    </section>
  </div>
</template>

<script>
/**
 * DualPaneWorkspace — 学工「连续处理双栏」布局（对齐冻结交互形态基准）。
 * 左：队列列表 + 筛选（aside / aside-foot 插槽，自带滚动）；右：当前记录详情与操作（默认插槽）。
 * 窄屏（<1100px）自动降级为上下堆叠。本组件只做布局，不写业务，不发请求。
 */
export default {
  name: 'DualPaneWorkspace',
  props: {
    asideTitle: { type: String, default: '' },
    asideCount: { type: [Number, String], default: null },
    asideWidth: { type: Number, default: 380 }
  }
}
</script>

<style scoped>
.dpw {
  display: grid;
  grid-template-columns: minmax(300px, var(--dpw-aside)) 1fr;
  gap: var(--space-4, 16px);
  align-items: start;
  min-height: 0;
}
.dpw__aside {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-base, #e5e7eb);
  border-radius: 12px;
  background: var(--bg-card, #fff);
  max-height: calc(100vh - 220px);
  min-height: 320px;
  overflow: hidden;
  position: sticky;
  top: 12px;
}
.dpw__aside-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border-light, #eef0f3);
  font-weight: 600;
  font-size: 13.5px;
  color: var(--text-primary, #111827);
}
.dpw__aside-count {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 10px;
  background: var(--fill-2, #f3f4f6);
  color: var(--text-secondary, #4b5563);
  font-size: 12px;
  font-weight: 600;
}
.dpw__aside-body {
  flex: 1;
  overflow: auto;
  min-height: 0;
}
.dpw__aside-foot {
  border-top: 1px solid var(--border-light, #eef0f3);
  padding: 8px 12px;
}
.dpw__main {
  min-width: 0;
  min-height: 320px;
}
@media (max-width: 1100px) {
  .dpw {
    grid-template-columns: 1fr;
  }
  .dpw__aside {
    position: static;
    max-height: 46vh;
  }
}
</style>
