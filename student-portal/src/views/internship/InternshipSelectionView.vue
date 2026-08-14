<template>
  <div class="selection-page">
    <header class="selection-header">
      <div>
        <p class="selection-kicker">岗位实习中心</p>
        <h1>实习选岗</h1>
        <p>浏览学校认可实习岗位，完善材料后选择 1–3 个志愿并整组投递。</p>
      </div>
    </header>

    <div v-if="loading" class="selection-state">正在加载当前招聘季…</div>
    <div v-else-if="error" class="selection-state selection-state--error">
      <strong>招聘季信息加载失败</strong>
      <span>{{ error }}</span>
      <button type="button" @click="loadContext">重新加载</button>
    </div>
    <RecruitmentContextBar v-else :context="context" />

    <main class="selection-shell" aria-label="实习选岗工作区">
      <section class="selection-placeholder">
        <strong>岗位目录</strong>
        <span>岗位查询、详情与志愿操作按当前招聘季上下文加载。</span>
      </section>
    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import RecruitmentContextBar from '../../components/recruitment/RecruitmentContextBar.vue'
import { normalizeRecruitmentContext } from '../../modules/internshipRecruitment/contextModel'
import { internshipSelectionApi } from '../../services/internshipSelectionApi'

const loading = ref(true)
const error = ref('')
const context = ref(normalizeRecruitmentContext())

async function loadContext() {
  loading.value = true
  error.value = ''
  try {
    context.value = normalizeRecruitmentContext(await internshipSelectionApi.context())
  } catch (err) {
    error.value = err?.message || '请稍后重试'
  } finally {
    loading.value = false
  }
}

onMounted(loadContext)
</script>

<style scoped>
.selection-page { min-width:0; padding:20px; background:#f7f8fa; min-height:100%; }
.selection-header { display:flex; align-items:flex-end; justify-content:space-between; gap:20px; margin-bottom:16px; }
.selection-kicker { margin:0 0 4px; color:#2f6bff; font-size:12px; font-weight:600; }
h1 { margin:0; color:#1a1a1a; font-size:24px; line-height:1.35; }
.selection-header p:last-child { margin:6px 0 0; color:#666; font-size:13px; }
.selection-state { display:flex; align-items:center; gap:12px; padding:18px 20px; border:1px solid #eef0f3; border-radius:12px; background:#fff; color:#595959; }
.selection-state--error { align-items:flex-start; flex-direction:column; border-color:#ffccc7; background:#fff2f0; color:#a8071a; }
.selection-state button { border:0; border-radius:6px; padding:7px 12px; background:#2f6bff; color:#fff; cursor:pointer; }
.selection-shell { margin-top:14px; }
.selection-placeholder { display:flex; align-items:center; justify-content:space-between; gap:16px; min-height:72px; padding:18px 20px; border:1px solid #eef0f3; border-radius:12px; background:#fff; }
.selection-placeholder strong { color:#1a1a1a; }
.selection-placeholder span { color:#8c8c8c; font-size:13px; }
@media (max-width:899px) {
  .selection-page { padding:12px; }
  .selection-placeholder { align-items:flex-start; flex-direction:column; }
}
</style>
