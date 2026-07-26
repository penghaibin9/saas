<template>
  <div class="legacy-safe">
    <section class="legacy-safe__notice" role="status">
      <div>
        <strong>综合教务兼容页</strong>
        <p>原客户端“官方成绩单”入口已停用。成绩查询与个人查询件请进入独立成绩工作区；学校正式证明须由服务端生成并验真。</p>
      </div>
      <button type="button" class="legacy-safe__action" @click="goGrades">进入成绩工作区</button>
    </section>
    <AcademicView />
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import AcademicView from './AcademicView.vue'

const router = useRouter()
const goGrades = () => router.push('/academic/grades')
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
.legacy-safe__action {
  flex: 0 0 auto;
  min-height: 38px;
  padding: 0 16px;
  border: 0;
  border-radius: 9px;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
  font-weight: 600;
}

/* 旧综合页第5项是客户端拼接HTML的“成绩单打印”。保留源码用于历史追溯，但从正式交互路径移除。 */
.legacy-safe :deep(.sp-tabs .sp-tab:nth-child(5)) { display: none !important; }

@media (max-width: 720px) {
  .legacy-safe__notice { align-items: flex-start; flex-direction: column; margin: 12px 12px 0; }
  .legacy-safe__action { width: 100%; }
}
</style>
