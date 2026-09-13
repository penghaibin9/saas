<template>
  <MiniLoginAuthPanel ref="authPanel" entry="teacher" :dorm-rectification-id="dormRectificationId" />
</template>

<script>
import MiniLoginAuthPanel from '@/components/login/MiniLoginAuthPanel.vue'

export default {
  components: { MiniLoginAuthPanel },
  data() { return { dormRectificationId: '' } },
  onHide() { this.$refs.authPanel?.invalidateLogin() },
  onUnload() { this.$refs.authPanel?.invalidateLogin() },
  onShow() { if (this.$refs.authPanel) this.$refs.authPanel.loginAlive = true },
  onLoad(q) { this.dormRectificationId = String(q?.dormRectificationId || '') }
}
</script>
