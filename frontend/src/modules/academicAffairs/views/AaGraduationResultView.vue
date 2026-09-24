<template>
  <ModulePageShell
    title="毕业预审结果"
    subtitle="十一项逐项证据 + 学院初审 → 教务终审（证据来源、主键、哈希和下钻入口完整留痕）"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <AppButton @click="$router.push('/admin/academic-affairs/graduation')">返回批次</AppButton>
    </template>

    <div class="mp-stack">
      <AppInlineAlert v-if="writeNotice" :type="pendingWrite ? 'warning' : 'success'" :description="writeNotice" />
      <AppInlineAlert
        type="info"
        title="逐项证据不是一句结论"
        description="每一项都保留来源域、来源主键、检查时点和内容哈希；终审人员可下钻到正式业务台账核对。"
      />

      <AppSectionCard v-if="rosters" title="三名单">
        <div class="aa-roster-row">
          <span class="aa-roster-chip is-grad">毕业 {{ (rosters.graduated || []).length }}</span>
          <span class="aa-roster-chip is-comp">结业 {{ (rosters.completed || []).length }}</span>
          <span class="aa-roster-chip is-delay">延毕 {{ (rosters.delayed || []).length }}</span>
        </div>
      </AppSectionCard>

      <div class="aa-filter">
        <AppSelect v-model="filters.overall" :options="overallOptions" placeholder="" @change="search" />
        <AppButton @click="search">查询</AppButton>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" title="暂无预审结果" description="到批次页执行「圈定应届生 + 十一项预审」后再来复核" />
      <template v-else>
        <div class="aa-result-list">
          <AppSectionCard v-for="r in rows" :key="r.resultId" :title="r.realName || ('学生 ' + r.studentId)">
            <template #header-extra>
              <AppStatusTag :type="overallColor(r.overall)">{{ overallLabel(r.overall) }}</AppStatusTag>
              <AppStatusTag :type="r.conclusion ? 'success' : 'default'" dot>{{ statusLabel(r.status) }}</AppStatusTag>
            </template>
            <div class="aa-items">
              <div v-for="it in r.items" :key="it.evidenceHash || it.item" class="aa-item">
                <div class="aa-item__head">
                  <span class="aa-item__label">{{ itemLabel(it.item) }}</span>
                  <AppStatusTag :type="gradItemColor(it.result)">{{ itemResult(it.result) }}</AppStatusTag>
                  <button v-if="it.drillRoute" class="mp-link aa-item__drill" @click="drillEvidence(it)">核对来源 ›</button>
                </div>
                <span v-if="it.evidence" class="aa-item__ev">{{ it.evidence }}</span>
                <div v-if="it.sourceType || it.evidenceHash" class="aa-item__lineage">
                  <span>来源：{{ sourceLabel(it.sourceType) }}</span>
                  <span v-if="it.sourceIds?.length">主键：{{ it.sourceIds.join('、') }}</span>
                  <span v-if="it.checkedAt">检查：{{ formatTime(it.checkedAt) }}</span>
                  <span v-if="it.evidenceHash" :title="it.evidenceHash">哈希：{{ shortHash(it.evidenceHash) }}</span>
                </div>
              </div>
            </div>
            <div class="aa-result-actions">
              <AppButton v-if="canCollegeApprove(r)" variant="primary" :loading="busy" @click="collegeReview(r, 'APPROVE')">学院初审通过</AppButton>
              <AppButton v-if="canCollegeReject(r)" :disabled="busy" @click="openCollegeReject(r)">学院驳回</AppButton>
              <span v-if="r.status === 'SYSTEM_ABNORMAL'" class="aa-blocked-tip">系统异常须先治理阻断项并重新预审，不能直接学院通过</span>
              <AppButton v-if="canNormalFinal(r)" variant="primary" :disabled="busy" @click="openFinal(r)">教务终审</AppButton>
              <span v-else-if="r.status === 'ACADEMIC_REVIEW' && r.overall !== 'SYSTEM_PASSED'" class="aa-blocked-tip">系统异常 · 普通教务终审不可用</span>
              <span v-if="r.conclusion" class="aa-final-tag">终审结论：{{ conclusionLabel(r.conclusion) }}</span>
            </div>
          </AppSectionCard>
        </div>
        <div class="aa-result-pager">
          <AppPagination
            :total="pagination.total"
            :page="pagination.page"
            :page-size="pagination.pageSize"
            :show-size-changer="false"
            @change="onPaginationChange"
          />
        </div>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="finalDlg.visible"
      title="教务终审"
      type="danger"
      confirm-text="确认终审并写学籍"
      :submitting="finalDlg.submitting"
      @confirm="doFinal"
    >
      <div class="aa-final-form">
        <p>终审结论涉及学籍终态，请谨慎选择：</p>
        <label v-for="(l, v) in CONCLUSION_LABEL" :key="v" class="aa-radio">
          <input v-model="finalDlg.conclusion" type="radio" :value="v" /> {{ l }}
        </label>
      </div>
    </AppConfirmDialog>

    <AppConfirmDialog
      v-model:visible="collegeRejectDlg.visible"
      title="学院初审驳回"
      type="danger"
      require-reason
      reason-label="驳回原因（≥5字）"
      :submitting="busy"
      @confirm="doCollegeReject"
    />
  </ModulePageShell>
</template>

<script>
/** 毕业预审结果 + 逐项证据复核（/admin/academic-affairs/graduation/:batchId/results）。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppStatusTag, AppConfirmDialog, AppSelect, AppInlineAlert, AppPagination } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { GRAD_ITEM_LABEL, GRAD_ITEM_RESULT, gradItemColor, OVERALL_LABEL, overallColor, CONCLUSION_LABEL, GRAD_STATUS_LABEL } from '@/modules/academicAffairs/constants/grade-graduation'
import { toast } from '@/utils/toast'
import { currentUserFromToken } from '@/services/http/client'
import { matchPermission } from '@/config/navPlan'
import { gradeError } from './parallel-c/grade-review'

const exactId=value=>typeof value==='string'&&value.trim()?value:(typeof value==='number'&&Number.isSafeInteger(value)?String(value):'')

const SOURCE_LABELS = {
  STUDENT_PROFILE: '学生主档', ACADEMIC_GRADE: '正式成绩主账', PROGRAM_AND_GRADE: '培养方案与正式成绩',
  INTERNSHIP_RECORD: '岗位实习台账', GRADUATION_STUDENT: '毕业设计台账',
  DISCIPLINE_RECORD: '处分台账', EMPLOYMENT_STUDENT: '就业去向台账',
  ARCHIVE_PACKAGE: '学生归档包', TEXTBOOK_FEE_LEDGER: '教材费用台账', UNKNOWN: '待治理来源'
}

export default {
  name: 'AaGraduationResultView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppButton, AppSectionCard, AppStatusTag, AppConfirmDialog, AppSelect, AppInlineAlert, AppPagination },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      CONCLUSION_LABEL,
      alive:true,scope:0,seq:0,rosterSeq:0,pendingWrite:null,writeNotice:'',
      loading: true, error: '', rows: [], rosters: null, busy: false,
      filters: { overall: '' },
      pagination: { page: 1, pageSize: 20, total: 0 },
      finalDlg: { visible: false, submitting: false, resultId: '', conclusion: 'GRADUATED' },
      collegeRejectDlg: { visible: false, row: null }
    }
  },
  computed: {
    batchId() { return String(this.$route.params.batchId) },
    identity(){const u=currentUserFromToken()||{};return JSON.stringify([u.tenantId,u.userId,u.activeContextId,u.currentRoleCode,this.ctx.currentRole,this.ctx.dataScope,this.ctx.permissionPatterns])},
    canCollege(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.graduation.collegeReview')},
    canFinal(){return matchPermission(this.ctx.permissionPatterns||[],'academicAffairs.graduation.final')},
    overallOptions() {
      return [
        { value: '', label: '全部预审结果' },
        { value: 'SYSTEM_PASSED', label: '系统通过' },
        { value: 'SYSTEM_ABNORMAL', label: '系统异常' }
      ]
    }
  },
  watch:{identity(){this.clearPrivate();this.load();this.loadRosters()},batchId(){this.clearPrivate();this.load();this.loadRosters()}},
  created() { this.load(); this.loadRosters() },
  beforeUnmount(){this.alive=false;this.clearPrivate()},
  methods: {
    capture(){return {scope:this.scope,identity:this.identity,batchId:this.batchId}},
    current(c){return this.alive&&c.scope===this.scope&&c.identity===this.identity&&c.batchId===this.batchId},
    denied(err){return /403|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN/.test([err?.code,err?.bizCode].join(' '))},
    clearPrivate(){this.scope++;this.seq++;this.rosterSeq++;this.rows=[];this.rosters=null;this.error='';this.loading=false;this.busy=false;this.pendingWrite=null;this.writeNotice='';this.finalDlg={visible:false,submitting:false,resultId:'',conclusion:'GRADUATED'};this.collegeRejectDlg={visible:false,row:null}},
    fail(err,fallback){if(this.denied(err))this.clearPrivate();return gradeError(err,fallback)},
    signature(row){return JSON.stringify([String(row?.resultId||''),String(row?.batchId||''),row?.status||'',row?.overall||'',(row?.items||[]).map(item=>[item.item,item.result,item.evidenceHash||'',item.checkedAt||''])])},
    gradItemColor, overallColor,
    itemLabel(i) { return GRAD_ITEM_LABEL[i] || i },
    itemResult(r) { return GRAD_ITEM_RESULT[r] || r },
    overallLabel(o) { return OVERALL_LABEL[o] || o || '' },
    statusLabel(s) { return GRAD_STATUS_LABEL[s] || (s ? '状态待确认' : '') },
    conclusionLabel(c) { return CONCLUSION_LABEL[c] || c },
    sourceLabel(value) { return SOURCE_LABELS[value] || (value ? '待确认' : '—') },
    shortHash(value) { return value ? `${String(value).slice(0, 10)}…` : '—' },
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 19) : '—' },
    drillEvidence(item) {
      const route = String(item.drillRoute || '')
      if (!route.startsWith('/admin/')) { toast.error('证据下钻地址无效'); return }
      this.$router.push(route)
    },
    canCollegeApprove(r) {
      return Boolean(this.canCollege && !this.pendingWrite && r && r.overall === 'SYSTEM_PASSED' && ['SYSTEM_PASSED', 'COLLEGE_REVIEW'].includes(r.status))
    },
    canCollegeReject(r) { return Boolean(this.canCollege && !this.pendingWrite && r && ['SYSTEM_PASSED', 'SYSTEM_ABNORMAL', 'COLLEGE_REVIEW'].includes(r.status)) },
    canNormalFinal(r) { return Boolean(this.canFinal && !this.pendingWrite && r && r.status === 'ACADEMIC_REVIEW' && r.overall === 'SYSTEM_PASSED') },
    search() { this.pagination.page = 1; this.load() },
    onPaginationChange({ page }) {
      if (!page || page === this.pagination.page || this.loading) return
      this.pagination.page = page
      this.load()
    },
    async loadRosters() {
      const c=this.capture(),seq=++this.rosterSeq
      try {
        const res=await academicAffairsApi.getGradRosters(c.batchId)
        if(!this.current(c)||seq!==this.rosterSeq)return
        if(res.code!==0)throw res
        if(!['graduated','completed','delayed'].every(key=>Array.isArray(res.data?.[key])))throw {code:503}
        this.rosters=res.data
      } catch (e) {
        if(this.current(c)&&seq===this.rosterSeq)toast.error(this.fail(e,'三名单加载失败'))
      }
    },
    async writeResult(kind,row,send,verify,success){
      if(this.pendingWrite||!row)return false
      const resultId=exactId(row.resultId),c=this.capture(),shown=this.signature(row)
      if(!resultId||String(row.batchId)!==c.batchId)return false
      this.busy=true
      try{
        const before=await academicAffairsApi.getGradResult(resultId)
        if(!this.current(c))return false
        if(before?.code!==0)throw before
        if(exactId(before.data?.resultId)!==resultId||String(before.data?.batchId)!==c.batchId)throw {code:409}
        if(this.signature(before.data)!==shown)throw {code:409,message:'正式结果已变化'}
        this.pendingWrite={kind,resultId,batchId:c.batchId};this.writeNotice='结果待核实，请勿重复操作。'
        let res;try{res=await send(before.data)}catch(err){res=err}
        if(!this.current(c))return false
        if(res?.code!==0&&/403|404|409|422|NO_DATA_SCOPE|NO_PERMISSION|FORBIDDEN|CONFLICT|VALIDATION/.test([res?.code,res?.bizCode].join(' '))){this.pendingWrite=null;this.writeNotice='';throw res}
        const after=await academicAffairsApi.getGradResult(resultId)
        if(!this.current(c))return false
        if(res?.code===0&&after?.code===0&&exactId(after.data?.resultId)===resultId&&String(after.data?.batchId)===c.batchId&&verify(after.data,res)){this.pendingWrite=null;this.writeNotice=success;return true}
        this.writeNotice='结果待核实：已读取当前正式结果，但不能证明本次操作完成，请勿重复操作。';return false
      }catch(err){if(this.current(c))toast.error(this.fail(err,'操作前核对未完成，请重新读取。'));return false}
      finally{if(this.current(c))this.busy=false}
    },
   async collegeReview(r, action) {
     if (this.busy || action !== 'APPROVE' || !this.canCollegeApprove(r)) return
      const ok=await this.writeResult('college-approve',r,()=>academicAffairsApi.collegeReviewGrad(r.resultId,'APPROVE',''),fresh=>fresh.status==='ACADEMIC_REVIEW','已核对正式学院初审通过状态。')
      if(ok){toast.success(this.writeNotice);await this.load()}
   },
    openCollegeReject(r) {
      if (!this.canCollegeReject(r) || this.busy) return
      this.collegeRejectDlg = { visible: true, row: r }
    },
    async doCollegeReject({ reason } = {}) {
      const row = this.collegeRejectDlg.row
      const note = String(reason || '').trim()
     if (!row || this.busy) return
     if (note.length < 5) { toast.error('驳回原因不少于 5 字'); return }
      const ok=await this.writeResult('college-reject',row,()=>academicAffairsApi.collegeReviewGrad(row.resultId,'REJECT',note),fresh=>fresh.status==='REJECTED'&&String(fresh.reviewNote||'')===note,'已核对正式学院初审退回状态和原因。')
      if(ok){toast.success(this.writeNotice);this.collegeRejectDlg={visible:false,row:null};await this.load()}
   },
    openFinal(r) {
      if (!this.canNormalFinal(r)) {
        toast.error('当前结果不满足普通教务终审条件，请先重新预审并核对系统结论')
        return
      }
      if (this.busy) return
      this.finalDlg = { visible: true, submitting: false, resultId: r.resultId, conclusion: 'GRADUATED' }
    },
    async doFinal() {
      const row = this.rows.find((item) => String(item.resultId) === String(this.finalDlg.resultId))
      if (!this.canNormalFinal(row)) {
        this.finalDlg.visible = false
        toast.error('当前结果已不满足普通终审条件，请重新加载并核对系统预审')
        return
      }
     if (this.finalDlg.submitting) return
      this.finalDlg.submitting=true
      try {
        const fresh=await academicAffairsApi.getGradResult(this.finalDlg.resultId)
        if(fresh?.code!==0||exactId(fresh.data?.resultId)!==exactId(this.finalDlg.resultId)||String(fresh.data?.batchId)!==this.batchId||!this.canNormalFinal(fresh.data))throw fresh
        Object.assign(row,fresh.data)
        const conclusion=this.finalDlg.conclusion
        const ok=await this.writeResult('final',row,before=>{if(before.status!=='ACADEMIC_REVIEW'||before.overall!=='SYSTEM_PASSED')throw {code:409};return academicAffairsApi.finalGrad(before.resultId,conclusion,true)},after=>after.status===conclusion&&after.conclusion===conclusion,`已核对正式终审结论：${CONCLUSION_LABEL[conclusion]||conclusion}。`)
        if(ok){toast.success(this.writeNotice);this.finalDlg.visible=false;await this.load();await this.loadRosters()}
      } catch(err) { toast.error(this.fail(err,'终审前核对未完成，请重新读取。')) }
      finally { this.finalDlg.submitting=false }
   },
    async load() {
      const c=this.capture(),seq=++this.seq
      this.loading = true
      this.error = ''
      try {
        const res = await academicAffairsApi.getGradResults(c.batchId, {
          overall: this.filters.overall || undefined,
          page: this.pagination.page,
          pageSize: this.pagination.pageSize
        })
        if(!this.current(c)||seq!==this.seq)return
        if(res.code!==0)throw res
        if(!Array.isArray(res.data?.list))throw {code:503}
        if(res.data.list.some(row=>String(row.batchId)!==c.batchId))throw {code:503}
        this.rows=res.data.list
        this.pagination.total = res.data.total
      } catch (e) {
        if(this.current(c)&&seq===this.seq)this.error=this.fail(e,'毕业预审结果加载失败')
      } finally {
        if(this.current(c)&&seq===this.seq)this.loading=false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-roster-row { display: flex; flex-wrap: wrap; gap: 12px; }
.aa-roster-chip { padding: 6px 14px; border-radius: 16px; font-size: 14px; font-weight: 500; }
.aa-roster-chip.is-grad { background: var(--success-50, #eafff3); color: var(--success-600, #16a34a); }
.aa-roster-chip.is-comp { background: var(--fill-100, #f2f3f5); color: var(--text-700, #4e5969); }
.aa-roster-chip.is-delay { background: var(--warning-50, #fffbeb); color: var(--warning-600, #d97706); }
.aa-filter { display: flex; gap: 12px; align-items: center; }.aa-filter :deep(.app-select) { width: 220px; }
.aa-result-list { display: flex; flex-direction: column; gap: 12px; }
.aa-result-pager { display: flex; justify-content: flex-end; margin-top: 14px; }
.aa-items { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); gap: 10px 14px; }
.aa-item { min-width: 0; padding: 10px 12px; border: 1px solid var(--border-200, #e5e7eb); border-radius: 8px; background: var(--fill-50, #fafafa); font-size: 13px; }
.aa-item__head { display: flex; align-items: center; gap: 8px; min-width: 0; }.aa-item__label { color: var(--text-700, #4e5969); min-width: 64px; font-weight: 600; }.aa-item__drill { margin: 0 0 0 auto; }
.aa-item__ev { display: block; margin-top: 7px; color: var(--text-600, #64748b); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
.aa-item__lineage { display: flex; flex-wrap: wrap; gap: 4px 12px; margin-top: 7px; padding-top: 7px; border-top: 1px dashed var(--border-200, #e5e7eb); color: var(--text-400, #8a9099); font-size: 11px; overflow-wrap: anywhere; }
.aa-result-actions { margin-top: 14px; display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }.aa-final-tag { color: var(--success-600, #16a34a); font-size: 13px; }.aa-blocked-tip { color: var(--warning-700, #b45309); font-size: 12px; }.aa-final-form { display: flex; flex-direction: column; gap: 8px; }.aa-radio { display: flex; align-items: center; gap: 8px; font-size: 14px; }
@media (max-width: 900px) { .aa-items { grid-template-columns: 1fr; } }
@media (max-width: 640px) {
  .aa-filter { align-items: stretch; flex-direction: column; }
  .aa-filter :deep(.app-select) { width: 100%; }
  .aa-item__head { align-items: flex-start; flex-wrap: wrap; }
  .aa-item__drill { width: 100%; margin-left: 0; text-align: left; }
  .aa-result-pager { justify-content: center; overflow-x: auto; }
}
</style>
