<template>
  <div class="section-route">
    <header class="section-route__head">
      <div>
        <button type="button" class="section-route__back" @click="router.push('/academic')">‹ 返回教务工作台</button>
        <h1>{{ title }}</h1>
        <p>{{ description }}</p>
      </div>
    </header>
    <div v-if="activationError" class="section-route__mapping-error" role="alert">
      <strong>当前教务服务入口配置异常</strong>
      <span>{{ activationError }}</span>
      <button type="button" @click="router.push('/academic')">返回教务工作台</button>
    </div>
    <div v-else ref="root" class="section-route__body">
      <AcademicView />
    </div>
  </div>
</template>

<script setup>
/**
 * 独立路由兼容迁移层：复用旧综合页的真实业务状态机，只显示当前路由指定面板。
 * 映射失败必须显式阻断，禁止静默回落到默认课表造成“标题是A、内容是B”。
 */
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AcademicView from './AcademicView.vue'

const route = useRoute()
const router = useRouter()
const root = ref(null)
const activationError = ref('')

const title = computed(() => route.meta.academicTitle || '教务服务')
const description = computed(() => route.meta.academicDescription || '当前学生本人教务事项')

async function activatePanel() {
  activationError.value = ''
  await nextTick()
  const target = String(route.meta.academicTab || '').trim()
  if (!target) {
    activationError.value = '路由未声明对应的教务业务面板。'
    return
  }
  const buttons = [...(root.value?.querySelectorAll('.sp-tabs .sp-tab') || [])]
  const button = buttons.find((item) => String(item.textContent || '').trim() === target)
  if (!button) {
    activationError.value = `未找到“${target}”业务面板，请联系管理员检查路由配置。`
    return
  }
  button.click()
}

onMounted(activatePanel)
watch(() => route.fullPath, activatePanel)
</script>

<style scoped>
.section-route { min-width: 0; }
.section-route__head { display: flex; align-items: flex-end; justify-content: space-between; gap: 20px; margin: 20px 24px 0; padding: 18px 20px; border: 1px solid #dbeafe; border-radius: 14px; background: #f8fbff; }
.section-route__back { border: 0; background: transparent; color: #2563eb; cursor: pointer; font-size: 12.5px; }
.section-route__head h1 { margin: 7px 0 4px; color: var(--t1); font-size: 20px; }
.section-route__head p { margin: 0; color: var(--t4); font-size: 12.5px; }
.section-route__mapping-error { display: grid; gap: 8px; margin: 16px 24px; padding: 18px 20px; border: 1px solid #fecaca; border-radius: 12px; background: #fff7f7; color: #991b1b; }
.section-route__mapping-error span { color: #7f1d1d; font-size: 13px; }
.section-route__mapping-error button { justify-self: start; border: 0; background: transparent; color: #2563eb; cursor: pointer; padding: 0; }
.section-route__body :deep(.sp-tabs) { display: none; }
@media (max-width: 720px) { .section-route__head { align-items: flex-start; flex-direction: column; margin: 12px 12px 0; } .section-route__mapping-error { margin: 12px; } }
</style>
