<template>
  <ModulePageShell
    title="教师管理"
    subtitle="教师本人签到、补签、工作报告、指导与巡访统一台账；补签须经校级管理员审核。"
    role-name="岗位实习管理员"
    data-scope-name="当前学校 / 当前批次"
    :watermark="false"
  >
    <template #actions>
      <AppButton variant="ghost" :disabled="loading" @click="load">刷新</AppButton>
      <AppExportButton
        :export-fn="exportFn"
        :has-permission="canExport"
        :disabled="!batchId || loading"
      >导出教师台账</AppExportButton>
    </template>

    <div class="tm-stack">
      <section class="tm-filter">
        <label>
          <span>教师搜索</span>
          <input v-model.trim="keyword" maxlength="100" placeholder="教师姓名 / 教工号" @keyup.enter="load" />
        </label>
        <AppButton :disabled="loading || !batchId" @click="load">查询</AppButton>
      </section>

      <div v-if="!batchId" class="tm-state">请先选择实习批次。</div>
      <LoadingState v-else-if="loading" />
      <ErrorState v-else-if="error" :description="error" @retry="load" />
      <template v-else>
        <section class="tm-card">
          <header class="tm-head">
            <div>
              <span class="eyebrow">AP16 · 教师业务台账</span>
              <h2>{{ batchName || '当前批次' }} · {{ teachers.length }} 名教师</h2>
            </div>
          </header>
          <DataTable v-if="teachers.length" :columns="teacherColumns" :rows="teachers" row-key="teacherUserId">
            <template #cell-teacher="{ row }">
              <div><strong>{{ row.teacherName }}</strong><small>{{ row.employeeNo || '无教工号' }}</small></div>
            </template>
            <template #cell-checkin="{ row }">
              <span>{{ row.checkinCount }} 次</span>
              <small v-if="row.makeupApprovedCount || row.makeupPendingCount">
                补签通过 {{ row.makeupApprovedCount }} / 待审 {{ row.makeupPendingCount }}
              </small>
            </template>
            <template #cell-reports="{ row }">
              <span>日报 {{ row.workReportCount }}</span>
              <small>周 {{ row.weeklyReportCount }} · 月 {{ row.monthlyReportCount }} · 总结 {{ row.summaryReportCount }}</small>
            </template>
            <template #cell-guidance="{ row }">
              <span>指导 {{ row.guidanceCount }}</span><small>巡访 {{ row.visitCount }}</small>
            </template>
          </DataTable>
          <div v-else class="tm-state">当前条件没有教师业务记录。</div>
        </section>

        <section class="tm-card">
          <header class="tm-head">
            <div>
              <span class="eyebrow">TP04 / TP05 · 报告批阅绩效</span>
              <h2>{{ reviewPerformance.length }} 名批阅教师 · {{ reviewFactCount }} 条不可变批阅事实</h2>
              <p>统计周报、日报、月报和实习总结的真实批阅事实；退回后重交再批阅会形成新的批阅事实，不用当前页面条数冒充绩效。</p>
            </div>
            <AppExportButton
              :export-fn="exportPerformanceFn"
              :has-permission="canReportExport"
              :disabled="!batchId || loading"
            >导出批阅绩效</AppExportButton>
          </header>
          <DataTable v-if="reviewPerformance.length" :columns="performanceColumns" :rows="reviewPerformance" row-key="reviewerUserId">
            <template #cell-reviewer="{ row }">
              <div><strong>{{ row.reviewerName }}</strong><small>{{ row.reviewerUserId ? ('账号ID ' + row.reviewerUserId) : '系统/历史批阅人' }}</small></div>
            </template>
            <template #cell-outcome="{ row }">
              <span>通过 {{ row.approvedCount }} / 退回 {{ row.returnedCount }}</span>
              <small>周报 {{ row.weeklyReviewCount }} · 过程报告 {{ row.processReviewCount }}</small>
            </template>
            <template #cell-rating="{ row }">
              <span>{{ row.averageRating == null ? '暂无评分' : ('平均 ' + row.averageRating + ' / 5') }}</span>
              <small>1～5级：{{ ratingDistributionText(row.ratingDistribution) }}</small>
            </template>
            <template #cell-summaryScore="{ row }">
              <span>{{ row.summaryAverageScore == null ? '暂无总结评分' : (row.summaryAverageScore + ' 分') }}</span>
              <small>{{ row.summaryScoredCount }} 篇总结已评分</small>
            </template>
            <template #cell-lastReviewedAt="{ row }">{{ displayTime(row.lastReviewedAt) || '—' }}</template>
          </DataTable>
          <div v-else class="tm-state">当前批次/数据范围尚无报告批阅事实。</div>
        </section>

        <section class="tm-card">
          <header class="tm-head">
            <div>
              <span class="eyebrow">教师本人补签</span>
              <h2>待审核 {{ pendingCount }} 条</h2>
              <p>审批通过后才生成教师 MAKEUP 签到事实；已存在同日签到时服务端会阻断重复补签。</p>
            </div>
            <select v-model="makeupStatus" @change="loadMakeups">
              <option value="PENDING">待审核</option>
              <option value="">全部</option>
              <option value="APPROVED">已通过</option>
              <option value="REJECTED">已驳回</option>
              <option value="WITHDRAWN">已撤回</option>
            </select>
          </header>
          <DataTable v-if="makeups.length" :columns="makeupColumns" :rows="makeups" row-key="id">
            <template #cell-status="{ row }">
              <AppStatusTag :type="statusTone(row.status)">{{ statusLabel(row.status) }}</AppStatusTag>
            </template>
            <template #cell-evidence="{ row }">
              <span>{{ row.evidenceFileId ? '已上传佐证' : '无佐证' }}</span>
            </template>
            <template #cell-actions="{ row }">
              <div v-if="row.status === 'PENDING'" class="actions">
                <AppButton size="sm" :disabled="busyId === row.id" @click="review(row, 'APPROVE')">通过</AppButton>
                <AppButton size="sm" variant="danger" :disabled="busyId === row.id" @click="openReject(row)">驳回</AppButton>
              </div>
              <span v-else>{{ row.reviewedByName || '—' }} {{ displayTime(row.reviewedAt) }}</span>
            </template>
          </DataTable>
          <div v-else class="tm-state">当前状态暂无补签申请。</div>
        </section>

        <section v-if="rejectRow" class="tm-reject">
          <div>
            <h3>驳回 {{ rejectRow.teacherName }} · {{ rejectRow.localDate }} 补签</h3>
            <p>驳回原因会回写给教师，至少 5 个字。</p>
          </div>
          <textarea v-model="rejectComment" maxlength="500" placeholder="填写驳回原因" />
          <div class="actions">
            <AppButton variant="ghost" @click="closeReject">取消</AppButton>
            <AppButton variant="danger" :disabled="rejectComment.trim().length < 5 || busyId === rejectRow.id" @click="review(rejectRow, 'REJECT')">确认驳回</AppButton>
          </div>
        </section>

        <div v-if="message" class="tm-message" :class="{ 'is-error': messageType === 'error' }">{{ message }}</div>
      </template>
    </div>
  </ModulePageShell>
</template>

<script>
import { DataTable, ErrorState, LoadingState, ModulePageShell } from '@/components/business'
import { AppExportButton, AppStatusTag } from '@/components/common'
import { AppButton } from '@/components/ui'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { canCode } from '@/modules/internship/composables/permission'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

export default {
  name: 'TeacherManagementView',
  components: { ModulePageShell, DataTable, ErrorState, LoadingState, AppExportButton, AppStatusTag, AppButton },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      loading: false, error: '', keyword: '', batchName: '', teachers: [], makeups: [],
      reviewPerformance: [], reviewFactCount: 0,
      makeupStatus: 'PENDING', pendingCount: 0, busyId: '', rejectRow: null,
      rejectComment: '', message: '', messageType: ''
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    batchId() { return this.batchStore.selectedBatchId || '' },
    canExport() { return canCode(this.ctx, 'internship.stats.export') },
    canReportExport() { return canCode(this.ctx, 'internship.report.export') },
    teacherColumns() {
      return [
        { key: 'teacher', title: '教师', width: '160px' },
        { key: 'studentCount', title: '所带学生', width: '90px' },
        { key: 'checkin', title: '本人签到 / 补签', width: '190px' },
        { key: 'reports', title: '教师本人报告', width: '220px' },
        { key: 'guidance', title: '指导 / 巡访', width: '150px' },
        { key: 'lastCheckinAt', title: '最近签到', width: '170px' }
      ]
    },
    performanceColumns() {
      return [
        { key: 'reviewer', title: '批阅教师', width: '160px' },
        { key: 'reviewCount', title: '批阅次数', width: '90px' },
        { key: 'outcome', title: '通过 / 退回', width: '220px' },
        { key: 'rating', title: '五级评价', width: '240px' },
        { key: 'summaryScore', title: '总结百分制', width: '170px' },
        { key: 'lastReviewedAt', title: '最近批阅', width: '170px' }
      ]
    },
    makeupColumns() {
      return [
        { key: 'teacherName', title: '教师', width: '130px' },
        { key: 'localDate', title: '补签日期', width: '120px' },
        { key: 'reason', title: '补签原因', width: '280px' },
        { key: 'evidence', title: '佐证', width: '110px' },
        { key: 'status', title: '状态', width: '100px' },
        { key: 'actions', title: '审核', width: '220px' }
      ]
    }
  },
  watch: {
    'batchStore.selectedBatchId'() { this.closeReject(); this.load() }
  },
  created() { this.load() },
  methods: {
    displayTime(value) { return value ? String(value).replace('T', ' ').slice(0, 19) : '' },
    ratingDistributionText(value) {
      const d=value || {}
      return [1,2,3,4,5].map(level => level + '级 ' + Number(d[String(level)] || 0)).join(' / ')
    },
    statusLabel(value) { return {PENDING:'待审核',APPROVED:'已通过',REJECTED:'已驳回',WITHDRAWN:'已撤回'}[value] || value || '—' },
    statusTone(value) { return {APPROVED:'success',REJECTED:'danger',PENDING:'warning'}[value] || 'default' },
    async load() {
      if (!this.batchId) { this.teachers=[]; this.makeups=[]; this.reviewPerformance=[]; this.reviewFactCount=0; this.error=''; return }
      this.loading=true; this.error=''; this.message=''
      const [ledger, makeups, performance] = await Promise.all([
        internshipApi.getTeacherManagement({ batchId:this.batchId, keyword:this.keyword || undefined }),
        internshipApi.getTeacherMakeups({ batchId:this.batchId, status:this.makeupStatus || undefined, pageSize:200 }),
        internshipApi.getReportReviewPerformance({ batchId:this.batchId })
      ])
      this.loading=false
      if (ledger.code !== 0) { this.error=ledger.message || '教师管理台账加载失败'; return }
      if (makeups.code !== 0) { this.error=makeups.message || '教师补签队列加载失败'; return }
      if (performance.code !== 0) { this.error=performance.message || '报告批阅绩效加载失败'; return }
      this.batchName=ledger.data?.batchName || performance.data?.batchName || ''
      this.teachers=ledger.data?.items || []
      this.makeups=makeups.data?.items || []
      this.reviewPerformance=performance.data?.items || []
      this.reviewFactCount=Number(performance.data?.reviewFactCount || 0)
      this.pendingCount=this.makeupStatus === 'PENDING'
        ? this.makeups.length
        : this.makeups.filter(item => item.status === 'PENDING').length
    },
    async loadMakeups() {
      if (!this.batchId) return
      const res=await internshipApi.getTeacherMakeups({batchId:this.batchId,status:this.makeupStatus || undefined,pageSize:200})
      if(res.code!==0){this.message=res.message || '补签队列加载失败';this.messageType='error';return}
      this.makeups=res.data?.items||[]
      this.pendingCount=this.makeupStatus==='PENDING'?this.makeups.length:this.makeups.filter(item=>item.status==='PENDING').length
    },
    openReject(row) { this.rejectRow=row; this.rejectComment=''; this.message='' },
    closeReject() { this.rejectRow=null; this.rejectComment='' },
    async review(row, action) {
      if(!row?.id || this.busyId) return
      const comment=action==='REJECT'?this.rejectComment.trim():'审核通过'
      if(action==='REJECT' && comment.length<5) return
      this.busyId=row.id; this.message=''; this.messageType=''
      const res=await internshipApi.reviewTeacherMakeup(row.id,{
        action, comment, expectedVersion:row.version
      })
      this.busyId=''
      if(res.code!==0){this.message=res.message || '教师补签审核失败';this.messageType='error';return}
      this.closeReject()
      this.message=action==='APPROVE'?'补签已通过，并已生成教师 MAKEUP 签到事实。':'补签已驳回。'
      await this.load()
    },
    exportPerformanceFn() {
      return internshipApi.exportReportReviewPerformance({ batchId:this.batchId })
    },
    exportFn() {
      return internshipApi.exportTeacherManagement({
        batchId:this.batchId,
        keyword:this.keyword || undefined
      })
    }
  }
}
</script>

<style scoped>
.tm-stack{display:grid;gap:18px}.tm-filter{display:flex;align-items:end;gap:10px;padding:14px 16px;border:1px solid var(--border-base);border-radius:10px;background:var(--bg-card)}
.tm-filter label{display:grid;gap:6px;min-width:280px;font-size:12px;color:var(--text-secondary)}.tm-filter input,.tm-head select{height:36px;padding:0 10px;border:1px solid var(--border-base);border-radius:7px;background:var(--bg-card);color:var(--text-primary)}
.tm-card{border:1px solid var(--border-base);border-radius:12px;background:var(--bg-card);overflow:hidden}.tm-head{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;padding:18px}.tm-head h2{margin:4px 0 0;font-size:17px}.tm-head p{margin:6px 0 0;color:var(--text-secondary);font-size:12px}
.eyebrow{font-size:11px;font-weight:700;color:var(--primary-600)}small{display:block;margin-top:4px;color:var(--text-secondary)}.actions{display:flex;gap:7px;align-items:center}.tm-state{padding:28px;text-align:center;color:var(--text-secondary)}
.tm-reject{display:grid;grid-template-columns:minmax(240px,1fr) minmax(320px,2fr) auto;gap:14px;align-items:end;padding:18px;border:1px solid var(--warning-300);border-radius:12px;background:var(--warning-50)}.tm-reject h3{margin:0}.tm-reject p{margin:5px 0 0;font-size:12px;color:var(--text-secondary)}.tm-reject textarea{min-height:76px;padding:9px;border:1px solid var(--border-base);border-radius:7px;resize:vertical}
.tm-message{padding:12px 14px;border:1px solid var(--border-base);border-radius:9px}.tm-message.is-error{color:var(--danger-600)}
@media(max-width:900px){.tm-filter,.tm-head{align-items:stretch;flex-direction:column}.tm-filter label{min-width:0}.tm-reject{grid-template-columns:1fr}}
</style>
