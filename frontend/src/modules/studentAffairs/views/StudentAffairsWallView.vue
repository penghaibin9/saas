<template>
  <section class="wall-page">
    <div v-if="errorMessage" class="wall-error" role="alert">{{ errorMessage }}<button @click="load">重试</button></div>
    <StudentAffairsOperationsWall :snapshot="snapshot" :ctx="ctx" :loading="loading" :auto-refresh="autoRefresh" @refresh="load" @toggle-auto="autoRefresh = !autoRefresh" @drill="drill" />
  </section>
</template>

<script setup>
import { toRef } from 'vue'
import { useRouter } from 'vue-router'
import StudentAffairsOperationsWall from '@/modules/studentAffairs/components/wall/StudentAffairsOperationsWall.vue'
import { useStudentAffairsWallData } from '@/modules/studentAffairs/composables/useStudentAffairsWallData'

const props = defineProps({ ctx: { type: Object, default: null } })
const router = useRouter()
const { snapshot, loading, errorMessage, autoRefresh, load, authorize } = useStudentAffairsWallData(toRef(props, 'ctx'))
async function drill(routeKey) { const path = await authorize(routeKey); if (path) router.push(path) }
</script>

<style scoped>
.wall-page{position:relative;min-width:0}.wall-error{position:absolute;z-index:40;left:50%;top:10px;transform:translateX(-50%);display:flex;align-items:center;gap:10px;padding:8px 12px;border:1px solid #a96a4c;background:#382721ed;color:#ffd6bd;font-size:12px}.wall-error button{border:0;background:transparent;color:#84dfff;cursor:pointer}
</style>

