<template>
  <div class="profile-page">
    <div class="profile-page__topbar"><div><p>岗位实习中心</p><h1>实习档案</h1></div><button type="button" @click="router.push({path:'/internship/selection',query:route.query})">返回原招聘季选岗</button></div>
    <StateBlock v-if="loading" type="loading" text="正在读取本人实习档案…" />
    <div v-else-if="error" class="page-state page-state--error"><p>{{ error }}</p><button type="button" @click="load">重新读取</button></div>
    <div v-else class="profile-content">
      <p v-if="actionError" role="alert">{{ actionError }}</p><p v-if="receipt" role="status">{{ receipt }}</p>
      <p v-if="readWarning" role="status">{{ readWarning }} <button type="button" :disabled="busy" @click="reread">重新读取办理结果</button></p>
      <section v-if="conflict" class="page-state"><p>实习档案已变化，本次输入仍保留。先读取最新档案并核对，再决定继续。</p><button type="button" :disabled="busy" @click="readLatest">读取最新档案</button><template v-if="latestProfile"><p>最新第{{ latestProfile.version }}版：{{ latestProfile.selfIntroduction || '未填写自我介绍' }}；{{ latestProfile.strengths || '未填写个人优势' }}</p><button type="button" @click="acceptLatest">已核对，保留本次填写继续</button></template></section>
      <InternshipProfileEditor :key="scopeKey" :profile="profile" :completeness="completeness" :items="items" :busy="busy || committed || conflict" :saved-item-version="savedItemVersion" @save="saveProfile" @add-item="addItem" @update-item="updateItem" @delete-item="deleteItem" @open-file="openEvidence" />
      <MaterialSharePreview :preview="preview" :loading="previewLoading" :error="previewError" :contact-sharing-mode="contactSharingMode" :confirmed="previewConfirmed" :pdf-busy="pdfBusy" :pdf-url="pdfUrl" @refresh="loadPreview" @pdf-preview="generatePdfPreview" @update:contact-sharing-mode="contactSharingMode=$event" @update:confirmed="previewConfirmed=$event" />
    </div>
  </div>
</template>
<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import InternshipProfileEditor from '../../components/recruitment/InternshipProfileEditor.vue'
import MaterialSharePreview from '../../components/recruitment/MaterialSharePreview.vue'
import { normalizeInternshipProfile, normalizeProfileCompleteness, normalizeProfileItems } from '../../modules/internshipRecruitment/profileModel'
import { buildPdfPreviewRequest, normalizeMaterialPreview } from '../../modules/internshipRecruitment/materialPreviewModel'
import { internshipSelectionApi } from '../../services/internshipSelectionApi'
import { fileSdk } from '../../services/fileSdk'
import { currentSessionGeneration } from '../../services/request'
import { systemConfirm } from '../../services/systemDialog'
import { useSessionStore } from '../../stores/session'
const router=useRouter(), route=useRoute(), session=useSessionStore()
const scopeKey=computed(()=>JSON.stringify([session.user?.tenantId,session.user?.userId,route.query.batchId,route.query.campaignId,route.query.recordId]))
const selectionApi=computed(()=>internshipSelectionApi.forScope(route.query))
const loading=ref(true),busy=ref(false),error=ref(''),actionError=ref(''),readWarning=ref(''),receipt=ref(''),committed=ref(false)
const profile=ref(normalizeInternshipProfile()),completeness=ref(normalizeProfileCompleteness()),items=ref([]),savedItemVersion=ref(0)
const preview=ref(normalizeMaterialPreview()),previewLoading=ref(false),previewError=ref(''),contactSharingMode=ref('MASKED_ONLY'),previewConfirmed=ref(false),pdfBusy=ref(false),pdfUrl=ref('')
const conflict=ref(false),latestProfile=ref(null)
let alive=true,requestSeq=0,previewRequestSeq=0
function capture(){return {sequence:requestSeq,generation:currentSessionGeneration(),scope:scopeKey.value,api:selectionApi.value}}
function current(t){return alive && t.sequence===requestSeq && t.generation===currentSessionGeneration() && t.scope===scopeKey.value}
function clearPdf(){if(pdfUrl.value)URL.revokeObjectURL(pdfUrl.value);pdfUrl.value=''}
function accept(data){profile.value=normalizeInternshipProfile(data||{});items.value=normalizeProfileItems(data||{})}
async function readReadiness(t){
  completeness.value=normalizeProfileCompleteness();readWarning.value=''
  try{const data=await t.api.profileCompleteness();if(current(t))completeness.value=normalizeProfileCompleteness(data||{})}
  catch(e){if(current(t))readWarning.value=e?.message||'暂无法核对本轮材料要求，可先维护本人档案。'}
}
async function load(){
  requestSeq++;previewRequestSeq++;clearPdf();let t
  try{t=capture()}catch(e){loading.value=false;error.value=e?.message||'原招聘季定位不完整';return}
  loading.value=true;error.value='';actionError.value='';readWarning.value='';receipt.value='';busy.value=false;committed.value=false;conflict.value=false;latestProfile.value=null
  profile.value=normalizeInternshipProfile();items.value=[];preview.value=normalizeMaterialPreview();previewConfirmed.value=false
  try{const data=await t.api.profile();if(!current(t))return;accept(data);loading.value=false;await readReadiness(t);if(current(t))await loadPreview()}
  catch(e){if(current(t))error.value=e?.message||'档案读取失败，请重试'}finally{if(current(t))loading.value=false}
}
async function loadPreview(){
  const t=capture(),seq=++previewRequestSeq;previewLoading.value=true;previewError.value='';previewConfirmed.value=false;clearPdf()
  try{const data=await t.api.profilePreview();if(current(t)&&seq===previewRequestSeq){preview.value=normalizeMaterialPreview(data||{});if(!preview.value.allowedContactSharingModes.includes(contactSharingMode.value))contactSharingMode.value=''}}
  catch(e){if(current(t)&&seq===previewRequestSeq){preview.value=normalizeMaterialPreview();previewError.value=e?.message||'当前招聘季预览暂不可用'}}
  finally{if(current(t)&&seq===previewRequestSeq)previewLoading.value=false}
}
async function reread(){
  if(busy.value)return;const t=capture();busy.value=true;actionError.value=''
  try{const data=await t.api.profile();if(!current(t))return;accept(data);committed.value=false;await readReadiness(t);if(current(t))await loadPreview()}
  catch(e){if(current(t))actionError.value=e?.message||'结果读取失败，请重试；无需重复提交'}finally{if(current(t))busy.value=false}
}
async function mutate(task,label,itemWrite=false){
  if(busy.value||committed.value||conflict.value)return
  const t=capture();busy.value=true;actionError.value='';receipt.value=''
  try{
    const result=await task(t.api);if(!current(t))return
    committed.value=true;receipt.value=label+'已保存，历史投递材料仍保留。';accept(result)
    if(itemWrite)savedItemVersion.value++
    try{const data=await t.api.profile();if(!current(t))return;accept(data);committed.value=false;await readReadiness(t);if(current(t))await loadPreview()}
    catch(e){if(current(t))readWarning.value='办理已保存，最新结果暂未读回，请重新读取核对，不要重复提交。'}
  }catch(e){if(current(t)){actionError.value=e?.message||'保存未完成，填写内容和附件已保留';conflict.value=e?.bizCode==='DATA_CONFLICT'||e?.status===409;latestProfile.value=null}}
  finally{if(current(t))busy.value=false}
}
function saveProfile(body){return mutate(api=>api.updateProfile(body),'实习档案')}
function addItem(body){return mutate(api=>api.createProfileItem(body),'证明材料',true)}
function updateItem(body){if(!items.value.some(item=>item.id===String(body.id)&&item.sourceType==='STUDENT_ENTERED'))return;return mutate(api=>api.updateProfileItem(body.id,body),'证明材料',true)}
async function deleteItem(item){
  if(item?.sourceType!=='STUDENT_ENTERED'||busy.value)return
  const t=capture();if(!await systemConfirm({title:'删除本人的材料条目',message:'本次删除不影响历史投递材料快照。确认删除“'+item.title+'”？',confirmText:'删除材料'})||!current(t))return
  return mutate(api=>api.deleteProfileItem(item.id),'材料删除')
}
async function readLatest(){
  if(busy.value||!conflict.value)return;const t=capture();busy.value=true
  try{const data=await t.api.profile();if(current(t))latestProfile.value=normalizeInternshipProfile(data)}catch(e){if(current(t))actionError.value=e?.message||'最新档案读取失败，原输入保留'}finally{if(current(t))busy.value=false}
}
function acceptLatest(){if(!conflict.value||!latestProfile.value)return;profile.value.version=latestProfile.value.version;conflict.value=false;latestProfile.value=null;actionError.value=''}
async function openEvidence(fileId){
  const id=String(fileId),t=capture();if(!items.value.some(item=>item.fileIds.includes(id)))return
  try{const meta=await fileSdk.metadata(id);if(!current(t))return;if(String(meta.fileId)!==id||!meta.readyForBusiness||!meta.canDownload)throw Error('证明附件尚未安全可用或无权查看，请重新读取检查结果');await fileSdk.download(id,meta.fileName||'实习证明附件')}
  catch(e){if(current(t))actionError.value=e?.message||'附件无法查看，请重试'}
}
async function generatePdfPreview(){
  if(pdfBusy.value)return;const t=capture(),seq=previewRequestSeq;pdfBusy.value=true;previewError.value=''
  try{
    const result=await t.api.profilePdfPreview(buildPdfPreviewRequest({previewHash:preview.value.previewHash,contactSharingMode:contactSharingMode.value}))
    if(!current(t)||seq!==previewRequestSeq)return
    if(!/^[1-9]\d*$/.test(String(result?.fileId||'')))throw Error('档案预览文件编号缺失，请重试')
    const meta=await fileSdk.metadata(String(result.fileId));if(!current(t)||seq!==previewRequestSeq)return
    if(String(meta.fileId)!==String(result.fileId)||!meta.readyForBusiness||!meta.canDownload)throw Error('档案预览尚未安全可用，请稍后重新生成预览')
    const blob=await fileSdk.fetchPreviewBlob(result.fileId);if(!current(t)||seq!==previewRequestSeq)return;clearPdf();pdfUrl.value=URL.createObjectURL(blob)
  }catch(e){if(current(t)&&seq===previewRequestSeq)previewError.value=e?.message||'档案预览生成失败'}finally{if(current(t)&&seq===previewRequestSeq)pdfBusy.value=false}
}
watch(scopeKey,load,{immediate:true})
onBeforeUnmount(()=>{alive=false;requestSeq++;previewRequestSeq++;clearPdf()})
</script>
<style scoped>
.profile-page { min-height:100%; padding:20px; background:#f7f8fa; }
.profile-page__topbar { display:flex; align-items:flex-end; justify-content:space-between; gap:16px; margin-bottom:14px; }
.profile-page__topbar p { margin:0 0 4px; color:#2f6bff; font-size:12px; font-weight:600; }
.profile-page__topbar h1 { margin:0; color:#1a1a1a; font-size:24px; }
.profile-page__topbar button { border:1px solid #d9d9d9; border-radius:7px; padding:8px 12px; background:#fff; color:#2f6bff; cursor:pointer; }
.page-state { display:flex; align-items:center; justify-content:center; gap:10px; min-height:220px; padding:20px; border:1px solid #eef0f3; border-radius:12px; background:#fff; color:#8c8c8c; }
.page-state--error { flex-direction:column; border-color:#ffccc7; background:#fff2f0; color:#a8071a; }
.page-state button { border:0; border-radius:6px; padding:7px 12px; background:#2f6bff; color:#fff; cursor:pointer; }
.profile-content { display:grid; gap:14px; }
@media (max-width:899px) { .profile-page { padding:12px; } }
</style>
