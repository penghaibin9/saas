<template>
  <div ref="root" class="legacy-safe">
    <section class="legacy-safe__notice" role="status">
      <div>
        <strong>综合教务兼容页</strong>
        <p>旧课表算法和客户端“官方成绩单”入口已停用。请使用独立课表、成绩工作区；学校正式证明须由服务端生成并验真。</p>
      </div>
      <div class="legacy-safe__actions">
        <button type="button" class="legacy-safe__action is-secondary" @click="goSchedule">进入课表工作区</button>
        <button type="button" class="legacy-safe__action" @click="goGrades">进入成绩工作区</button>
      </div>
    </section>
    <AcademicView />
  </div>
</template>

<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AcademicView from './AcademicView.vue'

const router = useRouter()
const root = ref(null)
const goSchedule = () => router.push('/academic/schedule')
const goGrades = () => router.push('/academic/grades')

onMounted(async () => {
  await nextTick()
  // 旧组件默认tab=课表。安全兼容页主动落到第2项“选课”，避免先展示错误课表。
  const tabs = root.value?.querySelectorAll('.sp-tabs .sp-tab') || []
  if (tabs.length > 1) tabs[1].click()
})
</script>

<style scoped>
.legacy-safe__notice {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  margin: 20px 24px 0;
  padding: 16px 18px;
  border: 1px solid #bfdbfe;
  border-radius: 14px;
  background: #eff6ff;
  color: #1e3a5f;
}
.legacy-safe__notice strong { display: block; margin-bottom: 4px; font-size: 15px; }
.legacy-safe__notice p { margin: 0; color: #475569; font-size: 13px; line-height: 1.6; }
.legacy-safe__actions { display: flex; flex: 0 0 auto; gap: 8px; }
.legacy-safe__action {
  min-height: 38px;
  padding: 0 16px;
  border: 0;
  border-radius: 9px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
  font-weight: 600;
}
.legacy-safe__action.is-secondary { border: 1px solid #93c5fd; background: #fff; color: #1d4ed8; }

/* 旧综合页第1项是错误课表，第5项是客户端拼HTML的成绩单；仅保留源码追溯，不再暴露交互入口。 */
.legacy-safe :deep(.sp-tabs .sp-tab:nth-child(1)),
.legacy-safe :deep(.sp-tabs .sp-tab:nth-child(5)) { display: none !important; }

@media (max-width: 720px) {
  .legacy-safe__notice { align-items: flex-start; flex-direction: column; margin: 12px 12px 0; }
  .legacy-safe__actions { width: 100%; flex-direction: column; }
  .legacy-safe__action { width: 100%; }
}
</style>
