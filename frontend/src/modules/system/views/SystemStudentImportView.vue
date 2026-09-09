<template>
  <IdentityImportWorkspace ref="importWorkspace" kind="students" :ctx="ctx" />
</template>
<script>
import IdentityImportWorkspace from '../components/workspace/IdentityImportWorkspace.vue'
export default {
  name: 'SystemStudentImportView', components: { IdentityImportWorkspace },
  props: { ctx: { type: Object, default: () => ({}) } },
  beforeRouteLeave(to) { return this.$refs.importWorkspace?.canLeave(to) ?? true },
  beforeRouteUpdate(to) { return this.$refs.importWorkspace?.canLeave(to) ?? true }
}
</script>
