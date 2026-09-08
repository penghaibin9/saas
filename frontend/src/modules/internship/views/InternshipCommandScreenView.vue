<template>
  <InternshipCommandScreen :ctx="ctx" @close="close" />
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import InternshipCommandScreen from '../components/command-screen/InternshipCommandScreen.vue'
import { withInternshipBatch } from '../navigation'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

defineProps({ ctx: { type: Object, required: true } })
const route = useRoute()
const router = useRouter()
const batch = useInternshipBatchStore()

function close() {
  // The renderer also emits close after a successful drilldown. Keep that destination.
  if (route.name !== 'internship-command-screen') return
  return router.replace(withInternshipBatch('/admin/internship', batch.selectedBatchId))
}
</script>
