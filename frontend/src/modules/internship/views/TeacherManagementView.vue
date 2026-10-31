<template>
  <ModulePageShell
    title="教师工作台账"
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
              <span class="eyebrow">教师工作概况</span>
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

        <section class="tm-card" aria-label="教师签到明细">
          <header class="tm-head">
            <div><span class="eyebrow">教师本人签到</span><h2>签到明细 · {{ checkinTotal }} 条</h2><p>日期按教师签到当地日期筛选，保留原备注、地址和核验结果；导出包含全部筛选记录，每次最多5000条。</p></div>
            <AppExportButton :export-fn="exportCheckinsFn" :has-permission="canExport">导出签到明细</AppExportButton>
          </header>
          <div class="tm-checkin-filter">
            <label>签到教师<select v-model="checkinTeacher" aria-label="签到教师"><option value="">全部教师</option><option v-for="teacher in teachers" :key="teacher.teacherUserId" :value="String(teacher.teacherUserId)">{{ teacher.teacherName }}</option></select></label>
            <label>开始日期<AppDatePicker v-model="checkinStart" /></label><label>结束日期<AppDatePicker v-model="checkinEnd" /></label>
            <label>签到结果<select v-model="checkinResult" aria-label="签到结果"><option value="">全部结果</option><option v-for="item in checkinResults" :key="item.value" :value="item.value">{{ item.label }}</option></select></label>
            <AppButton :disabled="checkinLoading" @click="queryCheckins">查询签到</AppButton>
          </div>
          <LoadingState v-if="checkinLoading" />
          <ErrorState v-else-if="checkinError" :description="checkinError" @retry="loadCheckins" />
          <template v-else>
            <DataTable v-if="checkins.length" :columns="checkinColumns" :rows="checkins" row-key="id">
              <template #cell-resultLabel="{ row }"><AppStatusTag :type="checkinTone(row.result)">{{ row.resultLabel }}</AppStatusTag></template>
              <template #cell-timezoneName="{ row }">{{ checkinTimezone(row) }}</template>
              <template #cell-place="{ row }"><span>{{ row.address || '未取得地图地址' }}</span><small>{{ row.countryRegion || '地区未填写' }} · {{ row.coordinateLabel }}</small><small v-if="row.latitude != null">纬度 {{ row.latitude }} · 经度 {{ row.longitude }}</small><small v-if="row.distanceM != null">距允许地点中心 {{ row.distanceM }} 米</small></template>
              <template #cell-note="{ row }"><span class="tm-checkin-note">{{ row.note || '无备注' }}</span></template>
              <template #cell-photo="{ row }"><div class="actions"><AppButton v-if="row.photoFileId" size="sm" variant="ghost" @click="openCheckinPhoto(row, true)">查看原图</AppButton><AppButton v-if="row.watermarkedFileId" size="sm" variant="ghost" @click="openCheckinPhoto(row)">查看水印</AppButton><span v-if="!row.photoFileId && !row.watermarkedFileId">未附照片</span></div></template>
            </DataTable>
            <div v-else class="tm-state">当前筛选条件没有教师签到记录。</div>
            <AppPagination :total="checkinTotal" v-model:page="checkinPage" v-model:page-size="checkinPageSize" @change="onCheckinPage" />
          </template>
          <section v-if="photoLoading || photoFile || photoError" class="tm-photo" aria-label="教师签到照片核对"><div class="actions"><strong>{{ photoRecord?.teacherName }} · {{ photoRecord?.localDate }} · {{ photoOriginal ? '现场原图' : '服务端水印' }}</strong><AppButton variant="ghost" @click="clearCheckinPhoto">关闭照片</AppButton></div><LoadingState v-if="photoLoading" /><p v-else-if="photoError" role="alert">{{ photoError }}</p><FilePreviewer v-else-if="photoFile" :key="photoFile.fileId" :file="photoFile" inline :provider="photoProvider" :allow-download="false" /></section>
        </section>

        <section class="tm-card">
          <header class="tm-head">
            <div>
              <span class="eyebrow">报告批阅绩效</span>
              <h2>{{ reviewPerformance.length }} 名批阅教师 · {{ reviewFactCount }} 条批阅记录</h2>
              <p>包含四类报告批阅；退回重交后的再次批阅单独计次。</p>
            </div>
            <AppExportButton
              :export-fn="exportPerformanceFn"
              :has-permission="canReportExport"
              :disabled="!batchId || loading"
            >导出批阅绩效</AppExportButton>
          </header>
          <DataTable v-if="reviewPerformance.length" :columns="performanceColumns" :rows="reviewPerformance" row-key="rowKey">
            <template #cell-reviewer="{ row }">
              <div><strong>{{ row.reviewerName }}</strong></div>
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
              <p>审核通过后生成补签；同日已有签到时不能重复补签。</p>
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
import { formatDateTime } from '@/utils/dateUtils'
import { AppDatePicker } from '@/components/common'
import { DataTable, ErrorState, LoadingState, ModulePageShell } from '@/components/business'
import { AppExportButton, AppStatusTag, AppPagination } from '@/components/common'
import { AppButton } from '@/components/ui'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { canCode } from '@/modules/internship/composables/permission'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { currentSessionGeneration } from '@/services/http/client'
import { fileSdk } from '@/services/file/fileSdk'
import FilePreviewer from '@/components/file/FilePreviewer.vue'

export default {
  name: 'TeacherManagementView',
  components: { AppDatePicker, ModulePageShell, DataTable, ErrorState, LoadingState, AppExportButton, AppStatusTag, AppPagination, AppButton, FilePreviewer },
  props: { ctx: { type: Object, default: () => ({}) } },
  data() {
    return {
      loading: false, error: '', keyword: '', batchName: '', teachers: [], makeups: [],
      loadSequence:0, checkinSequence:0, disposed:false, checkins:[], checkinTotal:0, checkinPage:1, checkinPageSize:20,
      checkinTeacher:'', checkinStart:'', checkinEnd:'', checkinResult:'', checkinLoading:false, checkinError:'',
      photoSequence:0, photoRecord:null, photoFile:null, photoError:'', photoLoading:false, photoOriginal:false,
      photoProvider:{fetchBytes:descriptor=>fileSdk.blob(descriptor.fileId),dispose(){}},
      checkinResults:[{value:'NORMAL',label:'正常签到'},{value:'RECORDED',label:'仅作留痕'},{value:'OUT_OF_RANGE',label:'超出范围待核实'},{value:'NO_LOCATION',label:'无定位待核实'},{value:'LOW_ACCURACY',label:'精度不足待核实'},{value:'LOCATION_UNCERTAIN',label:'定位待核实'},{value:'MOCK_LOCATION',label:'设备或定位异常待核实'},{value:'MAKEUP',label:'审批补签'}],
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
    checkinColumns() { return [{key:'teacherName',title:'教师',width:'140px'},{key:'localDate',title:'签到日期',width:'120px'},
      {key:'localCheckedInAt',title:'签到当地时间',width:'180px'},{key:'timezoneName',title:'时区',width:'150px'},
      {key:'resultLabel',title:'核验结果',width:'180px'},{key:'place',title:'地址与位置',width:'260px'},
      {key:'note',title:'签到备注',width:'260px'},{key:'photo',title:'现场照片',width:'220px'}] },
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
    'batchStore.selectedBatchId'() { this.resetCheckins(); this.closeReject(); this.load() },
    'ctx.ctxKey'() { this.resetCheckins(); this.closeReject(); this.load() }
  },
  created() { this.load() },
  beforeUnmount() { this.disposed=true; this.loadSequence++; this.resetCheckins() },
  methods: {
    snapshot() { return {batchId:String(this.batchId),generation:currentSessionGeneration(),ctxKey:this.ctx?.ctxKey} },
    current(snapshot) { return !this.disposed && String(this.batchId)===snapshot.batchId && currentSessionGeneration()===snapshot.generation && this.ctx?.ctxKey===snapshot.ctxKey },
    clearCheckinPhoto() { this.photoSequence++; this.photoRecord=null; this.photoFile=null; this.photoError=''; this.photoLoading=false },
    resetCheckins() { this.checkinSequence++; this.checkins=[]; this.checkinTotal=0; this.checkinPage=1; this.checkinTeacher=''; this.checkinLoading=false; this.checkinError=''; this.clearCheckinPhoto() },
    checkinParams() { return {batchId:String(this.batchId),teacherUserId:this.checkinTeacher||undefined,result:this.checkinResult||undefined,startDate:this.checkinStart||undefined,endDate:this.checkinEnd||undefined} },
    checkinTone(result) { return ['NORMAL','MAKEUP'].includes(result)?'success':result==='RECORDED'?'default':'warning' },
    checkinTimezone(row) {
      try { return new Intl.DateTimeFormat('zh-CN',{timeZone:row.timezoneName,timeZoneName:'long'}).formatToParts(new Date(row.checkedInAt)).find(part=>part.type==='timeZoneName')?.value || '时区未确认' }
      catch { return '时区未确认' }
    },
    async queryCheckins() { this.checkinPage=1; await this.loadCheckins() },
    async onCheckinPage({page,pageSize}) { this.checkinPage=page; this.checkinPageSize=pageSize; await this.loadCheckins() },
    async loadCheckins() {
      const sequence=++this.checkinSequence,snapshot=this.snapshot(),params=this.checkinParams()
      this.clearCheckinPhoto(); this.checkins=[]; this.checkinTotal=0; this.checkinError=''; this.checkinLoading=false
      if(!this.batchId || this.disposed) return
      if(this.checkinStart && this.checkinEnd && this.checkinStart>this.checkinEnd) { this.checkinError='开始日期不能晚于结束日期'; return }
      this.checkinLoading=true
      let res
      try { res=await internshipApi.getTeacherCheckins({...params,page:this.checkinPage,pageSize:this.checkinPageSize}) }
      catch { res={code:1,message:'教师签到明细读取失败，请重新读取'} }
      if(sequence!==this.checkinSequence || !this.current(snapshot)) return
      this.checkinLoading=false
      if(res.code!==0) { this.checkinError=res.message||'教师签到明细读取失败，请重新读取'; return }
      this.checkins=res.data?.items||[]; this.checkinTotal=Number(res.data?.total||0)
    },
    async exportCheckinsFn() {
      if(!this.canExport || !this.batchId || this.loading || this.checkinLoading) return {code:1,message:'当前没有可导出的教师签到上下文'}
      if(this.checkinStart && this.checkinEnd && this.checkinStart>this.checkinEnd) return {code:1,message:'开始日期不能晚于结束日期'}
      const snapshot=this.snapshot(),params=this.checkinParams()
      const res=await internshipApi.exportTeacherCheckins(params)
      if(!this.current(snapshot) || JSON.stringify(params)!==JSON.stringify(this.checkinParams())) return {code:1,message:'学校、批次或筛选条件已变化，请在当前页面重新导出'}
      return res
    },
    async openCheckinPhoto(row, original=false) {
      const canonical=this.checkins.find(item=>String(item.id)===String(row?.id))
      const fileId=canonical && (original?canonical.photoFileId:canonical.watermarkedFileId)
      if(!fileId || this.disposed || this.checkinLoading) return
      this.clearCheckinPhoto(); const sequence=this.photoSequence,snapshot=this.snapshot()
      this.photoLoading=true; this.photoRecord=canonical; this.photoOriginal=original
      try {
        const file=await fileSdk.metadata(String(fileId))
        if(sequence!==this.photoSequence || !this.current(snapshot)) return
        if(String(file.fileId)!==String(fileId)) throw new Error('照片信息未能确认')
        this.photoFile=file
      } catch { if(sequence===this.photoSequence && this.current(snapshot)) this.photoError='教师签到照片读取失败，请重新选择照片' }
      finally { if(sequence===this.photoSequence && this.current(snapshot)) this.photoLoading=false }
    },
    displayTime(value) { return formatDateTime(value, '未记录') },
    ratingDistributionText(value) {
      const d=value || {}
      return [1,2,3,4,5].map(level => level + '级 ' + Number(d[String(level)] || 0)).join(' / ')
    },
    statusLabel(value) { return {PENDING:'待审核',APPROVED:'已通过',REJECTED:'已驳回',WITHDRAWN:'已撤回'}[value] || '状态待确认' },
    statusTone(value) { return {APPROVED:'success',REJECTED:'danger',PENDING:'warning'}[value] || 'default' },
    async load() {
      const sequence=++this.loadSequence,snapshot=this.snapshot()
      this.checkinSequence++; this.clearCheckinPhoto(); this.checkins=[]; this.checkinTotal=0
      this.teachers=[]; this.makeups=[]; this.reviewPerformance=[]; this.reviewFactCount=0
      if (!this.batchId) { this.teachers=[]; this.makeups=[]; this.reviewPerformance=[]; this.reviewFactCount=0; this.loading=false; this.error=''; return }
      this.loading=true; this.error=''; this.message=''
      const [ledger, makeups, performance] = await Promise.all([
        internshipApi.getTeacherManagement({ batchId:this.batchId, keyword:this.keyword || undefined }),
        internshipApi.getTeacherMakeups({ batchId:this.batchId, status:this.makeupStatus || undefined, pageSize:200 }),
        internshipApi.getReportReviewPerformance({ batchId:this.batchId })
      ])
      if(sequence!==this.loadSequence || !this.current(snapshot)) return
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
      await this.loadCheckins()
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
      this.message=action==='APPROVE'?'补签已通过，并已生成教师补签记录。':'补签已驳回。'
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
.tm-checkin-filter{display:flex;flex-wrap:wrap;align-items:end;gap:12px;padding:16px}.tm-checkin-filter label{display:grid;gap:6px;font-size:12px}.tm-checkin-filter input,.tm-checkin-filter select{height:36px;border:1px solid var(--border-base);border-radius:6px;padding:0 10px;background:var(--bg-card);color:var(--text-primary)}.tm-checkin-note{white-space:pre-wrap;overflow-wrap:anywhere}.tm-photo{padding:16px}.tm-card :deep(.app-pagination){padding:16px}
@media(max-width:900px){.tm-filter,.tm-head{align-items:stretch;flex-direction:column}.tm-filter label{min-width:0}.tm-reject{grid-template-columns:1fr}}
</style>
