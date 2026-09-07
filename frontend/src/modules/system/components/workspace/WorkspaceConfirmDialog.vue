<template>
  <div ref="host" @keydown="onKeydown">
    <AppConfirmDialog ref="dialog" v-bind="$attrs" :visible="visible" :title="title" :submitting="submitting"
      @update:visible="close" @confirm="confirm"><slot /></AppConfirmDialog>
  </div>
</template>
<script>
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
export default {
  name: 'WorkspaceConfirmDialog', inheritAttrs: false, components: { AppConfirmDialog },
  props: { visible: Boolean, submitting: Boolean, title: { type: String, required: true }, initialReason: { type: String, default: '' } },
  emits: ['update:visible', 'confirm'],
  data() { return { returnFocus: null } },
  watch: {
    visible: { immediate: true, async handler(value) {
      if (!value) { this.restoreFocus(); return }
      this.returnFocus = document.activeElement
      await this.$nextTick()
      const dialog = this.$refs.host?.querySelector('[role="dialog"]')
      dialog?.setAttribute('aria-label', this.title)
      if (this.$refs.dialog) this.$refs.dialog.reason = this.initialReason
      this.$refs.host?.querySelector('textarea, button:not(:disabled)')?.focus()
    } }
  },
  beforeUnmount() { this.restoreFocus() },
  methods: {
    restoreFocus() { if (this.returnFocus?.isConnected) this.returnFocus.focus(); this.returnFocus = null },
    close(value) { if (!this.submitting) this.$emit('update:visible', value) },
    confirm(payload) { if (!this.submitting && !this.$attrs.confirmDisabled && !this.$attrs['confirm-disabled']) this.$emit('confirm', payload) },
    onKeydown(event) {
      if (!this.visible) return
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); this.close(false); return }
      if (event.key !== 'Tab') return
      const nodes = [...this.$refs.host.querySelectorAll('button:not(:disabled),textarea:not(:disabled),input:not(:disabled),select:not(:disabled),a[href]')]
        .filter(node => node.getClientRects().length)
      const first = nodes[0], last = nodes[nodes.length - 1]
      if (!first) { event.preventDefault(); return }
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    }
  }
}
</script>
