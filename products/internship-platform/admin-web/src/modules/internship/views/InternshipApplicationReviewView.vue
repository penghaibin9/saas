<template>
  <ModulePageShell :title="isDetail ? drawerTitle : '实习申请审核'" :subtitle="isDetail ? '核对学生申请与实习去向，查看材料后提交审核结论。' : '按办理状态查看岗位志愿与自主实习申请。'" :watermark="false">
    <template #actions>
      <AppButton v-if="isDetail" variant="ghost" @click="backToList">返回申请列表</AppButton>
      <AppButton
        v-else
        variant="ghost"
        :disabled="loading || exporting || !batchStore.selectedBatchId"
        @click="exportCurrent"
      >{{ exporting ? '正在导出…' : '导出当前筛选 Excel' }}</AppButton>
    </template>
    <section v-if="!isDetail" class="iar-card iar-list">
      <nav class="iar-tabs" aria-label="申请审核状态">
        <button v-for="item in statusOptions" :key="item.value" type="button" :class="{ 'is-active': status === item.value }" :aria-current="status === item.value ? 'page' : undefined" @click="setStatus(item.value)">{{ item.label }}</button>
      </nav>
      <div class="iar-filters">
        <AppSearchBox v-model="keyword" placeholder="搜索学生、企业或岗位" aria-label="搜索申请" @search="reload" />
        <AppSelect v-model="applicationType" class="iar-type-filter" :options="typeOptions" placeholder="全部申请类型" aria-label="申请类型" @change="reload" />
        <span v-if="!loading && !error" class="iar-count">{{ total }} 条申请</span>
      </div>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <DataTable v-else-if="rows.length" :columns="columns" :rows="rows" row-key="id" :pagination="pagination" @page-change="onPageChange">
        <template #cell-applicationType="{ row }"><AppStatusTag :type="row.applicationType === 'SELF_ARRANGED' ? 'warning' : 'info'">{{ row.applicationTypeLabel }}</AppStatusTag></template>
        <template #cell-applicant="{ row }"><div class="iar-cell"><strong>{{ row.studentName }}</strong><span>{{ row.studentNo }}<template v-if="row.advisorName"> · {{ row.advisorName }}</template></span></div></template>
        <template #cell-destination="{ row }"><div class="iar-cell"><strong>{{ row.applicationType === 'EXEMPTION' ? '免实习' : (row.companyName || '—') }}</strong><span>{{ row.applicationType === 'EXEMPTION' ? (row.exemptionDestination || '去向待补充') : (row.positionName || '—') }}</span></div></template>
        <template #cell-status="{ row }"><AppStatusTag :type="statusTone(row.status)">{{ row.statusLabel }}</AppStatusTag></template>
        <template #cell-actions="{ row }"><AppButton variant="ghost" size="sm" @click="openDetail(row.id)">{{ row.status === 'PENDING_REVIEW' ? '审核申请' : '查看详情' }}</AppButton></template>
      </DataTable>
      <p v-else class="iar-empty">当前条件下暂无申请，可切换状态或调整筛选。</p>
    </section>
    <template v-else>
      <section v-if="queueError" class="iar-conflict" role="alert"><strong>审核已完成，待审队列暂未更新</strong><p>{{ queueError }}</p><AppButton variant="ghost" :disabled="loading" @click="advanceAfterReview(drawer.id)">重新读取待审队列</AppButton></section>
      <LoadingState v-if="drawer.loading" />
      <ErrorState v-else-if="drawer.error" :description="drawer.error" @retry="loadDetail(drawer.id)" />
      <div v-else-if="drawer.data" class="iar-workspace">
        <div class="iar-main">
          <section class="iar-card"><header><h2>申请信息</h2><AppStatusTag :type="statusTone(drawer.data.status)">{{ drawer.data.statusLabel }}</AppStatusTag></header><div class="iar-body"><AppDescriptionList :items="detailItems" :columns="2" /></div></section>
          <section class="iar-card"><header><h2>申请说明与证明材料</h2></header><div class="iar-body"><p class="iar-note">{{ drawer.data.applicationNote || '学生未填写补充说明。' }}</p><AppFilePreview v-if="evidenceFiles.length" :files="evidenceFiles" @preview="previewEvidence" @download="downloadEvidence" /><p v-else class="iar-note">此申请暂无附件。</p></div></section>
          <section class="iar-card"><header><h2>办理记录</h2></header><div class="iar-body"><AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无操作记录" /></div></section>
        </div>
        <aside class="iar-card iar-review"><header><h2>{{ drawer.data.status === 'PENDING_REVIEW' ? '审核申请' : '审核结果' }}</h2></header><div class="iar-body">
          <template v-if="drawer.data.status === 'PENDING_REVIEW'"><p class="iar-note">{{ drawer.data.applicationType === 'EXEMPTION' ? '通过后正式标记为免实习，并取消该学生其他进行中的实习申请。' : '通过后落实本次实习去向，并取消该学生其他进行中的申请。' }}</p><div class="iar-actions"><AppPermissionButton code="internship.application.review" :allowed="canBtn('internship.application.review')" variant="primary" @click="askReview('APPROVE')">通过并落实去向</AppPermissionButton><AppPermissionButton code="internship.application.review" :allowed="canBtn('internship.application.review')" variant="ghost" :danger="true" @click="askReview('REJECT')">驳回申请</AppPermissionButton></div></template>
          <template v-else><AppStatusTag :type="statusTone(drawer.data.status)">{{ drawer.data.statusLabel }}</AppStatusTag><AppDescriptionList v-if="drawer.data.reviewedAt" :items="reviewItems" :columns="1" /><p v-else class="iar-note">当前申请无需审核，可查看左侧办理记录。</p></template>
        </div></aside>
      </div>
    </template>
    <AppConfirmDialog v-model:visible="confirm.visible" :title="confirm.title" :content="confirm.content" :danger="confirm.danger" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason" :reason-chips="confirm.requireReason ? REJECT_APPLICATION : []" reason-label="审核意见" :submitting="confirm.submitting" :confirm-disabled="conflict.active" @confirm="submitReview">
      <p v-if="reviewError" class="iar-review-error" role="alert">{{ reviewError }}</p>
      <section v-if="conflict.active" class="iar-conflict" role="alert">
        <strong>申请已变化，请重新核对</strong><p>{{ conflict.detail }}</p>
        <AppDescriptionList v-if="conflict.latest.length" :items="conflict.latest" :columns="1" />
        <p>本次审核意见已保留，原确认暂不能提交。</p>
        <AppButton v-if="conflict.stale" variant="ghost" :disabled="confirm.submitting" @click="readReviewConflict()">重新读取最新申请</AppButton>
        <AppButton v-else-if="drawer.data?.status === 'PENDING_REVIEW' && canBtn('internship.application.review')" variant="ghost" @click="acceptLatestReview">已核对，按最新记录重新确认</AppButton>
        <p v-else>该申请当前不可审核，请取消确认并查看处理结果。</p>
      </section>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import {
  AppStatusTag, AppSearchBox, AppSelect, AppDescriptionList,
  AppFilePreview, AppAuditTrail, AppPermissionButton, AppConfirmDialog
} from '@/components/common'
import { isConflict, captureConflict, emptyConflict } from '@/modules/internship/composables/conflictGuard'
import { pickNextPending, anchorIndexOf } from '@/modules/internship/composables/reviewQueue'
import { downloadAttachment } from '@/modules/internship/api/guidance-visit.api'
import { internshipApplicationApi } from '@/modules/internship/api/internship-application.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { fileSdk } from '@/services/file/fileSdk'
import { REJECT_APPLICATION } from '@/modules/internship/constants/presetPrompts'
import { useInternshipBatchStore } from '@/stores/internshipBatch'


const TYPE_OPTIONS = [
  { value: '', label: '全部申请' },
  { value: 'POSITION', label: '岗位志愿' },
  { value: 'SELF_ARRANGED', label: '自主实习' },
  { value: 'EXEMPTION', label: '免实习申请' }
]
const EXEMPTION_TYPE_LABEL = {
  FURTHER_STUDY: '升学',
  MILITARY: '参军入伍',
  HEALTH: '健康原因',
  OTHER: '其他'
}
const STATUS_OPTIONS = [
  { value: 'ALL', label: '全部状态' },
  { value: 'PENDING_REVIEW', label: '待审核' },
  { value: 'APPROVED', label: '已通过' },
  { value: 'REJECTED', label: '已驳回' },
  { value: 'WITHDRAWN', label: '已撤回' },
  { value: 'CANCELLED', label: '已取消' }
]
const COLUMNS = [
  { key: 'applicationType', title: '申请类型', width: '120px' },
  { key: 'applicant', title: '学生', width: '150px' },
  { key: 'destination', title: '申请去向' },
  { key: 'submittedAt', title: '提交时间', width: '160px' },
  { key: 'status', title: '状态', width: '110px' },
  { key: 'actions', title: '操作', width: '90px' }
]

export default {
  name: 'InternshipApplicationReviewView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, AppButton, AppStatusTag, AppSearchBox,
    AppSelect, AppDescriptionList, AppFilePreview, AppAuditTrail,
    AppPermissionButton, AppConfirmDialog
  },
  data() {
    return {
      REJECT_APPLICATION,
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, exporting: false, error: '',
      applicationType: '', status: 'PENDING_REVIEW', keyword: '',
      typeOptions: TYPE_OPTIONS, statusOptions: STATUS_OPTIONS, columns: COLUMNS,
      drawer: { visible: false, id: '', loading: false, error: '', data: null },
      confirm: { visible: false, title: '', content: '', danger: false, confirmText: '', requireReason: false, submitting: false, action: '' },
      conflict: emptyConflict(),
      reviewError: '', queueError: '',
      listTicket: 0, detailTicket: 0
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    drawerTitle() {
      const data = this.drawer.data
      return data ? `申请审核 · ${data.studentName}` : '申请审核'
    },
    isDetail() { return !!this.$route.query.id },
    detailItems() {
      const data = this.drawer.data || {}
      if (data.applicationType === 'EXEMPTION') {
        return [
          { label: '学生', value: `${data.studentName || '—'}（${data.studentNo || '—'}）` },
          { label: '校内指导教师', value: data.advisorName || '—' },
          { label: '申请类型', value: data.applicationTypeLabel || '免实习申请' },
          { label: '免实习类型', value: EXEMPTION_TYPE_LABEL[data.exemptionType] || data.exemptionType || '—' },
          { label: '免实习后去向', value: data.exemptionDestination || '—' },
          { label: '申请原因', value: data.exemptionReason || '—' },
          { label: '佐证材料', value: data.evidenceFileId ? '已上传' : '未上传' },
          { label: '提交时间', value: data.submittedAt || '未提交' },
          { label: '当前状态', value: data.statusLabel || '—' }
        ]
      }
      const companyRegion = [data.companyProvince, data.companyCity, data.companyDistrict].filter(Boolean).join(' / ')
      const workRegion = [data.workCountry, data.workProvince, data.workCity, data.workDistrict].filter(Boolean).join(' / ')
      const registry = data.companyRegistryVerified
        ? `已核验 · ${data.companyRegistryProvider || '授权企业登记数据源'}`
        : '未通过授权企业登记数据源核验'
      return [
        { label: '学生', value: `${data.studentName || '—'}（${data.studentNo || '—'}）` },
        { label: '校内指导教师', value: data.advisorName || '—' },
        { label: '申请类型', value: data.applicationTypeLabel || '—' },
        { label: '志愿顺序', value: data.applicationType === 'POSITION' ? `第 ${data.volunteerNo} 志愿` : '自主实习' },
        { label: '实习单位', value: data.companyName || '—' },
        { label: '统一社会信用代码', value: data.companyCreditCode || '—' },
        { label: '企业登记核验', value: registry },
        { label: '企业负责人', value: data.companyPrincipal || '—' },
        { label: '企业规模', value: data.companyScale || '—' },
        { label: '单位性质', value: data.companyNature || '—' },
        { label: '所属行业', value: data.companyIndustry || '—' },
        { label: '企业联系电话', value: data.companyPhone || '—' },
        { label: '企业邮箱', value: data.companyEmail || '—' },
        { label: '单位所在地区', value: companyRegion || '—' },
        { label: '单位注册地址', value: data.companyRegisteredAddress || '—' },
        { label: '企业邮编', value: data.companyPostalCode || '—' },
        { label: '单位联系人', value: data.contactName ? `${data.contactName}${data.contactPhone ? ` · ${data.contactPhone}` : ''}` : '—' },
        { label: '实习部门', value: data.internshipDepartment || '—' },
        { label: '实习岗位', value: data.positionName || '—' },
        { label: '岗位类别', value: data.positionCategory || '—' },
        { label: '工作内容', value: data.workContent || '—' },
        { label: '企业老师', value: data.enterpriseMentorName ? `${data.enterpriseMentorName}${data.enterpriseMentorPhone ? ` · ${data.enterpriseMentorPhone}` : ''}` : '—' },
        { label: '岗位所在地区', value: workRegion || '—' },
        { label: '岗位详细地址', value: data.workAddress || '—' },
        { label: '实习时间', value: data.internshipStartDate || data.internshipEndDate ? `${data.internshipStartDate || '—'} 至 ${data.internshipEndDate || '—'}` : '—' },
        { label: '实习方式', value: data.internshipMode || '—' },
        { label: '专业是否对口', value: data.majorMatch === true ? '是' : (data.majorMatch === false ? '否' : '—') },
        { label: '约定实习薪资', value: data.agreedSalary == null ? '—' : `${data.agreedSalary} 元/月` },
        { label: '三方协议材料', value: `${(data.agreementFileIds || []).length} 份` },
        { label: '提交时间', value: data.submittedAt || '未提交' },
        { label: '当前状态', value: data.statusLabel || '—' }
      ]
    },
    reviewItems() {
      const data = this.drawer.data || {}
      return [
        { label: '审核人', value: data.reviewedBy || '—' },
        { label: '审核时间', value: data.reviewedAt || '—' },
        { label: '审核意见', value: data.reviewComment || '—' }
      ]
    },
    evidenceFiles() {
      const data = this.drawer.data || {}
      const files = []
      if (data.evidenceFileId) files.push({ id: data.evidenceFileId, name: data.applicationType === 'EXEMPTION' ? '免实习佐证材料' : '自主实习证明材料', sensitive: true })
      ;(data.agreementFileIds || []).forEach((id, index) => {
        if (id) files.push({ id, name: `三方协议材料 ${index + 1}`, sensitive: true })
      })
      return files
    },
    auditRecords() {
      return (this.drawer.data?.auditTrail || []).map((item, index) => ({
        id: index, action: item.action, actor: item.operator,
        reason: item.detail?.comment || '', at: item.occurredAt
      }))
    }
  },
  watch: {
    '$route.fullPath': { immediate: true, handler() { this.restoreLocation() } },
    'batchStore.selectedBatchId'() { this.restoreLocation() }
  },
  beforeUnmount() { this.listTicket++; this.detailTicket++ },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    statusTone(value) {
      if (value === 'APPROVED') return 'success'
      if (value === 'REJECTED') return 'danger'
      if (value === 'PENDING_REVIEW') return 'warning'
      return 'default'
    },
    restoreLocation() {
      const q = this.$route.query
      this.applicationType = ['POSITION', 'SELF_ARRANGED', 'EXEMPTION'].includes(q.type) ? q.type : ''
      this.status = STATUS_OPTIONS.some(item => item.value === q.status) ? q.status : 'PENDING_REVIEW'
      this.keyword = String(q.keyword || '')
      const page = Number(q.page); this.page = Number.isSafeInteger(page) && page > 0 ? page : 1
      this.confirm.visible = false; this.conflict = emptyConflict()
      this.reviewError = ''; this.queueError = ''; this.confirm = { ...this.confirm, visible: false, submitting: false, snapshot: null }
      this.load()
      const id = String(q.id || '')
      this.drawer = { visible: !!id, id, loading: !!id, error: '', data: null }
      this.detailTicket++
      if (id) this.loadDetail(id)
    },
    listQuery() { return this.batchStore.withBatchQuery({ type: this.applicationType || undefined, status: this.status || 'ALL', keyword: this.keyword || undefined, page: this.page > 1 ? this.page : undefined }) },
    backToList() { return this.$router.push({ path: '/admin/internship/applications', query: this.listQuery() }) },
    updateLocation() { const to = { path: '/admin/internship/applications', query: this.listQuery() }; if (this.$router.resolve(to).fullPath === this.$route.fullPath) this.load(); else this.$router.replace(to) },
    setStatus(value) { this.status = value; this.reload() },
    reload() { this.page = 1; this.updateLocation() },
    onPageChange(page) { this.page = page; this.updateLocation() },
    async exportCurrent() {
      if (!this.batchStore.selectedBatchId || this.exporting) return
      this.exporting = true
      const params = {
        batchId: this.batchStore.selectedBatchId,
        keyword: this.keyword || undefined,
        applicationType: this.applicationType || undefined,
        status: this.status && this.status !== 'ALL' ? this.status : undefined
      }
      const result = await internshipApplicationApi.exportApplications(params)
      this.exporting = false
      if (result.code !== 0) {
        toast.error(result.message || '申请审核台账导出失败')
        return
      }
      toast.success(`已导出当前筛选条件下的完整申请台账，共 ${this.total} 条页面口径记录`)
    },
    async load() {
      const ticket = ++this.listTicket
      if (!this.batchStore.selectedBatchId) {
        this.loading = false
        this.error = '请先选择实习批次'
        this.rows = []
        this.total = 0
        return
      }
      this.loading = true; this.rows = []; this.total = 0
      this.error = ''
      const params = {
        page: this.page,
        pageSize: this.pageSize,
        keyword: this.keyword,
        batchId: this.batchStore.selectedBatchId
      }
      if (this.applicationType) params.applicationType = this.applicationType
      if (this.status && this.status !== 'ALL') params.status = this.status
      let result
      try { result = await internshipApplicationApi.getApplications(params) }
      catch (error) { result = { code: -1, message: error.message || '申请列表读取失败，请重试' } }
      if (ticket !== this.listTicket) return
      this.loading = false
      if (result.code !== 0) {
        this.error = result.message || '加载失败'
        this.rows = []
        this.total = 0
        return
      }
      this.rows = result.data.list
      this.total = result.data.total
    },
    openDetail(id) {
      return this.$router.push({ path: '/admin/internship/applications', query: { ...this.listQuery(), id: String(id) } })
    },
    async previewEvidence(file) {
      try { await fileSdk.preview(String(file.id)) } catch { toast.error('证明材料暂时无法预览，请重试或下载查看。') }
    },
    async loadDetail(id) {
      const ticket = ++this.detailTicket
      const value = String(id)
      this.drawer.loading = true
      this.drawer.error = ''; this.drawer.data = null
      let result
      try { result = await internshipApplicationApi.getDetail(value) }
      catch (error) { result = { code: -1, message: error.message || '申请详情读取失败，请重试' } }
      if (this.drawer.id !== value || ticket !== this.detailTicket) return
      this.drawer.loading = false
      if (result.code !== 0) {
        this.drawer.error = result.message || '申请详情加载失败'
        return
      }
      this.drawer.data = result.data
    },
    async downloadEvidence(file) {
      try {
        await downloadAttachment(file.id, file.name)
      } catch (error) {
        toast.error(error?.message || '下载失败')
      }
    },
    askReview(action) {
      const data = this.drawer.data
      if (!data || data.status !== 'PENDING_REVIEW' || this.confirm.submitting || !this.canBtn('internship.application.review') || !['APPROVE', 'REJECT'].includes(action)) return
      const approve = action === 'APPROVE'
      this.confirm = {
        visible: true,
        title: approve ? '通过实习申请' : '驳回实习申请',
        content: approve
          ? (data.applicationType === 'EXEMPTION'
              ? `确认通过「${data.studentName}」的免实习申请？系统将正式标记免实习，并取消该学生其他进行中的申请。`
              : `确认通过「${data.studentName}」的申请？系统将立即落实其实习去向，并取消该学生其他进行中的申请。`)
          : `确认驳回「${data.studentName}」的申请？请填写可执行的驳回原因。`,
        danger: !approve,
        confirmText: approve ? '通过并落实' : '确认驳回',
        requireReason: !approve,
        submitting: false,
        action,
        snapshot: { id: data.id, expectedVersion: data.version, recordExpectedVersion: data.recordVersion, batchId: this.batchStore.selectedBatchId, ticket: this.detailTicket }
      }
      this.conflict = emptyConflict()
      this.reviewError = ''
    },
    async readReviewConflict(result = { message: '请核对最新申请状态' }) {
      const confirmation = this.confirm, snapshot = confirmation.snapshot
      if (!snapshot || confirmation.submitting) return
      confirmation.submitting = true
      try {
        const state = await captureConflict({
          res: result,
          refresh: () => this.loadDetail(snapshot.id),
          latest: () => {
            const fresh = this.drawer.data
            if (!fresh) throw new Error('最新详情未拉回')
            return [
              { label: '最新状态', value: fresh.statusLabel || fresh.status || '' },
              { label: '审核人', value: fresh.reviewedBy || '' },
              { label: '审核意见', value: fresh.reviewComment || '' }
            ]
          }
        })
        if (this.confirm === confirmation && this.drawer.id === String(snapshot.id) && this.batchStore.selectedBatchId === snapshot.batchId) this.conflict = state
      } finally { if (this.confirm === confirmation) confirmation.submitting = false }
    },
    acceptLatestReview() {
      const data = this.drawer.data
      if (!this.conflict.active || this.conflict.stale || this.confirm.submitting || this.drawer.loading || this.drawer.error || !data || data.status !== 'PENDING_REVIEW' || !this.canBtn('internship.application.review')) return
      this.confirm.snapshot = { id: data.id, expectedVersion: data.version, recordExpectedVersion: data.recordVersion, batchId: this.batchStore.selectedBatchId, ticket: this.detailTicket }
      this.conflict = emptyConflict(); this.reviewError = ''
    },
    async submitReview({ reason = '' } = {}) {
      const confirmation = this.confirm, snapshot = confirmation.snapshot
      if (!confirmation.visible || !snapshot || confirmation.submitting || this.conflict.active || !this.canBtn('internship.application.review')) return
      if (snapshot.id !== this.drawer.data?.id || snapshot.ticket !== this.detailTicket || snapshot.batchId !== this.batchStore.selectedBatchId || this.drawer.data.status !== 'PENDING_REVIEW') {
        this.reviewError = '当前申请已变化，请取消确认并重新核对'; return
      }
      const current = () => this.confirm === confirmation && this.drawer.id === String(snapshot.id) && snapshot.batchId === this.batchStore.selectedBatchId && snapshot.ticket === this.detailTicket
      confirmation.submitting = true; this.reviewError = ''
      try {
        const result = await internshipApplicationApi.review(snapshot.id, { action: confirmation.action, comment: reason, expectedVersion: snapshot.expectedVersion, recordExpectedVersion: snapshot.recordExpectedVersion })
        if (!current()) return
        if (isConflict(result)) {
          this.conflict = { ...emptyConflict(), active: true, detail: result.message || '记录已更新', stale: true }
          confirmation.submitting = false
          await this.readReviewConflict(result)
          return
        }
        if (result.code !== 0) { this.reviewError = result.message || '审核失败，意见已保留'; return }
        confirmation.visible = false; this.conflict = emptyConflict()
        this.drawer.data = { ...this.drawer.data, ...result.data }
        toast.success(confirmation.action === 'APPROVE' ? '申请已通过，实习去向已落实' : '申请已驳回')
        await this.advanceAfterReview(snapshot.id)
      } catch (error) { if (current()) this.reviewError = error.message || '审核失败，意见已保留' }
      finally { if (this.confirm === confirmation) confirmation.submitting = false }
    },
    /**
     * 连续审核：完成当前对象后保留列表上下文，进入下一条申请的独立工作区。
     * 本页没有待审核对象时返回列表；不把当前页空当作全批次完成。
     */
    async advanceAfterReview(oldId) {
      const location = this.$route.fullPath, batchId = this.batchStore.selectedBatchId
      const anchor = anchorIndexOf(this.rows, oldId)
      await this.load()
      if (location !== this.$route.fullPath || batchId !== this.batchStore.selectedBatchId) return
      if (this.error) { this.queueError = this.error; return }
      this.queueError = ''
      const next = pickNextPending(this.rows, anchor, oldId, (r) => r.status === 'PENDING_REVIEW')
      if (next) {
        await this.openDetail(next.id)
        return
      }
      await this.backToList()
      toast.success('当前页没有其他待审核申请，可继续查看列表。')
    }
  }
}
</script>

<style scoped>
.iar-card { min-width: 0; background: var(--card, #fff); border: 1px solid var(--card-b, #e2e8f0); border-radius: 12px; }
.iar-list { overflow: hidden; }.iar-tabs { display: flex; gap: 24px; overflow-x: auto; padding: 0 20px; border-bottom: 1px solid var(--card-b, #e2e8f0); }
.iar-tabs button { flex: none; padding: 16px 0 14px; font: inherit; font-size: 14px; border: 0; border-bottom: 3px solid transparent; background: transparent; color: var(--t2, #526077); cursor: pointer; }.iar-tabs button.is-active { border-color: var(--pri, #315fba); color: var(--pri, #315fba); font-weight: 600; }.iar-tabs button:hover { color: var(--pri, #315fba); }.iar-tabs button:focus-visible { outline: 2px solid var(--pri, #315fba); outline-offset: -4px; }
.iar-filters { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; padding: 18px 20px; }.iar-type-filter { width: 180px; flex: 0 0 180px; }.iar-count { margin-left: auto; font-size: 13px; color: var(--text-tertiary); }
.iar-cell { display: grid; gap: 5px; line-height: 1.6; overflow-wrap: anywhere; }.iar-cell strong { font-size: 13px; font-weight: 500; }.iar-cell span { font-size: 12px; color: var(--text-tertiary); }
.iar-empty { padding: 48px 24px; margin: 0; text-align: center; color: var(--text-tertiary); font-size: 13px; }
.iar-review-error { color:var(--danger,#dc2626);font-size:13px;line-height:1.7; }.iar-conflict{padding:14px;border:1px solid var(--warning-300,#fcd34d);border-radius:8px;background:var(--warning-50,#fffbeb);font-size:13px;line-height:1.7}.iar-conflict p{margin:8px 0}
.iar-workspace { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 20px; align-items: start; }.iar-main { display: grid; min-width: 0; gap: 20px; }.iar-card header { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; padding: 18px 20px; border-bottom: 1px solid var(--card-b, #e2e8f0); }.iar-card h2 { font-size: 16px; margin: 0; }.iar-body { padding: 20px; }.iar-note { margin: 0 0 16px; font-size: 13px; line-height: 1.8; color: var(--text-secondary); white-space: pre-wrap; overflow-wrap: anywhere; }.iar-note:last-child { margin-bottom: 0; }.iar-review { position: sticky; top: 16px; }.iar-actions { display: flex; flex-direction: column; align-items: stretch; gap: 10px; }
@media (max-width: 980px) { .iar-workspace { grid-template-columns: 1fr; }.iar-review { position: static; } }
</style>
