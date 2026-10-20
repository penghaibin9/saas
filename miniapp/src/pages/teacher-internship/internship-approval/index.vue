<template><InternshipApprovalCore ref="core" /></template>
<script>
import InternshipApprovalCore from './ApprovalCore.vue'
export default {
  components: { InternshipApprovalCore },
  onLoad(options) { this.$nextTick(() => this.$refs.core?.open(options)) },
  onPullDownRefresh() {
    this.$refs.core?.load(() => uni.stopPullDownRefresh())
  },
  onReachBottom() { this.$refs.core?.loadMore() }
}
</script>
