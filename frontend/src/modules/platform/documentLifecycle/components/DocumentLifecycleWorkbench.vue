<template>
  <section class="plat-c-workbench" aria-label="文档智能与学生生命周期">
    <header>
      <div><p class="eyebrow">PLAT-C</p><h2>文档比较与学生里程碑</h2></div>
      <p class="hint">所有结果按源版本实时授权；任一侧失权后比较结果不可读取。</p>
    </header>

    <div class="grid">
      <article class="panel">
        <h3>不可变版本</h3>
        <form class="inline" @submit.prevent="loadVersions">
          <label>FileAsset ID <input v-model.trim="assetId" inputmode="numeric" required /></label>
          <button :disabled="busy">读取授权版本</button>
        </form>
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <div v-if="versions.length" class="versions">
          <label v-for="item in versions" :key="item.fileVersionId">
            <input v-model="selected" type="checkbox" :value="item.fileVersionId"
              :disabled="selected.length >= 2 && !selected.includes(item.fileVersionId)" />
            <span>V{{ item.versionNo }}</span><small>{{ item.ext }} · {{ size(item.sizeBytes) }}</small>
          </label>
        </div>
        <div class="actions">
          <button :disabled="selected.length !== 1 || busy" @click="extractSelected">抽取文本</button>
          <button :disabled="selected.length !== 2 || busy" @click="compareSelected">比较所选版本</button>
          <button v-if="jobId" :disabled="busy" @click="refreshJob">刷新处理状态</button>
        </div>
        <p v-if="jobId" class="status">任务 {{ jobId }}：{{ jobStatus }}</p>
        <dl v-if="comparison?.summary" class="summary">
          <div v-for="key in ['added','removed','modified','unchanged']" :key="key">
            <dt>{{ key }}</dt><dd>{{ comparison.summary[key] || 0 }}</dd>
          </div>
        </dl>
        <ol v-if="comparison?.changes?.length" class="changes">
          <li v-for="(change, index) in comparison.changes" :key="index">
            <strong>{{ change.status }}</strong>
            <span>段落 {{ change.left?.paragraph || '—' }} → {{ change.right?.paragraph || '—' }}</span>
          </li>
        </ol>
      </article>

      <article class="panel">
        <h3>跨域里程碑</h3>
        <form class="inline" @submit.prevent="loadTimeline">
          <label>Student ID <input v-model.trim="studentId" inputmode="numeric" required /></label>
          <label>模块 <input v-model.trim="sourceModule" placeholder="全部" /></label>
          <button :disabled="busy">读取</button>
        </form>
        <ol class="timeline">
          <li v-for="item in timeline" :key="item.id">
            <time>{{ formatTime(item.eventTime) }}</time>
            <div><strong>{{ item.title }}</strong><p>{{ item.summary || item.factType }}</p></div>
            <button disabled title="等待 typed navigation adapter">打开</button>
          </li>
        </ol>
        <p v-if="!busy && timelineLoaded && !timeline.length" class="empty">当前授权范围内暂无里程碑。</p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'
import { documentLifecycleApi as api } from '../api/document-lifecycle.api'

const props = defineProps({ initialStudentId: { type: [String, Number], default: '' } })
const assetId = ref('')
const studentId = ref(String(props.initialStudentId || ''))
const sourceModule = ref('')
const versions = ref([])
const selected = ref([])
const timeline = ref([])
const timelineLoaded = ref(false)
const busy = ref(false)
const error = ref('')
const jobId = ref('')
const jobStatus = ref('')
const comparison = ref(null)
const selectedVersions = computed(() => selected.value.map(id => versions.value.find(v => v.fileVersionId === id)).filter(Boolean))

async function run(task) {
  busy.value = true; error.value = ''
  try { return await task() } catch (e) { error.value = e?.message || '请求失败'; throw e } finally { busy.value = false }
}
async function loadVersions() {
  const data = await run(() => api.versions(assetId.value))
  versions.value = data?.items || []; selected.value = []
}
async function extractSelected() {
  const source = selectedVersions.value[0]
  const data = await run(() => api.extract(source.fileVersionId, source.sourceSha256))
  jobId.value = data.jobId; jobStatus.value = data.status
}
async function compareSelected() {
  const data = await run(() => api.compare(selectedVersions.value[0], selectedVersions.value[1]))
  jobId.value = data.jobId; jobStatus.value = data.status; comparison.value = null
}
async function refreshJob() {
  const data = await run(() => api.job(jobId.value)); jobStatus.value = data.status
  if (data.status === 'SUCCEEDED' && data.result?.compareResultId) {
    comparison.value = await run(() => api.comparison(data.result.compareResultId))
  }
}
async function loadTimeline() {
  const data = await run(() => api.lifecycle(studentId.value, { sourceModule: sourceModule.value || undefined, pageSize: 50 }))
  timeline.value = data?.items || []; timelineLoaded.value = true
}
const size = bytes => `${Math.max(0, Number(bytes || 0) / 1024).toFixed(1)} KB`
const formatTime = value => value ? new Date(value).toLocaleString('zh-CN') : '—'
</script>

<style scoped>
.plat-c-workbench{display:grid;gap:20px}.plat-c-workbench>header{display:flex;justify-content:space-between;gap:24px;align-items:end}.eyebrow{margin:0;color:#2563eb;font-weight:700;letter-spacing:.12em}.plat-c-workbench h2{margin:4px 0 0}.hint{max-width:520px;color:#64748b}.grid{display:grid;grid-template-columns:1fr 1fr;gap:18px}.panel{border:1px solid #e2e8f0;border-radius:14px;background:#fff;padding:20px;box-shadow:0 8px 24px #0f172a0a}.inline{display:flex;gap:10px;align-items:end;flex-wrap:wrap}.inline label{display:grid;gap:5px;color:#475569;font-size:13px}.inline input{border:1px solid #cbd5e1;border-radius:8px;padding:9px}.panel button{border:0;border-radius:8px;background:#1d4ed8;color:#fff;padding:9px 13px}.panel button:disabled{background:#94a3b8}.versions{display:grid;gap:8px;margin:16px 0}.versions label{display:flex;gap:10px;align-items:center;border:1px solid #e2e8f0;border-radius:9px;padding:10px}.versions small{margin-left:auto;color:#64748b}.actions{display:flex;gap:8px;flex-wrap:wrap}.status,.empty{color:#64748b}.error{color:#b91c1c}.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.summary div{background:#f8fafc;border-radius:8px;padding:8px}.summary dt{font-size:12px;color:#64748b}.summary dd{margin:3px 0 0;font-weight:700}.changes,.timeline{display:grid;gap:10px;padding:0;list-style:none}.changes li,.timeline li{display:flex;align-items:center;gap:12px;border-top:1px solid #f1f5f9;padding-top:10px}.timeline time{width:138px;color:#64748b;font-size:12px}.timeline div{flex:1}.timeline p{margin:3px 0;color:#64748b}@media(max-width:900px){.grid{grid-template-columns:1fr}.plat-c-workbench>header{align-items:start;flex-direction:column}}
</style>
