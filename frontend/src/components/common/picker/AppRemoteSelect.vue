<template>
  <div class="app-remote-select" :class="{ 'is-open': open, 'is-disabled': disabled, 'is-error': status === 'error' }">
    <div
      class="app-remote-select__control"
      role="combobox"
      :aria-expanded="open"
      :tabindex="disabled ? -1 : 0"
      :title="disabled && disabledReason ? disabledReason : ''"
      @click="toggleOpen"
      @keydown.enter.prevent="toggleOpen"
      @keydown.esc="open = false"
    >
      <!-- 多选标签 -->
      <template v-if="multiple && selectedItems.length">
        <span v-for="it in selectedItems" :key="it.value" class="app-remote-select__tag">
          {{ it.label }}
          <button type="button" class="app-remote-select__tag-x" aria-label="移除" @click.stop="removeValue(it.value)">✕</button>
        </span>
      </template>
      <!-- 单选文本 -->
      <span v-else-if="!multiple && singleLabel" class="app-remote-select__single">{{ singleLabel }}</span>
      <!-- 占位 -->
      <span v-else class="app-remote-select__placeholder">{{ placeholder }}</span>

      <button
        v-if="clearable && hasValue && !disabled"
        type="button"
        class="app-remote-select__clear"
        aria-label="清空"
        tabindex="-1"
        @click.stop="clearAll"
      >✕</button>
      <span class="app-remote-select__chevron" aria-hidden="true">▾</span>
    </div>

    <div v-if="open" class="app-remote-select__panel">
      <div class="app-remote-select__search">
        <input
          v-model="keyword"
          class="app-remote-select__search-el"
          type="text"
          :placeholder="searchPlaceholder"
          @click.stop
          @input="onKeyword"
        />
      </div>

      <div v-if="panelLoading" class="app-remote-select__state">
        <span class="app-remote-select__spinner" /> 加载中…
      </div>
      <div v-else-if="panelError" class="app-remote-select__state is-error">
        {{ panelError }}
        <button type="button" class="app-remote-select__retry" @click="doRemote">重试</button>
      </div>
      <ul v-else-if="displayOptions.length" class="app-remote-select__list">
        <li
          v-for="opt in displayOptions"
          :key="opt.value"
          class="app-remote-select__option"
          :class="{ 'is-checked': isChecked(opt.value), 'is-disabled': opt.disabled || isMaxed(opt.value) }"
          @click="pick(opt)"
        >
          <span v-if="multiple" class="app-remote-select__box">
            <span v-if="isChecked(opt.value)" class="app-remote-select__tick">✓</span>
          </span>
          <span class="app-remote-select__opt-main">
            <span class="app-remote-select__opt-label">{{ opt.label }}</span>
            <span v-if="opt.desc" class="app-remote-select__opt-desc">{{ opt.desc }}</span>
          </span>
          <span v-if="!multiple && isChecked(opt.value)" class="app-remote-select__opt-check">✓</span>
        </li>
      </ul>
      <div v-else class="app-remote-select__state is-empty">{{ emptyHint }}</div>

      <div v-if="dataScopeHint" class="app-remote-select__scope">
        <span class="app-remote-select__scope-dot" />{{ dataScopeHint }}
      </div>
    </div>
  </div>
</template>

<script>
/**
 * AppRemoteSelect — 业务选择器通用基座（学生/教师/组织/批次等所有业务 Picker 的底座）。
 *
 * ⚠️ 现状（partial 部分完成）：本组件只做通用 UI 与调用规范。是否接真实后端，取决于调用方是否传
 *    remoteSearch。未接后端（只传 options）时，属于 UI 就绪、数据未接，各业务 Picker 一律标 partial，
 *    不得当作“已接真实师生/组织数据”对外宣称。数据范围过滤必须由后端按数据范围返回，前端不自行放大。
 *
 * Props:
 *  - modelValue: 单选=值；多选=值数组
 *  - multiple: 是否多选
 *  - options: 本地选项 [{ label, value, desc?, disabled? }]
 *  - remoteSearch: (keyword) => Promise<options>  远程搜索（预留，业务方注入真实接口）
 *  - minKeyword: 触发远程搜索的最小字数（默认 1）
 *  - placeholder / searchPlaceholder / emptyText
 *  - clearable / disabled / disabledReason / size / status / max(多选上限)
 *  - dataScopeHint: 数据范围提示（如“仅显示你负责班级的学生”）
 * Emits: update:modelValue / change(value, items) / search(keyword)
 */
export default {
  name: 'AppRemoteSelect',
  props: {
    modelValue: { type: [String, Number, Array], default: '' },
    multiple: { type: Boolean, default: false },
    options: { type: Array, default: () => [] },
    remoteSearch: { type: Function, default: null },
    minKeyword: { type: Number, default: 1 },
    placeholder: { type: String, default: '请选择' },
    searchPlaceholder: { type: String, default: '输入关键词搜索…' },
    emptyText: { type: String, default: '暂无可选项' },
    clearable: { type: Boolean, default: true },
    disabled: { type: Boolean, default: false },
    disabledReason: { type: String, default: '' },
    size: { type: String, default: 'normal' },
    status: { type: String, default: 'default' },
    max: { type: Number, default: 0 },
    dataScopeHint: { type: String, default: '' }
  },
  emits: ['update:modelValue', 'change', 'search'],
  data() {
    return { open: false, keyword: '', remoteOptions: null, remoteLoading: false, panelError: '', labelCache: {} }
  },
  computed: {
    localNormalized() {
      return this.options.map((o) => (typeof o === 'object' ? o : { label: o, value: o }))
    },
    displayOptions() {
      const src = this.remoteSearch && this.remoteOptions !== null ? this.remoteOptions : this.localNormalized
      if (!this.remoteSearch && this.keyword) {
        const k = this.keyword.toLowerCase()
        return src.filter((o) => String(o.label).toLowerCase().includes(k))
      }
      return src
    },
    valueArray() {
      if (this.multiple) return Array.isArray(this.modelValue) ? this.modelValue : []
      return this.hasValue ? [this.modelValue] : []
    },
    hasValue() {
      if (this.multiple) return Array.isArray(this.modelValue) && this.modelValue.length > 0
      return this.modelValue !== '' && this.modelValue !== null && this.modelValue !== undefined
    },
    selectedItems() {
      return this.valueArray.map((v) => ({ value: v, label: this.labelOf(v) }))
    },
    singleLabel() {
      return this.hasValue ? this.labelOf(this.modelValue) : ''
    },
    panelLoading() { return this.remoteLoading },
    emptyHint() {
      if (this.remoteSearch && !this.keyword) return '输入关键词开始搜索'
      return this.emptyText
    }
  },
  watch: {
    options: { handler() { this.cacheLabels(this.localNormalized) }, immediate: true },
    displayOptions(v) { this.cacheLabels(v) }
  },
  methods: {
    labelOf(v) { return this.labelCache[v] != null ? this.labelCache[v] : v },
    cacheLabels(list) {
      if (!list) return
      const next = { ...this.labelCache }
      list.forEach((o) => { next[o.value] = o.label })
      this.labelCache = next
    },
    toggleOpen() {
      if (this.disabled) return
      this.open = !this.open
      if (this.open && this.remoteSearch && this.remoteOptions === null && !this.keyword) {
        // 打开即触发一次空搜索，业务方可返回默认列表
        this.doRemote()
      }
    },
    onKeyword() {
      this.$emit('search', this.keyword)
      if (!this.remoteSearch) return
      clearTimeout(this._t)
      if (this.keyword && this.keyword.length < this.minKeyword) return
      this._t = setTimeout(this.doRemote, 250)
    },
    async doRemote() {
      if (!this.remoteSearch) return
      this.remoteLoading = true
      this.panelError = ''
      try {
        const res = await this.remoteSearch(this.keyword)
        this.remoteOptions = (res || []).map((o) => (typeof o === 'object' ? o : { label: o, value: o }))
        this.cacheLabels(this.remoteOptions)
      } catch (e) {
        this.panelError = (e && e.message) || '搜索失败'
      } finally {
        this.remoteLoading = false
      }
    },
    isChecked(v) { return this.valueArray.includes(v) },
    isMaxed(v) { return this.multiple && this.max > 0 && this.valueArray.length >= this.max && !this.isChecked(v) },
    pick(opt) {
      if (opt.disabled) return
      if (this.multiple) {
        let next
        if (this.isChecked(opt.value)) next = this.valueArray.filter((v) => v !== opt.value)
        else { if (this.isMaxed(opt.value)) return; next = [...this.valueArray, opt.value] }
        this.emit(next)
      } else {
        this.emit(opt.value)
        this.open = false
      }
    },
    removeValue(v) { this.emit(this.valueArray.filter((x) => x !== v)) },
    clearAll() { this.emit(this.multiple ? [] : '') },
    emit(val) {
      this.$emit('update:modelValue', val)
      const items = (this.multiple ? val : [val]).filter((v) => v !== '' && v != null)
        .map((v) => ({ value: v, label: this.labelOf(v) }))
      this.$emit('change', val, items)
    },
    onOutside(e) { if (!this.$el.contains(e.target)) this.open = false }
  },
  mounted() { document.addEventListener('click', this.onOutside) },
  beforeUnmount() { document.removeEventListener('click', this.onOutside); clearTimeout(this._t) }
}
</script>

<style scoped>
.app-remote-select { position: relative; width: 100%; }
.app-remote-select__control {
  display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-1);
  min-height: 34px; padding: 3px var(--space-6) 3px var(--space-2);
  border: 1px solid var(--border-base); border-radius: var(--radius-base);
  background: var(--bg-card); cursor: pointer; transition: border-color 0.15s, box-shadow 0.15s;
}
.is-open .app-remote-select__control,
.app-remote-select__control:focus-visible {
  outline: none; border-color: var(--primary-500); box-shadow: 0 0 0 3px var(--primary-100);
}
.is-error .app-remote-select__control { border-color: var(--danger-500); }
.is-disabled .app-remote-select__control { background: var(--bg-disabled); cursor: not-allowed; }
.app-remote-select__tag {
  display: inline-flex; align-items: center; gap: var(--space-1);
  height: 22px; padding: 0 var(--space-1) 0 var(--space-2);
  border-radius: var(--radius-base); background: var(--primary-50); color: var(--primary-700); font-size: var(--font-size-xs);
}
.app-remote-select__tag-x { border: none; background: none; color: var(--primary-600); cursor: pointer; font-size: 10px; padding: 0; }
.app-remote-select__single { font-size: var(--font-size-base); color: var(--text-primary); padding-left: var(--space-1); }
.app-remote-select__placeholder { font-size: var(--font-size-base); color: var(--text-disabled); padding-left: var(--space-1); }
.app-remote-select__clear { position: absolute; right: var(--space-5); border: none; background: none; color: var(--text-tertiary); cursor: pointer; font-size: 10px; }
.app-remote-select__clear:hover { color: var(--text-secondary); }
.app-remote-select__chevron { position: absolute; right: var(--space-3); top: 50%; transform: translateY(-50%); color: var(--text-tertiary); font-size: 10px; pointer-events: none; }
.app-remote-select__panel {
  position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 30;
  background: var(--bg-card); border: 1px solid var(--border-base);
  border-radius: var(--radius-base); box-shadow: var(--shadow-md); overflow: hidden;
}
.app-remote-select__search { padding: var(--space-2); border-bottom: 1px solid var(--border-light); }
.app-remote-select__search-el {
  width: 100%; box-sizing: border-box; height: 30px; padding: 0 var(--space-2);
  border: 1px solid var(--border-base); border-radius: var(--radius-sm); font-size: var(--font-size-sm); outline: none; font-family: inherit;
}
.app-remote-select__search-el:focus { border-color: var(--primary-500); }
.app-remote-select__state {
  display: flex; align-items: center; justify-content: center; gap: var(--space-2);
  padding: var(--space-5); font-size: var(--font-size-sm); color: var(--text-tertiary);
}
.app-remote-select__state.is-error { color: var(--danger-600); }
.app-remote-select__retry { border: none; background: none; color: var(--text-link); cursor: pointer; font-size: var(--font-size-sm); }
.app-remote-select__spinner {
  width: 14px; height: 14px; border: 2px solid var(--primary-100); border-top-color: var(--primary-500);
  border-radius: var(--radius-full); animation: ars-spin 0.7s linear infinite;
}
@keyframes ars-spin { to { transform: rotate(360deg); } }
.app-remote-select__list { list-style: none; margin: 0; padding: var(--space-1); max-height: 240px; overflow-y: auto; }
.app-remote-select__option {
  display: flex; align-items: center; gap: var(--space-2);
  padding: var(--space-2); border-radius: var(--radius-sm); cursor: pointer;
  font-size: var(--font-size-sm); color: var(--text-primary);
}
.app-remote-select__option:hover { background: var(--bg-hover); }
.app-remote-select__option.is-checked { background: var(--primary-25, var(--primary-50)); }
.app-remote-select__option.is-disabled { color: var(--text-disabled); cursor: not-allowed; }
.app-remote-select__box {
  width: 15px; height: 15px; border: 1.5px solid var(--border-dark); border-radius: var(--radius-sm);
  display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.app-remote-select__option.is-checked .app-remote-select__box { background: var(--primary-600); border-color: var(--primary-600); }
.app-remote-select__tick { color: #fff; font-size: 10px; }
.app-remote-select__opt-main { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.app-remote-select__opt-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.app-remote-select__opt-desc { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.app-remote-select__opt-check { color: var(--primary-600); }
.app-remote-select__scope {
  display: flex; align-items: center; gap: var(--space-1);
  padding: var(--space-2) var(--space-3); border-top: 1px solid var(--border-light);
  background: var(--bg-subtle); font-size: var(--font-size-xs); color: var(--text-secondary);
}
.app-remote-select__scope-dot { width: 6px; height: 6px; border-radius: var(--radius-full); background: var(--primary-500); }
</style>
