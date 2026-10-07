<template>
  <div class="app-search-box" :class="[`is-${size}`, { 'is-focus': focused }]">
    <span class="app-search-box__icon" aria-hidden="true">🔍</span>
    <input
      ref="input"
      class="app-search-box__el"
      type="search"
      :value="modelValue"
      :placeholder="placeholder"
      :disabled="disabled"
      @input="onInput"
      @keydown.enter="emitSearch"
      @focus="focused = true"
      @blur="focused = false"
    />
    <button
      v-if="modelValue"
      type="button"
      class="app-search-box__clear"
      aria-label="清空"
      tabindex="-1"
      @click="onClear"
    >✕</button>
    <button v-if="button" type="button" class="app-search-box__btn" :disabled="disabled" @click="emitSearch">
      搜索
    </button>
  </div>
</template>

<script>
/**
 * AppSearchBox — 统一搜索框（带图标、清空、防抖搜索、回车搜索）。
 * v-model 绑定关键词。Props: placeholder / debounce(毫秒,0=不防抖) / button(带搜索按钮) / size / disabled
 * Emits: update:modelValue / search(keyword) / clear
 */
export default {
  name: 'AppSearchBox',
  props: {
    modelValue: { type: String, default: '' },
    placeholder: { type: String, default: '搜索…' },
    debounce: { type: Number, default: 300 },
    button: { type: Boolean, default: false },
    size: { type: String, default: 'normal', validator: (v) => ['normal', 'compact'].includes(v) },
    disabled: { type: Boolean, default: false }
  },
  emits: ['update:modelValue', 'search', 'clear'],
  data() {
    return { focused: false }
  },
  methods: {
    onInput(e) {
      const v = e.target.value
      this.$emit('update:modelValue', v)
      if (this.debounce > 0) {
        clearTimeout(this._t)
        this._t = setTimeout(() => this.$emit('search', v), this.debounce)
      }
    },
    emitSearch() {
      clearTimeout(this._t)
      this.$emit('search', this.modelValue)
    },
    onClear() {
      clearTimeout(this._t)
      this.$emit('update:modelValue', '')
      this.$emit('clear')
      this.$emit('search', '')
      this.$refs.input && this.$refs.input.focus()
    }
  },
  beforeUnmount() { clearTimeout(this._t) }
}
</script>

<style scoped>
.app-search-box {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  width: 100%;
  max-width: 320px;
  height: 34px;
  padding: 0 var(--space-2) 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  transition: border-color 0.15s, box-shadow 0.15s;
}
.app-search-box.is-compact { height: 30px; }
.app-search-box.is-focus { border-color: var(--primary-500); box-shadow: 0 0 0 3px var(--primary-100); }
.app-search-box__icon { font-size: 12px; opacity: 0.6; flex-shrink: 0; }
.app-search-box__el {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
  font-family: inherit;
}
.app-search-box__el::placeholder { color: var(--text-disabled); }
.app-search-box__el::-webkit-search-cancel-button { display: none; }
.app-search-box__clear { border: none; background: none; color: var(--text-tertiary); cursor: pointer; font-size: 11px; flex-shrink: 0; }
.app-search-box__clear:hover { color: var(--text-secondary); }
.app-search-box__btn {
  flex-shrink: 0;
  height: 26px;
  padding: 0 var(--space-3);
  border: none;
  border-radius: var(--radius-full);
  background: var(--primary-600);
  color: #fff;
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.app-search-box__btn:hover:not(:disabled) { background: var(--primary-700); }
</style>
