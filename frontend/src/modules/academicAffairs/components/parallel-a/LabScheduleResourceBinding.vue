<template>
  <AppDrawer :visible="true" title="关联正式排课场地" mode="modal" @close="!saving && $emit('close')">
    <LoadingState v-if="loading" />
    <template v-else-if="lab">
      <p>{{ lab.labName }} · {{ lab.labCode }}</p>
      <p>当前关联：{{ lab.classroomId ? `场地 #${lab.classroomId}` : '未关联' }} · 资源版本 {{ lab.version }}</p>
      <p>请确认这两条资源记录代表同一实际场地。关联后，实训室预约、教室借用和正式课表共同核对占用。</p>
      <AppFormItem label="正式排课场地"><AppClassroomPicker v-model="classroomId" :disabled="saving || !!pending" /></AppFormItem>
      <p>不按名称自动关联；已有批准预约的实训室不能直接改换场地。</p>
      <AppButton v-if="!pending" variant="primary" :loading="saving" :disabled="!changed || !validVersion || storageBlocked" @click="save">确认关联所选场地</AppButton>
      <AppButton v-if="pending" :disabled="saving || checking" @click="verify">只读核对原操作</AppButton>
      <p v-if="receipt">{{ receipt }}</p>
    </template>
    <AppInlineAlert v-if="error" type="danger" :description="error" />
  </AppDrawer>
</template>

<script>
import { AppDrawer, AppButton } from '@/components/ui'
import { AppClassroomPicker, AppFormItem, AppInlineAlert } from '@/components/common'
import { LoadingState } from '@/components/business'
import { academicAffairsLabApi as api, academicAffairsResourceApi } from '../../api/academic-affairs.api'
import { currentUserFromToken } from '@/services/http/client'

export default {
  name:'LabScheduleResourceBinding', components:{AppDrawer,AppButton,AppClassroomPicker,AppFormItem,AppInlineAlert,LoadingState},
  props:{labId:{type:String,required:true},ctx:{type:Object,required:true}}, emits:['close','saved'],
  data(){return{lab:null,classroomId:'',loading:false,saving:false,checking:false,pending:null,storageBlocked:false,error:'',receipt:'',seq:0,alive:true}},
  computed:{
    identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.currentRoleCode,u.activeContextId,this.ctx.permissionPatterns])},
    validVersion(){return this.lab?.version!=null&&Number.isSafeInteger(Number(this.lab.version))&&Number(this.lab.version)>=0},
    changed(){return String(this.lab?.classroomId||'')!==String(this.classroomId||'')}
  },
  watch:{identity(){this.load()},labId(){this.load()}}, mounted(){this.load()},beforeUnmount(){this.alive=false;this.seq++},
  methods:{
    capture(){return{seq:this.seq,identity:this.identity,id:this.labId}},current(c){return this.alive&&c.seq===this.seq&&c.identity===this.identity&&c.id===this.labId},
    async read(id){const r=await api.get(id);if(r?.code!==0)throw r;if(String(r.data?.labId)!==id)throw{code:409,message:'资源对象不一致'};return r.data},
    fail(e){if(/403|404|FORBIDDEN|NO_PERMISSION|NO_DATA_SCOPE/.test([e?.code,e?.bizCode].join(' '))){this.lab=null;this.receipt=''}this.error=e?.message||'场地关联暂不可核对，请重试读取'},
    storageKey(c){return 'aa-lab-room-command:'+c.identity+':'+c.id},
    persist(p){globalThis.sessionStorage.setItem(this.storageKey(p),JSON.stringify({id:p.id,target:p.target,version:p.version,commandKey:p.commandKey}))},
    forget(p){globalThis.sessionStorage.removeItem(this.storageKey(p))},
    restore(c){const text=globalThis.sessionStorage.getItem(this.storageKey(c));if(!text)return null;const p=JSON.parse(text)
      if(p.id!==c.id||!Number.isSafeInteger(p.version)||p.version<0||typeof p.target!=='string'||(p.target&&!/^[1-9]\d*$/.test(p.target))||!/^[A-Za-z0-9_-]{8,128}$/.test(p.commandKey))throw new Error('原场地关联命令引用不完整，不能继续发送')
      return {...p,...c,ack:false}
    },
    async load(){
      this.seq++;this.lab=null;this.pending=null;this.classroomId='';this.receipt='';this.error='';this.saving=false;this.checking=false;this.storageBlocked=false
      const c=this.capture();this.loading=true
      try{try{this.pending=this.restore(c)}catch(e){this.storageBlocked=true;throw e}
        const row=await this.read(c.id);if(this.current(c)){this.lab=row;this.classroomId=this.pending?this.pending.target:(row.classroomId||'')}
      }catch(e){if(this.current(c))this.fail(e)}finally{if(this.current(c))this.loading=false}
    },
    async save(){
      if(this.saving||this.pending||this.storageBlocked||!this.changed||!this.validVersion)return
      const c=this.capture(),original={...this.lab},target=String(this.classroomId||'')
      if(target&&!/^[1-9]\d*$/.test(target)){this.error='请选择正式场地';return}
      this.saving=true;this.error=''
      try{const fresh=await this.read(c.id);if(!this.current(c))return
        if(Number(fresh.version)!==Number(original.version)||String(fresh.classroomId||'')!==String(original.classroomId||'')){this.lab=fresh;this.error='资源已变化，请核对当前关联后重新确认';return}
        if(!globalThis.crypto?.randomUUID)throw new Error('当前浏览器无法生成可靠命令标识，未发送关联')
        const pending={...c,target,version:Number(original.version),ack:false,commandKey:globalThis.crypto.randomUUID()}
        this.persist(pending)
        this.pending=pending
        let r;try{r=await api.bindScheduleRoom(c.id,{classroomId:target||null,expectedVersion:Number(original.version)},this.pending.commandKey)}catch(e){r=e}
        if(!this.current(c))return
        if(r?.code!==0&&/403|404|409|422|FORBIDDEN|CONFLICT|VALIDATION/.test([r?.code,r?.bizCode].join(' '))){this.forget(this.pending);this.pending=null;throw r}
        this.pending.ack=r?.code===0&&String(r.data?.labId)===c.id&&String(r.data?.classroomId||'')===target&&Number(r.data?.version)===Number(original.version)+1
        await this.verify()
      }catch(e){if(this.current(c))this.fail(e)}finally{if(this.current(c))this.saving=false}
    },
    async verify(){const p=this.pending;if(!p||!this.current(p)||this.checking)return;this.checking=true
      try{
        if(!p.ack){const response=await academicAffairsResourceApi.commandReceipt(p.commandKey,'RESOURCE_LAB_BIND');if(!this.current(p))return
          if(response?.code!==0)throw response
          const r=response.data
          if(r?.commandKey!==p.commandKey||r.operation!=='RESOURCE_LAB_BIND'||!['SUCCESS','UNRESOLVED'].includes(r.state))throw new Error('原场地关联回执标识不一致')
          p.ack=r.state==='SUCCESS'&&String(r.result?.labId)===p.id&&String(r.result?.classroomId||'')===p.target&&Number(r.result?.version)===p.version+1
        }
        const row=await this.read(p.id);if(!this.current(p))return
        if(!p.ack){this.error='原命令回执尚未确认；只读结果不能证明本次操作成功，请勿重复提交';return}
        if(String(row.classroomId||'')!==p.target||Number(row.version)!==p.version+1){this.error='正式关联与原回执尚未吻合，请稍后只读核对';return}
        this.forget(p);this.lab=row;this.pending=null;this.receipt='场地关联已与正式资源核对一致';this.error='';this.$emit('saved')
      }catch(e){if(this.current(p))this.fail(e)}finally{if(this.current(p))this.checking=false}
    }
  }
}
</script>
