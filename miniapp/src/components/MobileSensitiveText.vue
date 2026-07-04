<template>
  <view class="mobile-sensitive-text">
    <text class="mst-value">{{ displayValue }}</text>
    <text v-if="revealable" class="mst-toggle" @click="toggle">{{ revealed ? '隐藏' : '查看' }}</text>
  </view>
</template>

<script>
import { maskByType } from '../utils/sensitive'

/**
 * MobileSensitiveText 移动端敏感字段脱敏展示
 * Props: value、type: phone|idcard|name|address|generic、code（对外编码）、revealable
 * Emits: reveal（查看明文时触发，调用方必须写敏感查看审计）
 * 默认脱敏。企业导师端与学生材料页禁止 revealable 明文展示他人敏感信息。
 */
export default {
  name: 'MobileSensitiveText',
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
.mobile-sensitive-text { display: inline-flex; align-items: center; gap: var(--space-1); }
.mst-value { font-size: inherit; color: inherit; }
.mst-toggle { font-size: var(--font-size-xs); color: var(--text-link); padding: var(--space-1); }
</style>
