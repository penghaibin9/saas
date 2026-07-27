<template>
  <div class="section-route">
    <header class="section-route__head">
      <div>
        <button type="button" class="section-route__back" @click="router.push('/academic')">‹ 返回教务工作台</button>
        <h1>{{ title }}</h1>
        <p>{{ description }}</p>
      </div>
      <button type="button" class="section-route__all" @click="router.push('/academic/all')">兼容综合页</button>
    </header>
    <div ref="root" class="section-route__body">
      <AcademicView />
    </div>
  </div>
</template>

<script setup>
/**
 * V2 R6 兼容迁移层：把旧综合页的真实业务面板拆成稳定独立路由。
 * 业务实现仍复用 AcademicView，避免复制状态机；路由只显示指定面板，旧 /academic/all 保留追溯。
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AcademicView from './AcademicView.vue'

const route = useRoute()
const router = useRouter()
const root = ref(null)

const title = computed(() => route.meta.academicTitle || '教务服务')
const description = computed(() => route.meta.academicDescription || '当前学生本人教务事项')

async function activatePanel() {
  await nextTick()
  const target = String(route.meta.academicTab || '')
  if (!target) return
  const buttons = [...(root.value?.querySelectorAll('.sp-tabs .sp-tab') || [])]
  const button = buttons.find((item) => String(item.textContent || '').trim() === target)
  if (button) button.click()
}

onMounted(activatePanel)
watch(() => route.fullPath, activatePanel)
</script>

<style scoped>
.section-route { min-width: 0; }
.section-route__head { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin: 20px 24px 0; padding: 18px 20px; border: 1px solid #dbeafe; border-radius: 14px; background: #f8fbff; }
.section-route__back, .section-route__all { border: 0; background: transparent; color: #2563eb; cursor: pointer; font-size: 12.5px; }
.section-route__head h1 { margin: 7px 0 4px; color: var(--t1); font-size: 20px; }
.section-route__head p { margin: 0; color: var(--t4); font-size: 12.5px; }
.section-route__all { padding: 8px 10px; border: 1px solid #bfdbfe; border-radius: 8px; background: #fff; white-space: nowrap; }
.section-route__body :deep(.sp-tabs) { display: none; }
@media (max-width: 720px) { .section-route__head { align-items: flex-start; flex-direction: column; margin: 12px 12px 0; } }
</style>
