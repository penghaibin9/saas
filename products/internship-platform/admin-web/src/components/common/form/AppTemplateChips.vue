<template>
  <div class="app-tpl-chips" :class="{ 'is-compact': size === 'compact' }" role="group">
    <button
      v-for="(opt, i) in normalizedOptions"
      :key="i"
      type="button"
      class="app-tpl-chips__chip"
      @click="$emit('pick', opt.value)"
    >
      {{ opt.label }}
    </button>
  </div>
</template>

<script>
/**
 * AppTemplateChips — 预设文案快捷芯片。点击只把文案通过 pick 事件透传给父级，
 * 不持有任何 v-model；父级自行决定填入/追加到目标输入框（支持多选拼接）。
 * Props: options:string[]|{label,value}[] / size
 * Emits: pick(text)
 */
export default {
  name: 'AppTemplateChips',
  props: {
    options: { type: Array, default: () => [] },
    size: { type: String, default: 'normal', validator: (v) => ['normal', 'compact'].includes(v) }
  },
  emits: ['pick'],
  computed: {
    normalizedOptions() {
      return this.options.map((o) => (typeof o === 'object' ? o : { label: o, value: o }))
    }
  }
}
</script>

<style scoped>
.app-tpl-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-1);
}
.app-tpl-chips__chip {
  border: 1px dashed var(--border-base);
  background: var(--bg-subtle, var(--bg-card));
  color: var(--text-secondary);
  border-radius: var(--radius-full, 999px);
  padding: 2px var(--space-3);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}
.app-tpl-chips__chip:hover { border-color: var(--primary-500); color: var(--primary-600); background: var(--primary-50); }
.app-tpl-chips.is-compact .app-tpl-chips__chip { padding: 1px var(--space-2); }
</style>
