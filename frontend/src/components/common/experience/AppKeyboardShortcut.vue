<template>
  <span v-if="showHint" class="app-kbd">
    <kbd v-for="(k, i) in displayKeys" :key="i" class="app-kbd__key">{{ k }}</kbd>
    <span v-if="label" class="app-kbd__label">{{ label }}</span>
  </span>
</template>

<script>
/**
 * AppKeyboardShortcut — 注册键盘快捷键并可选渲染提示（如 ⌘K 打开搜索）。
 * Props:
 *  - keys: 组合键，字符串 'ctrl+k' / 'shift+/' 或数组 ['ctrl','k']
 *  - disabled: 禁用监听
 *  - showHint: 是否渲染 kbd 提示徽标（默认渲染）
 *  - label: 提示文字（如“搜索”）
 *  - stop: 命中后是否 preventDefault（默认 true）
 * Emits: trigger(event)
 * 监听挂在 document；组件卸载自动解绑。
 */
export default {
  name: 'AppKeyboardShortcut',
  props: {
    keys: { type: [String, Array], required: true },
    disabled: { type: Boolean, default: false },
    showHint: { type: Boolean, default: true },
    label: { type: String, default: '' },
    stop: { type: Boolean, default: true }
  },
  emits: ['trigger'],
  computed: {
    parts() {
      const arr = Array.isArray(this.keys) ? this.keys : String(this.keys).split('+')
      return arr.map((k) => k.trim().toLowerCase()).filter(Boolean)
    },
    mods() {
      return {
        ctrl: this.parts.includes('ctrl') || this.parts.includes('cmd') || this.parts.includes('meta'),
        shift: this.parts.includes('shift'),
        alt: this.parts.includes('alt')
      }
    },
    mainKey() {
      return this.parts.find((k) => !['ctrl', 'cmd', 'meta', 'shift', 'alt'].includes(k)) || ''
    },
    displayKeys() {
      const map = { ctrl: '⌘/Ctrl', cmd: '⌘', meta: '⌘', shift: '⇧', alt: '⌥' }
      return this.parts.map((k) => map[k] || k.toUpperCase())
    }
  },
  methods: {
    onKey(e) {
      if (this.disabled) return
      const ctrl = e.ctrlKey || e.metaKey
      if (this.mods.ctrl !== ctrl) return
      if (this.mods.shift !== e.shiftKey) return
      if (this.mods.alt !== e.altKey) return
      if ((e.key || '').toLowerCase() !== this.mainKey) return
      if (this.stop) e.preventDefault()
      this.$emit('trigger', e)
    }
  },
  mounted() { document.addEventListener('keydown', this.onKey) },
  beforeUnmount() { document.removeEventListener('keydown', this.onKey) }
}
</script>

<style scoped>
.app-kbd { display: inline-flex; align-items: center; gap: 3px; }
.app-kbd__key {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 20px;
  padding: 0 5px;
  border: 1px solid var(--border-base);
  border-bottom-width: 2px;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  color: var(--text-secondary);
  font-size: 11px;
  font-family: inherit;
}
.app-kbd__label { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: 2px; }
</style>
