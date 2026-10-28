<template>
  <span class="app-copyable">
    <span class="app-copyable__text" :title="String(value)"><slot>{{ value }}</slot></span>
    <button
      type="button"
      class="app-copyable__btn"
      :class="{ 'is-done': copied }"
      :aria-label="copied ? '已复制' : '复制'"
      @click="copy"
    >{{ copied ? '✓ 已复制' : '复制' }}</button>
  </span>
</template>

<script>
/**
 * AppCopyableText — 可复制文本（学号、订单号、链接、邮箱等）。
 * Props: value(要复制的原始值)、successText
 * Emits: copied(value) / error(err)
 * 敏感字段（手机号/身份证）请用 AppSensitiveText，不要用本组件直接暴露明文。
 */
export default {
  name: 'AppCopyableText',
  props: {
    value: { type: [String, Number], default: '' },
    successText: { type: String, default: '已复制到剪贴板' }
  },
  emits: ['copied', 'error'],
  data() {
    return { copied: false, timer: null }
  },
  methods: {
    async copy() {
      const text = String(this.value ?? '')
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text)
        } else {
          const ta = document.createElement('textarea')
          ta.value = text
          ta.style.position = 'fixed'
          ta.style.opacity = '0'
          document.body.appendChild(ta)
          ta.select()
          document.execCommand('copy')
          document.body.removeChild(ta)
        }
        this.copied = true
        this.$emit('copied', text)
        clearTimeout(this.timer)
        this.timer = setTimeout(() => { this.copied = false }, 1600)
      } catch (e) {
        this.$emit('error', e)
      }
    }
  },
  beforeUnmount() {
    clearTimeout(this.timer)
  }
}
</script>

<style scoped>
.app-copyable {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  max-width: 100%;
}
.app-copyable__text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.app-copyable__btn {
  flex-shrink: 0;
  border: none;
  background: none;
  padding: 0;
  font-size: var(--font-size-xs);
  color: var(--text-link);
  cursor: pointer;
}
.app-copyable__btn:hover { color: var(--primary-700); }
.app-copyable__btn.is-done { color: var(--success-600); cursor: default; }
</style>
