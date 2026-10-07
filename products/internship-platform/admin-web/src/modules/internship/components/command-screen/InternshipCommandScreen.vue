<template>
  <Teleport to="body"><div ref="host"></div></Teleport>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { statsApi } from '@/modules/internship/api/stats.api'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { allowByPatterns } from '@/modules/internship/composables/permission'
import { REQUIRED_PERMISSIONS } from './screen-core.mjs'
import { mountScreen } from './screen-renderer.mjs'
import './screen.css'
import { getCommandScreenExtension } from './screen-api.mjs'

const props = defineProps({ ctx: { type: Object, required: true } })
const emit = defineEmits(['close'])
const host = ref(null), router = useRouter(), route = useRoute(), batch = useInternshipBatchStore()
let screen = null
function context() {
  const ctx = props.ctx
  // Fail closed even in development; reuse the repo matcher and the backend authority.
  const healthy = ctx.moduleAccessHealthy !== false && !ctx.permissionServiceError
  const known = Array.isArray(ctx.permissionPatterns)
  return {
    ctxKey: ctx.ctxKey || '', batchId: batch.selectedBatchId, batchName: batch.selectedBatchName,
    batchError: batch.batchError || '', schoolName: ctx.tenantBrandConfig?.schoolName || '',
    scopeName: ctx.dataScope?.scopeName || '按后端数据范围', accessHealthy: healthy,
    batches: batch.availableBatches.map(b => ({ id: String(b.id), batchName: b.batchName })),
    grants: Object.fromEntries(REQUIRED_PERMISSIONS.map(code => [code,
      healthy && known && allowByPatterns(ctx.permissionPatterns, code)]))
  }
}
onMounted(() => {
  screen = mountScreen(host.value, {
    context: context(),
    loaders: {
      overview: params => statsApi.getOverview(params),
      dashboard: params => internshipApi.getDashboardSummary(params),
      extension: params => getCommandScreenExtension(params)
    },
    onClose: () => emit('close'),
    onBatchChange: async id => {
      batch.selectBatch(id)
      try { await router.replace({ path: route.path, query: batch.withBatchQuery(route.query), hash: route.hash }) }
      catch { /* Router guard remains authoritative; context watch clears the old snapshot. */ }
    },
    onNavigate: async target => {
      // Keep the dialog open when navigation is rejected; never manufacture a successful write.
      try { const failure = await router.push(target); if (!failure) emit('close') }
      catch { /* Existing router guard handles authorization and route errors. */ }
    }
  })
})
watch(() => [batch.selectedBatchId, batch.batchError, props.ctx.ctxKey,
  props.ctx.permissionPatterns, props.ctx.moduleAccessHealthy, props.ctx.permissionServiceError,
  props.ctx.tenantBrandConfig?.schoolName, props.ctx.dataScope?.scopeName, batch.availableBatches],
() => screen?.updateContext(context()), { deep: true })
onBeforeUnmount(() => { screen?.destroy(); screen = null })
</script>
