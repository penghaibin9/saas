<template>
  <ModulePageShell title="学籍异动详情" subtitle="查看正式申请、材料与审批结果" :role-name="ctx.currentRole.roleName" :data-scope-name="ctx.dataScope.scopeName">
    <template #actions><AppButton :disabled="busy" @click="$router.push('/admin/academic-affairs/status-changes')">返回列表</AppButton><AppButton v-if="change" :disabled="busy || printBusy" @click="print">打印审批表</AppButton></template>
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-if="loading" />
    <div v-else-if="change" class="sc-detail">
      <StatusChangeReview :key="change.changeId" :change="change" :ctx="ctx" @updated="updateFormal" @denied="denied" @busy="busy=$event"><template #materials><button :disabled="materialsLoading || busy" @click="loadMaterials">{{ materialsLoading ? '正在读取…' : '读取正式绑定材料' }}</button></template></StatusChangeReview>
      <AppInlineAlert v-if="isPendingEffective" type="info" :message="pendingEffectiveMessage" />
      <section v-if="materialsOpened" class="sc-materials"><h3>正式申请材料</h3><p v-if="materialsError" role="alert">{{ materialsError }}</p><p v-if="materialsLoading">正在读取材料…</p><p v-else-if="!materials.length && !materialsError">当前正式申请没有绑定材料。</p><div v-else class="sc-material-list"><FilePreviewer v-for="file in materials" :key="file.bindingId || file.fileId" :file="file" @error="onFileError" /></div><p>每次打开都由公共文件中心重新核对权限与安全状态。</p></section>
      <section class="sc-materials"><h3>审批路径参考</h3><ol class="sc-flow"><li v-for="(node,index) in flowNodes" :key="node" :class="nodeState(index)"><b>{{ nodeLabel(node) }}</b><span>{{ nodeStateText(index) }}</span></li></ol><p>{{ reviewHint }}</p><p>路径顺序不代表历史节点已全部审核通过，办理事实以正式审批任务和最终状态为准。</p></section>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppInlineAlert } from '@/components/common'
import StatusChangeReview from './parallel-c/StatusChangeReview.vue'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import { academicAffairsApi as api } from '../api/academic-affairs.api'
import { statusChangeConvenienceApi } from '../api/status-change-convenience.api'
import { fileSdk } from '@/services/file/fileSdk'
import { currentUserFromToken } from '@/services/http/client'
import { CHANGE_FLOW_NODES, NODE_LABEL } from '../constants/status-change'
import { gradeError } from './parallel-c/grade-review'
import { toast } from '@/utils/toast'
const PENDING_EFFECTIVE = 'APPROVED_PENDING_EFFECTIVE'
export default {
  name:'AaStatusChangeDetailView',
  components:{ModulePageShell,LoadingState,ErrorState,AppButton,AppInlineAlert,StatusChangeReview,FilePreviewer},
  props:{ctx:{type:Object,required:true}},
  data(){return {alive:true,seq:0,materialSeq:0,fileSeq:0,loading:true,error:'',change:null,busy:false,printBusy:false,materialsOpened:false,materialsLoading:false,materialsError:'',materials:[],fileBusy:false}},
  computed:{
    changeId(){return String(this.$route.params.id||'')},
    identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
    flowNodes(){return CHANGE_FLOW_NODES[this.change?.changeType]||[]},
    currentIndex(){return this.flowNodes.indexOf(this.change?.currentNode)},
    isPendingEffective(){return this.change?.status===PENDING_EFFECTIVE},
    isInReview(){return ['SUBMITTED','IN_REVIEW'].includes(this.change?.status)},
    workflowFinished(){return this.change?.status === 'EFFECTIVE' || this.isPendingEffective},
    reviewHint(){if(this.isPendingEffective&&!this.change?.effectiveDate)return '申请已进入「已通过·待生效」，但正式计划生效时间缺失，请联系教务核对执行计划；当前学籍尚未变更。';if(this.change?.effectiveDate)return `该申请设置指定生效时间 ${this.change.effectiveDate}。终审通过时若仍未到期，将先进入「已通过·待生效」，当前学籍不会提前改写。`;return '通过后异动将立即生效并写入学籍主档。'},
    pendingEffectiveMessage(){return `终审已经通过，当前学籍尚未变更；系统将在 ${this.change?.effectiveDate||'指定时间'} 到期后按正式异动链生效。`}
  },
  watch:{changeId(){this.clear();this.load()},identity(){this.clear();this.load()}},
  created(){this.load()},beforeUnmount(){this.alive=false;this.clear()},
  methods:{
    capture(){return {seq:this.seq,id:this.changeId,identity:this.identity}},current(c){return this.alive&&c.seq===this.seq&&c.id===this.changeId&&c.identity===this.identity},
    clear(){this.seq++;this.materialSeq++;this.fileSeq++;this.change=null;this.materials=[];this.materialsOpened=false;this.materialsLoading=false;this.materialsError='';this.fileBusy=false;this.printBusy=false;this.loading=false;this.error='';this.busy=false},
    denied(){this.clear();this.error='当前身份无权读取此申请，请返回责任队列。'},
    fail(err,fallback){if(/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))){this.denied();return}this.error=gradeError(err,fallback)},
    updateFormal(row){if(String(row.changeId)===this.changeId)this.change={...row}},
    nodeLabel(node){return NODE_LABEL[node]||'节点待核对'},
    nodeState(index){return this.isInReview&&index===this.currentIndex?'is-current':'is-reference'},
    nodeStateText(index){if(this.workflowFinished)return '流程已结束·节点供参考';if(this.change?.status==='RETURNED')return '已退回·路径供参考';if(this.change?.status==='REJECTED')return '已驳回·路径供参考';if(!this.isInReview)return '当前状态待核对·路径供参考';if(this.currentIndex<0)return '节点状态待核对';if(index===this.currentIndex)return '当前审批';return index>this.currentIndex?'后续路径参考':'历史状态待核对'},
    onFileError(err){toast.error(gradeError(err,'材料预览或下载失败'))},
    async openFile(file,action){
      if(this.fileBusy||this.busy||!['preview','download'].includes(action)||!this.materials.some(f=>String(f.fileId)===String(file.fileId)))return
      const c=this.capture(),seq=++this.fileSeq;const valid=()=>this.current(c)&&seq===this.fileSeq
      this.fileBusy=true;this.materialsError=''
      try{const meta=await fileSdk.metadata(file.fileId);if(!valid())return;if(!meta.allowedActions?.includes(action))throw {code:403}
        if(action==='preview'){
          const preview=await fileSdk.preview(file.fileId);if(!valid())preview?.close?.()
          return
        }
        const auth=await fileSdk.authorizedUrl(file.fileId);if(!valid())return
        let href,objectUrl=false;if(auth?.delivery==='COS_PRESIGNED'&&/^https:\/\//i.test(auth.url||''))href=auth.url;else{const blob=await fileSdk.blob(file.fileId);if(!valid())return;href=URL.createObjectURL(blob);objectUrl=true}
        const a=document.createElement('a');a.href=href;a.rel='noopener noreferrer';a.download=file.fileName||'申请材料';document.body.appendChild(a);a.click();a.remove()
        if(objectUrl)setTimeout(()=>URL.revokeObjectURL(href),60000)
      }catch(err){if(valid()){this.materialsError=gradeError(err,'文件暂不可用，请重新核对。');if(/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' ')))this.denied()}}finally{if(valid())this.fileBusy=false}
    },
    async read(c){const res=await api.getStatusChange(c.id);if(res?.code!==0)throw res;if(String(res.data?.changeId||'')!==c.id)throw {code:409};return res.data},
    async load(){if(this.busy)return;this.clear();const c=this.capture();this.loading=true;try{const row=await this.read(c);if(this.current(c))this.change=row}catch(err){if(this.current(c))this.fail(err,'申请读取失败，请重试。')}finally{if(this.current(c))this.loading=false}},
    async loadMaterials(){
      if(!this.change||this.materialsLoading||this.busy)return
      const c=this.capture(),seq=++this.materialSeq;this.fileSeq++;this.fileBusy=false;this.materialsOpened=true;this.materialsLoading=true;this.materials=[];this.materialsError=''
      const valid=()=>this.current(c)&&seq===this.materialSeq
      try{const res=await statusChangeConvenienceApi.listMaterials(this.changeId);if(!valid())return;if(res?.code!==0)throw res;const items=Array.isArray(res.data?.items)?res.data.items:[];this.materials=items.map((file) => fileSdk.normalize(file))}
      catch(err){if(valid()){this.materialsError=gradeError(err,'材料读取失败，请重试。');if(/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' ')))this.denied()}}finally{if(valid())this.materialsLoading=false}
    },
    async print(){if(this.busy||this.printBusy||!this.change)return;const c=this.capture();this.printBusy=true;try{const row=await this.read(c);if(!this.current(c))return;this.updateFormal(row);this.$router.push(`/admin/academic-affairs/print/status-change/${encodeURIComponent(c.id)}`)}catch(err){if(this.current(c))this.fail(err,'打印前核对失败，请重试。')}finally{if(this.current(c))this.printBusy=false}}
  }
}
</script>

<style scoped>
.sc-detail{display:grid;gap:18px}.sc-materials{background:var(--bg-white,#fff);padding:18px;border:1px solid var(--border-200,#e1e7ef);border-radius:9px}.sc-materials h3{font-size:14px;margin:0 0 12px}.sc-materials p{font-size:13px;line-height:1.7;color:var(--text-500,#607087)}.sc-materials article{display:flex;gap:12px;align-items:center;flex-wrap:wrap;padding:12px 0;border-top:1px solid var(--border-200,#e1e7ef);font-size:13px}button{padding:7px 12px;border:1px solid var(--border-200,#d6e0ed);border-radius:7px;background:var(--bg-white,#fff);color:var(--primary-600,#285aab);cursor:pointer}button:disabled{opacity:.5;cursor:default}
</style>
