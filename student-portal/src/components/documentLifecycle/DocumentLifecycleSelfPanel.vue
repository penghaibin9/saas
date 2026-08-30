<template>
  <section class="self-panel">
    <header><div><span>我的成长档案</span><h2>版本记录与里程碑</h2></div><button @click="loadMilestones">刷新里程碑</button></header>
    <p v-if="error" class="error">{{ error }}</p>
    <ol class="milestones">
      <li v-for="item in milestones" :key="item.id">
        <time>{{ new Date(item.eventTime).toLocaleDateString('zh-CN') }}</time>
        <div><strong>{{ item.title }}</strong><p>{{ item.summary || item.factType }}</p></div>
      </li>
    </ol>
    <form @submit.prevent="loadVersions">
      <label>文件资产编号 <input v-model.trim="assetId" required inputmode="numeric" /></label>
      <button>读取我有权访问的版本</button>
    </form>
    <div class="versions">
      <label v-for="version in versions" :key="version.fileVersionId">
        <input v-model="selected" type="checkbox" :value="version.fileVersionId"
          :disabled="selected.length >= 2 && !selected.includes(version.fileVersionId)" />
        V{{ version.versionNo }} · {{ version.ext }}
      </label>
      <button :disabled="selected.length !== 2 || busy" @click="startCompare">比较两版</button>
      <button v-if="jobId" :disabled="busy" @click="refreshJob">刷新任务 {{ jobStatus }}</button>
    </div>
    <dl v-if="summary" class="summary"><div v-for="(value,key) in summary" :key="key"><dt>{{ key }}</dt><dd>{{ value }}</dd></div></dl>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import api from '@/services/documentLifecycleApi'
const props = defineProps({ studentId: { type: [String, Number], required: true } })
const milestones=ref([]),versions=ref([]),selected=ref([]),assetId=ref(''),error=ref(''),jobId=ref(''),jobStatus=ref(''),summary=ref(null),busy=ref(false)
const picks=computed(()=>selected.value.map(id=>versions.value.find(v=>v.fileVersionId===id)).filter(Boolean))
async function run(fn){busy.value=true;error.value='';try{return await fn()}catch(e){error.value=e?.message||'加载失败';throw e}finally{busy.value=false}}
async function loadMilestones(){const data=await run(()=>api.milestones(props.studentId));milestones.value=data?.items||[]}
async function loadVersions(){const data=await run(()=>api.versions(assetId.value));versions.value=data?.items||[];selected.value=[]}
async function startCompare(){const data=await run(()=>api.compare(picks.value[0],picks.value[1]));jobId.value=data.jobId;jobStatus.value=data.status}
async function refreshJob(){const data=await run(()=>api.job(jobId.value));jobStatus.value=data.status;if(data.status==='SUCCEEDED'&&data.result?.compareResultId){summary.value=(await run(()=>api.comparison(data.result.compareResultId))).summary}}
onMounted(loadMilestones)
</script>

<style scoped>
.self-panel{display:grid;gap:16px;padding:20px;border:1px solid #e5e7eb;border-radius:16px;background:#fff}.self-panel header{display:flex;justify-content:space-between;align-items:center}.self-panel h2{margin:4px 0}.self-panel button{border:0;border-radius:9px;padding:10px 14px;background:#155eef;color:#fff}.self-panel button:disabled{background:#9ca3af}.milestones{list-style:none;padding:0;display:grid;gap:12px}.milestones li{display:flex;gap:14px;border-left:3px solid #60a5fa;padding-left:12px}.milestones time{color:#64748b}.milestones p{margin:4px 0;color:#64748b}.versions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.summary{display:flex;gap:12px}.summary div{background:#eff6ff;border-radius:8px;padding:8px 12px}.summary dd{margin:2px 0 0;font-weight:700}.error{color:#b91c1c}
</style>
