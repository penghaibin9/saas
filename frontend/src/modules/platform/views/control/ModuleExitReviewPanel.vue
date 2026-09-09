<template>
  <section class="exit-review panel" aria-label="模块退出完整性检查" tabindex="-1">
    <header>
      <div><span class="eyebrow">EXIT READINESS · READ ONLY</span><h3>退出完整性检查</h3>
        <p>查看交付、保留、共享引用和资源归属还有哪些缺口。检查结果不等于销毁批准，本页没有清理执行按钮。</p></div>
      <button type="button" :disabled="loading || locked || !job" @click="loadReview">{{ loading ? '正在核查…' : '读取当前检查清单' }}</button>
    </header>
    <p v-if="!job" class="empty">先选择学校和模块。存在退出任务后，才能查看该任务的检查清单；不会为检查自动创建退出或冻结任务。</p>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <p v-if="loading" role="status">正在读取所选学校、模块代次和任务版本，旧检查结果已清除。</p>
    <template v-if="report">
      <div class="readonly-note" role="status"><strong>检查已返回 · 仍禁止物理清理</strong>
        <span>任务 #{{ report.jobId }} · 代次 {{ report.moduleGeneration }} · 任务版本 {{ report.jobVersion }}</span>
        <small>采集时间：{{ report.capturedAt }}（UTC）；这是即时只读视图，不是持久化验收或审批凭证。</small></div>
      <div class="risk-grid">
        <article><strong>{{ report.fileRisk?.logicalModuleFileCount ?? '未提供' }}</strong><span>逻辑关联文件</span></article>
        <article><strong>{{ report.fileRisk?.legalHoldFileCount ?? '未提供' }}</strong><span>保全文件</span></article>
        <article><strong>{{ report.fileRisk?.crossModuleReferencedFileCount ?? '未提供' }}</strong><span>其他模块仍引用</span></article>
        <article><strong>{{ report.fileRisk?.activeReservationCount ?? '未提供' }}</strong><span>未释放容量预留</span></article>
      </div>
      <div class="blocker-groups">
        <article v-for="group in groups" :key="group.label" class="blocker-group"><h4>{{ group.label }}</h4>
          <div v-for="(row, index) in group.rows" :key="`${row.code}:${index}`" class="blocker-row">
            <strong>{{ row.message }}</strong><small>{{ row.code }}<template v-if="row.count != null"> · {{ row.count }} 项</template></small>
            <details v-if="row.tables?.length"><summary>查看相关资源（{{ row.tables.length }}）</summary><p class="resource-list">{{ row.tables.join('、') }}</p></details>
          </div>
        </article>
      </div>
      <details class="inventory"><summary>查看模块资源候选（{{ candidates.length }}）；不是删除白名单</summary>
        <p>仅反映代码元数据中的候选。具备学校和代次字段不代表已经完成归属审查；SQL 动态资源仍可能未覆盖。</p>
        <div class="table-scroll"><table><thead><tr><th>候选资源</th><th>范围核验状态</th><th>清理授权</th></tr></thead><tbody>
          <tr v-for="row in visibleCandidates" :key="row.table"><td>{{ row.table }}</td><td>{{ selectorLabel(row.selectorStatus) }}</td><td>未授权</td></tr>
        </tbody></table></div>
        <div class="pager"><button type="button" :disabled="page === 1" @click="page--">上一页</button><span>{{ page }} / {{ Math.max(1, Math.ceil(candidates.length / 15)) }}</span><button type="button" :disabled="page * 15 >= candidates.length" @click="page++">下一页</button></div>
      </details>
      <p class="preserve">共享学校、账号、角色权限、学生主档、学院、专业和班级始终保留。检查摘要：<code>{{ report.preflightDigest }}</code></p>
      <button type="button" @click="$emit('focus-delivery')">回到交付、签收与保留办理区</button>
    </template>
  </section>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { moduleCommerceApi as api } from '@/modules/platform/api/moduleCommerce.api'
import { blockerGroup, exitReviewScope, validateExitReview } from '../../lib/moduleCommerceWorkbench.mjs'

const props = defineProps({ tenantId: { type: String, default: '' }, job: { type: Object, default: null }, locked: Boolean })
defineEmits(['focus-delivery'])
const report = ref(null), loading = ref(false), error = ref(''), page = ref(1)
let requestSeq = 0
const currentKey = () => JSON.stringify([props.tenantId, props.job?.jobId, props.job?.moduleKey, props.job?.moduleGeneration, props.job?.version])
const candidates = computed(() => report.value?.moduleTableInventory?.candidateTables || [])
const visibleCandidates = computed(() => candidates.value.slice((page.value - 1) * 15, page.value * 15))
const groups = computed(() => {
  const result = new Map()
  for (const row of report.value?.blockers || []) {
    const label = blockerGroup(row.code)
    if (!result.has(label)) result.set(label, [])
    result.get(label).push(row)
  }
  return [...result].map(([label, rows]) => ({ label, rows }))
})
const selectorLabel = (value) => ({
  NO_TENANT_SELECTOR_BLOCKED: '缺少学校范围，已阻断',
  TENANT_ONLY_SELECTOR_REVIEW_REQUIRED: '仅有学校范围，代次归属待审',
  TENANT_AND_GENERATION_SELECTOR_PRESENT: '有学校与代次字段，仍须逐项审核'
})[value] || '未知，保持阻断'

watch(currentKey, () => { requestSeq++; report.value = null; error.value = ''; loading.value = false; page.value = 1 })
async function loadReview() {
  if (props.locked || !props.job) return
  const seq = ++requestSeq, key = currentKey()
  report.value = null; error.value = ''; page.value = 1; loading.value = true
  try {
    const scope = exitReviewScope(props.tenantId, props.job)
    const data = await api.getExitReview(scope.tenantId, scope.jobId, {
      expectedGeneration: scope.expectedGeneration, expectedVersion: scope.expectedVersion
    })
    if (seq !== requestSeq || key !== currentKey()) return
    report.value = validateExitReview(data, scope)
  } catch (e) {
    if (seq === requestSeq && key === currentKey()) error.value = e.message || '未取得可核验检查结果，请刷新任务后重试'
  } finally { if (seq === requestSeq && key === currentKey()) loading.value = false }
}
onBeforeUnmount(() => { requestSeq++ })
</script>
<style scoped>
.exit-review{display:grid;gap:16px;background:#fff;border:1px solid #dce5f0;border-radius:16px;padding:24px;color:#21354e;scroll-margin-top:90px}.exit-review header{display:flex;justify-content:space-between;align-items:start;gap:18px;flex-wrap:wrap}h3{font-size:20px;margin:6px 0}h4{margin:0 0 12px}p,small{font-size:13px;line-height:1.7;color:#63748a}.eyebrow{font-size:11px;font-weight:700;color:#3b67a8;letter-spacing:1px}button{padding:9px 12px;border:1px solid #ccd8e8;border-radius:8px;background:#fff;color:#355274;cursor:pointer;min-height:38px}button:disabled{opacity:.5;cursor:not-allowed}.readonly-note,.empty,.error{padding:14px;border-radius:9px}.readonly-note{display:grid;gap:6px;background:#fff7e8;color:#865e1c}.empty{background:#f4f7fb}.error{background:#fff0f0;color:#a93d3d}.risk-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.risk-grid article{padding:14px;background:#f4f7fb;border-radius:10px}.risk-grid strong,.risk-grid span{display:block}.risk-grid strong{font-size:24px}.risk-grid span{font-size:12px;margin-top:5px}.blocker-groups{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.blocker-group{border:1px solid #e4e9f0;padding:16px;border-radius:10px}.blocker-row{border-top:1px solid #edf0f5;padding:12px 0;font-size:13px;line-height:1.7}.blocker-row small{display:block;color:#7b8899;font-size:11px}.resource-list,code{overflow-wrap:anywhere;word-break:break-word}.inventory{border:1px solid #e4e9f0;border-radius:10px;padding:14px}summary{cursor:pointer;font-size:13px;font-weight:600;line-height:1.7}.table-scroll{overflow:auto}table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:10px;border-bottom:1px solid #e8edf4;white-space:nowrap}th{background:#f4f7fb}.pager{display:flex;gap:14px;align-items:center;margin-top:12px}.preserve{border-left:3px solid #3b67a8;padding:10px 14px;background:#f5f9ff}button:focus-visible,summary:focus-visible{outline:2px solid #2563eb;outline-offset:3px}@media(max-width:800px){.exit-review{padding:16px}.blocker-groups{grid-template-columns:1fr}.risk-grid{grid-template-columns:repeat(2,1fr)}}
</style>
