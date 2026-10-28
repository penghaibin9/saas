<template>
  <div class="sp-page material-page">
    <section class="sp-card"><div class="sp-panel__head"><h1>实习材料</h1><button type="button" class="sp-btn sp-btn--ghost" :disabled="!!busyId" @click="returnHome">返回本批次实习</button></div><p>盖章企业鉴定表请提交到学校发布的对应收件任务。材料与学生、教师移动端共用同一原单；上传成功后仍需提交审核。</p><p v-if="batchName">当前批次：{{ batchName }}</p><button type="button" class="sp-btn sp-btn--ghost" :disabled="!!busyId" @click="load">刷新收件任务与办理结果</button></section>
    <StateBlock v-if="loading" type="loading" text="正在读取本人材料收件任务…" />
    <section v-else-if="error" class="sp-card"><StateBlock type="error" :text="error" /><button type="button" class="sp-btn" @click="load">重新读取</button></section>
    <section v-else-if="candidates.length && !context.internshipId" class="sp-card"><h2>请选择实习批次</h2><button v-for="candidate in candidates" :key="candidate.recordId" type="button" class="sp-btn sp-btn--ghost" @click="selectBatch(candidate.batchId)">{{ candidate.batchName || '实习批次' }}</button></section>
    <StateBlock v-else-if="!items.length" type="empty" text="当前批次暂无适用的材料任务。若需上传盖章企业鉴定表，请联系指导教师发布对应收件要求。" />
    <template v-else><p v-if="historyMode" class="sp-card">当前为历史实习，材料与审核记录只读。</p>
      <section v-for="item in items" :key="item.id" class="sp-card material-object">
        <div class="sp-panel__head"><h2>{{ item.materialName }}</h2><StatusTag :text="statusText(item.submission?.status)" /></div><p>{{ item.description || '请按学校要求上传本人材料。' }}</p><p>{{ item.isRequired ? '必交' : '选交' }} · {{ item.minFiles }}～{{ item.maxFiles }}份 · 截止：{{ item.dueAt ? String(item.dueAt).replace('T',' ').slice(0,16) : '学校未设置' }}</p><p>允许格式：{{ formatText(item.allowedExtensions) }}</p>
        <button v-if="item.template" type="button" class="sp-btn sp-btn--ghost" :disabled="!!busyId" @click="downloadTemplate(item)">下载学校模板（第{{ item.template.versionNo }}版）</button>
        <p v-if="item.submission?.reviewComment" class="material-feedback">教师意见：{{ item.submission.reviewComment }}</p><p v-if="draft(item).receipt" role="status">{{ draft(item).receipt }}</p><p v-if="draft(item).error" role="alert">{{ draft(item).error }}</p>
        <div v-if="item.submission" class="material-original"><h3>原单已提交材料 · 第{{ item.submission.version }}版</h3><p v-for="file in item.submission.files || []" :key="file.fileId">{{ file.fileName || '材料附件' }} · 第{{ file.versionNo }}版 <button type="button" class="sp-btn sp-btn--ghost" :disabled="!!busyId" @click="openFile(item,file)">查看附件</button></p><p>{{ nextStep(item) }}</p></div>
        <div v-if="draft(item).conflict" class="material-feedback"><p>原单已变化，本次文件已保留。请读取最新原单并明确核对后继续。</p><button type="button" class="sp-btn" :disabled="!!busyId" @click="readLatest(item)">读取最新原单</button><template v-if="draft(item).latest"><p>最新状态：{{ statusText(draft(item).latest.submission?.status) }} · 第{{ draft(item).latest.submission?.version ?? 0 }}版</p><button v-if="editable(draft(item).latest)" type="button" class="sp-btn" @click="acceptLatest(item)">已核对，保留本次文件继续</button><p v-else>学校已推进办理，不能覆盖当前原单。</p></template></div>
        <div v-if="editable(item) && !draft(item).committed" class="material-upload"><h3>{{ item.submission?.status==='RETURNED' ? '按意见补正原单' : '本次待提交材料' }}</h3><p v-for="file in draft(item).files" :key="file.fileId">{{ file.fileName }} · {{ file.statusText }} <button type="button" class="sp-btn sp-btn--ghost" :disabled="!!busyId" @click="removeFile(item,file.fileId)">移除</button></p><label v-if="draft(item).files.length<item.maxFiles">添加材料文件<input type="file" :accept="(item.allowedExtensions || []).map(ext=>'.'+ext).join(',')" :disabled="!!busyId || draft(item).conflict" @change="upload(item,$event)" /></label><div class="material-actions"><button v-if="draft(item).files.length" type="button" class="sp-btn sp-btn--ghost" :disabled="!!busyId" @click="refreshFiles(item)">读取文件安全检查</button><button type="button" class="sp-btn" :disabled="!!busyId || draft(item).conflict || !ready(item)" @click="submit(item)">{{ busyId===item.id ? '正在办理…' : item.submission?.status==='RETURNED' ? '补正后重交原单' : '提交指导教师审核' }}</button></div></div>
      </section>
    </template>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { internshipCoreApi } from '../../services/internshipCoreApi'
import { fileSdk } from '../../services/fileSdk'
import { refreshScanFiles } from '../../services/fileScanState'
import { currentSessionGeneration } from '../../services/request'
import { useSessionStore } from '../../stores/session'
const route=useRoute(),router=useRouter(),session=useSessionStore()
const identity=computed(()=>JSON.stringify([session.user?.tenantId,session.user?.userId,session.user?.roleCode]))
const loading=ref(true),error=ref(''),items=ref([]),candidates=ref([]),batchName=ref(''),historyMode=ref(false),busyId=ref(''),context=ref({batchId:'',internshipId:''}),drafts=reactive({})
let alive=true,sequence=0,draftScope='',draftIdentity=''
const statusText=s=>({SUBMITTED:'待教师审核',APPROVED:'已审核通过',RETURNED:'已退回补正',DRAFT:'草稿',WITHDRAWN:'已撤回'})[s] || (s?'状态待核对':'未提交')
function nextStep(item){return ({SUBMITTED:'已交指导教师审核，请稍后刷新原单。',APPROVED:'教师已通过，正式材料版本保留。',RETURNED:'请阅读教师意见，补充本次文件并重交同一原单。'})[item.submission?.status]||'按学校要求准备材料，提交后交指导教师审核。'}
function formatText(exts=[]){const labels={jpg:'图片',jpeg:'图片',png:'图片',webp:'图片',pdf:'可打印文档',doc:'文字文档',docx:'文字文档',xls:'电子表格',xlsx:'电子表格',zip:'压缩文件',rar:'压缩文件'};return [...new Set(exts.map(ext=>labels[ext]||'学校指定格式'))].join('、')||'以学校收件要求为准'}
function capture(){return {sequence,generation:currentSessionGeneration(),identity:identity.value,batch:context.value.batchId,record:context.value.internshipId}}
function current(t){return alive&&t.sequence===sequence&&t.generation===currentSessionGeneration()&&t.identity===identity.value&&t.batch===context.value.batchId&&t.record===context.value.internshipId}
function draft(item){const id=String(item.id);if(!drafts[id])drafts[id]={files:[],expectedVersion:item.submission?.version ?? 0,conflict:false,latest:null,committed:false,error:'',receipt:''};return drafts[id]}
function editable(item){return !historyMode.value && (!item.submission || ['DRAFT','RETURNED','WITHDRAWN'].includes(item.submission.status))}
function ready(item){const files=draft(item).files;return files.length>=item.minFiles&&files.length<=item.maxFiles&&files.every(file=>file.readyForBusiness===true)}
function returnHome(){router.push({path:'/internship',query:context.value.batchId?{batchId:context.value.batchId}:{}})}
function selectBatch(id){router.replace({path:'/internship/materials',query:{batchId:String(id)}})}
function validateRows(data){if(!Array.isArray(data))throw Error('材料收件任务读取结果不完整，请重试');if(data.some(item=>String(item.batchId)!==context.value.batchId||!/^[1-9]\d*$/.test(String(item.id||''))))throw Error('材料任务与当前批次不一致，请重新读取');return data}
async function load(){
  sequence++;loading.value=true;error.value='';busyId.value='';items.value=[];candidates.value=[]
  const account=identity.value,generation=currentSessionGeneration(),seq=sequence,raw=route.query.batchId
  const valid=()=>alive&&seq===sequence&&generation===currentSessionGeneration()&&account===identity.value
  if(raw!==undefined&&(typeof raw!=='string'||!/^[1-9]\d*$/.test(raw))){loading.value=false;error.value='实习批次定位无效，请从本人实习首页进入';return}
  let batch=raw||'';if(!batch)try{batch=sessionStorage.getItem('student_portal_internship_batch_v1')||''}catch{ /* 由本人首页选择批次。 */ }
  try{
    const dashboard=await portalApi.internshipMy(batch);if(!valid())return
    if(!dashboard||typeof dashboard.hasData!=='boolean')throw Error('实习上下文读取结果不完整')
    const scope=JSON.stringify([account,dashboard.batchId,dashboard.recordId]);if(draftScope!==scope){Object.keys(drafts).forEach(key=>delete drafts[key]);draftScope=scope}
    context.value={batchId:String(dashboard.batchId||''),internshipId:String(dashboard.recordId||'')};historyMode.value=dashboard.historyMode===true;batchName.value=dashboard.batchName||'';candidates.value=Array.isArray(dashboard.candidates)?dashboard.candidates:[]
    if(!dashboard.hasData||dashboard.needSelect)return
    if(!/^[1-9]\d*$/.test(context.value.batchId)||!/^[1-9]\d*$/.test(context.value.internshipId))throw Error('当前实习记录定位不完整')
    const data=await internshipCoreApi.materialRequirements(context.value);if(!valid())return;items.value=validateRows(data)
    for(const item of items.value){const d=draft(item);if(d.committed){d.files=[];d.committed=false;d.expectedVersion=item.submission?.version??0}else if(d.files.length&&d.expectedVersion!==(item.submission?.version??0)){d.conflict=true;d.latest=item}else if(!d.files.length&&!d.conflict)d.expectedVersion=item.submission?.version??0}
  }catch(e){if(valid())error.value=e?.message||'材料读取失败，原文件仍保留，请重试'}finally{if(valid())loading.value=false}
}
async function upload(item,event){
  const file=event.target.files?.[0];event.target.value='';if(!file||busyId.value||!editable(item)||draft(item).conflict)return
  const ext=file.name.split('.').pop().toLowerCase(),d=draft(item);if((item.allowedExtensions||[]).length&&!item.allowedExtensions.includes(ext)){d.error='文件格式不符合学校当前收件要求，原文件已保留';return}
  if(d.files.length>=item.maxFiles)return;const t=capture();busyId.value=item.id;d.error=''
  try{const uploaded=await fileSdk.upload(file,{bizType:'INTERNSHIP_CUSTOM_MATERIAL'});if(!current(t))return;if(!/^[1-9]\d*$/.test(String(uploaded?.fileId||'')))throw Error('上传未返回有效文件编号');d.files.push(uploaded)}catch(e){if(current(t))d.error=e?.message||'上传未完成，已选材料保留'}finally{if(current(t))busyId.value=''}
}
function removeFile(item,id){if(!busyId.value)draft(item).files=draft(item).files.filter(file=>file.fileId!==id)}
async function refreshFiles(item){
  if(busyId.value)return;const t=capture(),d=draft(item);busyId.value=item.id;d.error=''
  try{const files=await refreshScanFiles(d.files,id=>fileSdk.metadata(id),()=>current(t));if(files)d.files=files}catch(e){if(current(t))d.error=e?.message||'安全检查读取失败，文件已保留'}finally{if(current(t))busyId.value=''}
}
async function submit(item){
  const d=draft(item);if(busyId.value||!editable(item)||d.conflict||d.committed||!ready(item))return
  const t=capture();busyId.value=item.id;d.error='';d.receipt=''
  try{
    const result=await internshipCoreApi.submitMaterial(item.id,{...context.value,fileIds:d.files.map(file=>String(file.fileId)),expectedVersion:d.expectedVersion,comment:item.submission?.status==='RETURNED'?'按审核意见重新提交':'学生提交'})
    if(!current(t))return;d.committed=true;d.receipt='材料已提交，下一步由指导教师审核。'
    if(String(result?.requirementId)!==String(item.id)||String(result?.internshipId)!==t.record||String(result?.batchId)!==t.batch)throw Error('提交已发送，但原单回执未能核对，请刷新任务；不要重复提交')
    item.submission=result
    const data=await internshipCoreApi.materialRequirements(context.value);if(!current(t))return;items.value=validateRows(data)
    const saved=items.value.find(row=>String(row.id)===String(item.id));if(!saved?.submission||String(saved.submission.id)!==String(result.id))throw Error('提交已成功，原单最新结果暂未读回，请刷新任务核对')
    d.files=[];d.expectedVersion=saved.submission.version;d.committed=false
  }catch(e){if(current(t)){d.error=e?.message||'提交未完成，文件已保留';if(!d.committed)d.conflict=e?.bizCode==='DATA_CONFLICT'||e?.status===409}}
  finally{if(current(t))busyId.value=''}
}
async function readLatest(item){
  if(busyId.value)return;const t=capture(),d=draft(item);busyId.value=item.id
  try{const data=await internshipCoreApi.materialRequirements(context.value);if(!current(t))return;d.latest=validateRows(data).find(row=>String(row.id)===String(item.id))||null;if(!d.latest)d.error='该收件要求已变化或不再适用，请联系指导教师核对'}catch(e){if(current(t))d.error=e?.message||'原单读取失败，文件仍保留'}finally{if(current(t))busyId.value=''}
}
function acceptLatest(item){const d=draft(item);if(!d.latest||!editable(d.latest))return;const latest=d.latest;Object.assign(item,latest);d.expectedVersion=latest.submission?.version??0;d.conflict=false;d.latest=null;d.error='已保留本次文件，请再次核对后提交'}
async function openFile(item,file){
  if(busyId.value||!item.submission?.files?.some(row=>String(row.fileId)===String(file.fileId)))return;const t=capture(),d=draft(item);busyId.value=item.id
  try{const meta=await fileSdk.metadata(String(file.fileId));if(!current(t))return;if(String(meta.fileId)!==String(file.fileId)||!meta.readyForBusiness||!meta.canDownload)throw Error('当前材料尚未安全可用或无权查看');await fileSdk.download(meta.fileId,meta.fileName||file.fileName||'实习材料')}catch(e){if(current(t))d.error=e?.message||'材料无法查看，请重试'}finally{if(current(t))busyId.value=''}
}
async function downloadTemplate(item){if(busyId.value||!item.template)return;const t=capture();busyId.value=item.id;try{await internshipCoreApi.materialTemplate(context.value,item.id,item.template.fileName||'学校材料模板',item.template.versionId)}catch(e){if(current(t))draft(item).error=e?.message||'模板下载失败，请重试'}finally{if(current(t))busyId.value=''}}
watch(()=>[route.query.batchId,identity.value],()=>{if(draftIdentity!==identity.value){Object.keys(drafts).forEach(key=>delete drafts[key]);draftScope='';draftIdentity=identity.value}load()},{immediate:true,flush:'sync'})
onBeforeUnmount(()=>{alive=false;sequence++})
</script>
<style scoped>.material-page{display:grid;gap:16px}.material-page h1{font-size:22px;margin:0}.material-page h2{font-size:18px;margin:0}.material-page h3{font-size:15px}.material-page p{line-height:1.8;overflow-wrap:anywhere}.material-page .sp-panel__head{display:flex;justify-content:space-between;align-items:center;gap:16px}.material-object{display:grid;gap:10px}.material-original,.material-feedback{padding:14px;background:var(--bg2);border:1px solid var(--line);border-radius:8px}.material-feedback{color:var(--warn-fg)}.material-actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:14px}.material-upload label{display:flex;gap:12px;align-items:center;flex-wrap:wrap}.material-upload input{font:inherit;max-width:100%}.material-page button{min-height:40px}</style>
