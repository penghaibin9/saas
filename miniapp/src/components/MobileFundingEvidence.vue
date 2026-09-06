<template>
  <view class="fund-evidence">
    <view class="fund-evidence__head"><text>申请佐证材料</text><button size="mini" :disabled="loading" @click="refresh">刷新</button></view>
    <text v-if="loading" class="fund-evidence__hint">正在读取材料…</text>
    <MobileInlineAlert v-else-if="error" type="warning" title="材料暂不可用" :description="error" />
    <text v-else-if="!items.length" class="fund-evidence__hint">这份申请没有已提交的佐证材料。</text>
    <FilePreviewer v-for="item in items" :key="item.fileId" :file="item" @error="showError" />

    <view class="fund-evidence__requirements">
      <view class="fund-evidence__head"><text>补交与验收</text><button size="mini" @click="openMaterials()">查看办理</button></view>
      <text class="fund-evidence__hint">材料验收与奖助评审分别办理，请以各自进度为准。</text>
      <text v-if="requirementsLoading" class="fund-evidence__hint">正在读取补交要求…</text>
      <view v-if="requirementsError"><text class="fund-evidence__hint">{{ requirementsError }}</text><button size="mini" @click="loadRequirements(requirementsTargetPage)">重试补交清单</button></view>
      <text v-else-if="!requirementsLoading && !requirements.length" class="fund-evidence__hint">{{ requirementsTotal ? '本页暂无补交项，请返回上一页或刷新。' : '学校尚未对这份申请登记补交要求。' }}</text>
      <view v-for="row in requirements" :key="row.requirementId" class="fund-evidence__requirement">
        <view class="fund-evidence__head"><text>{{ row.itemName }}</text><MobileStatusTag :status="row.status" :label="row.statusLabel" /></view>
        <text v-if="row.requirementReason" class="fund-evidence__hint">{{ row.requirementReason }}</text>
        <text v-if="row.dueAt" class="fund-evidence__hint">{{ row.overdue ? '已逾期 · ' : '' }}截止 {{ materialTime(row.dueAt) }}</text>
        <text v-if="row.currentSubmission" class="fund-evidence__hint">已提交 {{ row.versionCount }} 个版本 · {{ row.currentSubmission.fileName || '查看当前提交材料' }}</text>
        <text v-if="row.currentSubmission?.reviewNote" class="fund-evidence__opinion">验收意见：{{ row.currentSubmission.reviewNote }}</text>
        <button size="mini" @click="openMaterials(row.requirementId)">查看办理 · {{ row.itemName }}</button>
      </view>
      <view v-if="requirementsTotal" class="fund-evidence__pages"><button size="mini" :disabled="requirementsLoading || requirementsPage <= 1" @click="loadRequirements(requirementsPage - 1)">上一页</button><text>第 {{ requirementsPage }} 页 · 共 {{ requirementsTotal }} 项</text><button size="mini" :disabled="requirementsLoading || requirementsPage * 10 >= requirementsTotal" @click="loadRequirements(requirementsPage + 1)">下一页</button></view>
    </view>
  </view>
</template>
<script setup>
import { affairsContractApi } from '@/services/affairsContractApi'
import { onUnmounted, ref, watch } from 'vue'
import FilePreviewer from './file/FilePreviewer.vue'
import { fileSdk } from '@/services/fileSdk'
import { normalizeError } from '@/services/request'
const props = defineProps({ applicationId: { type: String, required: true }, audience: { type: String, default: 'student' } })
const items = ref([]), loading = ref(false), error = ref('')
let seq = 0
function showError(e) { error.value = normalizeError(e).text || '无法打开材料，请重试' }
function refresh() { load(); loadRequirements(requirementsPage.value) }
async function load() {
  const request = ++seq; items.value = []; error.value = ''; loading.value = true
  try {
    const data = await fileSdk.list({bizType:'FUNDING',bizId:props.applicationId})
    if (request === seq) items.value = data.filter(x => x.isCurrent !== false)
  } catch (e) { if (request === seq) showError(e) }
  finally { if (request === seq) loading.value = false }
}
watch(() => props.applicationId, load, {immediate:true})
onUnmounted(() => { seq++ })


const requirements = ref([]), requirementsLoading = ref(false), requirementsError = ref(''), requirementsPage = ref(1), requirementsTotal = ref(0), requirementsTargetPage = ref(1)
let requirementSeq = 0
function materialTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '' }
function openMaterials(id) {
  const base = props.audience === 'teacher' ? '/pages/teacher/affairs/index' : '/pages/student/affairs/index'
  uni.navigateTo({ url: base + '?bizType=FUNDING&bizId=' + encodeURIComponent(props.applicationId) + (id ? '&materialRequirementId=' + encodeURIComponent(id) : '') })
}
async function loadRequirements(page = 1) {
  const request = ++requirementSeq
  requirementsTargetPage.value = page; requirementsLoading.value = true; requirementsError.value = ''
  const context = { bizType: 'FUNDING', bizId: props.applicationId }
  try {
    const data = await (props.audience === 'teacher' ? affairsContractApi.getMaterialRequirements('', page, 10, context) : affairsContractApi.getMyMaterialRequirements({ ...context, page, pageSize: 10 }))
    if (request !== requirementSeq) return
    if (!data || !Array.isArray(data.items) || data.items.some(row => row.bizType !== 'FUNDING' || String(row.bizId) !== String(props.applicationId))) throw new Error('材料关联不一致，请重新打开申请')
    requirements.value = data.items; requirementsTotal.value = Number(data.total || 0); requirementsPage.value = page
  } catch (e) { if (request === requirementSeq) requirementsError.value = e?.message || '补交清单暂不可用，请重试' }
  finally { if (request === requirementSeq) requirementsLoading.value = false }
}
watch(() => [props.applicationId, props.audience], () => { requirements.value = []; requirementsTotal.value = 0; requirementsPage.value = 1; loadRequirements() }, { immediate: true })
onUnmounted(() => { requirementSeq++ })
</script>
<style scoped>
.fund-evidence { display: flex; flex-direction: column; gap: 8px; margin: 12px 0; padding-top: 10px; border-top: 1px solid var(--border-light, #e5e7eb); }
.fund-evidence__head { display: flex; justify-content: space-between; align-items: center; font-weight: 600; font-size: 14px; }
.fund-evidence__head button { margin: 0; background: transparent; color: var(--brand-primary); font-size: 12px; }
.fund-evidence__hint { font-size: 12px; color: var(--text-secondary); }

.fund-evidence__requirements { display: flex; flex-direction: column; gap: 10px; margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border-light, #e2e8f0); }
.fund-evidence__requirement { display: flex; flex-direction: column; gap: 7px; padding: 12px; border: 1px solid var(--border-light, #e2e8f0); border-radius: 10px; overflow-wrap: anywhere; }
.fund-evidence__requirement button { justify-self: start; margin: 0; font-size: 12px; }
.fund-evidence__opinion { color: var(--text-primary, #243c31) !important; font-size: 13px; line-height: 1.6; }
.fund-evidence__pages { display: flex; justify-content: space-between; align-items: center; gap: 8px; font-size: 12px; color: var(--text-secondary, #64748b); }
</style>
