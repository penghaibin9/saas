<template>
  <section class="integrity-page">
    <header class="integrity-head">
      <div><p class="eyebrow">PLAT-A</p><h1>完整性异常中心</h1><p>只读探测冻结清单、文件版本链和物理对象；处置状态不会修改业务域数据。</p></div>
      <button type="button" :disabled="busy" @click="scan">{{ busy ? '巡检中…' : '执行有界巡检' }}</button>
    </header>
    <div class="integrity-filter">
      <select v-model="filters.status" @change="reload"><option value="">全部状态</option><option>OPEN</option><option>ACKNOWLEDGED</option><option>RESOLVED</option><option>IGNORED</option></select>
      <select v-model="filters.moduleCode" @change="reload"><option value="">全部模块</option><option value="GRADUATION">毕业设计</option></select>
      <span>游标分页 · 单页最多 100 条 · 深度 SHA 默认关闭</span>
    </div>
    <div class="integrity-metrics">
      <article><small>Critical</small><strong>{{ overview.critical || 0 }}</strong></article>
      <article><small>High</small><strong>{{ overview.high || 0 }}</strong></article>
      <article><small>Medium</small><strong>{{ overview.medium || 0 }}</strong></article>
      <article><small>Today New</small><strong>{{ overview.todayNew || 0 }}</strong></article>
      <article><small>7d Unresolved</small><strong>{{ overview.unresolved7d || 0 }}</strong></article>
    </div>
    <div v-if="overview.byModule?.length" class="module-strip"><span v-for="module in overview.byModule" :key="module.moduleCode">{{ module.moduleCode }} {{ module.count }}</span></div>
    <div v-if="notice" class="state notice">{{ notice }}</div>
    <div v-if="error" class="state error">{{ error }}</div>
    <div v-else-if="loading" class="state">正在读取异常投影…</div>
    <div v-else-if="!items.length" class="state">当前筛选下没有完整性异常。</div>
    <article v-for="item in items" v-else :key="item.id" class="integrity-row">
      <div class="integrity-main">
        <div class="integrity-title"><strong>{{ item.exceptionType }}</strong><span :class="`severity is-${item.severity.toLowerCase()}`">{{ item.severity }}</span><span class="status">{{ item.status }}</span></div>
        <p>{{ item.message }}</p>
        <small>{{ item.moduleCode || 'PLATFORM' }} · {{ item.subjectType }} #{{ item.subjectId }} · 首次 {{ item.firstDetectedAt || '—' }} · 最近 {{ item.lastDetectedAt || '—' }} · 累计 {{ item.occurrenceCount || 1 }} 次</small>
      </div>
      <div class="integrity-actions">
        <button v-if="item.target" type="button" @click="goTarget(item.target)">进入业务</button>
        <button v-if="item.manifestId" type="button" @click="downloadPackage(item)">冻结包</button>
        <button v-if="item.status === 'OPEN'" type="button" @click="transition(item, 'ACKNOWLEDGED')">确认</button>
        <button type="button" @click="recheck(item)">复检</button>
        <button v-if="item.status !== 'RESOLVED'" type="button" @click="transition(item, 'RESOLVED')">解决</button>
        <button v-if="item.status !== 'IGNORED'" type="button" @click="transition(item, 'IGNORED')">忽略</button>
      </div>
    </article>
    <button v-if="nextCursor" class="more" type="button" :disabled="loading" @click="loadMore">加载下一页</button>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import fileSdk from '@/services/file/fileSdk'
import { platformIntegrityApi } from '@/modules/system/api/platformIntegrity.api'

const items = ref([])
const nextCursor = ref(null)
const overview = ref({ critical: 0, high: 0, medium: 0, todayNew: 0, unresolved7d: 0, byModule: [] })
const loading = ref(false)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const filters = reactive({ status: '', moduleCode: '' })
const router = useRouter()

async function load(cursor = 0, append = false) {
  loading.value = true; error.value = ''; notice.value = ''
  try {
    const data = await platformIntegrityApi.list({ cursor, limit: 100, ...filters })
    items.value = append ? [...items.value, ...(data.items || [])] : (data.items || [])
    nextCursor.value = data.nextCursor || null
    overview.value = data.overview || overview.value
  } catch (e) { error.value = e?.message || '完整性异常加载失败' }
  finally { loading.value = false }
}
function reload() { return load(0, false) }
function loadMore() { return nextCursor.value ? load(nextCursor.value, true) : null }
async function scan() {
  busy.value = true; error.value = ''
  try { await platformIntegrityApi.scan({ detector: 'ALL', cursor: 0, limit: 100, deepSha: false, deepShaLimit: 0, timeoutMs: 2000 }); await reload() }
  catch (e) { error.value = e?.message || '巡检失败' }
  finally { busy.value = false }
}
async function transition(item, status) {
  try { await platformIntegrityApi.transition(item.id, { status, version: item.version, note: '' }); await reload() }
  catch (e) { error.value = e?.message || '状态更新失败' }
}
async function recheck(item) {
  try {
    const result = await platformIntegrityApi.recheck(item.id, { version: item.version, timeoutMs: 2000 })
    const message = result.probeStatus === 'CONCLUSIVE' ? '复检完成，异常投影已刷新。' : `复检未得出结论：${result.error || '探测器不可用'}`
    await reload()
    notice.value = message
  } catch (e) { error.value = e?.message || '复检失败' }
}
function goTarget(target) {
  if (!target?.routeName) return
  router.push({ name: target.routeName, params: target.routeParams || {}, query: target.query || {} }).catch(() => {})
}
async function downloadPackage(item) {
  try {
    let result = await platformIntegrityApi.packageStatus(item.manifestId)
    if (!result.artifact && !['LEGACY_UNAVAILABLE', 'UNAVAILABLE'].includes(result.packageStatus)) result = await platformIntegrityApi.buildPackage(item.manifestId)
    const artifact = result.artifact
    if (!artifact?.fileId) {
      notice.value = result.packageStatus === 'LEGACY_UNAVAILABLE' ? '历史清单保持原打包语义。' : result.packageStatus === 'UNAVAILABLE' ? '冻结包已失效或尚未通过安全检查，已禁止下载。' : `冻结包已进入任务队列（${result.packageStatus || 'PENDING'}），完成后可安全下载。`
      return
    }
    await fileSdk.download(artifact.fileId, artifact.fileName)
  } catch (e) { error.value = e?.message || '冻结包下载失败' }
}
onMounted(reload)
</script>

<style scoped>
.integrity-page{display:grid;gap:14px;padding:24px}.integrity-head{display:flex;align-items:flex-start;justify-content:space-between;gap:24px;padding:24px;border:1px solid #dbe5f2;border-radius:16px;background:linear-gradient(135deg,#f7fbff,#edf5ff)}.integrity-head h1{margin:2px 0 7px;font-size:25px}.integrity-head p{margin:0;color:#66758a}.eyebrow{font-size:12px!important;font-weight:800;color:#1769e0!important;letter-spacing:.12em}.integrity-head button,.integrity-actions button,.more{border:1px solid #b9cbe4;border-radius:8px;background:#fff;color:#1769e0;padding:9px 13px;cursor:pointer}.integrity-filter{display:flex;align-items:center;gap:10px;padding:12px 14px;border:1px solid #e1e8f0;border-radius:12px;background:#fff}.integrity-filter select{padding:8px;border:1px solid #d2dce8;border-radius:7px}.integrity-filter span{margin-left:auto;color:#7b8798;font-size:12px}.integrity-metrics{display:grid;grid-template-columns:repeat(5,minmax(110px,1fr));gap:10px}.integrity-metrics article{padding:14px;border:1px solid #e0e7ef;border-radius:12px;background:#fff}.integrity-metrics small,.integrity-metrics strong{display:block}.integrity-metrics small{color:#728096}.integrity-metrics strong{margin-top:5px;font-size:24px}.module-strip{display:flex;gap:8px;flex-wrap:wrap}.module-strip span{padding:5px 9px;border-radius:999px;background:#eef4fb;color:#45556b;font-size:12px}.integrity-row{display:flex;justify-content:space-between;gap:18px;padding:17px;border:1px solid #e0e7ef;border-radius:12px;background:#fff}.integrity-title{display:flex;align-items:center;gap:8px}.integrity-main p{margin:7px 0;color:#475467}.integrity-main small{color:#7b8798}.severity,.status{padding:3px 7px;border-radius:999px;background:#eef3f8;font-size:11px}.severity.is-critical,.severity.is-high,.severity.is-error{background:#fff0f0;color:#c53636}.severity.is-medium,.severity.is-warning{background:#fff7e6;color:#9a6300}.integrity-actions{display:flex;align-items:center;gap:7px;flex-wrap:wrap}.state{padding:28px;text-align:center;border:1px dashed #cbd7e5;border-radius:12px;color:#66758a}.state.error{color:#ba2929;background:#fff5f5}.state.notice{padding:12px;background:#f2f8ff;color:#245eaa}.more{justify-self:center}@media(max-width:800px){.integrity-head,.integrity-row{display:grid}.integrity-filter{flex-wrap:wrap}.integrity-filter span{width:100%;margin:0}.integrity-metrics{grid-template-columns:repeat(2,1fr)}}
</style>
