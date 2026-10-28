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
 * DualPaneWorkspace — 岗位实习模块内部「连续处理双栏」布局。
 * 左：队列列表 + 筛选（aside / aside-foot 插槽，自带滚动）；
 * 右：当前记录完整详情与操作（默认插槽）。
 * 窄屏（<1100px）自动降级为上下堆叠，左栏限高滚动，不使用窄抽屉。
 * 本组件只做布局，不写业务，不发请求。
 */
export default {
  name: 'DualPaneWorkspace',
  props: {
    asideTitle: { type: String, default: '' },
    /** 左栏计数徽标（如待处理条数）；null 不显示 */
    asideCount: { type: [Number, String], default: null },
    asideWidth: { type: Number, default: 400 }
  }
}
</script>

<style scoped>
.dpw {
  display: grid;
  grid-template-columns: minmax(320px, var(--dpw-aside)) 1fr;
  gap: var(--space-5, 20px);
  align-items: start;
  min-height: 0;
}
.dpw__aside {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--bd, #e5e7eb);
  border-radius: 14px;
  background: linear-gradient(180deg, var(--card-bg, #fff), var(--fill-1, #fafbfc));
  box-shadow: 0 10px 24px rgba(15, 23, 42, .045);
  max-height: calc(100vh - 210px);
  min-height: 320px;
  overflow: hidden;
  position: sticky;
  top: 16px;
}
.dpw__aside-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--bd, #eef0f3);
  background: linear-gradient(100deg, var(--pri-bg, #eff6ff), transparent 65%);
  font-weight: 600;
  font-size: 13.5px;
  color: var(--t1, #111827);
}
.dpw__aside-count {
  display: inline-flex;
  align-items: center;
  height: 20px;
  padding: 0 8px;
  border-radius: 10px;
  background: var(--pri, #2563eb);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
}
.dpw__aside-body {
  flex: 1;
  overflow: auto;
  min-height: 0;
}
.dpw__aside-foot {
  border-top: 1px solid var(--bd, #eef0f3);
  padding: 8px 12px;
}
.dpw__main {
  min-width: 0;
  min-height: 320px;
  border-radius: 14px;
}
@media (max-width: 1100px) {
  .dpw {
    grid-template-columns: 1fr;
  }
  .dpw__aside {
    position: static;
    max-height: 42vh;
  }
}
</style>
