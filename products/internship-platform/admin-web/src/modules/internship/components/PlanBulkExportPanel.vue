<template>
  <section class="plan-bulk" aria-labelledby="plan-bulk-title">
    <header class="plan-bulk__header">
      <div><h3 id="plan-bulk-title">批量导出实习计划</h3><p>跨页选择最多100份计划；导出保存或发布的正式版本，不包含未保存的编辑。</p></div>
      <AppButton variant="ghost" @click="$emit('close')">收起批量导出</AppButton>
    </header>
    <p v-if="!canExport" role="alert">当前账号无实习计划导出权限。</p>
    <template v-else>
      <form class="plan-bulk__search" @submit.prevent="bulk.search()">
        <label for="plan-bulk-keyword">计划名称、编号或批次</label>
        <input id="plan-bulk-keyword" v-model="s.keyword" maxlength="100" :disabled="!!s.exporting" placeholder="输入关键词检索计划" />
        <AppButton :disabled="s.loading || !!s.exporting" @click="bulk.search()">检索计划</AppButton>
      </form>
      <p v-if="s.loading" role="status">正在读取可导出的计划…</p>
      <div v-else-if="s.error" class="plan-bulk__error" role="alert"><p>{{ s.error }}</p><AppButton @click="bulk.load()">重试计划列表</AppButton></div>
      <template v-else>
        <p v-if="!s.rows.length">本页没有当前权限下可导出的计划。{{ s.hasMore ? '可继续下一页或调整检索。' : '请调整检索，或先保存实习计划。' }}</p>
        <div v-else class="plan-bulk__table-wrap">
          <table><caption>当前权限下的实习计划</caption><thead><tr>
            <th><input type="checkbox" aria-label="选择本页计划" :checked="s.rows.every(row => bulk.selected(row.id))" :disabled="!!s.exporting" @change="bulk.togglePage()" /></th>
            <th>计划名称 / 编号</th><th>所属批次 / 专业</th><th>状态 / 版本</th>
          </tr></thead><tbody><tr v-for="row in s.rows" :key="row.id">
            <td><input type="checkbox" :aria-label="`选择计划 ${row.planTitle} ${row.planNo}`" :checked="bulk.selected(row.id)" :disabled="!!s.exporting" @change="bulk.toggle(row)" /></td>
            <td><strong>{{ row.planTitle }}</strong><small>{{ row.planNo || '未登记计划编号' }}</small></td>
            <td>{{ row.batchName }}<small>{{ row.majorName || '未登记专业' }}</small></td>
            <td>{{ row.planStatus === 'PUBLISHED' ? '已发布' : '草稿' }}<small>V{{ row.version }}</small></td>
          </tr></tbody></table>
        </div>
      </template>
      <div class="plan-bulk__actions">
        <span>第 {{ s.page }} 页 · 本页 {{ s.rows.length }} 份 · 已选 {{ s.selected.length }} / 100 份</span>
        <AppButton variant="ghost" :disabled="s.loading || !!s.exporting || s.page <= 1" @click="bulk.load(s.page - 1)">上一页计划</AppButton>
        <AppButton variant="ghost" :disabled="s.loading || !!s.exporting || !s.hasMore" @click="bulk.load(s.page + 1)">下一页计划</AppButton>
      </div>
      <details v-if="s.selected.length" class="plan-bulk__selection">
        <summary>查看已选 {{ s.selected.length }} 份计划（检索、翻页不会清空）</summary>
        <div v-for="row in s.selected" :key="row.id"><span>{{ row.planTitle }} · {{ row.planNo }}</span><button type="button" :disabled="!!s.exporting" :aria-label="`移除计划 ${row.planNo}`" @click="bulk.remove(row.id)">移除</button></div>
      </details>
      <p v-if="s.exportError" class="plan-bulk__error" role="alert">{{ s.exportError }}</p>
      <p v-if="s.receipt" class="plan-bulk__receipt" role="status">已生成 {{ s.receipt.count }} 份计划的 {{ s.receipt.format }}，已发起下载：{{ s.receipt.filename }}</p>
      <div class="plan-bulk__actions">
        <AppButton :disabled="blocked" :loading="s.exporting === 'pdf'" @click="bulk.exportSelected('pdf')">批量导出 PDF</AppButton>
        <AppButton :disabled="blocked" :loading="s.exporting === 'xlsx'" @click="bulk.exportSelected('xlsx')">批量导出 Excel</AppButton>
        <AppButton variant="ghost" :disabled="!!s.exporting || !s.selected.length" @click="bulk.clear()">清空计划选择</AppButton>
      </div>
      <p class="plan-bulk__note">导出时重新核验权限和计划。任何一份失效或无权读取都会明确报错，不会悄悄漏导；失败后选择保留。</p>
    </template>
  </section>
</template>

<script setup>
import { computed, reactive, watch, onBeforeUnmount } from 'vue'
import { AppButton } from '@/components/ui'
import { planApi } from '@/modules/internship/api/plan-insurance.api'
import { downloadXlsxFromApi } from '@/utils/xlsxDownload'
import { createPlanBulkExport } from '@/modules/internship/composables/planBulkExport'
const props = defineProps({ canExport: Boolean, ctx: { type: Object, required: true } })
defineEmits(['close'])
const bulk = createPlanBulkExport({ reactive,
  loadPage: params => planApi.getExportOptions(params),
  exportFile: (format, ids) => format === 'pdf' ? planApi.bulkExportPdf(ids) : planApi.bulkExportXlsx(ids),
  download: data => downloadXlsxFromApi(data), canExport: () => props.canExport })
const s = bulk.state
const blocked = computed(() => !props.canExport || !!s.exporting || s.loading || !!s.error || !s.selected.length)
watch(() => [props.ctx, props.canExport], () => { bulk.reset(); if (props.canExport) bulk.load(1) }, { deep: true, immediate: true })
onBeforeUnmount(() => bulk.destroy())
</script>

<style scoped>
.plan-bulk { margin: 12px 0 20px; padding: 20px; background: var(--bg-card, white); border: 1px solid var(--border-light, #ddd); border-radius: 12px; }
.plan-bulk__header,.plan-bulk__actions { display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:12px; }
.plan-bulk h3 { margin:0 0 8px; font-size:18px; }
.plan-bulk p { line-height:1.7; margin:8px 0; }
.plan-bulk__search { display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin:16px 0; }
.plan-bulk__search input { flex:1; min-width:160px; padding:9px 12px; border:1px solid var(--border-light, #ddd); border-radius:8px; }
.plan-bulk__table-wrap { overflow-x:auto; }
.plan-bulk table { width:100%; border-collapse:collapse; }
.plan-bulk caption { text-align:left; margin-bottom:8px; font-weight:600; }
.plan-bulk th,.plan-bulk td { text-align:left; padding:10px 12px; border-bottom:1px solid var(--border-light, #ddd); vertical-align:top; overflow-wrap:anywhere; }
.plan-bulk th:first-child,.plan-bulk td:first-child { width:32px; }
.plan-bulk small { display:block; margin-top:5px; color:var(--text-secondary, #666); }
.plan-bulk input[type=checkbox] { width:18px; height:18px; }
.plan-bulk__selection { margin:12px 0; }.plan-bulk__selection summary { cursor:pointer; padding:8px 0; }
.plan-bulk__selection div { display:flex; gap:12px; justify-content:space-between; padding:6px 0; }.plan-bulk__selection span { overflow-wrap:anywhere; }
.plan-bulk__error { color:var(--color-danger, #b42318); }.plan-bulk__receipt { color:var(--color-success, #067647); }
.plan-bulk__note { font-size:12px; color:var(--text-secondary, #666); }
@media(max-width:600px) {
  .plan-bulk { padding:12px; }.plan-bulk__search label { width:100%; }
  .plan-bulk th,.plan-bulk td { padding:8px 5px; font-size:12px; }
  .plan-bulk__actions > span { width:100%; }.plan-bulk__selection div { align-items:flex-start; }
}
</style>
