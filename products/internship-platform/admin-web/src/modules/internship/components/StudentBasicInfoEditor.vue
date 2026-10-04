<template>
  <AppDrawer :visible="visible" title="学生基础资料" mode="modal" size="large" @update:visible="close">
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <form v-else-if="profile" class="basic-editor" @submit.prevent="save">
      <p>{{ profile.name }} · {{ profile.studentNo }} · {{ profile.statusLabel }}</p>
      <p class="hint">维护本批次学生的生源地、民族与性别，学生首页及实习台账同步使用当前资料。</p>
      <div class="field"><span>生源地</span><AppChinaRegionPicker v-model="form.sourceRegion" :disabled="!canManage || saving" level="city" @change="markDirty" /><AppInput v-model="form.sourceRegion" :disabled="!canManage || saving" :maxlength="100" placeholder="不在选择列表中的地区可在此填写，不填详细家庭住址" @update:model-value="markDirty" /></div>
      <label class="field"><span>民族</span><AppInput v-model="form.nation" :disabled="!canManage || saving" :maxlength="50" placeholder="按实际资料填写，暂未采集保持空白" @update:model-value="markDirty" /></label>
      <div class="field"><span>性别</span><AppSelect v-model="form.gender" :disabled="!canManage || saving" :options="genderOptions" placeholder="暂未采集" @update:model-value="markDirty" /></div>
      <p class="hint">空白保存后仍会显示待完善。此处更新资料，不替代学校对身份材料的核验。</p>
      <p v-if="conflict" class="warning">资料已更新，当前输入已保留。最新生源地：{{ profile.sourceRegion || '未采集' }}；民族：{{ profile.nation || '未采集' }}；性别：{{ profile.gender || '未采集' }}。</p>
      <p v-if="formError" class="warning" role="alert">{{ formError }}</p>
      <p v-if="receipt" class="success">资料已保存；学生基础资料{{ receipt.complete ? '已完善' : '仍有待办' }}。</p>
      <div class="actions">
        <button type="button" class="mp-btn" :disabled="saving" @click="load">重新读取资料</button>
        <button v-if="canManage && conflict" type="button" class="mp-btn" :disabled="saving" @click="acceptLatest">已核对最新资料，保留输入继续修改</button>
        <button v-if="canManage" type="submit" class="mp-btn mp-btn--primary" :disabled="saving || conflict">{{ saving ? '正在保存…' : '保存基础资料' }}</button>
      </div>
    </form>
  </AppDrawer>
</template>
<script>
import { AppDrawer } from '@/components/ui'
import { AppTextInput as AppInput, AppSelect, AppChinaRegionPicker } from '@/components/common'
import { LoadingState, ErrorState } from '@/components/business'
import { internStudentApi } from '@/modules/internship/api/internship-student.api'
import { normalizeUiError } from '@/utils/presentationSafety'
const emptyForm = () => ({sourceRegion:'', nation:'', gender:''})
export default {
  components:{AppDrawer,AppInput,AppSelect,AppChinaRegionPicker,LoadingState,ErrorState},
  props:{visible:Boolean,canManage:Boolean,recordId:{type:String,default:''},batchId:{type:String,default:''}},
  emits:['update:visible','saved'],
  data:()=>({sequence:0,epoch:0,loading:false,error:'',profile:null,form:emptyForm(),baseVersion:0,dirty:false,saving:false,formError:'',receipt:null,
    genderOptions:[{value:'',label:'暂未采集'},{value:'男',label:'男'},{value:'女',label:'女'}]}),
  computed:{conflict(){return this.dirty && this.baseVersion!==this.profile?.version}},
  watch:{visible(){this.reset();if(this.visible)this.load()},recordId(){this.reset();if(this.visible)this.load()},batchId(){this.reset();if(this.visible)this.load()}},
  beforeUnmount(){this.reset()},
  methods:{
    reset(){this.sequence++;this.epoch++;this.loading=false;this.error='';this.profile=null;this.form=emptyForm();this.baseVersion=0;this.dirty=false;this.saving=false;this.formError='';this.receipt=null},
    close(){if(!this.saving)this.$emit('update:visible',false)},
    markDirty(){this.dirty=true;this.formError='';this.receipt=null},
    acceptLatest(){if(this.canManage && this.conflict && !this.saving){this.baseVersion=this.profile.version;this.formError=''}},
    async load(){
      if(!this.visible || !this.batchId || !this.recordId)return;
      const seq=++this.sequence,batch=this.batchId,id=this.recordId,current=()=>this.visible && seq===this.sequence && batch===this.batchId && id===this.recordId;
      this.loading=true;this.error='';
      try{const result=await internStudentApi.getBasicInfo(id,batch);if(!current())return;if(result.code!==0)throw result;this.profile=result.data;
        if(!this.dirty){this.form={sourceRegion:this.profile.sourceRegion,nation:this.profile.nation,gender:this.profile.gender};this.baseVersion=this.profile.version}
        if(this.receipt && this.receipt.version!==this.profile.version)this.receipt=null;
      }catch(e){if(current())this.error=normalizeUiError(e).userMessage}
      finally{if(current())this.loading=false}
    },
    async save(){
      if(!this.visible || !this.profile || !this.canManage || this.saving || this.conflict)return;
      const epoch=this.epoch,batch=this.batchId,id=this.recordId,form=this.form,current=()=>this.visible && epoch===this.epoch && batch===this.batchId && id===this.recordId && form===this.form;
      this.saving=true;this.formError='';
      try{const result=await internStudentApi.saveBasicInfo(id,batch,{...form,expectedVersion:this.baseVersion});if(!current())return;
        if(result.code!==0)throw result;this.profile=result.data;this.receipt=result.data;this.baseVersion=result.data.version;this.dirty=false;
        this.form={sourceRegion:result.data.sourceRegion,nation:result.data.nation,gender:result.data.gender};this.$emit('saved',result.data);
      }catch(e){if(current())this.formError=e.bizCode==='DATA_CONFLICT'?'基础资料已在其他页面更新，输入已保留。请重新读取并核对。':normalizeUiError(e).userMessage}
      finally{if(this.visible && epoch===this.epoch && batch===this.batchId && id===this.recordId)this.saving=false}
    }
  }
}
</script>
<style scoped>
.basic-editor{display:flex;flex-direction:column;gap:14px}.field{display:flex;flex-direction:column;gap:8px}.hint{font-size:13px;color:var(--text-tertiary);line-height:1.7}.warning{color:#ad4e00;line-height:1.7}.success{color:#177d4d}.actions{display:flex;gap:10px;flex-wrap:wrap}
</style>
