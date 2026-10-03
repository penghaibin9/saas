<template>
  <div class="app-multi-select" :class="{ 'is-open': open, 'is-disabled': disabled, 'is-error': status === 'error' }">
    <div
      class="app-multi-select__control"
      role="combobox"
      :aria-expanded="open"
      tabindex="0"
      @click="toggleOpen"
      @keydown.enter.prevent="toggleOpen"
      @keydown.esc="open = false"
    >
      <template v-if="selected.length">
        <span v-for="opt in selected" :key="opt.value" class="app-multi-select__tag">
          {{ opt.label }}
          <button
            type="button"
            class="app-multi-select__tag-x"
            aria-label="移除"
            @click.stop="remove(opt.value)"
          >✕</button>
        </span>
      </template>
      <span v-else class="app-multi-select__placeholder">{{ placeholder }}</span>
      <span class="app-multi-select__chevron" aria-hidden="true">▾</span>
    </div>

    <div v-if="open" class="app-multi-select__panel">
      <div v-if="searchable" class="app-multi-select__search">
        <input
          v-model="keyword"
          class="app-multi-select__search-el"
          type="text"
          placeholder="搜索…"
          @click.stop
        />
      </div>
      <ul class="app-multi-select__list">
        <li
          v-for="opt in filteredOptions"
          :key="opt.value"
          class="app-multi-select__option"
          :class="{ 'is-checked': isChecked(opt.value), 'is-disabled': opt.disabled || isMaxed(opt.value) }"
          @click="toggle(opt)"
        >
          <span class="app-multi-select__box">
            <span v-if="isChecked(opt.value)" class="app-multi-select__tick">✓</span>
          </span>
          {{ opt.label }}
        </li>
        <li v-if="!filteredOptions.length" class="app-multi-select__empty">无匹配项</li>
      </ul>
      <div v-if="max > 0" class="app-multi-select__hint">最多可选 {{ max }} 项</div>
    </div>
  </div>
</template>

<script>
/**
 * AppMultiSelect — 通用多选下拉（标签展示 + 勾选面板 + 可选搜索）。
 * v-model 绑定数组。Props: options:[{label,value,disabled?}] / placeholder / searchable / max / disabled / status
 * Emits: update:modelValue / change
 * 大数据量 + 远程搜索的业务多选，请用 Group3 业务选择器（multiple 模式）。
 */
export default {
  name: 'AppMultiSelect',
  props: {
    modelValue: { type: Array, default: () => [] },
    options: { type: Array, default: () => [] },
    placeholder: { type: String, default: '请选择' },
    searchable: { type: Boolean, default: false },
    max: { type: Number, default: 0 },
    disabled: { type: Boolean, default: false },
    status: { type: String, default: 'default' }
  },
  emits: ['update:modelValue', 'change'],
  data() {
    return { open: false, keyword: '' }
  },
  computed: {
    normalizedOptions() {
      return this.options.map((o) => (typeof o === 'object' ? o : { label: o, value: o }))
    },
    filteredOptions() {
      if (!this.keyword) return this.normalizedOptions
      const k = this.keyword.toLowerCase()
      return this.normalizedOptions.filter((o) => String(o.label).toLowerCase().includes(k))
    },
    selected() {
      return this.normalizedOptions.filter((o) => this.modelValue.includes(o.value))
    }
  },
  methods: {
    toggleOpen() {
      if (this.disabled) return
      this.open = !this.open
    },
    isChecked(v) { return this.modelValue.includes(v) },
    isMaxed(v) { return this.max > 0 && this.modelValue.length >= this.max && !this.isChecked(v) },
    toggle(opt) {
      if (opt.disabled) return
      let next
      if (this.isChecked(opt.value)) next = this.modelValue.filter((v) => v !== opt.value)
      else { if (this.isMaxed(opt.value)) return; next = [...this.modelValue, opt.value] }
      this.emitChange(next)
    },
    remove(v) {
      this.emitChange(this.modelValue.filter((x) => x !== v))
    },
    emitChange(next) {
      this.$emit('update:modelValue', next)
      this.$emit('change', next)
    },
    onOutside(e) {
      if (!this.$el.contains(e.target)) this.open = false
    }
  },
  mounted() { document.addEventListener('click', this.onOutside) },
  beforeUnmount() { document.removeEventListener('click', this.onOutside) }
}
</script>

<style scoped>
.app-multi-select { position: relative; width: 100%; }
.app-multi-select__control {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-1);
  min-height: 34px;
  padding: 3px var(--space-5) 3px var(--space-2);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.app-multi-select__control:focus-visible { outline: none; border-color: var(--primary-500); box-shadow: 0 0 0 3px var(--primary-100); }
.is-open .app-multi-select__control { border-color: var(--primary-500); box-shadow: 0 0 0 3px var(--primary-100); }
.is-error .app-multi-select__control { border-color: var(--danger-500); }
.is-disabled .app-multi-select__control { background: var(--bg-disabled); cursor: not-allowed; }
.app-multi-select__tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 22px;
  padding: 0 var(--space-1) 0 var(--space-2);
  border-radius: var(--radius-base);
  background: var(--primary-50);
  color: var(--primary-700);
  font-size: var(--font-size-xs);
}
.app-multi-select__tag-x { border: none; background: none; color: var(--primary-600); cursor: pointer; font-size: 10px; padding: 0; }
.app-multi-select__tag-x:hover { color: var(--danger-600); }
.app-multi-select__placeholder { color: var(--text-disabled); font-size: var(--font-size-base); padding-left: var(--space-1); }
.app-multi-select__chevron { position: absolute; right: var(--space-3); top: 50%; transform: translateY(-50%); color: var(--text-tertiary); font-size: 10px; }
.app-multi-select__panel {
  position: absolute;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  z-index: 30;
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}
.app-multi-select__search { padding: var(--space-2); border-bottom: 1px solid var(--border-light); }
.app-multi-select__search-el {
  width: 100%; box-sizing: border-box; height: 28px; padding: 0 var(--space-2);
  border: 1px solid var(--border-base); border-radius: var(--radius-sm);
  font-size: var(--font-size-sm); outline: none; font-family: inherit;
}
.app-multi-select__list { list-style: none; margin: 0; padding: var(--space-1); max-height: 220px; overflow-y: auto; }
.app-multi-select__option {
  display: flex; align-items: center; gap: var(--space-2);
  padding: var(--space-2); border-radius: var(--radius-sm);
  font-size: var(--font-size-sm); color: var(--text-primary); cursor: pointer;
}
.app-multi-select__option:hover { background: var(--bg-hover); }
.app-multi-select__option.is-disabled { color: var(--text-disabled); cursor: not-allowed; }
.app-multi-select__box {
  width: 15px; height: 15px; border: 1.5px solid var(--border-dark);
  border-radius: var(--radius-sm); display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.app-multi-select__option.is-checked .app-multi-select__box { background: var(--primary-600); border-color: var(--primary-600); }
.app-multi-select__tick { color: #fff; font-size: 10px; }
.app-multi-select__empty { padding: var(--space-3); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); }
.app-multi-select__hint { padding: var(--space-1) var(--space-2); font-size: var(--font-size-xs); color: var(--text-tertiary); border-top: 1px solid var(--border-light); }
</style>
