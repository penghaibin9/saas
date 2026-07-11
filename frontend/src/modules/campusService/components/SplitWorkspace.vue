<template>
  <div class="sw" :class="{ 'is-narrow': narrow }">
    <!-- 左：筛选结果列表（窄屏且已选中时隐藏，进入全屏详情模式，不降级为窄抽屉） -->
    <aside v-show="!narrow || !hasSelection" class="sw__left">
      <slot name="left" :narrow="narrow" />
    </aside>
    <!-- 右：完整详情工作区 -->
    <section v-show="!narrow || hasSelection" class="sw__right">
      <slot name="detail" :narrow="narrow" />
    </section>
  </div>
</template>

<script>
/**
 * SplitWorkspace — 学工（在校服务承接页）「列表＋详情双栏」布局壳。
 * 仅做布局与窄屏降级（<1100px 单列：未选中显示列表，选中后显示全屏详情），
 * 业务逻辑、权限、数据全部由使用方提供；不修改任何公共组件全局行为。
 */
export default {
  name: 'SplitWorkspace',
  props: {
    /** 右栏是否有选中记录（窄屏模式下决定显示列表还是全屏详情） */
    hasSelection: { type: Boolean, default: false }
  },
  data() {
    return { narrow: false, mq: null }
  },
  mounted() {
    this.mq = window.matchMedia('(max-width: 1100px)')
    this.narrow = this.mq.matches
    this.onMq = (e) => {
      this.narrow = e.matches
    }
    this.mq.addEventListener ? this.mq.addEventListener('change', this.onMq) : this.mq.addListener(this.onMq)
  },
  beforeUnmount() {
    if (!this.mq) return
    this.mq.removeEventListener ? this.mq.removeEventListener('change', this.onMq) : this.mq.removeListener(this.onMq)
  }
}
</script>

<style scoped>
.sw {
  display: grid;
  grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
  gap: var(--space-4);
  align-items: start;
}
.sw__left {
  min-width: 0;
}
.sw__right {
  min-width: 0;
}
.sw.is-narrow {
  grid-template-columns: minmax(0, 1fr);
}
</style>
