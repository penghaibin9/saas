<template>
  <section class="fund-evidence" aria-label="已提交的申请材料">
    <header><strong>已提交的申请材料</strong><button type="button" :disabled="loading" @click="refresh">刷新</button></header>
    <p v-if="loading">正在读取材料…</p><p v-else-if="error" role="alert">{{ error }}</p><p v-else-if="!items.length">这份申请没有已提交的佐证材料。</p>
    <FilePreviewer v-for="item in items" :key="item.fileId" :file="item" @error="showError" />

    <section class="fund-evidence__requirements" aria-label="补交与验收">
      <header><strong>补交与验收</strong><button type="button" @click="openMaterials()">查看办理</button></header>
      <p>材料验收与奖助评审分别办理，请以各自进度为准。</p>
      <p v-if="requirementsLoading">正在读取补交要求…</p>
      <p v-if="requirementsError" role="alert">{{ requirementsError }} <button type="button" @click="loadRequirements(requirementsTargetPage)">重试补交清单</button></p>
      <p v-else-if="!requirementsLoading && !requirements.length">{{ requirementsTotal ? '本页暂无补交项，请返回上一页或刷新。' : '学校尚未对这份申请登记补交要求。' }}</p>
      <article v-for="row in requirements" :key="row.requirementId" class="fund-evidence__requirement">
        <header><strong>{{ row.itemName }}</strong><span class="fund-evidence__status" :data-status="row.status">{{ row.statusLabel }}</span></header>
        <p v-if="row.requirementReason">{{ row.requirementReason }}</p>
        <p v-if="row.dueAt">{{ row.overdue ? '已逾期 · ' : '' }}截止 {{ materialTime(row.dueAt) }}</p>
        <p v-if="row.currentSubmission">已提交 {{ row.versionCount }} 个版本 · {{ row.currentSubmission.fileName || '查看当前提交材料' }}</p>
        <p v-if="row.currentSubmission?.reviewNote" class="fund-evidence__opinion">验收意见：{{ row.currentSubmission.reviewNote }}</p>
        <button type="button" @click="openMaterials(row.requirementId)">查看办理 · {{ row.itemName }}</button>
      </article>
      <div v-if="requirementsTotal" class="fund-evidence__pages"><button type="button" :disabled="requirementsLoading || requirementsPage <= 1" @click="loadRequirements(requirementsPage - 1)">上一页</button><span>第 {{ requirementsPage }} 页 · 共 {{ requirementsTotal }} 项</span><button type="button" :disabled="requirementsLoading || requirementsPage * 10 >= requirementsTotal" @click="loadRequirements(requirementsPage + 1)">下一页</button></div>
    </section>
  </section>
</template>
<script setup>
import { useRouter } from 'vue-router'
import { affairsFourEndApi } from '../../services/affairsFourEndApi'
import { onBeforeUnmount, ref, watch } from 'vue'
import { fileSdk } from '../../services/fileSdk'
import FilePreviewer from '../../components/file/FilePreviewer.vue'
const props = defineProps({ applicationId: { type: String, required: true } })
const items = ref([]), loading = ref(false), error = ref('')
let seq = 0
function showError(e) { error.value = e.message || '读取失败，请重试' }
function refresh() { load(); loadRequirements(requirementsPage.value) }
async function load() {
  const request = ++seq; items.value = []; error.value = ''; loading.value = true
  try {
    const rows = await fileSdk.list({bizType:'FUNDING',bizId:props.applicationId})
    if (request === seq) items.value = rows.filter(x => x.isCurrent !== false)
  } catch (e) { if (request === seq) showError(e) }
  finally { if (request === seq) loading.value = false }
}
watch(() => props.applicationId, load, {immediate:true})
onBeforeUnmount(() => { seq++ })

const router = useRouter()
const requirements = ref([]), requirementsLoading = ref(false), requirementsError = ref(''), requirementsPage = ref(1), requirementsTotal = ref(0), requirementsTargetPage = ref(1)
let requirementSeq = 0
function materialTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '' }
function openMaterials(id) {
  router.push({ name: 'material-supplement', query: { bizType: 'FUNDING', bizId: props.applicationId, ...(id ? { materialRequirementId: String(id) } : {}) } })
}
async function loadRequirements(page = 1) {
  const request = ++requirementSeq
  requirementsTargetPage.value = page; requirementsLoading.value = true; requirementsError.value = ''
  const context = { bizType: 'FUNDING', bizId: props.applicationId }
  try {
    const data = await (affairsFourEndApi.myMaterialRequirements({ ...context, page, pageSize: 10 }))
    if (request !== requirementSeq) return
    if (!data || !Array.isArray(data.items) || data.items.some(row => row.bizType !== 'FUNDING' || String(row.bizId) !== String(props.applicationId))) throw new Error('材料关联不一致，请重新打开申请')
    requirements.value = data.items; requirementsTotal.value = Number(data.total || 0); requirementsPage.value = page
  } catch (e) { if (request === requirementSeq) requirementsError.value = e?.message || '补交清单暂不可用，请重试' }
  finally { if (request === requirementSeq) requirementsLoading.value = false }
}
watch(() => props.applicationId, () => { requirements.value = []; requirementsTotal.value = 0; requirementsPage.value = 1; loadRequirements() }, { immediate: true })
onBeforeUnmount(() => { requirementSeq++ })
</script>
<style scoped>
.fund-evidence { display: grid; gap: 8px; padding: 14px; margin-top: 10px; border: 1px solid var(--border-light); border-radius: 10px; }
.fund-evidence header { display: flex; align-items: center; justify-content: space-between; gap: 10px; font-size: 13px; }.fund-evidence p { margin: 0; color: var(--text-secondary); font-size: 12px; }
.fund-evidence button { border: 0; background: transparent; color: var(--primary); min-height: 32px; cursor: pointer; }

.fund-evidence__requirements { display: grid; gap: 10px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border-light, #e2e8f0); }
.fund-evidence__requirement { display: grid; gap: 7px; padding: 12px; border: 1px solid var(--border-light, #e2e8f0); border-radius: 10px; overflow-wrap: anywhere; }
.fund-evidence__requirement > button { justify-self: start; text-align: left; }
.fund-evidence__opinion { color: var(--text-primary, #243c31) !important; font-size: 13px; line-height: 1.6; }
.fund-evidence__pages { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary, #64748b); }
.fund-evidence__status { flex-shrink: 0; border-radius: 5px; padding: 3px 7px; font-size: 12px; background: var(--bg-secondary, #eef2f5); }.fund-evidence__status[data-status="RETURNED"], .fund-evidence__status[data-status="MISSING"] { color: var(--color-warning, #a15c16); }.fund-evidence__status[data-status="ACCEPTED"] { color: var(--color-success, #208264); }
</style>
