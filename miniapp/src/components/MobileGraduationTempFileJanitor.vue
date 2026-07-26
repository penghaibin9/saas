<template><view v-if="false" /></template>

<script>
import { realRequest } from '@/services/request'
function pageStack() { return typeof getCurrentPages === 'function' ? getCurrentPages() : [] }
export default {
  name: 'MobileGraduationTempFileJanitor',
  data() { return { active: false, known: new Set(), initialized: false, timer: null } },
  mounted() {
    const pages = pageStack(); const page = pages[pages.length - 1]
    const route = (page && (page.route || page.__route__)) || ''
    this.active = route === 'pages/student/graduation/index'
    if (this.active) { this.sync(); this.timer = setInterval(this.sync, 600) }
  },
  beforeUnmount() {
    if (this.timer) clearInterval(this.timer)
    if (this.active) this.currentIds().forEach((id) => this.abandon(id))
  },
  methods: {
    currentVm() { const pages = pageStack(); const page = pages[pages.length - 1]; return page && page.$vm },
    currentIds() {
      const vm = this.currentVm()
      const values = [...((vm && vm.propAtts) || []), ...((vm && vm.finalAtts) || [])]
      return new Set(values.map((item) => String(item && item.fileId || '')).filter(Boolean))
    },
    sync() {
      const current = this.currentIds()
      if (this.initialized) this.known.forEach((id) => { if (!current.has(id)) this.abandon(id) })
      this.known = current
      this.initialized = true
    },
    abandon(fileId) {
      realRequest(`/mobile/graduation/materials/${fileId}/abandon`, { method: 'POST', data: {} })
        .catch(() => { /* 已提交并绑定时后端 409 是正确保护 */ })
    }
  }
}
</script>
