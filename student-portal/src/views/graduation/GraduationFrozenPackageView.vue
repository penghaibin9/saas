<template>
  <section class="package-page">
    <header><p>冻结证据</p><h1>我的毕业归档包</h1><span>文件内容来自归档时固定的材料版本和业务快照，后续姓名、课题或流程变化不会改写历史包。</span></header>
    <div v-if="loading" class="state">正在读取归档包状态…</div>
    <div v-else-if="error" class="state error">{{ error }}<button type="button" @click="load">重试</button></div>
    <article v-else class="package-card">
      <div><small>包状态</small><strong>{{ statusText }}</strong><p v-if="data.manifestId">Manifest #{{ data.manifestId }} · revision {{ data.revision }} · {{ data.digestSchemaVersion }}</p></div>
      <button v-if="data.artifact?.fileId" type="button" :disabled="downloading" @click="download">{{ downloading ? '下载中…' : '通过文件中心下载' }}</button>
      <p v-else class="hint">{{ data.packageStatus === 'LEGACY_UNAVAILABLE' ? '该历史归档继续沿用原有导出入口。' : '归档完成后系统会生成冻结包，请稍后刷新。' }}</p>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { portalApi } from '@/services/portalApi'
import fileSdk from '@/services/fileSdk'

const data = ref({})
const loading = ref(true)
const downloading = ref(false)
const error = ref('')
const statusText = computed(() => ({ AVAILABLE: '可下载', SUCCEEDED: '可下载', PENDING: '等待生成', RUNNING: '正在生成', RETRY: '等待重试', NOT_FROZEN: '尚未归档', LEGACY_UNAVAILABLE: '历史归档' }[data.value.packageStatus] || data.value.packageStatus || '暂无'))
async function load() { loading.value = true; error.value = ''; try { data.value = await portalApi.graduationFrozenPackage() } catch (e) { error.value = e?.message || '归档包状态加载失败' } finally { loading.value = false } }
async function download() { downloading.value = true; try { const file = data.value.artifact; await fileSdk.download(file.fileId, file.fileName) } catch (e) { error.value = e?.message || '下载失败' } finally { downloading.value = false } }
onMounted(load)
</script>

<style scoped>
.package-page{display:grid;gap:18px;padding:26px}.package-page header,.package-card{padding:24px;border:1px solid #dbe5f0;border-radius:16px;background:#fff}.package-page header{background:linear-gradient(135deg,#f7fbff,#edf5ff)}header p{margin:0;color:#1769e0;font-size:12px;font-weight:800;letter-spacing:.12em}header h1{margin:5px 0 8px}header span,.package-card p{color:#6d7b8e}.package-card{display:flex;align-items:center;justify-content:space-between;gap:20px}.package-card small,.package-card strong{display:block}.package-card strong{margin-top:5px;font-size:22px}.package-card button,.state button{border:0;border-radius:9px;background:#1769e0;color:#fff;padding:11px 17px;cursor:pointer}.state{padding:30px;text-align:center;border:1px dashed #cbd7e5;border-radius:14px}.state.error{color:#ba2929}.state button{margin-left:12px}.hint{max-width:420px}@media(max-width:700px){.package-card{display:grid}}
</style>
