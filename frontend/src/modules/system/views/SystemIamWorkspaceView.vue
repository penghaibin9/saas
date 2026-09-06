<template>
  <SystemRoleListView v-if="roleSurface" ref="roleWorkspace" :ctx="ctx" :surface="roleSurface" />
  <SystemAccessInspector v-else-if="accessSurface" :ctx="ctx" />
  <SystemIamGovernancePanel v-else />
</template>
<script>
import SystemRoleListView from './SystemRoleListView.vue'
import SystemAccessInspector from '../components/workspace/SystemAccessInspector.vue'
import SystemIamGovernancePanel from '../components/workspace/SystemIamGovernancePanel.vue'
export default {
  name: 'SystemIamWorkspaceView',
  components: { SystemRoleListView, SystemAccessInspector, SystemIamGovernancePanel },
  props: { ctx: { type: Object, required: true } },
  computed: {
    roleSurface() {
      const surface = String(this.$route.query.surface || '')
      return ['roles', 'templates', 'permissions', 'members'].includes(surface) ? surface : ''
    },
    accessSurface() {
      return ['access', 'accessExplain'].includes(String(this.$route.query.surface || ''))
        || (this.$route.hash === '#access-explain' && this.$route.query.surface !== 'diagnostics')
    }
  },
  // Nested workspaces are not route records: the owning route forwards their leave guard.
  beforeRouteLeave(to) { return this.$refs.roleWorkspace?.canLeave(to) ?? true },
  beforeRouteUpdate(to) { return this.$refs.roleWorkspace?.canLeave(to) ?? true }
}
</script>
