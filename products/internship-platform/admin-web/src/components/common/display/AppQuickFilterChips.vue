<template>
  <div class="app-quick-chips" :class="{ 'is-compact': size === 'compact' }" role="group">
    <button
      v-for="opt in normalizedOptions"
      :key="opt.value"
      type="button"
      class="app-quick-chips__chip"
      :class="{ 'is-active': isActive(opt.value), 'is-disabled': opt.disabled }"
      :disabled="opt.disabled"
      @click="pick(opt)"
    >
      {{ opt.label }}
      <span v-if="opt.count != null" class="app-quick-chips__count">{{ opt.count }}</span>
    </button>
  </div>
</template>

<script>
/**
 * AppQuickFilterChips — 快捷筛选胶囊组（列表页顶部「全部 / 待处理 / 已通过…」一键切换）。
 * v-model 绑定；single 时为单值，multiple 时为数组。
 * Props: options:[{ label, value, count?, disabled? }] / multiple / allowClear(单选可再点取消) / size
 * Emits: update:modelValue / change
 */
export default {
  name: 'AppQuickFilterChips',
  props: {
    modelValue: { type: [String, Number, Array], default: '' },
    options: { type: Array, default: () => [] },
    multiple: { type: Boolean, default: false },
    allowClear: { type: Boolean, default: false },
    size: { type: String, default: 'normal', validator: (v) => ['normal', 'compact'].includes(v) }
  },
  emits: ['update:modelValue', 'change'],
  computed: {
    normalizedOptions() {
      return this.options.map((o) => (typeof o === 'object' ? o : { label: o, value: o }))
    }
  },
  methods: {
    isActive(v) {
      if (this.multiple) return Array.isArray(this.modelValue) && this.modelValue.includes(v)
      return this.modelValue === v
    },
    pick(opt) {
      if (opt.disabled) return
      let next
      if (this.multiple) {
        const arr = Array.isArray(this.modelValue) ? this.modelValue : []
        next = this.isActive(opt.value) ? arr.filter((v) => v !== opt.value) : [...arr, opt.value]
      } else {
        next = this.allowClear && this.modelValue === opt.value ? '' : opt.value
      }
      this.$emit('update:modelValue', next)
      this.$emit('change', next)
    }
  }
}
</script>

<style scoped>
.app-quick-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
.app-quick-chips__chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
  transition: all 0.12s;
}
.app-quick-chips.is-compact .app-quick-chips__chip { height: 26px; padding: 0 var(--space-2); font-size: var(--font-size-xs); }
.app-quick-chips__chip:hover:not(.is-disabled):not(.is-active) { border-color: var(--primary-300, var(--primary-500)); color: var(--primary-600); }
.app-quick-chips__chip.is-active {
  background: var(--primary-50);
  border-color: var(--primary-500);
  color: var(--primary-700);
  font-weight: var(--font-weight-medium);
}
.app-quick-chips__chip.is-disabled { opacity: 0.5; cursor: not-allowed; }
.app-quick-chips__count {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--radius-full);
  background: var(--gray-100);
  color: var(--text-tertiary);
  font-size: 11px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
.app-quick-chips__chip.is-active .app-quick-chips__count { background: var(--primary-100); color: var(--primary-700); }
</style>
