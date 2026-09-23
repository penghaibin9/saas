<template>
  <ModulePageShell
    :title="pageTitle"
    :subtitle="pageSubtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton v-if="!batch && canManage" variant="primary" @click="showCreate = !showCreate">{{ showCreate ? '收起新建' : '新建审核批次' }}</AppButton>
      <AppButton v-if="batch" variant="ghost" :disabled="busy || !!pendingCommand" @click="resetBatch">返回批次队列</AppButton>
      <AppButton v-if="batch" variant="primary" :disabled="busy" @click="enterAudit(batch, 'results')">进入审核工作台</AppButton>
    </template>
    <div class="mp-stack">
      <GraduationStageRail v-if="batch" :active="batch.status === 'ARCHIVED' ? 5 : (batch.status === 'PRECHECKED' ? 2 : 1)" />

      <section v-if="batch" class="grad-object" aria-label="当前毕业审核对象">
        <div><span>当前批次</span><strong>{{ batch.batchName }}</strong><small>来源：毕业审核批次 #{{ batch.batchId }}</small></div>
        <div><span>当前状态</span><strong>{{ academicStatusLabel(batch.status) }}</strong><small>应审 {{ batch.total || 0 }} 人 · 系统异常 {{ batch.abnormal || 0 }} 人</small></div>
        <div><span>当前责任</span><strong>{{ Number(batch.abnormal || 0) ? '证据责任岗' : '学院审核岗' }}</strong><small>{{ Number(batch.abnormal || 0) ? '先治理阻断项并重新预审' : '核对十一项正式证据' }}</small></div>
        <div><span>下一岗位</span><strong>{{ Number(batch.abnormal || 0) ? '学院审核岗' : '教务终审岗' }}</strong><small>完成当前阶段后自动进入下一队列</small></div>
      </section>

      <AppSectionCard v-if="!batch && showCreate" title="新建审核批次">
        <div class="aa-cal-form">
          <label class="aa-cal-form__item aa-cal-form__item--grow">批次名称<input v-model.trim="draft.batchName" class="aa-input" placeholder="如 2026届毕业资格审核" maxlength="60" /></label>
          <label class="aa-cal-form__item">年级<input v-model.trim="draft.gradeYear" class="aa-input aa-input--sm" placeholder="如 2023" /></label>
          <label class="aa-cal-form__item">专业<AppMajorPicker v-model="draft.majorId" placeholder="选择专业（选填）" /></label>
          <AppButton variant="primary" :loading="creating" :disabled="!canManage || creating || !!pendingCommand || !draft.batchName" @click="createBatch">创建</AppButton>
        </div>
      </AppSectionCard>

      <template v-if="batch">
        <AppSectionCard :title="`批次：${batch.batchName}`">
          <div class="aa-batch-actions">
            <AppStatusTag type="primary">{{ academicStatusLabel(batch.status) }}</AppStatusTag>
            <AppButton :loading="busy" :disabled="!canManage || busy || !!pendingCommand" @click="generate">圈定应届生</AppButton>
            <AppButton :loading="busy" :disabled="!canManage || busy || !!pendingCommand" @click="precheck">执行十一项预审</AppButton>
            <AppButton variant="primary" :disabled="busy" @click="enterAudit(batch, 'results')">查看结果 / 复核</AppButton>
          </div>
          <AppInlineAlert v-if="genInfo" type="success" :message="genInfo" />
          <AppInlineAlert v-if="preInfo" type="success" :message="preInfo" />
          <AppInlineAlert v-if="pendingCommand" type="warning" description="上一次写操作结果待核实，请勿重复执行；可从审核工作台读取当前正式结果。" />
          <p class="mp-note">十一项含学籍/学分/必修/选修/实践/实习/毕设/处分/就业/学工归档/费用。必需项处于“待治理”时会形成系统异常，须先治理并重新预审；只有最新一次完整正式检查达到“系统预审通过”，才能由学院通过并进入教务终审。</p>
        </AppSectionCard>
      </template>

      <section v-if="isBatchList" class="grad-metrics" aria-label="批次真实概览">
        <article><span>当前页批次</span><strong>{{ batches.length }}</strong><small>总计 {{ batchPagination.total }} 个正式批次</small></article>
        <article><span>当前页应审</span><strong>{{ pageTotals.total }}</strong><small>已圈定审核范围</small></article>
        <article><span>系统异常</span><strong>{{ pageTotals.abnormal }}</strong><small>需返回责任模块治理</small></article>
        <article><span>已终审</span><strong>{{ pageTotals.concluded }}</strong><small>可进入证书与归档</small></article>
      </section>

      <AppSectionCard :title="isBatchList ? '审核批次队列' : '毕业预审批次'">
        <ErrorState v-if="listError" :description="listError" @retry="loadBatches" />
        <LoadingState v-else-if="loadingList" />
        <EmptyState v-else-if="!batches.length" title="暂无历史批次" description="新建的审核批次会持久保存在此，刷新页面不丢失" />
        <DataTable
          v-else
          :columns="listColumns"
          :rows="batches"
          row-key="batchId"
          :pagination="batchPagination"
          @page-change="onBatchPageChange"
        >
          <template #cell-status="{ row }"><AppStatusTag :type="row.status === 'ARCHIVED' ? 'default' : 'primary'" dot>{{ academicStatusLabel(row.status) }}</AppStatusTag></template>
          <template #cell-precheck="{ row }"><span>{{ row.total ? `通过 ${row.passed || 0} · 异常 ${row.abnormal || 0}` : '尚未预审' }}</span></template>
          <template #cell-ops="{ row }">
            <button v-if="!isBatchList && row.status !== 'ARCHIVED'" class="mp-link" @click="chooseBatch(row)">继续预审</button>
            <button class="mp-link" @click="enterAudit(row, row.status === 'ARCHIVED' ? 'archive' : 'results')">{{ row.status === 'ARCHIVED' ? '查看归档结果' : '查看结果与办理' }}</button>
          </template>
        </DataTable>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
// 后端门禁：只有最新完整正式 Run 为 SYSTEM_PASSED 才能学院通过并进入教务终审。
/** 审核批次（/admin/academic-affairs/graduation）：建批次 + 圈定 + 预审 + 历史批次列表（进审核工作台）。 */
import { ModulePageShell, DataTable, LoadingState, EmptyState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppInlineAlert, AppMajorPicker } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicStatusLabel } from '@/modules/academicAffairs/constants/academic-display.constants'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { gradeError } from './parallel-c/grade-review'
import { matchPermission } from '@/config/navPlan'
import GraduationStageRail from '@/modules/academicAffairs/components/graduation/GraduationStageRail.vue'

const exactId = (value) => typeof value === 'string' && /^[1-9]\d*$/.test(value)
  ? value
  : (typeof value === 'number' && Number.isSafeInteger(value) && value > 0 ? String(value) : '')

export default {
  name: 'AaGraduationBatchView',
  components: { ModulePageShell, DataTable, LoadingState, EmptyState, ErrorState, AppButton, AppSectionCard, AppStatusTag, AppInlineAlert, AppMajorPicker, GraduationStageRail },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  data() {
    return {
      alive: true, scope: 0, listSeq: 0, pendingCommand: null, showCreate: false,
      draft: { batchName: '', gradeYear: '', majorId: '' },
      creating: false, batch: null, busy: false, genInfo: '', preInfo: '',
      batches: [], loadingList: true, listError: '',
      batchPagination: { page: 1, pageSize: 20, total: 0 },
      listColumns: [
        { key: 'batchName', title: '批次名称' }, { key: 'gradeYear', title: '年级' },
        { key: 'total', title: '学生数' }, { key: 'precheck', title: '预审结论' },
        { key: 'status', title: '当前阶段' }, { key: 'ops', title: '办理入口', width: '190px' }
      ]
    }
  },
  computed:{
    identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
    canManage(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.graduation.manage')},
    isBatchList(){return this.$route.query.tab==='batches'},
    pageTitle(){return this.isBatchList?'审核批次':'毕业预审'},
    pageSubtitle(){return this.isBatchList?'建立正式审核范围，跟踪十一项供数三态预审与终审进度':'从学生对象进入十一项正式证据（学籍/学分/必修/选修/实践/实习/毕设/处分/就业/学工归档/费用），先治理阻断，再依次完成学院审核与教务终审'},
    pageTotals(){return this.batches.reduce((sum,row)=>({total:sum.total+Number(row.total||0),abnormal:sum.abnormal+Number(row.abnormal||0),concluded:sum.concluded+Number(row.concluded||0)}),{total:0,abnormal:0,concluded:0})}
  },
  watch:{identity(){this.scope++;this.listSeq++;this.batch=null;this.batches=[];this.pendingCommand=null;this.genInfo='';this.preInfo='';this.loadBatches()}},
  created() { const page=Number(this.$route.query.page);this.batchPagination.page=Number.isSafeInteger(page)&&page>0&&page<=1000000?page:1;this.loadBatches() },
  beforeUnmount(){this.alive=false;this.scope++;this.listSeq++},
  methods: {
    academicStatusLabel,
    chooseBatch(row){if(this.busy||this.pendingCommand)return;this.batch={...row};this.genInfo='';this.preInfo=''},
    enterAudit(row,tab){const id=exactId(row?.batchId);if(!id)return;const returnToken=this.academicFlow?.captureReturn?.();this.$router.push({path:'/admin/academic-affairs/graduation/audit-console',query:{batchId:id,tab,...(returnToken?{returnToken}:{})}})},
    current(c){return this.alive&&c.scope===this.scope&&c.identity===this.identity},
    denied(err){return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))},
    clearPrivate(){this.scope++;this.listSeq++;this.batch=null;this.batches=[];this.pendingCommand=null;this.genInfo='';this.preInfo=''},
    fail(err,fallback){if(this.denied(err))this.clearPrivate();return gradeError(err,fallback)},
    async loadBatches() {
      const c={scope:this.scope,identity:this.identity,seq:++this.listSeq,page:this.batchPagination.page};this.loadingList = true;this.listError='';this.batches=[]
      try {
        const res = await academicAffairsApi.listGradBatches({
          page: this.batchPagination.page,
          pageSize: this.batchPagination.pageSize
        })
        if(!this.current(c)||c.seq!==this.listSeq||c.page!==this.batchPagination.page)return
        if(res.code!==0)throw res;if(!Array.isArray(res.data?.list))throw {code:503}
        this.batches=res.data.list;this.batchPagination.total = res.data.total
      } catch (e) {
        if(this.current(c)){this.listError=this.fail(e,'审核批次加载失败');this.batches=[]}
      } finally {
        if(this.current(c)&&c.seq===this.listSeq)this.loadingList=false
      }
    },
    async readBatch(batchId){const id=exactId(batchId);if(!id)return null;const res=await academicAffairsApi.listGradBatches({batchId:id,page:1,pageSize:1});if(res?.code!==0)throw res;if(!Array.isArray(res.data?.list))throw {code:503};return res.data.list.find(item=>exactId(item.batchId)===id)||null},
    onBatchPageChange(page) {
      this.batchPagination.page = page
      this.$router.replace({path:this.$route.path,query:{...this.$route.query,page:String(page)}})
      this.loadBatches()
    },
    async createBatch() {
      if (!this.canManage || this.creating || this.pendingCommand || !this.draft.batchName) return
      const majorId=this.draft.majorId?exactId(this.draft.majorId):''
      if(this.draft.majorId&&!majorId){toast.error('所选专业标识无法准确核对，请重新选择');return}
      const c={scope:this.scope,identity:this.identity},body={batchName:this.draft.batchName,gradeYear:this.draft.gradeYear||undefined,majorId:majorId||undefined};this.creating = true;this.pendingCommand={kind:'create'}
      try {
        let res;try{res=await academicAffairsApi.createGradBatch(body)}catch(err){res=err}if(!this.current(c))return
        const createdId=exactId(res?.data?.batchId)
        if(res?.code===0&&createdId){const fresh=await this.readBatch(createdId);if(!this.current(c))return;if(!fresh||fresh.batchName!==body.batchName||String(fresh.gradeYear||'')!==String(body.gradeYear||'')||String(fresh.majorId||'')!==String(body.majorId||'')){toast.error('创建结果待核实，请勿重复创建');return}
          this.batch=fresh;this.pendingCommand=null;toast.success('已核对正式审核批次')
          this.batchPagination.page = 1
          await this.loadBatches()
        } else if(this.denied(res)||/409|422|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingCommand=null;throw res}else toast.error('创建结果待核实，请勿重复创建')
      } catch (e) {
        if(this.current(c))toast.error(this.fail(e,'创建失败'))
      } finally {
        if(this.current(c))this.creating=false
      }
    },
    resetBatch() {
      if (this.busy || this.pendingCommand) return
      this.batch = null
      this.genInfo = ''
      this.preInfo = ''
      this.draft = { batchName: '', gradeYear: '', majorId: '' }
    },
    async generate() {
      if (!this.canManage || this.busy || this.pendingCommand || !this.batch) return
      const batchId=exactId(this.batch.batchId);if(!batchId){toast.error('当前批次标识无法准确核对');return}
      const c={scope:this.scope,identity:this.identity,batchId};this.busy = true;this.pendingCommand={kind:'generate',batchId:c.batchId}
      try {
        let res;try{res=await academicAffairsApi.generateGradStudents(c.batchId,null)}catch(err){res=err}if(!this.current(c)||String(this.batch?.batchId)!==c.batchId)return
        if(res?.code===0&&Number.isFinite(res.data?.generated)){const fresh=await this.readBatch(c.batchId);if(!this.current(c))return;if(!fresh){toast.error('圈定结果待核实，请勿重复执行');return}this.batch=fresh;this.pendingCommand=null;this.genInfo=`正式回执圈定 ${res.data.generated} 人，已回读当前批次`;toast.success('已读取当前批次')
          await this.loadBatches()
        } else if(this.denied(res)||/409|422|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingCommand=null;throw res}else toast.error('圈定结果待核实，请勿重复执行')
      } catch (e) {
        if(this.current(c))toast.error(this.fail(e,'圈定失败'))
      } finally {
        if(this.current(c))this.busy = false
      }
    },
    async precheck() {
      if (!this.canManage || this.busy || this.pendingCommand || !this.batch) return
      const batchId=exactId(this.batch.batchId);if(!batchId){toast.error('当前批次标识无法准确核对');return}
      const c={scope:this.scope,identity:this.identity,batchId};this.busy = true;this.pendingCommand={kind:'precheck',batchId:c.batchId}
      try {
        let res;try{res=await academicAffairsApi.precheckGrad(c.batchId)}catch(err){res=err}if(!this.current(c)||String(this.batch?.batchId)!==c.batchId)return
        if(res?.code===0&&Number.isFinite(res.data?.passed)&&Number.isFinite(res.data?.abnormal)){const fresh=await this.readBatch(c.batchId);if(!this.current(c))return;if(!fresh){toast.error('预审结果待核实，请勿重复执行');return}this.batch=fresh;this.pendingCommand=null;this.preInfo=`正式回执：通过 ${res.data.passed} · 异常 ${res.data.abnormal}；已回读当前批次`;toast.success('已读取当前预审批次')
          await this.loadBatches()
        } else if(this.denied(res)||/409|422|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingCommand=null;throw res}else toast.error('预审结果待核实，请勿重复执行')
      } catch (e) {
        if(this.current(c))toast.error(this.fail(e,'预审失败'))
      } finally {
        if(this.current(c))this.busy = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-cal-form { display: flex; flex-wrap: wrap; gap: 14px; align-items: flex-end; }
.aa-cal-form__item { display: inline-flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--text-700, #4e5969); }
.aa-cal-form__item--grow { flex: 1; min-width: 240px; }
.aa-input { height: 34px; padding: 0 10px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 13px; box-sizing: border-box; }
.aa-input--sm { width: 120px; }
.aa-batch-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; margin-bottom: 12px; }
.grad-object { display: grid; grid-template-columns: 1.25fr repeat(3, minmax(0, 1fr)); gap: 0; overflow: hidden; border: 1px solid #dce6f3; border-radius: 12px; background: #fff; }
.grad-object > div { display: grid; gap: 5px; padding: 15px 17px; border-right: 1px solid #e8eef6; }
.grad-object > div:last-child { border-right: 0; }
.grad-object span, .grad-object small, .grad-metrics span, .grad-metrics small { color: #738198; font-size: 12px; }
.grad-object strong { color: #17345c; font-size: 14px; }
.grad-metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.grad-metrics article { display: grid; gap: 5px; padding: 16px 18px; border: 1px solid #dce6f3; border-radius: 12px; background: #fff; }
.grad-metrics strong { color: #18365f; font-size: 25px; font-variant-numeric: tabular-nums; }
@media (max-width: 900px) { .grad-object, .grad-metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } .grad-object > div:nth-child(2) { border-right: 0; } }
@media (max-width: 560px) { .grad-object, .grad-metrics { grid-template-columns: 1fr; } .grad-object > div { border-right: 0; border-bottom: 1px solid #e8eef6; } }
</style>
