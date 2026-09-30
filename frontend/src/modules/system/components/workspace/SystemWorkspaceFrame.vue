<template>
  <ModulePageShell class="system-workspace" :title="title" :subtitle="subtitle"
    :role-name="ctx.currentRole?.roleName || ''" :data-scope-name="ctx.dataScope?.scopeName || ''">
    <template #actions><slot name="actions" /></template>
    <slot />
  </ModulePageShell>
</template>

<script>
import ModulePageShell from '@/components/business/ModulePageShell.vue'
export default {
  name: 'SystemWorkspaceFrame',
  components: { ModulePageShell },
  props: { title: { type: String, required: true }, subtitle: { type: String, default: '' }, ctx: { type: Object, required: true } }
}
</script>

<style src="./workspace.css"></style>
