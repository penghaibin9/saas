<template>
  <AppCard class="wf-tpl-card" hoverable @click="$emit('view', template)">
    <div class="wf-tpl-card__head">
      <div class="wf-tpl-card__titles">
        <span class="wf-tpl-card__name">{{ template.templateName }}</span>
        <code class="wf-tpl-card__code">{{ template.templateCode }} · v{{ template.version }}</code>
      </div>
      <AppBadge :type="statusType">{{ statusText }}</AppBadge>
    </div>
    <div class="wf-tpl-card__meta">
      <AppBadge type="info">{{ moduleLabel }}</AppBadge>
      <span class="wf-tpl-card__meta-item">节点 {{ template.nodes.length }} 个</span>
      <span class="wf-tpl-card__meta-item">维护人：{{ template.updatedBy || '—' }}</span>
      <span class="wf-tpl-card__meta-item">更新：{{ template.updatedAt || '—' }}</span>
    </div>
    <div class="wf-tpl-card__nodes">
      <span v-for="(n, i) in template.nodes" :key="n.nodeId" class="wf-tpl-card__node">
        <span class="wf-tpl-card__node-name" :class="`is-${n.nodeType.toLowerCase()}`">{{ n.nodeName }}</span>
        <span v-if="i < template.nodes.length - 1" class="wf-tpl-card__arrow">→</span>
      </span>
    </div>
    <div class="wf-tpl-card__actions" @click.stop>
      <slot name="actions" />
    </div>
  </AppCard>
</template>

<script>
/** ProcessTemplateCard —— 流程模板卡片（节点链路预览 + 操作插槽） */
import { AppCard, AppBadge } from '@/components/ui'
import { getModuleLabel, getProcessStatusText, getProcessStatusType } from '../helpers/workflow.helpers'

export default {
  name: 'ProcessTemplateCard',
  components: { AppCard, AppBadge },
  props: {
    template: { type: Object, required: true }
  },
  emits: ['view'],
  computed: {
    statusText() {
      return getProcessStatusText(this.template.status)
    },
    statusType() {
      return getProcessStatusType(this.template.status)
    },
    moduleLabel() {
      return getModuleLabel(this.template.moduleCode)
    }
  }
}
</script>

<style scoped>
.wf-tpl-card { padding: var(--card-padding-pc); display: flex; flex-direction: column; gap: var(--space-3); cursor: pointer; }
.wf-tpl-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); }
.wf-tpl-card__titles { min-width: 0; display: flex; flex-direction: column; gap: var(--space-1); }
.wf-tpl-card__name { font-size: var(--font-size-lg); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.wf-tpl-card__code { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.wf-tpl-card__meta { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.wf-tpl-card__meta-item { font-size: var(--font-size-sm); color: var(--text-secondary); }
.wf-tpl-card__nodes {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  flex-wrap: wrap;
  padding: var(--space-2) var(--space-3);
  background: var(--gray-50);
  border-radius: var(--radius-base);
}
.wf-tpl-card__node { display: inline-flex; align-items: center; gap: var(--space-1); }
.wf-tpl-card__node-name { font-size: var(--font-size-xs); color: var(--text-secondary); padding: 1px var(--space-2); border-radius: var(--radius-sm); background: var(--bg-card); border: 1px solid var(--border-light); }
.wf-tpl-card__node-name.is-approval { color: var(--primary-700); border-color: var(--primary-100); }
.wf-tpl-card__node-name.is-condition { color: var(--warning-700); border-color: var(--warning-100); }
.wf-tpl-card__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.wf-tpl-card__actions { display: flex; gap: var(--space-2); justify-content: flex-end; }
</style>
