<template>
  <section class="wall-page">
    <div v-if="errorMessage" class="wall-error" role="alert">{{ errorMessage }}<button @click="load">重试</button></div>
    <StudentAffairsLeaderWall :snapshot="snapshot" :ctx="ctx" :loading="loading" @refresh="load" @drill="drill" />
  </section>
</template>

<script setup>
import { toRef } from 'vue'
import { useRouter } from 'vue-router'
import StudentAffairsLeaderWall from '@/modules/studentAffairs/components/wall/StudentAffairsLeaderWall.vue'
import { useStudentAffairsWallData } from '@/modules/studentAffairs/composables/useStudentAffairsWallData'

const props = defineProps({ ctx: { type: Object, default: null } })
const router = useRouter()
const { snapshot, loading, errorMessage, load, authorize } = useStudentAffairsWallData(toRef(props, 'ctx'))
async function drill(routeKey) { const path = await authorize(routeKey); if (path) router.push(path) }
</script>

<style scoped>
.wall-page{position:relative;min-width:0}.wall-error{position:absolute;z-index:40;left:50%;top:10px;transform:translateX(-50%);display:flex;align-items:center;gap:10px;padding:8px 12px;border:1px solid #775d43;background:#2d2922ed;color:#f6d6a4;font-size:12px}.wall-error button{border:0;background:transparent;color:#8cded2;cursor:pointer}
</style>
