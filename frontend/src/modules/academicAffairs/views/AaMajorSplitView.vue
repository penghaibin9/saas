<template>
  <ModulePageShell
    title="分流批次"
    subtitle="志愿、分配、调剂与正式确认保留在同一批次"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    show-subtitle-in-concise
  >
    <template #actions>
      <AppButton v-if="canManage" variant="primary" :disabled="saving || !!pending" @click="openCreate">创建分流批次</AppButton>
    </template>

    <ol class="aams-progress" aria-label="专业分流办理顺序">
      <li v-for="(step,index) in splitSteps" :key="step" :class="{ 'is-current': index === currentStage, 'is-complete': index < currentStage }">
        <span>{{ index < currentStage ? '✓' : index + 1 }}</span><div><strong>{{ step }}</strong><small>{{ splitStepNotes[index] }}</small></div>
      </li>
    </ol>
    <section v-if="!current && !loading && !error" class="aams-metrics" aria-label="当前页分流批次概况">
      <article><span>本页批次</span><strong>{{ rows.length }}</strong><small>正式总数 {{ batchTotal }}</small></article>
      <article><span>待启动</span><strong>{{ batchCount('DRAFT') }}</strong><small>需要配置专业与容量</small></article>
      <article><span>填报 / 分配中</span><strong>{{ batchCount('OPEN','CLOSED','ALLOCATED') }}</strong><small>按批次独立推进</small></article>
      <article><span>已确认</span><strong>{{ batchCount('CONFIRMED') }}</strong><small>可核对学籍回写</small></article>
    </section>
    <div :class="['aams-layout', { 'is-list': !current }]">
      <div v-if="!current" class="aams-list"><ErrorState v-if="error" :description="error" @retry="load" /><LoadingState v-else-if="loading" /><EmptyState v-else-if="!rows.length" title="暂无分流批次" description="有权限的岗位可新建批次" /><DataTable v-else :columns="batchColumns" :rows="rows" row-key="batchId" :pagination="{page:batchPage,pageSize:20,total:batchTotal}" @page-change="turnBatch"><template #cell-status="{row}"><StatusTag :label="stLabel(row.status)" :type="stType(row.status)" /></template><template #cell-action="{row}"><button class="mp-link" :disabled="saving || !!pending" @click="select(row)">进入批次</button></template></DataTable></div>
      <div v-if="current" class="aams-detail"><AppButton :disabled="saving || !!pending" @click="backToList">返回批次列表</AppButton><AppButton :disabled="saving || !!pending" @click="refresh">刷新当前批次明细</AppButton><p v-if="error" class="aams-warn" role="alert">{{ error }}</p>
        <EmptyState v-if="!current" title="选择一个批次" description="从左侧选择分流批次" />
        <template v-else>
          <div class="aams-head">
            <div>
              <div class="aams-title">{{ current.batchName }}</div>
              <StatusTag :type="stType(current.status)" :label="stLabel(current.status)" dot />
            </div>
            <div v-if="canManage" class="aams-actions">
              <AppButton v-if="current.status === 'DRAFT'" :disabled="saving || !!pending || detailLoading || !detailReady" size="small" variant="ghost" @click="openAddOption">+ 可选专业</AppButton>
              <AppButton v-if="current.status === 'DRAFT'" :disabled="saving || !!pending || detailLoading || !detailReady" size="small" variant="primary" @click="act('open', '开放志愿填报')">开放填报</AppButton>
              <AppButton v-if="current.status === 'OPEN'" :disabled="saving || !!pending || detailLoading || !detailReady" size="small" variant="warning" @click="act('close', '截止志愿')">截止</AppButton>
              <AppButton v-if="current.status === 'CLOSED'" :disabled="saving || !!pending || detailLoading || !detailReady" size="small" variant="ghost" @click="allocate(true)">试分预览</AppButton>
              <AppButton v-if="current.status === 'CLOSED'" :disabled="saving || !!pending || detailLoading || !detailReady" size="small" variant="primary" @click="allocateConfirm">自动分配</AppButton>
              <AppButton v-if="current.status === 'ALLOCATED'" :disabled="saving || !!pending || detailLoading || !detailReady" size="small" variant="primary" @click="act('confirm', '确认分流（写学籍专业）')">确认分流</AppButton>
            </div>
          </div>

          <div class="aams-context"><p>{{ current.grade }} 级 · 最多 {{ current.maxChoices }} 个志愿</p><p>填报开始：{{ current.volunteerStart || '未返回' }} · 截止：{{ current.volunteerEnd || '未返回' }}</p><p>容量与试分仅供核对。正式分配、调剂及确认均由服务器重新校验；确认分流后可到学生学籍档案核对回写。</p></div><LoadingState v-if="detailLoading" />
          <template v-if="detailReady"><div class="aams-section-title">可选专业与容量</div>
          <EmptyState v-if="!options.length" title="未配置可选专业" description="草稿阶段添加专业与容量" />
          <DataTable v-else :columns="optionColumns" :rows="options.slice(0,optionLimit)" row-key="optionId">
            <template #cell-fill="{ row }">{{ row.allocatedCount ?? '待核对' }} / {{ row.capacity ?? '待核对' }}（余 {{ row.remain ?? '待核对' }}）</template>
          </DataTable>

          <AppButton v-if="optionLimit<options.length" @click="optionLimit+=20">显示更多专业</AppButton>
          <AppInlineAlert v-if="allocPreview" type="info"
                          :description="'试分结果（未落库）：可分配 ' + allocPreview.allocated + ' 人，待调剂 ' + allocPreview.unallocated + ' 人'" />

          <div class="aams-section-title">志愿与分配结果</div>
          <EmptyState v-if="!volunteers.length" title="暂无志愿" description="开放填报后学生志愿显示在此" />
          <DataTable v-else :columns="volColumns" :rows="volunteers" row-key="volunteerId" :pagination="{page:volPage,pageSize:20,total:volTotal}" @page-change="turnVol">
            <template #cell-student="{ row }">{{ row.studentName }}（{{ row.studentNo }}）<span v-if="row.gpa != null" class="mp-cell-sub">绩点 {{ row.gpa }}</span></template>
            <template #cell-choices="{row}">{{ (row.choices||[]).map((id,i)=>(i+1)+'志愿：'+majorName(id)).join('；') || '志愿未返回' }}</template>
            <template #cell-result="{ row }">
              <span v-if="row.status === 'UNALLOCATED'" class="aams-warn">待调剂</span>
              <span v-else-if="row.resultMajorId">{{ majorName(row.resultMajorId) }}<span class="mp-cell-sub">（{{ row.resultChoiceRank === 0 ? '调剂' : row.resultChoiceRank == null ? '志愿序号待核对' : '第' + row.resultChoiceRank + '志愿' }}）</span></span>
              <span v-else>—</span>
            </template>
            <template #cell-status="{ row }"><StatusTag :type="volType(row.status)" :label="volLabel(row.status)" dot /></template>
            <template #cell-ops="{ row }">
              <button v-if="canManage && current.status === 'ALLOCATED' && row.status !== 'CONFIRMED'" class="mp-link" :disabled="saving || !!pending || !detailReady" @click="openReassign(row)">调剂</button>
            </template>
          </DataTable>
          </template>
        </template>
      </div>
    </div>

    <section v-if="receipt" class="aams-receipt" role="status"><b>{{ receipt.verified ? '已核对正式结果' : '结果待核实' }}</b><p>{{ receipt.label }}</p><AppButton v-if="pending" :disabled="saving || checking" @click="verify">只读查询原批次结果</AppButton></section>
    <AppDrawer :visible="createVisible" title="新建专业分流批次" mode="modal" size="medium" @close="createVisible = false">
      <div class="aams-form">
        <AppFormItem label="批次名称" required><AppTextInput v-model="form.batchName" placeholder="如 2024级电子信息大类分流" :disabled="saving || !!pending" /></AppFormItem>
        <AppFormItem label="分流年级" required><AppTextInput v-model="form.grade" placeholder="如 2024" :disabled="saving || !!pending" /></AppFormItem>
        <AppFormItem label="大类源专业"><AppMajorPicker v-model="form.sourceMajorId" placeholder="选填；限定只有该大类学生可报" :disabled="saving || !!pending" /></AppFormItem>
        <AppFormItem label="志愿数上限"><AppNumberInput v-model="form.maxChoices" :min="1" :max="10" :disabled="saving || !!pending" /></AppFormItem>
        <AppInlineAlert v-if="formError" type="danger" :description="formError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving || !!pending" @click="createVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitCreate">创建</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="optionVisible" title="添加可选专业" mode="modal" size="medium" @close="optionVisible = false">
      <div class="aams-form">
        <AppFormItem label="专业" required><AppMajorPicker v-model="optionForm.majorId" :disabled="saving || !!pending" /></AppFormItem>
        <AppFormItem label="容量" required><AppNumberInput v-model="optionForm.capacity" :min="1" :max="2000" :disabled="saving || !!pending" /></AppFormItem>
        <AppInlineAlert v-if="optionError" type="danger" :description="optionError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving || !!pending" @click="optionVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitOption">添加</AppButton>
      </template>
    </AppDrawer>

    <AppDrawer :visible="reassignVisible" :title="'人工调剂 · ' + (reassignRow ? reassignRow.studentName : '')" mode="modal" size="medium" @close="reassignVisible = false">
      <div class="aams-form">
        <AppFormItem label="目标专业" required>
          <AppMajorPicker v-model="reassignForm.majorId" :options="options.map(o => ({ label: o.majorName + '（余 ' + (o.remain ?? '待核对') + '）', value: o.majorId }))" :disabled="saving || !!pending" />
        </AppFormItem>
        <AppFormItem label="调剂原因（≥5字）" required><AppTextarea v-model="reassignForm.reason" placeholder="如：第一志愿容量满，经与学生沟通同意调剂" :disabled="saving || !!pending" /></AppFormItem>
        <AppInlineAlert v-if="reassignError" type="danger" :description="reassignError" />
      </div>
      <template #footer>
        <AppButton variant="ghost" :disabled="saving || !!pending" @click="reassignVisible = false">取消</AppButton>
        <AppButton variant="primary" :loading="saving" @click="submitReassign">调剂</AppButton>
      </template>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirmVisible" :title="confirmTitle" :message="confirmMessage" :submitting="saving" :confirm-disabled="!!pending" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import {ModulePageShell,DataTable,StatusTag,LoadingState,ErrorState,EmptyState} from '@/components/business'
import {AppButton,AppDrawer} from '@/components/ui'
import {AppTextInput,AppNumberInput,AppTextarea,AppFormItem,AppConfirmDialog,AppInlineAlert,AppMajorPicker} from '@/components/common'
import {academicAffairsMajorSplitApi as api} from '../api/academic-affairs.api'
import {currentUserFromToken} from '@/services/http/client'
import {matchPermission} from '@/config/navPlan'
import {gradeError} from './parallel-c/grade-review'
const LABELS={DRAFT:'草稿',OPEN:'填报中',CLOSED:'已截止',ALLOCATED:'已分配，待确认',CONFIRMED:'已确认分流'}
const VOL_LABELS={PENDING:'待分配',ALLOCATED:'已分配',UNALLOCATED:'待调剂',CONFIRMED:'已确认'}
const exactId=v=>typeof v==='string'&&/^[1-9]\d*$/.test(v)?v:(typeof v==='number'&&Number.isSafeInteger(v)&&v>0?String(v):'')
export default {
 name:'AaMajorSplitView',components:{ModulePageShell,DataTable,StatusTag,LoadingState,ErrorState,EmptyState,AppButton,AppDrawer,AppTextInput,AppNumberInput,AppTextarea,AppFormItem,AppConfirmDialog,AppInlineAlert,AppMajorPicker},props:{ctx:{type:Object,required:true}},
 data(){return {alive:true,scope:0,readSeq:0,detailSeq:0,loading:true,detailLoading:false,detailReady:false,error:'',rows:[],current:null,options:[],volunteers:[],optionLimit:20,batchPage:1,batchTotal:0,volPage:1,volTotal:0,allocPreview:null,saving:false,checking:false,pending:null,receipt:null,confirmVisible:false,confirmTitle:'',confirmMessage:'',command:null,
 batchColumns:[{key:'batchName',title:'批次名称'},{key:'grade',title:'适用年级'},{key:'maxChoices',title:'志愿数上限'},{key:'status',title:'当前阶段'},{key:'action',title:'办理入口'}],optionColumns:[{key:'majorName',title:'可选专业'},{key:'fill',title:'容量使用'}],volColumns:[{key:'student',title:'学生'},{key:'choices',title:'志愿顺序'},{key:'result',title:'分配结果'},{key:'status',title:'正式状态'},{key:'ops',title:'操作'}],
 createVisible:false,form:{batchName:'',grade:'',sourceMajorId:'',maxChoices:3},formError:'',optionVisible:false,optionForm:{majorId:'',capacity:50},optionError:'',reassignVisible:false,reassignRow:null,reassignForm:{majorId:'',reason:''},reassignError:''}},
 computed:{
  identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
  canManage(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.majorSplit.manage')},
  splitSteps(){return ['创建批次','填报志愿','分配调剂','确认结果','学籍回写']},
  splitStepNotes(){return ['上游事实可回查','学生志愿可回查','当前设计视角','正式状态解锁','核对学生主档']},
  currentStage(){const map={DRAFT:0,OPEN:1,CLOSED:2,ALLOCATED:3,CONFIRMED:4};return this.current?map[this.current.status]??0:0}
 },
 watch:{identity(){this.invalidate();this.restoreRoute()},'$route.query'(){const q=this.$route?.query||{};if(String(q.batchId||'')===String(this.current?.batchId||'')&&this.pageNumber(q.page)===this.batchPage&&this.pageNumber(q.volPage)===this.volPage)return;this.restoreRoute()}},created(){this.restoreRoute()},beforeUnmount(){this.alive=false;this.invalidate()},
 beforeRouteLeave(){if((this.pending&&this.valid(this.pending))||(this.saving&&this.command&&this.valid(this.command)))return false},
 beforeRouteUpdate(){if((this.pending&&this.valid(this.pending))||(this.saving&&this.command&&this.valid(this.command)))return false},
 methods:{
  pageNumber(v){const n=Number(v);return Number.isSafeInteger(n)&&n>0?n:1},
  batchCount(...states){return this.rows.filter(row=>states.includes(row.status)).length},
  writeQuery(push=false){if(!this.$router)return;const query={...(this.$route?.query||{}),page:String(this.batchPage)};if(this.current){query.batchId=String(this.current.batchId);query.volPage=String(this.volPage)}else{delete query.batchId;delete query.volPage}const result=this.$router[push?'push':'replace']({query});result?.catch?.(()=>{})},
  async restoreRoute(){if(this.saving||this.pending)return;this.invalidate();const q=this.$route?.query||{},id=String(q.batchId||'');this.batchPage=this.pageNumber(q.page);this.volPage=this.pageNumber(q.volPage);const c=this.capture();await this.load();if(!id||!this.valid(c)||this.error)return;this.detailLoading=true;try{const row=await this.findBatch(c,id,true);if(!this.valid(c))return;if(!row)throw {code:404};this.current={...row};await this.refresh()}catch(err){if(this.valid(c))this.fail(err,'原批次尚未定位，请返回批次列表继续查询。')}finally{if(this.valid(c))this.detailLoading=false}},
  stLabel(v){return LABELS[v]||'状态待核对'},stType(v){return v==='CONFIRMED'?'success':v==='ALLOCATED'?'warning':'primary'},volLabel(v){return VOL_LABELS[v]||'状态待核对'},volType(v){return v==='CONFIRMED'?'success':v==='UNALLOCATED'?'warning':'primary'},majorName(id){return this.options.find(o=>String(o.majorId)===String(id))?.majorName||'专业名称待核对'},
  capture(){return {scope:this.scope,identity:this.identity,bid:this.current?.batchId,batchPage:this.batchPage,volPage:this.volPage}},valid(c){return this.alive&&c.scope===this.scope&&c.identity===this.identity},
  cancelConfirm(){this.command=null;this.confirmVisible=false},
  invalidate(){this.scope++;this.readSeq++;this.detailSeq++;this.rows=[];this.current=null;this.options=[];this.volunteers=[];this.allocPreview=null;this.batchTotal=0;this.volTotal=0;this.loading=false;this.detailLoading=false;this.detailReady=false;this.saving=false;this.checking=false;this.pending=null;this.receipt=null;this.cancelConfirm();this.createVisible=false;this.optionVisible=false;this.reassignVisible=false;this.reassignRow=null;this.form={batchName:'',grade:'',sourceMajorId:'',maxChoices:3};this.optionForm={majorId:'',capacity:50};this.reassignForm={majorId:'',reason:''};this.error='';this.formError='';this.optionError='';this.reassignError=''},
  fail(err,fallback){if(/403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' ')))this.invalidate();this.error=gradeError(err,fallback);this.formError=this.error;this.optionError=this.error;this.reassignError=this.error},
  async load(){if(this.saving||this.pending)return;const c=this.capture(),seq=++this.readSeq;this.loading=true;this.error='';this.rows=[];this.batchTotal=0;try{const res=await api.listBatches({page:this.batchPage,pageSize:20});if(!this.valid(c)||seq!==this.readSeq)return;if(res?.code!==0)throw res;if(!Array.isArray(res.data?.list))throw {code:503};this.rows=res.data.list;this.batchTotal=res.data?.total??this.rows.length}catch(err){if(this.valid(c)&&seq===this.readSeq)this.fail(err,'批次读取失败，请重试。')}finally{if(this.valid(c)&&seq===this.readSeq)this.loading=false}},
  turnBatch(page){if(this.saving||this.pending)return;this.batchPage=page;this.cancelConfirm();this.writeQuery();this.load()},
  async select(row){if(this.saving||this.pending)return;this.scope++;this.cancelConfirm();this.current={...row};this.allocPreview=null;this.receipt=null;this.optionVisible=false;this.reassignVisible=false;this.reassignRow=null;this.volPage=1;this.optionLimit=20;this.writeQuery(true);await this.refresh()},
  backToList(){if(this.saving||this.pending)return;this.scope++;this.detailSeq++;this.current=null;this.options=[];this.volunteers=[];this.detailReady=false;this.volPage=1;this.allocPreview=null;this.cancelConfirm();this.writeQuery(true);this.load()},
  turnVol(page){if(this.saving||this.pending)return;this.volPage=page;this.cancelConfirm();this.writeQuery();this.refresh()},
  async refresh(){
    if(!this.current)return
    const c=this.capture(),seq=++this.detailSeq;this.options=[];this.volunteers=[];this.volTotal=0;this.detailReady=false;this.detailLoading=true;this.error=''
    try{const [batch,op,vo]=await Promise.all([this.findBatch(c,c.bid,true),api.listOptions(c.bid),api.listVolunteers(c.bid,{page:this.volPage,pageSize:20})]);if(!this.valid(c)||seq!==this.detailSeq)return;if(op?.code!==0)throw op;if(vo?.code!==0)throw vo;if(!batch||!Array.isArray(op.data?.items)||!Array.isArray(vo.data?.list))throw {code:503};this.current={...batch};this.options=op.data.items;this.volunteers=vo.data.list;this.volTotal=vo.data.total??this.volunteers.length;this.detailReady=true}
    catch(err){if(this.valid(c)&&seq===this.detailSeq)this.fail(err,'批次明细读取失败，请重试。')}
    finally{if(this.valid(c)&&seq===this.detailSeq)this.detailLoading=false}
  },
  openCreate(){if(!this.canManage||this.saving||this.pending)return;this.form={batchName:'',grade:'',sourceMajorId:'',maxChoices:3};this.formError='';this.createVisible=true},
  submitCreate(){if(!this.canManage||this.saving||this.pending)return;const sourceMajorId=this.form.sourceMajorId?exactId(this.form.sourceMajorId):'';if(!this.form.batchName.trim()||!this.form.grade.trim()||(this.form.sourceMajorId&&!sourceMajorId)||!Number.isInteger(Number(this.form.maxChoices))||Number(this.form.maxChoices)<1||Number(this.form.maxChoices)>10){this.formError='请填写批次名称、年级、有效来源专业和1至10的志愿上限。';return}return this.run({...this.capture(),kind:'create',body:{batchName:this.form.batchName.trim(),grade:this.form.grade.trim(),sourceMajorId:sourceMajorId||undefined,maxChoices:Number(this.form.maxChoices)},label:'创建分流批次'})},
  openAddOption(){if(!this.canManage||this.saving||this.pending||!this.detailReady||this.current?.status!=='DRAFT')return;this.optionForm={majorId:'',capacity:50};this.optionError='';this.optionVisible=true},
  submitOption(){if(!this.canManage||this.saving||this.pending||!this.detailReady||this.current?.status!=='DRAFT')return;const majorId=exactId(this.optionForm.majorId);if(!majorId||this.optionForm.capacity==null||this.optionForm.capacity===''||!Number.isInteger(Number(this.optionForm.capacity))||Number(this.optionForm.capacity)<1||Number(this.optionForm.capacity)>2000){this.optionError='请选择有效专业并填写1至2000的整数容量。';return}return this.run({...this.capture(),kind:'option',before:{...this.current},body:{majorId,capacity:Number(this.optionForm.capacity)},label:'添加可选专业'})},
  act(kind,label){if(!this.canManage||this.saving||this.pending||this.detailLoading||!this.detailReady)return;const expected={open:'DRAFT',close:'OPEN',confirm:'ALLOCATED'}[kind];if(!expected||!this.detailReady||this.current?.status!==expected)return;this.command={...this.capture(),kind,before:{...this.current},label};this.confirmTitle=label;this.confirmMessage=`${this.current.batchName} · ${this.current.grade}级。服务器将重新核验批次、容量和学生来源；正式结果需回读确认。`;this.confirmVisible=true},
  allocateConfirm(){if(!this.canManage||this.saving||this.pending||!this.detailReady||this.current?.status!=='CLOSED')return;this.command={...this.capture(),kind:'allocate',before:{...this.current},label:'自动分配'};this.confirmTitle='确认自动分配';this.confirmMessage=`${this.current.batchName}。按服务器当前正式绩点与志愿重新分配，试分预览不保证本次结果。`;this.confirmVisible=true},
  async allocate(dryRun){if(!dryRun)return this.allocateConfirm();if(!this.canManage||this.saving||this.pending||!this.detailReady||this.current?.status!=='CLOSED')return;const c=this.capture();this.saving=true;this.allocPreview=null;try{const res=await api.allocate(c.bid,true);if(!this.valid(c))return;if(res?.code!==0)throw res;if(String(res.data?.batchId)!==String(c.bid)||res.data?.dryRun!==true)throw {code:503};this.allocPreview=res.data}catch(err){if(this.valid(c))this.fail(err,'试分预览读取失败，请重试。')}finally{if(this.valid(c))this.saving=false}},
  openReassign(row){if(!this.canManage||this.saving||this.pending||!this.detailReady||this.current?.status!=='ALLOCATED'||row.status==='CONFIRMED')return;this.reassignRow={...row,choices:[...(row.choices||[])]};this.reassignForm={majorId:'',reason:''};this.reassignError='';this.reassignVisible=true},
  submitReassign(){if(!this.reassignRow||!this.canManage||this.saving||this.pending)return;const majorId=exactId(this.reassignForm.majorId);if(!majorId||this.reassignForm.reason.trim().length<5){this.reassignError='请选择有效目标专业并填写至少5字原因。';return}return this.run({...this.capture(),kind:'reassign',before:{...this.current},row:{...this.reassignRow},body:{majorId,reason:this.reassignForm.reason.trim()},label:'人工调剂'})},
  async onConfirm(){const c=this.command;if(!c||!this.valid(c)||this.saving||this.pending)return;await this.run(c)},
  async findBatch(c,id,reset=false){if(!id)return null;let page=reset?(c.batchPage||1):(c.batchLookupPage||c.batchPage||1);for(let i=0;i<3;i++,page++){const res=await api.listBatches({page,pageSize:20});if(!this.valid(c))return null;if(res?.code!==0)throw res;const row=res.data?.list?.find(r=>String(r.batchId)===String(id));if(row){c.batchLookupPage=page;return row}const total=res.data?.total;if((Number.isFinite(total)&&page*20>=total)||(res.data?.list||[]).length<20){c.batchLookupPage=1;return null}c.batchLookupPage=page+1}return null},
  async findVolunteer(c){let page=c.volLookupPage||c.volPage||1;for(let i=0;i<3;i++,page++){const res=await api.listVolunteers(c.bid,{page,pageSize:20});if(!this.valid(c))return null;if(res?.code!==0)throw res;const row=res.data?.list?.find(r=>String(r.volunteerId)===String(c.row.volunteerId));if(row){c.volLookupPage=page;return row}if((Number.isFinite(res.data?.total)&&page*20>=res.data.total)||(res.data?.list||[]).length<20){c.volLookupPage=1;return null}c.volLookupPage=page+1}return null},
  sameBatch(a,b){return !!a&&!!b&&['batchId','batchName','grade','sourceMajorId','maxChoices','status','volunteerStart','volunteerEnd'].every(k=>String(a[k]??'')===String(b[k]??''))},
  async run(c){
    if(!this.canManage||this.saving||this.pending||!this.valid(c)||(c.kind!=='create'&&!this.detailReady))return;if((c.kind!=='create'&&!exactId(c.bid))||(c.kind==='reassign'&&!exactId(c.row?.volunteerId))){this.error='当前对象无法准确核对，请重新选择。';return}this.saving=true;this.error=''
    try{if(c.kind!=='create'){const before=await this.findBatch(c,c.bid,true);if(!this.valid(c))return;if(!this.sameBatch(before,c.before))throw {code:409};if(c.kind==='reassign'){const row=await this.findVolunteer(c);if(!this.valid(c))return;if(!row||['volunteerId','studentId','resultMajorId','status','adjustReason'].some(k=>String(row[k]??'')!==String(c.row[k]??''))||JSON.stringify(row.choices||[])!==JSON.stringify(c.row.choices||[]))throw {code:409}}}
      this.pending=c;this.receipt={verified:false,label:c.label+'：结果待核实'}
      let res;try{if(c.kind==='create')res=await api.createBatch(c.body);else if(c.kind==='option')res=await api.addOption(c.bid,c.body);else if(c.kind==='reassign')res=await api.reassign(c.row.volunteerId,c.body.majorId,c.body.reason);else if(c.kind==='allocate')res=await api.allocate(c.bid,false);else res=await api[c.kind](c.bid)}catch(err){res=err}
      if(!this.valid(c))return
      if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|FORBIDDEN|NO_PERMISSION|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pending=null;this.receipt=null;throw res}
      c.ack=res?.code===0?res.data:null;this.cancelConfirm();await this.verify()
    }catch(err){if(this.valid(c)){this.cancelConfirm();this.fail(err,'本次办理未确认，请核对原批次后重试。')}}finally{if(this.valid(c))this.saving=false}
  },
  async verify(){
    const c=this.pending;if(!c||!this.valid(c)||this.checking)return;this.checking=true
    try{const targetBatchId=c.kind==='create'?exactId(c.ack?.batchId):exactId(c.bid);let row,matches=false,batch=targetBatchId?await this.findBatch(c,targetBatchId):null;if(!this.valid(c))return
      if(c.kind==='create')matches=!!batch&&!!c.ack&&['batchName','grade','sourceMajorId','maxChoices'].every(k=>String(batch[k]??'')===String(c.body[k]??''))&&batch.status==='DRAFT'
      else if(c.kind==='option'){const res=await api.listOptions(c.bid);if(!this.valid(c))return;if(res?.code!==0)throw res;row=res.data?.items?.find(o=>String(o.optionId)===String(c.ack?.optionId));matches=!!c.ack&&!!row&&String(row.majorId)===c.body.majorId&&Number(row.capacity)===c.body.capacity;this.options=res.data?.items||[]}
      else if(c.kind==='reassign'){row=await this.findVolunteer(c);if(!this.valid(c))return;matches=!!c.ack&&String(c.ack.volunteerId)===String(c.row.volunteerId)&&!!row&&row.status==='ALLOCATED'&&String(row.resultMajorId)===c.body.majorId&&row.adjustReason===c.body.reason;if(row){const existing=this.volunteers.find(v=>String(v.volunteerId)===String(row.volunteerId));if(existing)Object.assign(existing,row)}}
      else {const expected=({open:'OPEN',close:'CLOSED',allocate:'ALLOCATED',confirm:'CONFIRMED'})[c.kind];matches=!!c.ack&&String(c.ack.batchId)===String(c.bid)&&(c.kind==='allocate'?c.ack.dryRun===false:c.ack.status===expected)&&!!batch&&batch.status===expected}
      if(!matches){if(batch)await this.refresh();if(!this.valid(c)||this.pending!==c)return;this.error='结果待核实：当前正式状态已尽可能回读，但尚不能确认本次操作归属，请只读查询，勿重复提交。';return}
      if(batch){this.current={...batch};const old=this.rows.find(r=>String(r.batchId)===String(batch.batchId));if(old)Object.assign(old,batch)}
      this.receipt={verified:true,label:c.label+'：已核对正式'+(c.kind==='reassign'?'本人分配记录':'批次结果')};this.pending=null;this.error='';this.formError='';this.optionError='';this.reassignError='';this.createVisible=false;this.optionVisible=false;this.reassignVisible=false;this.allocPreview=null;await this.refresh()
    }catch(err){if(this.valid(c))this.fail(err,'结果待核实，请稍后只读查询。')}finally{if(this.valid(c))this.checking=false}
  }
 }
}
</script>

<style scoped>
.aams-layout { display: grid; grid-template-columns: minmax(0,1fr); gap: 16px; }.aams-layout.is-list{grid-template-columns:minmax(0,1fr)!important}.aams-list,.aams-detail{min-width:0;padding:18px;border:1px solid var(--border-200,#e1e7ef);border-radius:10px;background:var(--bg-white,#fff)}.aams-context,.aams-receipt{padding:14px;border-radius:8px;background:var(--primary-50,#edf3ff);margin:14px 0}.aams-context p,.aams-receipt p{font-size:13px;line-height:1.7;margin:6px 0}
.aams-progress{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;list-style:none;margin:0;padding:15px 16px;border:1px solid var(--card-b,#dce5ef);border-radius:12px;background:#fff}.aams-progress li{display:flex;gap:9px;color:var(--t3,#65778b);font-size:12px}.aams-progress li>span{display:grid;place-items:center;flex:0 0 24px;height:24px;border:1px solid var(--card-b,#dce5ef);border-radius:50%}.aams-progress strong,.aams-progress small{display:block}.aams-progress strong{padding-top:3px;color:var(--t2,#40536b)}.aams-progress small{margin-top:7px;line-height:1.45}.aams-progress .is-current>span{border-color:var(--pri,#2f66bd);background:var(--pri,#2f66bd);color:#fff}.aams-progress .is-complete>span{border-color:#b8dcc5;background:#edf8f1;color:#167647}
.aams-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.aams-metrics article{display:grid;gap:7px;padding:15px 16px;border:1px solid var(--card-b,#dce5ef);border-radius:12px;background:#fff}.aams-metrics span,.aams-metrics small{color:var(--t3,#65778b);font-size:12px}.aams-metrics strong{font-size:25px;color:var(--t1,#18304f)}
.aams-batches { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.aams-batch { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border: 1px solid var(--border-color, #e5e7eb); border-radius: 8px; cursor: pointer; }
.aams-batch.is-active { border-color: var(--primary-color, #2563eb); background: var(--primary-light, #eff6ff); }
.aams-batch-name { font-weight: 500; font-size: 14px; }
.aams-head { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px; }
.aams-title { font-size: 16px; font-weight: 600; margin-bottom: 6px; }
.aams-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.aams-section-title { font-weight: 500; margin: 16px 0 8px; }
.aams-warn { color: var(--danger-color, #dc2626); font-weight: 600; }
.aams-form { display: flex; flex-direction: column; gap: 12px; }
@media(max-width:900px){.aams-progress{grid-template-columns:1fr}.aams-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
