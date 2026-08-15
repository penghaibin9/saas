<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { uploadTemporaryFile } from '../services/request'

const MAX_LOGO_BYTES=5*1024*1024
const loading=ref(true),saving=ref(false),facadeReady=ref(false),error=ref(''),message=ref('')
const form=reactive({logoFileId:null,shortName:'',shortIntro:'',website:'',mainBusiness:'',establishedYear:null,address:''})
const school=reactive({qualificationStatus:'—',coopStatus:'—',accessValidUntil:'—',blacklist:false,schoolReview:'—'})
const logoFile=ref(null),logoPreview=ref(''),serverLogoUrl=ref(''),uploadedLogoFileId=ref(null)
const logoDisplay=computed(()=>logoPreview.value||serverLogoUrl.value||'')

function clearPreview(){if(logoPreview.value){URL.revokeObjectURL(logoPreview.value);logoPreview.value=''}}
function chooseLogo(event){
  error.value='';message.value=''
  if(!facadeReady.value){event.target.value='';error.value='学校端尚未开放企业资料编辑，当前不能上传 Logo';return}
  const file=event.target.files?.[0]||null
  if(!file)return
  if(!['image/png','image/jpeg','image/webp'].includes(file.type)){event.target.value='';error.value='Logo 仅支持 PNG、JPG 或 WebP';return}
  if(file.size>MAX_LOGO_BYTES){event.target.value='';error.value='Logo 文件不能超过 5MB';return}
  clearPreview();logoFile.value=file;uploadedLogoFileId.value=null;logoPreview.value=URL.createObjectURL(file)
}
function publicPatch(){return {shortName:form.shortName,shortIntro:form.shortIntro,website:form.website,mainBusiness:form.mainBusiness,establishedYear:form.establishedYear,address:form.address}}

onMounted(async()=>{
  try{
    const data=await enterpriseInternshipApi.company()
    facadeReady.value=true
    Object.assign(form,{logoFileId:data?.logoFileId??null,shortName:data?.shortName||'',shortIntro:data?.shortIntro||'',website:data?.website||'',mainBusiness:data?.mainBusiness||'',establishedYear:data?.establishedYear??null,address:data?.address||''})
    serverLogoUrl.value=data?.logoUrl||data?.logoPreviewUrl||''
    Object.assign(school,{qualificationStatus:data?.qualificationStatus||'—',coopStatus:data?.coopStatus||'—',accessValidUntil:data?.accessValidUntil||'—',blacklist:Boolean(data?.blacklist),schoolReview:data?.schoolReview||data?.reviewComment||'—'})
  }catch(e){facadeReady.value=false;error.value=e.message||'企业资料加载失败'}finally{loading.value=false}
})
onUnmounted(clearPreview)

async function save(){
  error.value='';message.value=''
  // Company GET/PUT 未冻结时必须在任何 File Center 上传之前 fail-closed，避免孤儿临时文件。
  if(!facadeReady.value){error.value='学校端尚未开放企业资料编辑，当前不能保存或上传 Logo';return}
  saving.value=true
  try{
    const patch=publicPatch()
    if(logoFile.value){
      if(!uploadedLogoFileId.value){
        const upload=await uploadTemporaryFile(logoFile.value,{bizType:'INTERNSHIP_ENTERPRISE_LOGO'})
        uploadedLogoFileId.value=upload.fileId
      }
      patch.logoFileId=uploadedLogoFileId.value
    }
    const saved=await enterpriseInternshipApi.updateCompany(patch)
    if(patch.logoFileId)form.logoFileId=patch.logoFileId
    if(saved?.logoUrl||saved?.logoPreviewUrl)serverLogoUrl.value=saved.logoUrl||saved.logoPreviewUrl
    clearPreview();logoFile.value=null;uploadedLogoFileId.value=null
    message.value='企业公开资料已保存'
  }catch(e){error.value=e.message||'保存失败'}finally{saving.value=false}
}
</script>
<template>
  <section class="ep-page">
    <div class="ep-page-head"><div><h1 class="ep-title">企业资料</h1><p class="ep-subtitle">维护学生能看到的企业公开介绍；学校准入结论始终只读。</p></div><button class="ep-btn ep-btn-primary" :disabled="loading||saving||!facadeReady" @click="save">{{ saving?'保存中…':'保存公开资料' }}</button></div>
    <div v-if="error" class="ep-error">{{ error }}</div><div v-if="message" class="notice">{{ message }}</div>
    <div class="grid">
      <div class="ep-card panel">
        <h2 class="ep-section-title">公开资料</h2>
        <fieldset class="profile-fields" :disabled="!facadeReady">
          <div class="logo-row">
            <div class="logo-preview"><img v-if="logoDisplay" :src="logoDisplay" alt="企业 Logo 预览"><span v-else>企业 Logo</span></div>
            <div><label class="ep-btn file-button">选择 Logo<input type="file" accept="image/png,image/jpeg,image/webp" @change="chooseLogo"></label><p class="ep-muted">建议方形 PNG/JPG/WebP，≤5MB。学校开放企业资料编辑后，保存时会通过文件中心安全上传，不需要填写文件编号。</p></div>
          </div>
          <label>企业简称<input v-model.trim="form.shortName" class="ep-input" maxlength="100"></label>
          <label>官网<input v-model.trim="form.website" type="url" class="ep-input" placeholder="https://"></label>
          <label>成立年份<input v-model.number="form.establishedYear" type="number" min="1800" max="2100" class="ep-input"></label>
          <label>主营业务<textarea v-model.trim="form.mainBusiness" class="ep-textarea" rows="3" maxlength="1000" /></label>
          <label>一句话介绍<textarea v-model.trim="form.shortIntro" class="ep-textarea" rows="3" maxlength="500" /></label>
          <label>办公地址<input v-model.trim="form.address" class="ep-input" maxlength="300"></label>
        </fieldset>
      </div>
      <aside class="ep-card panel"><h2 class="ep-section-title">学校审核信息 · 只读</h2><dl><div><dt>资质状态</dt><dd>{{ school.qualificationStatus }}</dd></div><div><dt>合作状态</dt><dd>{{ school.coopStatus }}</dd></div><div><dt>准入有效期</dt><dd>{{ school.accessValidUntil }}</dd></div><div><dt>黑名单</dt><dd>{{ school.blacklist?'是':'否' }}</dd></div><div><dt>学校审核</dt><dd>{{ school.schoolReview }}</dd></div></dl><p class="ep-muted">以上信息由学校审核维护，企业端仅查看，不能修改。</p></aside>
    </div>
  </section>
</template>
<style scoped>.grid{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:16px}.panel{padding:20px}.profile-fields{margin:0;padding:0;border:0;min-inline-size:0}.profile-fields:disabled{opacity:.72}label{display:flex;flex-direction:column;gap:7px;font-size:13px;color:var(--t2);margin-bottom:15px}.ep-input,.ep-textarea{width:100%}.logo-row{display:grid;grid-template-columns:96px 1fr;gap:16px;align-items:center;margin-bottom:20px}.logo-preview{width:96px;height:96px;border:1px dashed var(--line);border-radius:14px;background:var(--page);display:grid;place-items:center;overflow:hidden;color:var(--t3);font-size:12px}.logo-preview img{width:100%;height:100%;object-fit:contain;background:#fff}.file-button{display:inline-flex;width:max-content;position:relative;overflow:hidden;margin:0 0 8px}.file-button input{position:absolute;inset:0;opacity:0;cursor:pointer}dl{margin:0}dl div{display:flex;justify-content:space-between;gap:20px;padding:13px 0;border-bottom:1px solid var(--line)}dt{color:var(--t3)}dd{margin:0;font-weight:600}.notice{padding:12px 14px;background:var(--ok-bg);color:var(--ok-fg);border-radius:8px;margin-bottom:14px}@media(max-width:900px){.grid{grid-template-columns:1fr}}@media(max-width:560px){.logo-row{grid-template-columns:1fr}.logo-preview{width:84px;height:84px}}</style>
