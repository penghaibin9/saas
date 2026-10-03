<template>
  <div class="app-qrcode" :style="{ width: size + 'px' }">
    <div class="app-qrcode__box" :style="{ width: size + 'px', height: size + 'px' }">
      <slot>
        <div class="app-qrcode__placeholder">
          <span class="app-qrcode__ico">▦</span>
          <span class="app-qrcode__hint">二维码占位</span>
        </div>
      </slot>
    </div>
    <div v-if="label" class="app-qrcode__label">{{ label }}</div>
    <div v-if="showValue && value" class="app-qrcode__value">{{ value }}</div>
  </div>
</template>

<script>
/**
 * AppQRCode —（partial 部分完成）二维码占位组件。
 *
 * ⚠️ 现状：为避免引入较重的二维码库，本组件默认只渲染占位框 + 文案 + 原始值展示，
 *    不生成真实二维码图形。真实二维码有两种正规接入方式：
 *      1) 后端返回二维码图片/base64，用默认插槽放 <img>；
 *      2) 项目确定引入二维码库后，在此组件内替换占位为真实渲染。
 *    未接入前标 partial，禁止对外宣称“已支持扫码”。
 * Props: value(二维码内容) / size(px) / label / showValue
 * Slot: default（放真实二维码 img / canvas）
 */
export default {
  name: 'AppQRCode',
  props: {
    value: { type: String, default: '' },
    size: { type: Number, default: 128 },
    label: { type: String, default: '' },
    showValue: { type: Boolean, default: false }
  }
}
</script>

<style scoped>
.app-qrcode { display: inline-flex; flex-direction: column; align-items: center; gap: var(--space-2); }
.app-qrcode__box {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.app-qrcode__placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1);
  color: var(--text-disabled);
}
.app-qrcode__ico { font-size: 40px; line-height: 1; }
.app-qrcode__hint { font-size: var(--font-size-xs); }
.app-qrcode__label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.app-qrcode__value { font-size: var(--font-size-xs); color: var(--text-tertiary); word-break: break-all; text-align: center; max-width: 100%; }
</style>
