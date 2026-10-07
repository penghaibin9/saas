<template>
  <AppButton :variant="variant" :disabled="disabled" @click="onPrint">
    <slot>🖨 {{ label }}</slot>
  </AppButton>
</template>

<script>
/**
 * AppPrintButton — 打印按钮（触发浏览器打印，或调用方自定义 handler）。
 *
 * ⚠️ 声明：本组件只触发打印动作，不生成正式套打模板。正式成绩单 / 台账 / 证书套打，
 *    应由后端出 PDF 或专门打印模板，本组件不伪造正式打印排版。
 *
 * 三种用法：
 *  1) 不传 handler / printSelector：直接 window.print() 打印整页；
 *  2) printSelector：把该元素克隆到隐藏 iframe 中单独打印；
 *  3) handler：完全由业务方接管（如请求后端 PDF）。
 * Props: label / variant / disabled / printSelector / handler / title(打印文档标题)
 * Emits: print
 */
import { AppButton } from '@/components/ui'

export default {
  name: 'AppPrintButton',
  components: { AppButton },
  props: {
    label: { type: String, default: '打印' },
    variant: { type: String, default: 'secondary' },
    disabled: { type: Boolean, default: false },
    printSelector: { type: String, default: '' },
    handler: { type: Function, default: null },
    title: { type: String, default: '' }
  },
  emits: ['print'],
  methods: {
    onPrint() {
      if (this.disabled) return
      this.$emit('print')
      if (this.handler) { this.handler(); return }
      if (this.printSelector) { this.printElement(); return }
      window.print()
    },
    printElement() {
      const el = document.querySelector(this.printSelector)
      if (!el) { window.print(); return }
      const iframe = document.createElement('iframe')
      iframe.style.position = 'fixed'
      iframe.style.right = '0'
      iframe.style.bottom = '0'
      iframe.style.width = '0'
      iframe.style.height = '0'
      iframe.style.border = '0'
      document.body.appendChild(iframe)
      const doc = iframe.contentWindow.document
      doc.open()
      doc.write(`<html><head><title>${this.title || document.title}</title></head><body>${el.outerHTML}</body></html>`)
      doc.close()
      iframe.contentWindow.focus()
      iframe.contentWindow.print()
      setTimeout(() => document.body.removeChild(iframe), 500)
    }
  }
}
</script>
