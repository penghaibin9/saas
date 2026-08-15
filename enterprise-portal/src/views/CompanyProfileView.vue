<script setup>
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { enterpriseInternshipApi } from '../services/enterpriseInternshipApi'
import { uploadTemporaryFile } from '../services/request'

const MAX_LOGO_BYTES=5*1024*1024
const loading=ref(true),saving=ref(false),facadeReady=ref(false),error=ref(''),message=ref(''),profileVersion=ref(null)
const form=reactive({logoFileId:null,shortName:'',shortIntro:'',website:'',mainBusiness:'',establishedYear:null,address:''})
const school=reactive({qualificationStatus:'—',coopStatus:'—',accessValidUntil:'—',blacklist:false,schoolReview:'—'})
const logoFile=ref(null),logoPreview=ref(''),serverLogoUrl=ref(''),uploadedLogoFileId=ref(null)
const logoDisplay=computed(()=>logoPreview.value||serverLogoUrl.value||'')
const admissionTone=computed(()=>school.blacklist?'danger':(school.qualificationStatus==='PASSED'&&school.coopStatus==='ACTIVE'?'ok':'warn'))
const admissionLabel=computed(()=>school.blacklist?'学校限制准入':(school.qualificationStatus==='PASSED'&&school.coopStatus==='ACTIVE'?'准入正常':'待学校确认'))

function hasVersion(value){return value!==null&&value!==undefined&&value!==''&&Number.isInteger(Number(value))&&Number(value)>=0}
function clearPreview(){if(logoPreview.value){URL.revokeObjectURL(logoPreview.value);logoPreview.value=''}}
function chooseLogo(event){
  error.value='';message.value=''
  if(!facadeReady.value||!hasVersion(profileVersion.value)){event.target.value='';error.value='企业资料版本尚未加载完成，当前不能上传 Logo';return}
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
    if(!hasVersion(data?.version))throw new Error('学校端未返回企业资料版本，已停止编辑以避免覆盖他人修改')
    profileVersion.value=Number(data.version);facadeReady.value=true
    Object.assign(form,{logoFileId:data?.logoFileId??null,shortName:data?.shortName||'',shortIntro:data?.shortIntro||'',website:data?.website||'',mainBusiness:data?.mainBusiness||'',establishedYear:data?.establishedYear??null,address:data?.address||''})
    serverLogoUrl.value=data?.logoUrl||data?.logoPreviewUrl||''
    Object.assign(school,{qualificationStatus:data?.qualificationStatus||'—',coopStatus:data?.coopStatus||'—',accessValidUntil:data?.accessValidUntil||'—',blacklist:Boolean(data?.blacklist),schoolReview:data?.schoolReview||data?.reviewComment||'—'})
  }catch(e){facadeReady.value=false;profileVersion.value=null;error.value=e.message||'企业资料加载失败'}finally{loading.value=false}
})
onUnmounted(clearPreview)

async function save(){
  error.value='';message.value=''
  if(!facadeReady.value||!hasVersion(profileVersion.value)){error.value='企业资料版本尚未加载完成，当前不能保存或上传 Logo';return}
  saving.value=true
  try{
    const patch={...publicPatch(),expectedVersion:Number(profileVersion.value)}
    if(logoFile.value){
      if(!uploadedLogoFileId.value){
        const upload=await uploadTemporaryFile(logoFile.value,{bizType:'INTERNSHIP_ENTERPRISE_LOGO'})
        uploadedLogoFileId.value=upload.fileId
      }
      patch.logoFileId=uploadedLogoFileId.value
    }
    const saved=await enterpriseInternshipApi.updateCompany(patch)
    if(!hasVersion(saved?.version))throw new Error('保存成功响应缺少最新版本，请刷新页面后继续编辑')
    profileVersion.value=Number(saved.version)
    if(patch.logoFileId)form.logoFileId=patch.logoFileId
    if(saved?.logoUrl||saved?.logoPreviewUrl)serverLogoUrl.value=saved.logoUrl||saved.logoPreviewUrl
    clearPreview();logoFile.value=null;uploadedLogoFileId.value=null
    message.value='企业公开资料已保存'
  }catch(e){error.value=e.message||'保存失败'}finally{saving.value=false}
}
</script>
<template>
  <section class="ep-page">
    <div class="ep-page-head"><div><h1 class="ep-title">企业资料</h1><p class="ep-subtitle">维护学生能看到的企业公开介绍；企业仅编辑公开资料，学校准入与审核结论始终只读。</p></div><button class="ep-btn ep-btn-primary" :disabled="loading||saving||!facadeReady" @click="save">{{ saving?'保存中…':'保存公开资料' }}</button></div>
    <div v-if="error" class="ep-error">{{ error }}</div><div v-if="message" class="notice">{{ message }}</div>
    <div class="status-strip ep-card"><div><span>资料编辑状态</span><strong>{{ facadeReady?'可编辑':'暂不可编辑' }}</strong></div><div><span>学校准入</span><strong><i class="status-dot" :class="admissionTone"></i>{{ admissionLabel }}</strong></div><div><span>准入有效期</span><strong>{{ school.accessValidUntil }}</strong></div><div><span>资料版本</span><strong>{{ profileVersion===null?'—':`v${profileVersion}` }}</strong></div></div>
    <div class="grid">
      <div class="ep-card panel public-panel">
        <div class="panel-head"><div><span class="section-kicker">学生可见</span><h2 class="ep-section-title">公开资料</h2></div><small>保存后作为当前企业公开信息展示</small></div>
        <fieldset class="profile-fields" :disabled="!facadeReady">
          <div class="logo-row">
            <div class="logo-preview"><img v-if="logoDisplay" :src="logoDisplay" alt="企业 Logo 预览"><span v-else>企业 Logo</span></div>
            <div class="logo-copy"><strong>企业品牌标识</strong><p class="ep-muted">建议使用清晰的方形 Logo，支持 PNG/JPG/WebP，≤5MB。保存时由文件中心安全绑定，不需要填写文件编号。</p><label class="ep-btn file-button">选择 Logo<input type="file" accept="image/png,image/jpeg,image/webp" @change="chooseLogo"></label></div>
          </div>
          <div class="field-grid three"><label>企业简称<input v-model.trim="form.shortName" class="ep-input" maxlength="100"></label><label>官网<input v-model.trim="form.website" type="url" class="ep-input" placeholder="https://"></label><label>成立年份<input v-model.number="form.establishedYear" type="number" min="1800" max="2100" class="ep-input"></label></div>
          <div class="field-grid two"><label>主营业务<textarea v-model.trim="form.mainBusiness" class="ep-textarea" rows="4" maxlength="1000" /></label><label>一句话介绍<textarea v-model.trim="form.shortIntro" class="ep-textarea" rows="4" maxlength="500" /></label></div>
          <label class="address-field">办公地址<input v-model.trim="form.address" class="ep-input" maxlength="300"></label>
        </fieldset>
      </div>
      <aside class="ep-card panel review-panel"><div class="panel-head"><div><span class="section-kicker">学校维护</span><h2 class="ep-section-title">审核与准入 · 只读</h2></div><span class="ep-tag" :class="admissionTone">{{ admissionLabel }}</span></div><dl><div><dt>资质状态</dt><dd>{{ school.qualificationStatus }}</dd></div><div><dt>合作状态</dt><dd>{{ school.coopStatus }}</dd></div><div><dt>准入有效期</dt><dd>{{ school.accessValidUntil }}</dd></div><div><dt>黑名单</dt><dd>{{ school.blacklist?'是':'否' }}</dd></div></dl><div class="school-review"><span>学校审核意见</span><p>{{ school.schoolReview }}</p></div><p class="review-note">以上信息由学校审核维护，企业端仅查看，不能修改；公开资料的编辑不会改变学校准入结论。</p></aside>
    </div>
  </section>
</template>
<style scoped>
.notice{padding:12px 14px;background:var(--ok-bg);color:var(--ok-fg);border-radius:8px;margin-bottom:14px}.status-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:14px;overflow:hidden}.status-strip>div{padding:13px 16px;border-right:1px solid var(--line)}.status-strip>div:last-child{border-right:0}.status-strip span{display:block;font-size:10px;color:var(--t3);margin-bottom:4px}.status-strip strong{display:flex;align-items:center;gap:7px;font-size:12px;color:#29364c}.status-dot{width:7px;height:7px;border-radius:50%;background:var(--warn-fg)}.status-dot.ok{background:var(--ok-fg)}.status-dot.danger{background:var(--danger-fg)}
.grid{display:grid;grid-template-columns:minmax(0,2.2fr) minmax(300px,.8fr);gap:14px;align-items:start}.panel{padding:20px}.panel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;padding-bottom:14px;margin-bottom:18px;border-bottom:1px solid var(--line)}.panel-head .ep-section-title{margin:2px 0 0}.panel-head>small{color:var(--t3);font-size:10px;margin-top:4px}.section-kicker{font-size:10px;color:var(--pri);font-weight:750;letter-spacing:.08em}.profile-fields{margin:0;padding:0;border:0;min-inline-size:0}.profile-fields:disabled{opacity:.72}label{display:flex;flex-direction:column;gap:7px;font-size:12px;color:var(--t2);margin-bottom:0}.ep-input,.ep-textarea{width:100%}
.logo-row{display:grid;grid-template-columns:108px minmax(0,1fr);gap:18px;align-items:center;padding:16px;margin-bottom:18px;border:1px solid var(--line);border-radius:12px;background:var(--surface-soft)}.logo-preview{width:108px;height:108px;border:1px dashed var(--line-strong);border-radius:16px;background:#fff;display:grid;place-items:center;overflow:hidden;color:var(--t3);font-size:12px}.logo-preview img{width:100%;height:100%;object-fit:contain;background:#fff}.logo-copy strong{font-size:13px}.logo-copy p{margin:7px 0 11px;line-height:1.6;font-size:11px}.file-button{display:inline-flex;width:max-content;position:relative;overflow:hidden;margin:0}.file-button input{position:absolute;inset:0;opacity:0;cursor:pointer}.field-grid{display:grid;gap:12px;margin-bottom:14px}.field-grid.three{grid-template-columns:1fr 1.4fr .7fr}.field-grid.two{grid-template-columns:1fr 1fr}.address-field{margin-bottom:0}
.review-panel{position:sticky;top:82px}dl{margin:0}dl div{display:flex;justify-content:space-between;gap:20px;padding:13px 0;border-bottom:1px solid var(--line)}dt{color:var(--t3);font-size:11px}dd{margin:0;font-weight:700;font-size:12px;text-align:right}.school-review{margin-top:16px;padding:14px;border-radius:10px;background:var(--surface-soft);border:1px solid var(--line)}.school-review span{font-size:10px;color:var(--t3);font-weight:700}.school-review p{margin:7px 0 0;line-height:1.55;font-size:12px;font-weight:650;color:#344158}.review-note{margin:14px 0 0;color:var(--t3);font-size:10px;line-height:1.65}
@media(max-width:1000px){.status-strip{grid-template-columns:repeat(2,1fr)}.status-strip>div:nth-child(2){border-right:0}.status-strip>div:nth-child(-n+2){border-bottom:1px solid var(--line)}.grid{grid-template-columns:1fr}.review-panel{position:static}}
@media(max-width:700px){.field-grid.three,.field-grid.two{grid-template-columns:1fr}.logo-row{grid-template-columns:1fr}.logo-preview{width:88px;height:88px}.status-strip{grid-template-columns:1fr}.status-strip>div{border-right:0;border-bottom:1px solid var(--line)}.status-strip>div:last-child{border-bottom:0}}
</style>
