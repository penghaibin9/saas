<template>
  <section class="cb-workspace" aria-label="整批建教室">
    <header class="cb-heading"><div><p class="cb-eyebrow">教室资源 / 整批建库</p><h2>{{ mode === 'import' ? '导入教室台账' : mode === 'resume' ? '教室建库批次' : '按楼层批量建教室' }}</h2><p>统一设置，核对例外，再整批入库。已有编号保留原资料。</p></div><AppButton :disabled="busy" @click="$emit('close')">返回教室资源</AppButton></header>
    <nav class="cb-steps" aria-label="建库进度"><span v-for="(label, index) in ['设置建库规则', '预检与核对', '入库结果']" :key="label" :class="{ active: step === index + 1, done: step > index + 1 }"><b>{{ index + 1 }}</b>{{ label }}</span></nav>
    <AppInlineAlert v-if="error" type="danger" :description="error" />
    <AppInlineAlert v-if="pendingBatch" type="warning" title="入库结果待确认" description="已发出本批确认请求。请只查询正式结果，不要重复入库。" />
    <AppButton v-if="pendingBatch" :disabled="busy" @click="queryResult">重新查询入库结果</AppButton>
    <AppInlineAlert v-if="step === 2 && preview && !preview.createCount && !preview.errorCount" type="info" title="本批全部保留，无需创建" description="所有编号已有记录，原资料保持；可下载核对清单后返回教室资源。" />
    <form v-if="step === 1 && mode === 'generate'" class="cb-setup" @submit.prevent="generate">
      <div class="cb-card"><div class="cb-section"><h3>01 所在教学楼</h3><div class="cb-building"><OfficeBuilding /><div><strong>{{ building.buildingName }}</strong><p>{{ building.campusCode || '校区未填写' }} · 编码 {{ building.buildingCode }} · 共 {{ building.floorCount }} 层</p></div></div></div>
        <div class="cb-section"><h3>02 楼层与编号规则</h3><div class="cb-fields">
          <label>起始楼层<input v-model.number="rules.startFloor" type="number" min="1" :max="building.floorCount" required></label><label>结束楼层<input v-model.number="rules.endFloor" type="number" :min="rules.startFloor" :max="building.floorCount" required></label>
          <label>每层教室数<input v-model.number="rules.roomsPerFloor" type="number" min="1" max="100" required></label><label>流水号起始值<input v-model.number="rules.startSequence" type="number" min="0" max="9999" required></label>
          <label>编号前缀<input v-model="rules.prefix" maxlength="20" placeholder="可不填，如 A-"></label><label>流水号位数<select v-model.number="rules.digits"><option v-for="n in 4" :key="n" :value="n">{{ n }} 位</option></select></label>
          <label class="cb-wide">跳过的完整教室编号<input v-model="excluded" placeholder="如 104, 204；多个编号用逗号隔开"><small>楼梯间、设备间等不生成教室；特殊房型可在下一步单独修改。</small></label>
        </div></div>
        <div class="cb-section"><h3>03 统一教室属性</h3><div class="cb-fields"><label>教室类型<select v-model="rules.roomType"><option v-for="t in types" :key="t.value" :value="t.value">{{ t.label }}</option></select></label><label>教学座位<input v-model.number="rules.capacity" type="number" min="0" max="1000" required></label><label>考试座位<input v-model="rules.examSeats" type="number" min="0" max="1000" placeholder="按实际考位填写；可留空"><small>留空时沿用教学座位，不做折半；0 会按零考位保存。</small></label><label class="cb-check"><input v-model="rules.isExclusive" type="checkbox">专用教室（自动排课跳过）</label><label class="cb-check"><input v-model="rules.allowSchedule" type="checkbox">允许排课</label><label class="cb-check"><input v-model="rules.allowExam" type="checkbox">允许排考</label><label class="cb-check"><input v-model="rules.allowBorrow" type="checkbox">开放借用</label><p class="cb-wide cb-rule-note">三项用途规则彼此独立；资源状态、占用和专用教室规则仍分别生效。</p></div></div>
      </div><aside class="cb-card cb-summary"><span>编号示例</span><strong>{{ example }}</strong><p>前缀 + 楼层 + 流水号</p><hr><span>计划生成</span><strong>{{ planned }}<small> 间</small></strong><p>预检会扣除跳过编号和已有教室。每批最多 1,000 间。</p><AppButton variant="primary" :disabled="busy || planned < 1 || planned > 1000" @click="generate">{{ busy ? '正在预检…' : '生成预检清单' }}</AppButton></aside>
    </form>
    <section v-else-if="step === 1" class="cb-card cb-import"><h3>用现有 Excel 台账一次导入</h3><p>先建立教学楼，再填写楼栋编码、楼层、教室编号及容量。编号列使用文本格式，保留 0101 等前导零。</p><AppButton :disabled="busy" @click="downloadTemplate">下载 xlsx 模板</AppButton><label class="cb-upload">选择教室台账<input type="file" accept=".xlsx" :disabled="busy" @change="upload"><span>{{ busy ? '正在读取并预检…' : '支持 .xlsx，最多 1,000 行、5 MB；上传只预检，不直接入库。' }}</span></label></section>
    <template v-else-if="step === 2 && preview">
      <div class="cb-preview-head"><div><h3>核对本批 {{ preview.total }} 行教室</h3><p><b>{{ preview.createCount }}</b> 间待建 · {{ preview.keepCount }} 间保留 · <strong :class="{ 'cb-error': preview.errorCount }">{{ preview.errorCount }} 行需修正</strong></p></div><div><AppButton :disabled="busy" @click="downloadResult">下载核对清单</AppButton><AppButton :disabled="busy" @click="step = 1">返回修改{{ mode === 'generate' ? '规则' : '文件' }}</AppButton></div></div>
      <p class="cb-note">可取消不需要的行，并直接修正楼层、编号、类型、实际座位和三项用途规则。修改后须重新预检。KEEP 行展示正式原值且不可修改。</p>
      <div class="cb-table-wrap"><table><thead><tr><th>纳入</th><th>楼栋 / 楼层</th><th>教室编号 / 名称</th><th>类型</th><th>教学 / 考试座位</th><th>用途规则</th><th>预检结果</th></tr></thead><tbody><tr v-for="item in visibleItems" :key="item.line" :class="{ 'cb-keep': item.action === 'KEEP' }">
        <td><input v-model="item.selected" type="checkbox" :aria-label="`纳入第${item.line}行`" :disabled="busy || item.action === 'KEEP'" @change="dirty = true"></td>
        <td><span>{{ item.edit.buildingCode }}</span><input v-model="item.edit.floorNo" type="number" min="1" max="100" :aria-label="`第${item.line}行楼层`" :disabled="busy || item.action === 'KEEP'" @input="dirty = true"></td>
        <td><input v-model="item.edit.roomCode" maxlength="50" :aria-label="`第${item.line}行教室编号`" :disabled="busy || item.action === 'KEEP'" @input="dirty = true"><input v-model="item.edit.roomName" maxlength="100" placeholder="名称可不填" :aria-label="`第${item.line}行教室名称`" :disabled="busy || item.action === 'KEEP'" @input="dirty = true"></td>
        <td><select v-model="item.edit.roomType" :aria-label="`第${item.line}行类型`" :disabled="busy || item.action === 'KEEP'" @change="dirty = true"><option v-for="t in types" :key="t.value" :value="t.value">{{ t.label }}</option></select></td>
        <td><div class="cb-seats"><input v-model="item.edit.capacity" type="number" min="0" max="1000" :aria-label="`第${item.line}行教学座位`" :disabled="busy || item.action === 'KEEP'" @input="dirty = true"><input v-model="item.edit.examSeats" type="number" min="0" max="1000" placeholder="留空沿用教学座位" :aria-label="`第${item.line}行考试座位`" :disabled="busy || item.action === 'KEEP'" @input="dirty = true"></div></td><td><div class="cb-rules"><label>排课<select v-model="item.edit.allowSchedule" :aria-label="`第${item.line}行允许排课`" :disabled="busy || item.action === 'KEEP'" @change="dirty = true"><option :value="null" disabled>未提供</option><option :value="true">允许</option><option :value="false">禁止</option></select></label><label>排考<select v-model="item.edit.allowExam" :aria-label="`第${item.line}行允许排考`" :disabled="busy || item.action === 'KEEP'" @change="dirty = true"><option :value="null" disabled>未提供</option><option :value="true">允许</option><option :value="false">禁止</option></select></label><label>借用<select v-model="item.edit.allowBorrow" :aria-label="`第${item.line}行开放借用`" :disabled="busy || item.action === 'KEEP'" @change="dirty = true"><option :value="null" disabled>未提供</option><option :value="true">开放</option><option :value="false">关闭</option></select></label></div></td><td><span :class="{ 'cb-error': item.action === 'ERROR' }">{{ item.message }}</span></td>
      </tr></tbody></table></div>
      <div class="cb-pager"><span>每页 20 行 · 第 {{ page }} / {{ pages }} 页</span><AppButton :disabled="page === 1" @click="page--">上一页</AppButton><AppButton :disabled="page >= pages" @click="page++">下一页</AppButton></div>
      <footer class="cb-footer"><span>{{ dirty ? '清单已修改，请重新预检后再入库。' : '确认后创建待建教室，已有资料原样保留。' }}</span><AppButton v-if="dirty || preview.errorCount" variant="primary" :disabled="busy || Boolean(pendingBatch)" @click="recheck">{{ busy ? '正在预检…' : '重新预检所选教室' }}</AppButton><AppButton v-else variant="primary" :disabled="busy || Boolean(pendingBatch) || !preview.createCount || invalidBatch" @click="confirm">{{ busy ? '正在整批入库…' : `确认创建 ${preview.createCount} 间教室` }}</AppButton></footer>
    </template>
    <section v-else-if="step === 3 && result" class="cb-card cb-result" role="status"><CircleCheck /><h3>{{ result.createdCount }} 间教室已入库</h3><p>保留已有 {{ result.keptCount }} 间。现在可以查看楼层教室及其排课、排考、借用规则。</p><small>批次 {{ result.batchNo }}</small><small>办理时间：{{ result.completedAt || '服务端未提供' }}</small><div><AppButton @click="downloadResult">下载入库结果</AppButton><AppButton variant="primary" @click="$emit('complete')">查看教室资源</AppButton></div></section>
  </section>
</template>
<script setup>
import { computed, ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { AppButton } from '@/components/ui'
import { AppInlineAlert } from '@/components/common'
import { OfficeBuilding, CircleCheck } from '@element-plus/icons-vue'
import { classroomCatalogApi as api, downloadClassroomFile } from '../api/academic-classroom-catalog.api'
import { isDeniedResult, isConflictResult, isMissingResult } from './parallel-a/resultState'
const props = defineProps({ building: { type: Object, default: null }, mode: { type: String, default: 'generate' }, initialBatchId: { type: String, default: '' } })
const emit = defineEmits(['close', 'complete', 'batch'])
const types = [{ value: 'LECTURE', label: '普通教室' }, { value: 'MULTIMEDIA', label: '多媒体教室' }, { value: 'COMPUTER', label: '机房' }, { value: 'LAB', label: '实验室' }, { value: 'OTHER', label: '其他' }]
const rules = ref({ buildingId: props.building?.buildingId, startFloor: 1, endFloor: props.building?.floorCount || 1, roomsPerFloor: 10, startSequence: 1, digits: 2, prefix: '', capacity: 60, examSeats: '', roomType: 'MULTIMEDIA', isExclusive: false, allowSchedule: true, allowExam: true, allowBorrow: false })
const excluded = ref(''), step = ref(1), busy = ref(false), error = ref(''), preview = ref(null), result = ref(null), dirty = ref(false), page = ref(1)
const pendingBatch = ref(''), invalidBatch = ref(false)
const planned = computed(() => (rules.value.endFloor - rules.value.startFloor + 1) * rules.value.roomsPerFloor)
const example = computed(() => `${rules.value.prefix}${rules.value.startFloor}${String(rules.value.startSequence).padStart(rules.value.digits, '0')}`)
const pages = computed(() => Math.max(1, Math.ceil((preview.value?.items.length || 0) / 20)))
const visibleItems = computed(() => preview.value?.items.slice((page.value - 1) * 20, page.value * 20) || [])
let disposed = false, revision = 0
function handleError(e) {
  error.value = e.message || '操作未完成，已保留当前内容，请重新核对。'
  if (isDeniedResult(e)) {
    revision++; preview.value = null; result.value = null; pendingBatch.value = ''; step.value = 1; dirty.value = false; busy.value = false
    excluded.value = ''; rules.value = { ...rules.value, prefix: '' }
    error.value += '；已清除先前批次内容。'
  } else if (isConflictResult(e) || isMissingResult(e)) {
    invalidBatch.value = true; pendingBatch.value = ''; dirty.value = true
  }
}
async function run(action) {
  if (busy.value || disposed) return
  const runRevision = revision
  const current = () => !disposed && revision === runRevision
  busy.value = true; error.value = ''
  try { await action(current) } catch (e) { if (current()) handleError(e) }
  finally { if (current()) busy.value = false }
}
onBeforeUnmount(() => { disposed = true; revision++ })
onMounted(() => { if (props.initialBatchId) resume(props.initialBatchId) })
watch(() => props.initialBatchId, id => {
  // Emitting a newly previewed batch updates the parent's query; it is already current.
  if (!id || id === preview.value?.batchNo) return
  revision++; preview.value = null; result.value = null; pendingBatch.value = ''; busy.value = false; step.value = 1
  resume(id)
})
function resume(id) { return run(async current => { const saved = await api.batch(id); if (current()) { accept(saved); acceptResult(saved, id) } }) }
function accept(data) {
  if (disposed) return
  if (!data?.batchNo || !Array.isArray(data.items) || data.items.length > 1000) throw new Error('未返回有效的完整预检清单，请重新预检。')
  preview.value = { ...data, items: data.items.map(i => { const source = i.existing || i.row || i.input || {}; const recheckRow = i.row || i.input || {}; const edit = { ...source }; edit.roomType = types.find(t => t.label === edit.roomType)?.value || edit.roomType; edit.examSeats = edit.examSeats === undefined ? null : edit.examSeats; for (const key of ['allowSchedule', 'allowExam', 'allowBorrow']) edit[key] = typeof source[key] === 'boolean' ? source[key] : null; return { ...i, recheckRow: { ...recheckRow }, selected: i.action !== 'KEEP', edit } }) }
  step.value = 2; page.value = 1; dirty.value = false; invalidBatch.value = false; pendingBatch.value = ''; emit('batch', data.batchNo)
}
function acceptResult(saved, id) {
  if (saved?.status !== 'SUCCESS') return false
  if (String(saved.batchNo) !== String(id) || String(saved.result?.batchNo) !== String(id) || !Number.isInteger(saved.result?.createdCount)) throw new Error('入库回执与当前批次不一致，请重新查询。')
  result.value = saved.result; step.value = 3; pendingBatch.value = ''; invalidBatch.value = false; error.value = ''
  return true
}
function generate() {
  if (pendingBatch.value || !props.building?.buildingId || !Number.isInteger(planned.value) || planned.value < 1 || planned.value > 1000) { error.value = '请选择教学楼并设置 1–1000 间教室；结果待确认时请先查询原批次。'; return }
  return run(async current => { const data = await api.generate({ ...rules.value, buildingId: props.building.buildingId, examSeats: rules.value.examSeats === '' ? null : Number(rules.value.examSeats), excludeCodes: excluded.value.split(/[,，、\s]+/).filter(Boolean) }); if (current()) accept(data) })
}
function editableRow(edit) {
  return { ...edit, capacity: edit.capacity === '' ? null : Number(edit.capacity), examSeats: edit.examSeats === '' || edit.examSeats === null ? null : Number(edit.examSeats) }
}
function recheck() {
  if (pendingBatch.value || !preview.value) return
  const rows = preview.value.items.filter(i => i.selected || i.action === 'KEEP').map(i => i.action === 'KEEP' ? { ...i.recheckRow } : editableRow(i.edit))
  if (!rows.length || rows.length > 1000) { error.value = '请选择 1–1000 行重新预检。'; return }
  return run(async current => { const data = await api.preview(rows); if (current()) accept(data) })
}
function upload(event) {
  const file = event.target.files?.[0]
  if (!file || pendingBatch.value) return
  if (!/\.xlsx$/i.test(file.name) || file.size > 5 * 1024 * 1024) { error.value = '请选择不超过 5 MB 的 .xlsx 台账。'; return }
  return run(async current => { const data = await api.upload(file); if (current()) accept(data) })
}
function queryResult() {
  const id = pendingBatch.value || preview.value?.batchNo
  if (!id) return
  return run(async current => { const saved = await api.batch(id); if (current() && !acceptResult(saved, id)) error.value = '尚未读到正式入库结果，请稍后再次查询。不会自动重发确认。' })
}
function confirm() {
  if (pendingBatch.value) return queryResult()
  if (!preview.value?.batchNo || dirty.value || invalidBatch.value || preview.value.errorCount || !preview.value.createCount) return
  const id = preview.value.batchNo
  return run(async current => {
    const checked = await api.batch(id)
    if (!current()) return
    if (acceptResult(checked, id)) return
    if (String(checked.batchNo) !== String(id) || checked.status !== 'PREVIEW' || checked.errorCount || !checked.createCount || dirty.value || id !== preview.value?.batchNo) throw new Error('当前批次不能入库，请重新核对预检清单。')
    pendingBatch.value = id
    let commandError
    try { await api.confirm(id) } catch (e) { commandError = e }
    if (!current()) return
    if (commandError && (isDeniedResult(commandError) || isConflictResult(commandError) || isMissingResult(commandError))) throw commandError
    // Only GET after a lost command response; never automatically replay confirm.
    const saved = await api.batch(id)
    if (!current()) return
    if (!acceptResult(saved, id)) error.value = commandError?.message || '结果待确认，请再次查询正式入库结果。'
  })
}
function downloadTemplate() { return run(async () => downloadClassroomFile(await api.template(), '教室台账模板.xlsx')) }
function downloadResult() { return run(async () => downloadClassroomFile(await api.result(preview.value.batchNo), '教室建库核对结果.xlsx')) }
defineExpose({ busy, dirty })
</script>
<style scoped>
.cb-workspace{color:var(--text-primary);font-size:14px}.cb-heading{display:flex;align-items:center;justify-content:space-between;gap:20px}.cb-heading h2{font-size:24px;margin:4px 0 10px}.cb-heading p,.cb-summary p,.cb-note{color:var(--text-secondary);line-height:1.7}.cb-eyebrow{font-size:12px;margin:0}.cb-steps{display:flex;gap:36px;margin:24px 0;padding:18px 22px;background:var(--bg-card);border:1px solid var(--border-base);border-radius:10px}.cb-steps span{display:flex;align-items:center;gap:9px;color:var(--text-secondary)}.cb-steps b{display:grid;place-items:center;width:25px;height:25px;border-radius:50%;background:var(--bg-page,#f4f6fb);font-size:12px}.cb-steps .active{color:var(--pri);font-weight:600}.cb-steps .active b{background:var(--pri);color:#fff}.cb-steps .done b{color:var(--pri);background:var(--pri-bg)}.cb-setup{display:grid;grid-template-columns:minmax(0,1fr) 250px;gap:20px;align-items:start}.cb-card{background:var(--bg-card);border:1px solid var(--border-base);border-radius:12px;min-width:0}.cb-section{padding:22px 24px;border-bottom:1px solid var(--border-base)}.cb-section:last-child{border:0}.cb-section h3{font-size:15px;margin:0 0 18px}.cb-building{display:flex;gap:14px;align-items:center}.cb-building svg{width:32px;height:32px;color:var(--pri)}.cb-building p{margin:6px 0 0;color:var(--text-secondary);font-size:12px}.cb-fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px 22px}.cb-fields label{display:grid;gap:8px;font-size:13px;min-width:0}.cb-wide{grid-column:1/-1}.cb-workspace input:not([type=checkbox]):not([type=file]),.cb-workspace select{height:38px;box-sizing:border-box;width:100%;min-width:0;border:1px solid var(--border-base);border-radius:6px;padding:0 10px;color:var(--text-primary);background:var(--bg-card);font:inherit}.cb-workspace input:focus,.cb-workspace select:focus{outline:2px solid var(--pri);outline-offset:1px}.cb-workspace input[type=checkbox]{width:16px;height:16px;accent-color:var(--pri)}.cb-fields .cb-check{display:flex;gap:8px;align-items:center;padding-top:24px}.cb-fields small{font-size:12px;color:var(--text-secondary);line-height:1.6}.cb-summary{padding:24px;position:sticky;top:12px}.cb-summary>span{font-size:12px;color:var(--text-secondary)}.cb-summary>strong{display:block;font-size:30px;margin-top:12px;overflow-wrap:anywhere}.cb-summary small{font-size:14px;font-weight:400}.cb-summary p{font-size:12px}.cb-summary hr{border:0;border-top:1px solid var(--border-base);margin:22px 0}.cb-summary :deep(button){margin-top:16px;width:100%}.cb-import{padding:32px;max-width:800px;margin:auto}.cb-import p{line-height:1.8;color:var(--text-secondary)}.cb-upload{display:grid;gap:16px;border:1px dashed var(--border-base);background:var(--bg-page,#f5f8fe);padding:28px;margin-top:24px;border-radius:10px}.cb-upload span{font-size:12px;color:var(--text-secondary)}.cb-preview-head{display:flex;justify-content:space-between;gap:16px;align-items:center}.cb-preview-head h3{margin:0;font-size:18px}.cb-preview-head p{color:var(--text-secondary)}.cb-preview-head>div:last-child{display:flex;gap:8px}.cb-preview-head b{color:var(--pri)}.cb-error{color:var(--danger-500,#c93838)}.cb-table-wrap{overflow:auto;border:1px solid var(--border-base);border-radius:10px;background:var(--bg-card)}.cb-table-wrap table{border-collapse:collapse;min-width:850px;width:100%;font-size:13px}.cb-table-wrap th{background:var(--pri-bg);font-weight:500;text-align:left;padding:13px 12px}.cb-table-wrap td{padding:10px 12px;border-top:1px solid var(--border-base);vertical-align:middle;max-width:180px}.cb-table-wrap td:nth-child(2){width:90px}.cb-table-wrap td:nth-child(3){width:190px}.cb-table-wrap td:last-child{min-width:120px}.cb-table-wrap td>input+input{margin-top:5px}.cb-table-wrap td>span+input{margin-top:6px}.cb-seats{display:flex;gap:6px}.cb-seats input{max-width:80px}.cb-keep{background:var(--bg-page,#f8faff);color:var(--text-secondary)}.cb-keep input,.cb-keep select{opacity:.7}.cb-pager,.cb-footer{display:flex;align-items:center;justify-content:flex-end;gap:10px;margin-top:16px}.cb-pager span,.cb-footer span{font-size:12px;color:var(--text-secondary)}.cb-footer{justify-content:space-between;background:var(--bg-card);border:1px solid var(--border-base);padding:16px 20px;border-radius:10px;position:sticky;bottom:0}.cb-result{display:grid;justify-items:center;text-align:center;padding:48px 20px;gap:14px}.cb-result>svg{width:52px;height:52px;color:var(--success-500,#27845a)}.cb-result h3{font-size:24px;margin:0}.cb-result p,.cb-result small{color:var(--text-secondary);line-height:1.7;margin:0}.cb-result>div{display:flex;gap:12px;margin-top:18px}
.cb-rule-note{margin:0;color:var(--text-secondary);font-size:12px;line-height:1.7}.cb-table-wrap table{min-width:1080px}.cb-rules{display:grid;gap:5px;min-width:145px}.cb-rules label{display:grid;grid-template-columns:34px minmax(0,1fr);align-items:center;gap:6px;font-size:11px}.cb-rules select{height:30px}
@media(max-width:1200px){.cb-setup{grid-template-columns:1fr}.cb-summary{position:static;display:flex;align-items:center;gap:16px;flex-wrap:wrap}.cb-summary hr,.cb-summary>p:first-of-type{display:none}.cb-summary>strong{margin:0}.cb-summary :deep(button){width:auto;margin:0}}
@media(max-width:650px){.cb-heading,.cb-preview-head,.cb-footer{align-items:flex-start;flex-direction:column}.cb-steps{gap:14px;font-size:12px;padding:12px}.cb-steps span{gap:5px}.cb-fields{grid-template-columns:1fr}.cb-wide{grid-column:auto}.cb-section{padding:18px}.cb-fields .cb-check{padding-top:0}.cb-steps b{width:20px;height:20px}}
</style>
