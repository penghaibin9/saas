<template>
  <IdentityImportWorkspace ref="importWorkspace" kind="teachers" :ctx="ctx" />
</template>
<script>
import IdentityImportWorkspace from '../components/workspace/IdentityImportWorkspace.vue'
export default {
  name: 'SystemTeacherImportView', components: { IdentityImportWorkspace },
  props: { ctx: { type: Object, default: () => ({}) } },
  beforeRouteLeave(to) { return this.$refs.importWorkspace?.canLeave(to) ?? true },
  beforeRouteUpdate(to) { return this.$refs.importWorkspace?.canLeave(to) ?? true }
}
</script>
