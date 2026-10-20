<template>
  <MiniLoginAuthPanel ref="authPanel" entry="student" :dorm-rectification-id="dormRectificationId" :tenant-code-hint="tenantCodeHint" />
</template>

<script>
import { normalizeLoginTenantHint } from '@/utils/loginTenantHint.mjs'
import MiniLoginAuthPanel from '@/components/login/MiniLoginAuthPanel.vue'

export default {
  components: { MiniLoginAuthPanel },
  data() { return { dormRectificationId: '', tenantCodeHint: '' } },
  onHide() { this.$refs.authPanel?.invalidateLogin() },
  onUnload() { this.$refs.authPanel?.invalidateLogin() },
  onShow() { if (this.$refs.authPanel) this.$refs.authPanel.loginAlive = true },
  onLoad(q) { this.tenantCodeHint = normalizeLoginTenantHint(q?.tenant || q?.tenantCode); this.dormRectificationId = String(q?.dormRectificationId || '') }
}
</script>
