<template>
  <div class="app-watermark">
    <slot />
    <div class="app-watermark__layer" :style="layerStyle" aria-hidden="true" />
  </div>
</template>

<script>
/**
 * AppWaterMark — 通用防截屏水印（学校名 + 用户姓名 + 时间，覆盖在内容上，不挡点击）。
 * 用于导出预览、敏感名单、成绩单等页面的防泄露留痕。
 * Props:
 *  - text: 水印文字（字符串或多段数组，如 [schoolName, userName, time]）
 *  - fontSize / color(rgba) / rotate(角度) / gapX / gapY（平铺间距）
 * 注：这是展示层防护，不能替代后端导出审计与权限控制。
 */
export default {
  name: 'AppWatermark',
  props: {
    text: { type: [String, Array], default: '内部资料' },
    fontSize: { type: Number, default: 14 },
    color: { type: String, default: 'rgba(15, 40, 90, 0.06)' },
    rotate: { type: Number, default: -22 },
    gapX: { type: Number, default: 160 },
    gapY: { type: Number, default: 110 }
  },
  computed: {
    lines() {
      return Array.isArray(this.text) ? this.text.filter(Boolean) : [this.text]
    },
    layerStyle() {
      const w = this.gapX
      const h = this.gapY
      const lineEls = this.lines.map((t, i) =>
        `<text x="0" y="${20 + i * (this.fontSize + 4)}" font-size="${this.fontSize}" fill="${this.color}" font-family="sans-serif">${this.escape(t)}</text>`
      ).join('')
      const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}">` +
        `<g transform="rotate(${this.rotate} ${w / 2} ${h / 2})">${lineEls}</g></svg>`
      const uri = `url("data:image/svg+xml,${encodeURIComponent(svg)}")`
      return { backgroundImage: uri, backgroundSize: `${w}px ${h}px` }
    }
  },
  methods: {
    escape(s) {
      return String(s).replace(/[<>&]/g, (c) => ({ '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]))
    }
  }
}
</script>

<style scoped>
.app-watermark { position: relative; }
.app-watermark__layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 5;
  background-repeat: repeat;
}
</style>
