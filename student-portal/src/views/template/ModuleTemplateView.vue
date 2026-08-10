<template>
  <div class="sp-page">
    <section class="sp-card capability-card">
      <div class="sp-panel__head">{{ title }}</div>
      <StateBlock
        type="empty"
        :text="message"
      />
      <div class="capability-actions">
        <button class="sp-btn" type="button" @click="goHall">返回办事大厅</button>
        <button class="sp-btn sp-btn--ghost" type="button" @click="goHome">返回首页</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import { moduleByPath } from '../../platform/moduleRegistry'

const route = useRoute()
const router = useRouter()

const modulePath = computed(() => String(route.params.module || '').trim())
const registeredModule = computed(() => moduleByPath(modulePath.value))
const title = computed(() => registeredModule.value?.title || '未登记的门户能力')
const message = computed(() => registeredModule.value
  ? `「${registeredModule.value.title}」当前没有登记可执行的独立页面。系统已停止使用通用模板、演示按钮或猜测字段代替正式能力，请从办事大厅进入已登记事项。`
  : '该地址未登记为学生门户正式能力。系统不会用演示数据或通用模板伪装为可用功能，请从办事大厅选择已开通事项。')

function goHall() {
  router.push('/service-hall')
}

function goHome() {
  router.push('/home')
}
</script>

<style scoped>
.capability-card { max-width: 760px; }
.capability-actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 16px; }
</style>
