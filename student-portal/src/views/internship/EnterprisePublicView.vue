<template>
  <div class="enterprise-page">
    <div class="enterprise-page__topbar">
      <button type="button" @click="router.push('/internship/selection')">← 返回实习选岗</button>
      <span>企业公开资料</span>
    </div>

    <div v-if="loading" class="enterprise-state">正在加载企业公开资料…</div>
    <div v-else-if="error" class="enterprise-state enterprise-state--error">
      <strong>企业公开资料加载失败</strong>
      <span>{{ error }}</span>
      <button type="button" @click="load">重新加载</button>
    </div>
    <EnterprisePublicProfile v-else :company="company" />
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import EnterprisePublicProfile from '../../components/recruitment/EnterprisePublicProfile.vue'
import { normalizeEnterprisePublic } from '../../modules/internshipRecruitment/companyModel'
import { internshipSelectionApi } from '../../services/internshipSelectionApi'

const route = useRoute()
const router = useRouter()
const loading = ref(true)
const error = ref('')
const company = ref(normalizeEnterprisePublic())
let requestSeq = 0

async function load() {
  const companyId = route.params.companyId
  if (!companyId) {
    error.value = '缺少企业标识'
    loading.value = false
    return
  }
  const requestId = ++requestSeq
  loading.value = true
  error.value = ''
  try {
    const data = await internshipSelectionApi.company(companyId)
    if (requestId !== requestSeq) return
    company.value = normalizeEnterprisePublic(data || {})
  } catch (err) {
    if (requestId !== requestSeq) return
    error.value = err?.message || '请稍后重试'
  } finally {
    if (requestId === requestSeq) loading.value = false
  }
}

watch(() => route.params.companyId, load)
onMounted(load)
</script>

<style scoped>
.enterprise-page { min-height:100%; padding:20px; background:#f7f8fa; }
.enterprise-page__topbar { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:14px; }
.enterprise-page__topbar button { border:0; background:transparent; color:#2f6bff; cursor:pointer; font-size:13px; }
.enterprise-page__topbar span { color:#8c8c8c; font-size:12px; }
.enterprise-state { display:flex; align-items:center; justify-content:center; gap:10px; min-height:220px; padding:20px; border:1px solid #eef0f3; border-radius:12px; background:#fff; color:#8c8c8c; }
.enterprise-state--error { flex-direction:column; border-color:#ffccc7; background:#fff2f0; color:#a8071a; }
.enterprise-state button { border:0; border-radius:6px; padding:7px 12px; background:#2f6bff; color:#fff; cursor:pointer; }
@media (max-width:899px) { .enterprise-page { padding:12px; } }
</style>
