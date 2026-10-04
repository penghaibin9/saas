<template>
  <view class="page-wrap employment">
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view v-if="loaded" class="page-pad stack">
        <view class="card stack">
          <text class="card-title">就业上报</text><text>{{ batchName }} · {{ mentorName }}负责核验</text>
          <text class="hint">核对学生信息，填写就业单位和岗位，提交后交给指导教师。学校核验通过后可回读结果。</text>
          <text v-if="historyMode" class="warning">当前为历史实习批次，仅可查看已有登记。</text>
          <text v-if="registration">登记编号：{{ registration.id }} · {{ registration.statusLabel }} · 已提交 {{ registration.revisionCount }} 版</text>
          <text v-if="registration?.current?.review" class="review">{{ registration.current.review.actionLabel }}：{{ registration.current.review.comment || '教师已完成核验' }}</text>
          <button class="minor" :disabled="submitting" @click="load">刷新登记结果</button>
        </view>
        <view v-if="notifications.total" class="card stack">
          <text class="card-title">审核结果通知 · {{ notifications.unread }} 条未读</text>
          <text class="hint">打开登记不会自动确认已读。通知保留当次结果，当前登记与完整历史以下方回读为准。</text>
          <view v-for="item in notifications.items" :key="item.id" class="history">
            <text>{{ item.title }} · {{ item.statusLabel }}</text><text>{{ item.content }}</text>
            <text class="hint">{{ formatDateTime(item.createdAt) }}</text>
            <button v-if="item.status==='UNREAD'" class="minor" :disabled="!!readingNotification" @click="readNotification(item)">{{ readingNotification===item.id?'正在确认…':'确认已读' }}</button>
          </view>
          <text v-if="notificationError" class="warning" role="alert">{{ notificationError }}</text>
          <view class="modes"><button class="minor" :disabled="notificationPage<=1 || !!readingNotification" @click="changeNotificationPage(-1)">上一页通知</button><text>第 {{ notificationPage }} 页</text><button class="minor" :disabled="!notifications.hasMore || !!readingNotification" @click="changeNotificationPage(1)">下一页通知</button></view>
        </view>
        <view v-if="receipt" class="card receipt"><text class="card-title">已提交第 {{ receipt.revisionCount }} 版</text><text>登记编号：{{ receipt.id }} · {{ receipt.statusLabel }}</text><text>下一步由 {{ mentorName }}审核，请在这里查看处理结果。</text></view>
        <view v-if="conflict" class="card stack warning"><text>登记版本已变化。未提交内容已保留，请先核对下方最新历史再继续。</text><button class="minor" :disabled="!editable || submitting" @click="acceptLatestVersion">已核对最新版本，继续修改</button></view>
        <view class="card stack">
          <text class="card-title">登记方式</text>
          <view class="modes"><button :class="{'chosen':form.mode==='EMPLOYMENT'}" :disabled="!editable || submitting" @click="chooseMode('EMPLOYMENT')">就业上报</button><button :class="{'chosen':form.mode==='INTERNSHIP_TRANSFER'}" :disabled="!editable || !prefill.canTransfer || submitting" @click="chooseMode('INTERNSHIP_TRANSFER')">实习转就业</button></view>
          <text v-if="form.mode==='INTERNSHIP_TRANSFER'" class="hint">已带入当前正式实习企业；单位名称、信用代码固定，请核对岗位和其他就业信息后提交。</text>
          <text v-else-if="!prefill.canTransfer" class="hint">{{ prefill.transferHint }}</text>
        </view>
        <view v-for="group in groups" :key="group.key" class="card stack">
          <text class="card-title">{{ group.label }}</text>
          <view v-for="field in fieldsFor(group.key)" :id="'employment-'+field.key" :key="field.key" class="field">
            <text class="label">{{ field.label }} <text class="required">*</text></text>
            <text v-if="fieldReadonly(field)" class="readonly">{{ form.fields[field.key] || '学校档案尚未提供，请联系学校核实' }}</text>
            <view v-else-if="field.boolean" class="modes"><button :class="{'chosen':form.fields.majorMatch===true}" :disabled="!editable || submitting" @click="chooseMatch(true)">是（专业对口）</button><button :class="{'chosen':form.fields.majorMatch===false}" :disabled="!editable || submitting" @click="chooseMatch(false)">否（专业不对口）</button></view>
            <input v-else v-model="form.fields[field.key]" class="input" :maxlength="field.max" :disabled="!editable || submitting" :placeholder="'请填写'+field.label" @input="markDirty" />
            <text v-if="field.school || field.key==='enrollmentYear'" class="hint">{{ fieldReadonly(field)?'来自学校档案；更正请联系学校':'本次登记声明，不修改学校档案' }}</text>
            <text v-if="field.key==='studentPhone'" class="hint">可填写当前手机，仅用于本次就业登记。</text>
            <text v-if="invalidKey===field.key" class="warning">{{ formError }}</text>
          </view>
        </view>
        <view class="card stack">
          <text class="card-title">就业佐证照片（选填，最多9张）</text>
          <view v-for="(file,index) in form.attachments" :key="file.fileId" class="photo-row"><view class="flex-1" @click="openPhoto(file)"><text>{{ file.fileName || '就业佐证照片' }}</text><text class="hint">{{ file.statusText }}</text></view><button class="minor" :disabled="!editable || submitting || uploading || scanning" @click="removePhoto(index)">移除</button></view>
          <button class="minor" :disabled="!editable || uploading || scanning || submitting || form.attachments.length>=9" @click="addPhoto">{{ uploading?'上传中…':'添加就业照片' }}</button>
          <button v-if="form.attachments.length" class="minor" :disabled="scanning || uploading || submitting" @click="refreshPhotos">{{ scanning?'读取扫描结果中…':'刷新照片安全状态' }}</button>
          <text v-if="!photosReady" class="warning">照片安全就绪前不能提交，已填写内容会保留。</text>
        </view>
        <view v-if="registration && editable" class="card field"><text class="label">补正或更正说明 <text class="required">*</text></text><textarea v-model="form.correctionReason" class="input reason" maxlength="500" placeholder="说明本次根据教师意见补充或更正了哪些内容，至少5字" :disabled="submitting" @input="markDirty" /></view>
        <view v-if="formError && !invalidKey" class="card warning">{{ formError }}</view>
        <view class="card stack"><text class="card-title">我的提交与审核历史</text><text v-if="!registration">尚未提交就业登记。</text><view v-for="version in registration?.history || []" :key="version.id" class="history"><text class="label">第 {{ version.revisionNo }} 版 · {{ version.modeLabel }} · {{ formatDateTime(version.submittedAt) }}</text><text v-if="version.review">{{ version.review.actionLabel }} · {{ version.review.reviewerName }}：{{ version.review.comment || '已核验' }}</text><text v-if="version.correctionReason">更正说明：{{ version.correctionReason }}</text><button class="minor" @click="toggleHistory(version.id)">{{ expandedId===version.id?'收起登记内容':'查看本版登记内容' }}</button><view v-if="expandedId===version.id" class="stack"><view v-for="field in version.fieldRows" :key="field.key" class="history-field"><text>{{ field.label }}：{{ field.value }}</text><text class="hint">{{ field.sourceLabel }}</text></view><button v-for="photo in version.attachments" :key="photo.fileId" class="minor" @click="openPhoto(photo)">查看{{ photo.fileName || '本版照片' }}</button></view></view></view>
        <ReportFilePreview ref="photos" />
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="loaded && state==='ready'"><button class="btn btn-primary flex-1" :disabled="!canSubmit" @click="submit">{{ submitting?'提交中…':registration?'提交补正或更正':'提交就业登记' }}</button></MobileSafeAreaBar>
  </view>
</template>
<script>
import { studentApi } from '@/services/studentApi'
import fileSdk from '@/services/fileSdk'
import ReportFilePreview from '@/components/ReportFilePreview.vue'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { employmentFields, employmentGroups, employmentView, employmentDraft, validateEmployment } from '@/services/employmentPresentation.mjs'
import { reportFileState, reportFilesReady, refreshReportFiles } from '@/services/weeklyReportPresentation.mjs'
import { formatDateTime } from '@/utils/format'

export default {
  components:{ReportFilePreview},
  data:()=>({state:'loading',error:'',loaded:false,hidden:false,generation:currentSessionGeneration(),epoch:0,loadSequence:0,
    requestedBatch:'',requestedRecord:'',requestedRegistration:'',batchId:'',internshipId:'',batchName:'',mentorName:'指导教师',historyMode:false,
    contextKey:'',prefill:{},registration:null,form:employmentDraft(),baseVersion:0,dirty:false,receipt:null,submitting:false,uploading:false,scanning:false,
    formError:'',invalidKey:'',expandedId:'',groups:employmentGroups,
    notifications:{items:[],total:0,unread:0,hasMore:false},notificationPage:1,readingNotification:'',notificationError:''}),
  computed:{
    editable(){return this.loaded && this.state==='ready' && !this.hidden && this.generation===currentSessionGeneration() && !this.historyMode && this.registration?.status!=='SUBMITTED'},
    conflict(){return this.dirty && this.baseVersion!==(this.registration?.version||0)},
    photosReady(){return reportFilesReady(this.form.attachments)},
    canSubmit(){return this.editable && !this.conflict && !this.submitting && !this.uploading && !this.scanning && this.photosReady}
  },
  onLoad(q){this.requestedBatch=String(q?.batchId||'');this.requestedRecord=String(q?.internshipId||'');this.requestedRegistration=String(q?.registrationId||'');this.load()},
  onShow(){const wasHidden=this.hidden;this.hidden=false;if(this.generation!==currentSessionGeneration()){this.resetAccount();this.load()}else if(wasHidden){this.load()}},
  onHide(){this.pause()},onUnload(){this.pause();this.form=employmentDraft();this.registration=null},
  methods:{
    formatDateTime,
    fieldsFor(group){return employmentFields.filter(x=>x.group===group)},
    fieldReadonly(field){return field.school || (field.key==='enrollmentYear' && this.prefill.identityEditable?.enrollmentYear===false) || (this.form.mode==='INTERNSHIP_TRANSFER' && ['companyName','creditCode'].includes(field.key))},
    markDirty(){this.dirty=true;this.receipt=null;this.formError='';this.invalidKey=''},
    chooseMatch(value){if(!this.editable || this.submitting)return;this.form.fields.majorMatch=value;this.markDirty()},
    chooseMode(mode){if(!this.editable || this.submitting || (mode==='INTERNSHIP_TRANSFER' && !this.prefill.canTransfer))return;this.form.mode=mode;if(mode==='INTERNSHIP_TRANSFER')Object.assign(this.form.fields,this.prefill.transfer);this.markDirty()},
    toggleHistory(id){this.expandedId=this.expandedId===id?'':id},
    pause(){this.hidden=true;this.epoch++;this.loadSequence++;this.submitting=false;this.uploading=false;this.scanning=false;this.readingNotification='';this.$refs.photos?.reset()},
    resetAccount(){this.epoch++;this.loadSequence++;this.generation=currentSessionGeneration();this.form=employmentDraft();this.registration=null;this.prefill={};this.loaded=false;this.dirty=false;this.receipt=null;this.contextKey='';this.batchId='';this.internshipId='';this.requestedBatch='';this.requestedRecord='';this.requestedRegistration='';this.baseVersion=0;this.formError='';this.invalidKey='';this.expandedId='';this.notifications={items:[],total:0,unread:0,hasMore:false};this.notificationPage=1;this.readingNotification='';this.notificationError=''},
    fence(){const epoch=this.epoch,generation=currentSessionGeneration(),key=this.contextKey,form=this.form;return ()=>!this.hidden && epoch===this.epoch && generation===currentSessionGeneration() && key===this.contextKey && form===this.form},
    async load(){
      const sequence=++this.loadSequence,generation=currentSessionGeneration(),current=()=>!this.hidden && generation===currentSessionGeneration() && sequence===this.loadSequence;
      this.state='loading';this.error='';
      try{
        const dashboard=await studentApi.getInternship(this.requestedBatch);if(!current())return;
        if(!dashboard.hasBatch){this.loaded=false;this.state='empty';this.error='请从实习首页选择本人的批次后进入就业上报。';return}
        const batch=String(dashboard.batchId),record=String(dashboard.recordId);
        if((this.requestedBatch && batch!==this.requestedBatch)||(this.requestedRecord && record!==this.requestedRecord))throw {code:404001};
        const data=await studentApi.getInternshipEmployment(batch,record,this.notificationPage);if(!current())return;
        if(String(data.batchId)!==batch || String(data.internshipId)!==record || (this.requestedRegistration && String(data.registration?.id)!==this.requestedRegistration))throw {code:404001};
        const key=batch+':'+record,row=employmentView(data.registration);
        if(key!==this.contextKey){this.epoch++;this.dirty=false;this.receipt=null;this.expandedId=''}
        this.contextKey=key;this.batchId=batch;this.internshipId=record;this.prefill=data.prefill;this.registration=row;
        this.notifications=data.resultNotifications||{items:[],total:0,unread:0,hasMore:false};this.notificationPage=this.notifications.page||1;this.readingNotification='';this.notificationError='';
        if(this.receipt && this.receipt.version!==row?.version)this.receipt=null;
        this.batchName=dashboard.batch;this.mentorName=dashboard.schoolMentor||'指导教师';this.historyMode=!!dashboard.historyMode;
        if(!this.dirty){this.form=employmentDraft(data.prefill,row);this.form.attachments=this.form.attachments.map(reportFileState);this.baseVersion=row?.version||0}
        else{for(const field of employmentFields.filter(x=>x.school))this.form.fields[field.key]=data.prefill.identity?.[field.key]||'';if(data.prefill.identityEditable?.enrollmentYear===false)this.form.fields.enrollmentYear=data.prefill.identity.enrollmentYear}
        this.loaded=true;this.state='ready';
        if(this.form.attachments.length)await this.refreshPhotos();
      }catch(e){if(current()){const error=normalizeError(e);this.state=error.pageState||'error';this.error=error.text}}
    },
    async changeNotificationPage(delta){if(this.state!=='ready' || this.readingNotification || (delta<0 && this.notificationPage<=1) || (delta>0 && !this.notifications.hasMore))return;this.notificationPage+=delta;await this.load()},
    async readNotification(item){
      if(this.state!=='ready' || this.hidden || this.readingNotification || item.status!=='UNREAD' || !this.notifications.items.some(x=>x.id===item.id))return;
      const current=this.fence(),sequence=this.loadSequence;this.readingNotification=item.id;this.notificationError='';
      try{const result=await studentApi.readInternshipEmploymentResult(item.id,this.batchId,this.internshipId);
        if(!current() || sequence!==this.loadSequence)return;
        if(String(result.id)!==String(item.id) || result.status!=='READ')throw {code:409001};
        this.notifications.items=this.notifications.items.map(x=>x.id===item.id?result:x);this.notifications.unread=Math.max(0,this.notifications.unread-1);
      }catch(e){if(current() && sequence===this.loadSequence)this.notificationError=normalizeError(e).text}
      finally{if(current() && sequence===this.loadSequence)this.readingNotification=''}
    },
    acceptLatestVersion(){if(!this.editable || !this.conflict)return;this.baseVersion=this.registration?.version||0;this.formError='';this.invalidKey=''},
    async addPhoto(){if(!this.editable || this.uploading || this.submitting || this.scanning || this.form.attachments.length>=9)return;const current=this.fence();this.uploading=true;try{const picked=await fileSdk.choose({kind:'image'});if(!current() || !picked)return;const photo=reportFileState(await fileSdk.upload(picked,{bizType:'INTERNSHIP_EMPLOYMENT'}));if(!current())return;this.form.attachments.push(photo);this.markDirty()}catch(e){if(current())this.formError=normalizeError(e).text}finally{if(current())this.uploading=false}},
    removePhoto(index){if(!this.editable || this.submitting || this.uploading || this.scanning)return;this.form.attachments.splice(index,1);this.markDirty()},
    async refreshPhotos(){if(this.scanning || this.uploading || this.submitting || !this.loaded)return;const current=this.fence();this.scanning=true;try{const fresh=await refreshReportFiles(this.form.attachments,id=>fileSdk.metadata(id),current);if(fresh)this.form.attachments=fresh}catch(e){if(current())this.formError=normalizeError(e).text}finally{if(current())this.scanning=false}},
    async openPhoto(photo){await this.$refs.photos?.open(photo)},
    async submit(){
      if(!this.canSubmit)return;
      const invalid=validateEmployment(this.form,this.prefill);
      if(invalid){this.formError=invalid.text;this.invalidKey=invalid.key;uni.pageScrollTo({selector:'#employment-'+invalid.key,duration:200});return}
      if(this.registration && this.form.correctionReason.trim().length<5){this.formError='补正或更正说明不少于5字';this.invalidKey='';return}
      const current=this.fence();this.submitting=true;this.formError='';this.invalidKey='';
      try{const row=employmentView(await studentApi.submitInternshipEmployment({batchId:this.batchId,internshipId:this.internshipId,
        expectedVersion:this.baseVersion,registrationMode:this.form.mode,fields:{...this.form.fields},attachmentFileIds:this.form.attachments.map(x=>String(x.fileId)),correctionReason:this.form.correctionReason.trim()}));
        if(!current())return;this.registration=row;this.receipt=row;this.dirty=false;this.baseVersion=row.version;this.submitting=false;await this.load()
      }catch(e){if(current()){const error=normalizeError(e);this.formError=error.text;this.invalidKey='';if(error.kind==='conflict')await this.load()}}
      finally{if(current())this.submitting=false}
    }
  }
}
</script>
<style scoped>
.employment{padding-bottom:90px}.hint{display:block;font-size:12px;color:var(--text-tertiary);line-height:1.6;overflow-wrap:anywhere}.warning{color:#ad4e00;line-height:1.6;display:block}.review{display:block;padding:10px;background:#fff6e9;line-height:1.6}.field{display:flex;flex-direction:column;gap:7px}.label{font-size:14px;font-weight:600}.required{color:#ba3030}.input{display:block;border:1px solid var(--border-base,#d8dee8);border-radius:7px;padding:10px;box-sizing:border-box;font-size:14px;width:100%;height:44px}.readonly{display:block;overflow-wrap:anywhere;font-size:14px;line-height:1.6;padding:7px 0}.reason{height:100px}.minor{font-size:13px;padding:4px 10px;margin:0;background:#f2f5f9;color:var(--brand-primary);line-height:2;border:0}.modes{display:flex;gap:10px}.modes button{flex:1;margin:0;font-size:14px;background:#f4f6fa}.modes .chosen{border:1px solid var(--brand-primary);color:var(--brand-primary);background:#eef5ff}.photo-row{display:flex;gap:8px;align-items:center}.photo-row .flex-1{min-width:0;overflow-wrap:anywhere}.history{border-top:1px solid var(--border-base,#eee);padding-top:12px;display:flex;flex-direction:column;gap:8px}.history-field{display:flex;flex-direction:column;gap:3px;overflow-wrap:anywhere;font-size:13px;line-height:1.6}.receipt{border-left:4px solid #278b5f;display:flex;flex-direction:column;gap:8px}
</style>
