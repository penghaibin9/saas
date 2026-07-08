<template>
  <ol class="app-wf-timeline" :class="{ 'is-horizontal': horizontal }">
    <li
      v-for="(n, i) in nodes"
      :key="n.key || i"
      class="app-wf-timeline__node"
      :class="`is-${stateOf(n)}`"
    >
      <span class="app-wf-timeline__marker">
        <span class="app-wf-timeline__marker-inner">{{ markerOf(n, i) }}</span>
      </span>
      <div class="app-wf-timeline__content">
        <div class="app-wf-timeline__title-row">
          <span class="app-wf-timeline__name">{{ n.name || n.label }}</span>
          <span v-if="n.result" class="app-wf-timeline__result" :class="`is-${stateOf(n)}`">{{ n.result }}</span>
        </div>
        <div v-if="n.handler || n.at" class="app-wf-timeline__meta">
          <template v-if="n.handler">{{ n.handler }}</template>
          <template v-if="n.at"> · {{ n.at }}</template>
        </div>
        <div v-if="n.comment" class="app-wf-timeline__comment">{{ n.comment }}</div>
      </div>
    </li>
  </ol>
</template>

<script>
/**
 * AppWorkflowTimeline — 审批流 / 业务流转时间线（比 AppStepBar 更适合“审批历史+当前节点”）。
 * Props:
 *  - nodes: [{ key, name/label, state?, result?, handler?, at?, comment? }]
 *      state: done|current|pending|rejected|returned（缺省按位置推断需配合 currentIndex）
 *  - currentIndex: 当前进行中的节点下标（未显式给 state 时用它推断 done/current/pending）
 *  - horizontal: 横向展示（默认纵向）
 * 纯展示组件；真实流转由后端审批引擎驱动。
 */
export default {
  name: 'AppWorkflowTimeline',
  props: {
    nodes: { type: Array, default: () => [] },
    currentIndex: { type: Number, default: -1 },
    horizontal: { type: Boolean, default: false }
  },
  methods: {
    stateOf(n) {
      if (n.state) return n.state
      const i = this.nodes.indexOf(n)
      if (this.currentIndex < 0) return 'pending'
      if (i < this.currentIndex) return 'done'
      if (i === this.currentIndex) return 'current'
      return 'pending'
    },
    markerOf(n, i) {
      const s = this.stateOf(n)
      if (s === 'done') return '✓'
      if (s === 'rejected') return '✕'
      if (s === 'returned') return '↩'
      return i + 1
    }
  }
}
</script>

<style scoped>
.app-wf-timeline {
  list-style: none;
  margin: 0;
  padding: 0;
}
.app-wf-timeline__node {
  position: relative;
  display: flex;
  gap: var(--space-3);
  padding-bottom: var(--space-4);
}
.app-wf-timeline__node:not(:last-child)::before {
  content: '';
  position: absolute;
  left: 11px;
  top: 24px;
  bottom: 0;
  width: 2px;
  background: var(--border-light);
}
.app-wf-timeline__node.is-done:not(:last-child)::before { background: var(--success-500); }
.app-wf-timeline__marker {
  position: relative;
  z-index: 1;
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gray-100);
  color: var(--text-tertiary);
  font-size: var(--font-size-xs);
  border: 2px solid var(--border-base);
}
.app-wf-timeline__marker-inner { line-height: 1; }
.app-wf-timeline__node.is-done .app-wf-timeline__marker {
  background: var(--success-500); color: #fff; border-color: var(--success-500);
}
.app-wf-timeline__node.is-current .app-wf-timeline__marker {
  background: var(--primary-600); color: #fff; border-color: var(--primary-600);
  box-shadow: 0 0 0 4px var(--primary-100);
}
.app-wf-timeline__node.is-rejected .app-wf-timeline__marker {
  background: var(--danger-500); color: #fff; border-color: var(--danger-500);
}
.app-wf-timeline__node.is-returned .app-wf-timeline__marker {
  background: var(--warning-500); color: #fff; border-color: var(--warning-500);
}
.app-wf-timeline__content { flex: 1; min-width: 0; padding-top: 2px; }
.app-wf-timeline__title-row { display: flex; align-items: center; gap: var(--space-2); }
.app-wf-timeline__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.app-wf-timeline__result { font-size: var(--font-size-xs); }
.app-wf-timeline__result.is-done { color: var(--success-700); }
.app-wf-timeline__result.is-rejected { color: var(--danger-600); }
.app-wf-timeline__result.is-returned { color: var(--warning-700); }
.app-wf-timeline__result.is-current { color: var(--primary-700); }
.app-wf-timeline__meta { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.app-wf-timeline__comment { font-size: var(--font-size-xs); color: var(--text-secondary); margin-top: var(--space-1); }

/* 横向 */
.app-wf-timeline.is-horizontal {
  display: flex;
  gap: 0;
}
.app-wf-timeline.is-horizontal .app-wf-timeline__node {
  flex-direction: column;
  align-items: center;
  flex: 1;
  text-align: center;
  padding-bottom: 0;
}
.app-wf-timeline.is-horizontal .app-wf-timeline__node:not(:last-child)::before {
  left: 50%;
  top: 11px;
  bottom: auto;
  right: -50%;
  width: auto;
  height: 2px;
}
.app-wf-timeline.is-horizontal .app-wf-timeline__content { padding-top: var(--space-2); }
</style>
