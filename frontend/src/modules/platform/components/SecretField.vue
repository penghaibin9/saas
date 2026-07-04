<template>
  <span class="sf">
    <code class="sf__value">{{ masked }}</code>
    <span class="sf__lock" :title="lockReason">🔒</span>
  </span>
</template>

<script>
/**
 * SecretField — 平台运营模块局部组件：密钥 / 凭证脱敏展示。
 * 平台冻结规则：AppSecret / Token / 签名密钥明文不在任何页面展示（viewSecretFull visible=false），
 * 仅在创建 / 重置时通过安全信道一次性下发。本组件只负责渲染脱敏值与锁定提示。
 */
export default {
  name: 'SecretField',
  props: {
    masked: { type: String, required: true },
    lockReason: { type: String, default: '明文密钥不在页面展示，仅创建/重置时一次性下发' }
  }
}
</script>

<style scoped>
.sf {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
}
.sf__value {
  font-size: var(--font-size-xs);
  color: var(--text-secondary);
  background: var(--bg-section-blue);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 0 var(--space-2);
  letter-spacing: 0.04em;
  font-variant-numeric: var(--font-numeric);
}
.sf__lock {
  font-size: var(--font-size-xs);
  cursor: help;
}
</style>
