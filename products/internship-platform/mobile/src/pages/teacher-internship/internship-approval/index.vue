<template><view class="mobile-page mobile-teacher "><InternshipApprovalCore ref="core" /></view></template>
<script>
import InternshipApprovalCore from './ApprovalCore.vue'
export default {
  components: { InternshipApprovalCore },
  onLoad(options) { this.$nextTick(() => this.$refs.core?.open(options)) },
  onShow() { this.$refs.core?.resume() },
  onHide() { this.$refs.core?.pause() },
  onUnload() { this.$refs.core?.pause() },
  onPullDownRefresh() {
    this.$refs.core?.load(() => uni.stopPullDownRefresh())
  },
  onReachBottom() { this.$refs.core?.loadMore() }
}
</script>
