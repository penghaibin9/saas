<template>
  <ModulePageShell title="月度工资台账" subtitle="查看学生实发工资及教师审核结果，按已查询条件导出。" :watermark="false">
    <form class="payroll-filters" @submit.prevent="search">
      <label>工资月份<input v-model="draft.payMonth" type="month" /></label>
      <label>院系<AppSelect v-model="draft.collegeId" :options="colleges" placeholder="全部院系" /></label>
      <label>审核状态<AppSelect v-model="draft.status" :options="statuses" /></label>
      <label>姓名或学号<input v-model.trim="draft.keyword" maxlength="100" placeholder="输入姓名或学号" /></label>
      <AppButton :disabled="loading || !batchId" @click="search">查询</AppButton>
      <AppButton variant="ghost" :disabled="loading" @click="clear">清空条件</AppButton>
      <AppButton variant="ghost" :disabled="loading || !loaded || exporting || !canView" @click="exportRows">{{ exporting ? '正在生成…' : '导出查询结果' }}</AppButton>
    </form>
    <p v-if="exportFile" role="status"><a :href="exportFile.url" :download="exportFile.filename">下载月度工资台账（{{ exportFile.rowCount }}条）</a>，包含全部查询结果，不限当前页。</p>
    <p v-if="actionError" role="alert" class="payroll-error">{{ actionError }}</p>
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <template v-else>
      <p>共 {{ total }} 条工资单。金额按币种分别记录，历史版本不重复计入列表。</p>
      <DataTable v-if="rows.length" :columns="columns" :rows="rows" row-key="id" :pagination="{page,pageSize:20,total}" @page-change="changePage">
        <template #cell-student="{row}"><strong>{{ row.studentName }}</strong><div>{{ row.studentNo }}</div></template>
        <template #cell-organization="{row}">{{ row.college || '未填院系' }}<div>{{ row.major }} · {{ row.className }}</div></template>
        <template #cell-position="{row}">{{ row.enterpriseName || '未填单位' }}<div>{{ row.positionName }}</div></template>
        <template #cell-amount="{row}">{{ money(row.current) }}</template>
        <template #cell-status="{row}"><AppStatusTag>{{ row.current.statusLabel }}</AppStatusTag><div>第{{ row.current.revisionNo }}版</div></template>
        <template #cell-submitted="{row}">{{ formatDateTime(row.current.submittedAt) }}</template>
        <template #cell-actions="{row}"><AppButton variant="ghost" @click="openDetail(row)">凭证与历史</AppButton></template>
      </DataTable>
      <p v-else>当前查询条件没有工资单。</p>
    </template>
    <section v-if="selected" class="payroll-detail">
      <h2>{{ selected.studentName }} · {{ selected.payMonth }}工资单</h2>
      <AppButton variant="ghost" @click="closeDetail">收起详情</AppButton>
      <p v-if="detailLoading">正在读取工资单…</p>
      <p v-if="detailError" role="alert">{{ detailError }}</p>
      <article v-for="version in detail?.history || []" :key="version.id">
        <h3>第{{ version.revisionNo }}版 · {{ version.statusLabel }} · {{ money(version) }}</h3>
        <p>发薪日期：{{ version.paidOn || '未填写' }}；提交时间：{{ formatDateTime(version.submittedAt) }}</p>
        <p v-if="version.correctionReason">更正原因：{{ version.correctionReason }}</p>
        <p>审核人：{{ version.reviewedBy || '待审核' }}；审核意见：{{ version.reviewComment || '无' }}</p>
        <AppButton variant="ghost" @click="preview(version)">查看第{{ version.revisionNo }}版工资凭证</AppButton>
      </article>
      <FilePreviewer v-if="previewFile" :file="previewFile" inline :provider="previewProvider" :allow-download="false" />
    </section>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, ErrorState, LoadingState } from '@/components/business'
import { AppSelect, AppStatusTag } from '@/components/common'
import { AppButton } from '@/components/ui'
import FilePreviewer from '@/components/file/FilePreviewer.vue'
import { request, currentSessionGeneration } from '@/services/http/client'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { canCode } from '@/modules/internship/composables/permission'
import { formatDateTime } from '@/utils/dateUtils'
import { prepareXlsxDownload } from '@/utils/xlsxDownload'
import { normalizeUiError } from '@/utils/presentationSafety'
import { fileSdk } from '@/services/file/fileSdk'

const blank = () => ({payMonth:'',collegeId:'',status:'ALL',keyword:''})
export default {
  components:{ModulePageShell,DataTable,ErrorState,LoadingState,AppSelect,AppStatusTag,AppButton,FilePreviewer},
  props:{ctx:{type:Object,required:true}},
  data:()=>({draft:blank(),applied:blank(),rows:[],total:0,page:1,colleges:[],loading:false,loaded:false,exporting:false,error:'',actionError:'',exportFile:null,sequence:0,disposed:false,selected:null,detail:null,detailLoading:false,detailError:'',detailSequence:0,previewFile:null,previewProvider:{fetchBytes:d=>fileSdk.blob(d.fileId),dispose(){}},
    statuses:[{value:'ALL',label:'全部'},{value:'SUBMITTED',label:'待审核'},{value:'APPROVED',label:'已确认'},{value:'RETURNED',label:'已退回'}],
    columns:[{key:'student',title:'学生'},{key:'organization',title:'院系 / 专业 / 班级'},{key:'payMonth',title:'工资月份'},{key:'position',title:'当前实习单位 / 岗位'},{key:'amount',title:'实发金额'},{key:'status',title:'审核状态'},{key:'submitted',title:'提交时间'},{key:'actions',title:'操作'}]}),
  computed:{batchStore(){return useInternshipBatchStore()},batchId(){return String(this.batchStore.selectedBatchId||'')},canView(){return canCode(this.ctx,'internship.payroll.view')}},
  watch:{batchId:{immediate:true,handler(){this.restore();this.load()}},'ctx.ctxKey'(){this.reset();this.load()}},
  beforeUnmount(){this.disposed=true;this.reset()},
  methods:{formatDateTime,
    money(v){return v ? `${({CNY:'人民币',USD:'美元',JPY:'日元',EUR:'欧元',HKD:'港币'})[v.currency] || '币种代码：'+v.currency} ${Number(v.actualAmount).toFixed(2)}` : '未填写'},
    clearExport(){if(this.exportFile)URL.revokeObjectURL(this.exportFile.url);this.exportFile=null},
    reset(){this.sequence++;this.clearExport();this.closeDetail();this.rows=[];this.total=0;this.loaded=false;this.exporting=false;this.error='';this.actionError='';this.draft=blank();this.applied=blank();this.page=1;this.colleges=[]},
    restore(){this.reset();const q=this.$route.query;if(q.batchId && String(q.batchId)!==this.batchId)return;this.applied={payMonth:/^20\d{2}-(0[1-9]|1[0-2])$/.test(q.payMonth)?q.payMonth:'',collegeId:/^\d+$/.test(q.collegeId)?q.collegeId:'',status:this.statuses.some(x=>x.value===q.status)?q.status:'ALL',keyword:typeof q.keyword==='string'?q.keyword.slice(0,100):''};this.draft={...this.applied};this.page=/^[1-9]\d{0,5}$/.test(q.page)?Number(q.page):1},
    fence(){const sequence=this.sequence,batch=this.batchId,generation=currentSessionGeneration(),key=this.ctx.ctxKey;return ()=>!this.disposed&&sequence===this.sequence&&batch===this.batchId&&generation===currentSessionGeneration()&&key===this.ctx.ctxKey},
    params(){return {batchId:this.batchId,...this.applied,collegeId:this.applied.collegeId||undefined}},
    saveQuery(){return this.$router.replace({query:{batchId:this.batchId,...this.applied,page:String(this.page)}})},
    search(){this.applied={...this.draft};this.page=1;this.saveQuery();return this.load()},
    clear(){this.draft=blank();return this.search()},
    changePage(value){this.page=Number(value)||1;this.saveQuery();return this.load()},
    async load(){this.sequence++;const current=this.fence();this.closeDetail();this.clearExport();this.loaded=false;this.loading=true;this.error='';this.actionError='';this.exporting=false;
      if(!this.batchId||!this.canView){this.rows=[];this.total=0;this.loading=false;this.error=this.batchId?'当前身份无工资台账查看权限':'请先选择实习批次';return}
      try{const [result,org]=await Promise.all([request('/internship/payroll',{params:{...this.params(),page:this.page,pageSize:20}}),request('/directory/org-tree')]);if(!current())return;if(!Array.isArray(result?.items))throw new Error('工资台账返回不完整，请重试');this.rows=result.items;this.total=result.total;this.colleges=[{value:'',label:'全部院系'},...(org.tree||[]).filter(x=>/^\d+$/.test(x.value)).map(x=>({value:String(x.value),label:x.label}))];this.loaded=true}
      catch(e){if(current()){this.rows=[];this.total=0;this.error=normalizeUiError(e).userMessage}}
      finally{if(current())this.loading=false}
    },
    async exportRows(){if(!this.loaded||this.loading||this.exporting||!this.canView)return;const current=this.fence();this.exporting=true;this.actionError='';this.clearExport();try{const data=await request('/internship/payroll/export',{method:'POST',params:this.params()});if(current())this.exportFile=prepareXlsxDownload(data)}catch(e){if(current())this.actionError=normalizeUiError(e).userMessage}finally{if(current())this.exporting=false}},
    closeDetail(){this.detailSequence++;this.selected=null;this.detail=null;this.detailError='';this.detailLoading=false;this.previewFile=null},
    async openDetail(row){this.closeDetail();this.selected=row;const seq=this.detailSequence,current=this.fence();this.detailLoading=true;try{const detail=await request('/internship/payroll/'+row.id);if(current()&&seq===this.detailSequence)this.detail=detail}catch(e){if(current()&&seq===this.detailSequence)this.detailError=normalizeUiError(e).userMessage}finally{if(current()&&seq===this.detailSequence)this.detailLoading=false}},
    async preview(version){const seq=this.detailSequence,current=this.fence();this.previewFile=null;try{const meta=await fileSdk.metadata(version.evidenceFileId);if(!current()||seq!==this.detailSequence)return;if(meta.readyForBusiness!==true)throw new Error('凭证尚未通过安全检查');this.previewFile=meta}catch(e){if(current()&&seq===this.detailSequence)this.detailError=normalizeUiError(e).userMessage}}
  }
}
</script>

<style scoped>
.payroll-filters{display:flex;flex-wrap:wrap;align-items:flex-end;gap:12px;margin-bottom:16px}.payroll-filters label{display:flex;flex-direction:column;gap:6px;font-size:14px;width:180px}.payroll-filters input{box-sizing:border-box;width:100%;min-height:36px;border:1px solid #dcdfe6;border-radius:6px;padding:6px 10px;font:inherit}.payroll-error{color:#b42318}.payroll-detail{margin-top:20px;padding:20px;border:1px solid #dcdfe6;border-radius:8px}.payroll-detail article{padding:12px 0;border-bottom:1px solid #ebeef5}.payroll-detail p{line-height:1.7;overflow-wrap:anywhere}
</style>
