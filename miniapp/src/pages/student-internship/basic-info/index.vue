<template>
  <view class="internship-surface mobile-page mobile-student page-wrap basic-info">
    <MobileNavBar title="基础资料" show-back :fallback-url="homePath" :before-back="beforeBack">
      <template #right><button class="mobile-control basic-refresh" :disabled="submitting" @click="load">刷新</button></template>
    </MobileNavBar>
    <MobileGlobalState :state="state" :description="error" @retry="load">
      <view v-if="profile" class="page-pad stack">
        <view class="card student-heading">
          <view class="student-facts"><text class="card-title">{{ profile.name }}</text><text class="hint">{{ profile.studentNo }}</text></view>
          <MobileStatusTag :label="profile.statusLabel" :type="profile.complete ? 'success' : 'warning'" />
        </view>
        <view v-if="conflict" class="card stack warning">
          <text>资料已更新，输入已保留。请核对最新资料后继续。</text>
          <text>最新生源地：{{ profile.sourceRegion || '未填写' }}；民族：{{ profile.nation || '未填写' }}；性别：{{ profile.gender || '未填写' }}。</text>
          <button class="mobile-control minor" :disabled="submitting || !profile.editable" @click="acceptLatest">已核对，保留输入继续修改</button>
        </view>
        <view class="card stack">
          <label class="field"><text>生源地</text><input id="student-basic-source-region" v-model="form.sourceRegion" class="mobile-input input" :disabled="!editable || submitting" maxlength="100" placeholder="省、市或区县，不填详细住址" @input="markDirty" /></label>
          <label class="field"><text>民族</text><input v-model="form.nation" class="mobile-input input" :disabled="!editable || submitting" maxlength="50" placeholder="" @input="markDirty" /></label>
          <view class="field"><text>性别</text><picker class="mobile-picker" :range="genderLabels" :value="genderIndex" :disabled="!editable || submitting" @change="chooseGender"><view class="input">{{ form.gender || '暂未填写，请选择' }}</view></picker></view>
          <text v-if="!profile.editable" class="hint">当前历史批次仅可查看。</text>
          <text v-if="formError" class="warning" role="alert">{{ formError }}</text>

        </view>
        <view v-if="receipt" class="card success"><text>资料已保存，{{ receipt.complete ? '已完善。' : '仍有未填项。' }}</text></view>
      </view>
    </MobileGlobalState>
    <MobileSafeAreaBar v-if="profile && state === 'ready'"><button id="student-basic-info-save" class="mobile-control btn btn-primary flex-1" :disabled="!editable || submitting || conflict" @click="submit">{{ submitting ? '正在保存…' : '保存基础资料' }}</button></MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { normalizeError } from '@/services/request'
const emptyForm = () => ({ sourceRegion: '', nation: '', gender: '' })
export default {
  data: () => ({ state:'loading', error:'', formError:'', requestedBatch:'', requestedRecord:'', batchId:'', recordId:'',
    batchName:'', profile:null, form:emptyForm(), baseVersion:0, dirty:false, receipt:null,
    sequence:0, epoch:0, hidden:false, generation:currentSessionGeneration(), submitting:false,
    genderLabels:['暂未填写','男','女'] }),
  computed: {
    homePath(){const batch=this.batchId||this.requestedBatch;return '/pages/student-internship/index'+(batch?'?batchId='+encodeURIComponent(batch):'')},
    editable(){return this.state==='ready' && !!this.profile?.editable && !this.hidden && this.generation===currentSessionGeneration()},
    conflict(){return this.dirty && this.baseVersion!==this.profile?.version},
    genderIndex(){return Math.max(0,this.genderLabels.indexOf(this.form.gender))}
  },
  onLoad(q){this.requestedBatch=String(q?.batchId||'');this.requestedRecord=String(q?.internshipId||'');this.load()},
  onShow(){const wasHidden=this.hidden;this.hidden=false;if(this.generation!==currentSessionGeneration()){this.resetAccount();this.load()}else if(wasHidden)this.load()},
  onHide(){this.pause()},onUnload(){this.pause();this.form=emptyForm();this.profile=null},
  methods: {
    beforeBack(){if(this.submitting)return false;if(!this.dirty)return true;return new Promise(resolve=>uni.showModal({title:'尚有未保存内容',content:'离开后本次输入不会保存，是否离开？',confirmText:'离开',cancelText:'继续填写',success:result=>resolve(!!result.confirm),fail:()=>resolve(false)}))},
    pause(){this.hidden=true;this.sequence++;this.epoch++;this.submitting=false},
    resetAccount(){this.sequence++;this.epoch++;this.generation=currentSessionGeneration();this.profile=null;this.form=emptyForm();this.dirty=false;this.receipt=null;this.submitting=false;this.requestedBatch='';this.requestedRecord='';this.batchId='';this.recordId='';this.formError='';this.baseVersion=0},
    markDirty(){this.dirty=true;this.receipt=null;this.formError=''},
    chooseGender(e){if(!this.editable || this.submitting)return;const value=this.genderLabels[Number(e.detail.value)];this.form.gender=value==='暂未填写'?'':value||'';this.markDirty()},
    acceptLatest(){if(!this.editable || !this.conflict || this.submitting)return;this.baseVersion=this.profile.version;this.formError=''},
    async load(){
      if(this.generation!==currentSessionGeneration())this.resetAccount();
      const seq=++this.sequence, generation=currentSessionGeneration(), current=()=>!this.hidden && seq===this.sequence && generation===currentSessionGeneration();
      this.state='loading';this.error='';
      try{
        const dashboard=await studentApi.getInternship(this.requestedBatch);if(!current())return;
        if(!dashboard.hasBatch){this.profile=null;this.state='empty';this.error='请从实习首页选择本人的批次后进入基础资料。';return}
        const batch=String(dashboard.batchId), record=String(dashboard.recordId);
        if((this.requestedBatch && batch!==this.requestedBatch)||(this.requestedRecord && record!==this.requestedRecord))throw {code:404001};
        const profile=await studentApi.getBasicInfo(batch,record);if(!current())return;
        if(this.batchId!==batch || this.recordId!==record){this.epoch++;this.dirty=false;this.receipt=null;this.form=emptyForm()}
        this.batchId=batch;this.recordId=record;this.batchName=dashboard.batch;this.profile=profile;
        if(!this.dirty){this.form={sourceRegion:profile.sourceRegion,nation:profile.nation,gender:profile.gender};this.baseVersion=profile.version}
        if(this.receipt && this.receipt.version!==profile.version)this.receipt=null;
        this.state='ready';
      }catch(e){if(current()){const err=normalizeError(e);this.state=err.pageState||'error';this.error=err.text}}
    },
    async submit(){
      if(!this.editable || this.submitting || this.conflict)return;
      const epoch=this.epoch,generation=currentSessionGeneration(),batch=this.batchId,record=this.recordId,form=this.form;
      const current=()=>!this.hidden && epoch===this.epoch && generation===currentSessionGeneration() && batch===this.batchId && record===this.recordId && form===this.form;
      this.submitting=true;this.formError='';
      try{const result=await studentApi.saveBasicInfo(batch,record,{...form,expectedVersion:this.baseVersion});if(!current())return;this.profile=result;this.receipt=result;this.baseVersion=result.version;this.form={sourceRegion:result.sourceRegion,nation:result.nation,gender:result.gender};this.dirty=false}
      catch(e){if(current()){this.formError=e?.bizCode==='DATA_CONFLICT'?'基础资料已在其他页面更新，输入已保留。请重新读取学校资料并核对。':normalizeError(e).text}}
      finally{if(!this.hidden && epoch===this.epoch && generation===currentSessionGeneration() && batch===this.batchId && record===this.recordId)this.submitting=false}
    }
  }
}
</script>
<style scoped>
.basic-info{padding-bottom:30px}.student-heading{display:flex;justify-content:space-between;align-items:center;gap:12px}.student-facts{display:flex;flex-direction:column;gap:4px;min-width:0}.field{display:flex;flex-direction:column;gap:8px;font-size:var(--font-size-base)}.input{height:44px;width:100%;box-sizing:border-box;padding:10px;border:1px solid var(--border-base,#d8dee8);border-radius:7px;font-size:var(--font-size-md)}.hint{font-size:var(--font-size-base);color:var(--text-tertiary);line-height:1.6;overflow-wrap:anywhere}.warning{color:#ad4e00;font-size:var(--font-size-base);line-height:1.7;overflow-wrap:anywhere}.success{color:#177d4d;font-size:var(--font-size-base);line-height:1.7}.minor{min-height:44px;font-size:var(--font-size-base);background:#f2f5f9;color:var(--brand-primary);margin:0;line-height:1.6;padding:10px}.basic-refresh{min-height:44px;margin:0;padding:0 6px;background:transparent;color:var(--brand-primary);font-size:var(--font-size-base)}.basic-refresh::after{border:0}
</style>
