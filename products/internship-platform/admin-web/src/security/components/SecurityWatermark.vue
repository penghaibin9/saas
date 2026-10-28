<template>
  <div v-if="visible" class="security-watermark" aria-hidden="true">
    <div
      v-for="i in tileCount"
      :key="i"
      class="security-watermark__tile"
    >
      {{ watermarkText }}
    </div>
  </div>
</template>

<script>
/**
 * SecurityWatermark — 页面级明水印（总册 §9）。
 * 覆盖整个页面区域、半透明、-25° 旋转、pointer-events:none 不影响点击。
 * 内容：学校名 · 用户姓名 · 时间 ·（用途或 requestId）。
 * 注意：前端明水印仅为威慑与溯源辅助，防截图篡改需配合后端暗水印（后端阶段）。
 */
import { getAuthContext } from '../auth/auth.context'

export default {
  name: 'SecurityWatermark',
  props: {
    visible: { type: Boolean, default: true },
    /** 用途说明或 requestId，二选一传入 */
    purpose: { type: String, default: '' },
    requestId: { type: String, default: '' },
    /** 平铺块数量（自适应场景可调） */
    tileCount: { type: Number, default: 24 }
  },
  computed: {
    watermarkText() {
      const auth = getAuthContext()
      const d = new Date()
      const p = (n) => String(n).padStart(2, '0')
      const time = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
      const tail = this.purpose || this.requestId || ''
      return [auth.schoolName || '学校', auth.displayName || '用户', time, tail].filter(Boolean).join(' · ')
    }
  }
}
</script>

<style scoped>
.security-watermark {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 5;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  align-content: space-around;
  justify-items: center;
  gap: var(--space-10);
}
.security-watermark__tile {
  transform: rotate(-25deg);
  opacity: 0.07;
  font-size: 15px;
  color: var(--gray-900);
  white-space: nowrap;
  user-select: none;
}
</style>
