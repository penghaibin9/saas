<template>
  <span class="app-sensitive-text">
    <span class="app-sensitive-text__value">{{ displayValue }}</span>
    <button
      v-if="revealable"
      type="button"
      class="app-sensitive-text__toggle"
      :aria-label="revealed ? '隐藏' : '查看明文'"
      @click="toggle"
    >
      {{ revealed ? '隐藏' : '查看' }}
    </button>
  </span>
</template>

<script>
import { maskByType } from '../../utils/sensitive'

/**
 * AppSensitiveText 敏感字段脱敏展示
 * Props:
 *  - value: 原始值
 *  - type: phone | idcard | name | address | generic
 *  - code: 对外编码（type=name 时优先显示，如 S2026-000001）
 *  - revealable: 是否允许点击查看明文（需权限，由调用方控制）
 * Emits:
 *  - reveal: 用户查看明文时触发，调用方必须在此写敏感查看审计（V3.0 §10.9）
 * 默认脱敏，禁止直接渲染明文敏感字段。
 */
export default {
  name: 'AppSensitiveText',
  props: {
    value: { type: [String, Number], default: '' },
    type: {
      type: String,
      default: 'generic',
      validator: (v) => ['phone', 'idcard', 'name', 'address', 'generic'].includes(v)
    },
    code: { type: String, default: '' },
    revealable: { type: Boolean, default: false }
  },
  emits: ['reveal'],
  data() {
    return { revealed: false }
  },
  computed: {
    displayValue() {
      if (this.revealed) return String(this.value ?? '')
      return maskByType(this.type, this.value, this.code)
    }
  },
  methods: {
    toggle() {
      this.revealed = !this.revealed
      if (this.revealed) this.$emit('reveal', { type: this.type })
    }
  }
}
</script>

<style scoped>
.app-sensitive-text {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}
.app-sensitive-text__value {
  font-variant-numeric: var(--font-numeric);
}
.app-sensitive-text__toggle {
  border: none;
  background: none;
  padding: 0;
  font-size: var(--font-size-xs);
  color: var(--text-link);
  cursor: pointer;
}
.app-sensitive-text__toggle:hover {
  color: var(--primary-700);
}
</style>
