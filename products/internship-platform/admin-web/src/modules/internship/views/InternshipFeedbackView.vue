<template>
  <ModulePageShell
    :title="isDetail ? '学生意见反馈详情' : '学生意见反馈'"
    :subtitle="isDetail ? '查看学生原始反馈、图片和学校处理记录。' : '集中查看学生在实习过程中的学院级、系部级建议与想法。'"
    :watermark="false"
  >
    <template v-if="isDetail" #actions>
      <AppButton variant="ghost" @click="backToList">返回反馈列表</AppButton>
    </template>

    <section v-if="!isDetail" class="ifb-card">
      <div class="ifb-toolbar">
        <AppSelect v-model="filters.feedbackLevel" :options="levelOptions" placeholder="全部反馈级别" @change="reload" />
        <AppSelect v-model="filters.status" :options="statusOptions" placeholder="全部状态" @change="reload" />
        <span v-if="!loading && !error" class="ifb-count">{{ total }} 条反馈</span>
      </div>
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <DataTable
        v-else-if="rows.length"
        :columns="columns"
        :rows="rows"
        row-key="id"
        :pagination="pagination"
        @page-change="onPageChange"
      >
        <template #cell-student="{ row }">
          <div class="ifb-cell"><strong>{{ row.studentName || '学生' }}</strong><span>{{ row.createdAt || '—' }}</span></div>
        </template>
        <template #cell-title="{ row }">
          <div class="ifb-cell"><strong>{{ row.title || '未命名反馈' }}</strong><span>{{ previewText(row.content) }}</span></div>
        </template>
        <template #cell-level="{ row }">
          <AppStatusTag type="info">{{ levelLabel(row.feedbackLevel) }}</AppStatusTag>
        </template>
        <template #cell-images="{ row }">{{ (row.imageFileIds || []).length }} 张</template>
        <template #cell-status="{ row }">
          <AppStatusTag :type="statusTone(row.status)">{{ row.statusLabel || row.status }}</AppStatusTag>
        </template>
        <template #cell-actions="{ row }">
          <AppButton variant="ghost" size="sm" @click="openDetail(row.id)">
            {{ ['RECEIVED', 'ACCEPTED', 'INVESTIGATING'].includes(row.status) ? '处理反馈' : '查看详情' }}
          </AppButton>
        </template>
      </DataTable>
      <EmptyState v-else title="当前批次暂无学生意见反馈" description="学生通过移动端提交后会进入这里，不需要另建处理台账。" />
    </section>

    <template v-else>
      <LoadingState v-if="detail.loading" />
      <ErrorState v-else-if="detail.error" :description="detail.error" @retry="loadDetail(detail.id)" />
      <div v-else-if="detail.data" class="ifb-workspace">
        <main class="ifb-main">
          <section class="ifb-card">
            <header class="ifb-head">
              <div>
                <h2>{{ detail.data.title || '学生意见反馈' }}</h2>
                <p>{{ detail.data.complaintNo || '反馈记录' }} · {{ detail.data.studentName || '学生' }}</p>
              </div>
              <AppStatusTag :type="statusTone(detail.data.status)">{{ detail.data.statusLabel || detail.data.status }}</AppStatusTag>
            </header>
            <AppDescriptionList :items="detailItems" :columns="2" />
          </section>

          <section class="ifb-card">
            <h2>学生原始反馈</h2>
            <p class="ifb-content">{{ detail.data.content || '—' }}</p>
          </section>

          <section class="ifb-card">
            <h2>反馈图片</h2>
            <AppFilePreview
              v-if="imageFiles.length"
              :files="imageFiles"
              @preview="previewImage"
              @download="downloadImage"
            />
            <p v-else class="ifb-muted">学生本次未上传图片。</p>
          </section>

          <section class="ifb-card">
            <h2>办理记录</h2>
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无办理记录" />
          </section>
        </main>

        <aside class="ifb-card ifb-actions">
          <h2>学校处理</h2>
          <p class="ifb-muted">反馈沿用学校既有受理、调查、办结留痕，避免另造一套工单。</p>
          <template v-if="canHandle">
            <AppButton v-if="detail.data.status === 'RECEIVED'" variant="primary" @click="transition('ACCEPT')">受理反馈</AppButton>
            <AppButton v-if="detail.data.status === 'ACCEPTED'" variant="primary" @click="transition('INVESTIGATE')">开始处理</AppButton>
            <AppButton v-if="detail.data.status === 'INVESTIGATING'" variant="primary" @click="askConclusion('RESOLVE')">填写意见并办结</AppButton>
            <AppButton
              v-if="['RECEIVED', 'ACCEPTED', 'INVESTIGATING'].includes(detail.data.status)"
              variant="ghost"
              @click="askConclusion('REJECT')"
            >不采纳并说明</AppButton>
          </template>
          <p v-else class="ifb-muted">当前账号可查看反馈，但没有反馈受理权限。</p>
          <div v-if="detail.data.conclusion" class="ifb-result">
            <strong>处理意见</strong>
            <p>{{ detail.data.conclusion }}</p>
          </div>
          <div v-if="detail.data.followupResult" class="ifb-result">
            <strong>回访结果</strong>
            <p>{{ detail.data.followupResult }}</p>
          </div>
        </aside>
      </div>
    </template>

    <AppConfirmDialog
      v-model:visible="confirm.visible"
      :title="confirm.action === 'RESOLVE' ? '办结学生反馈' : '不采纳本次反馈'"
      :content="confirm.action === 'RESOLVE' ? '请填写学校处理意见，提交后学生端可查看。' : '请说明不采纳原因，提交后学生端可查看。'"
      :danger="confirm.action === 'REJECT'"
      :confirm-text="confirm.action === 'RESOLVE' ? '提交并办结' : '确认不采纳'"
      require-reason
      reason-label="处理意见"
      :submitting="confirm.submitting"
      @confirm="submitConclusion"
    />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import {
  AppStatusTag, AppSelect, AppDescriptionList, AppFilePreview,
  AppAuditTrail, AppConfirmDialog
} from '@/components/common'
import { AppButton } from '@/components/ui'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { canCode } from '@/modules/internship/composables/permission'
import { useInternshipBatchStore } from '@/stores/internshipBatch'
import { fileSdk } from '@/services/file/fileSdk'
import { toast } from '@/utils/toast'

const LEVEL_OPTIONS = [
  { value: '', label: '全部反馈级别' },
  { value: 'COLLEGE', label: '学院级' },
  { value: 'DEPARTMENT', label: '系部级' }
]
const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'RECEIVED', label: '已提交' },
  { value: 'ACCEPTED', label: '已受理' },
  { value: 'INVESTIGATING', label: '处理中' },
  { value: 'RESOLVED', label: '已办结' },
  { value: 'REJECTED', label: '未采纳' },
  { value: 'WITHDRAWN', label: '已撤回' },
  { value: 'CLOSED', label: '已关闭' }
]

export default {
  name: 'InternshipFeedbackView',
  components: {
    ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState,
    AppStatusTag, AppSelect, AppDescriptionList, AppFilePreview,
    AppAuditTrail, AppConfirmDialog, AppButton
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      filters: { feedbackLevel: '', status: '' },
      levelOptions: LEVEL_OPTIONS, statusOptions: STATUS_OPTIONS,
      columns: [
        { key: 'student', title: '学生', width: '170px' },
        { key: 'title', title: '反馈内容' },
        { key: 'level', title: '反馈级别', width: '110px' },
        { key: 'images', title: '图片', width: '80px' },
        { key: 'status', title: '状态', width: '110px' },
        { key: 'actions', title: '操作', width: '100px' }
      ],
      detail: { id: '', loading: false, error: '', data: null },
      confirm: { visible: false, action: '', submitting: false },
      listTicket: 0, detailTicket: 0
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    pagination() { return { page: this.page, pageSize: this.pageSize, total: this.total } },
    isDetail() { return !!this.$route.query.id },
    canHandle() { return canCode(this.ctx, 'internship.complaint.intake') },
    detailItems() {
      const d = this.detail.data || {}
      return [
        { label: '学生', value: d.studentName || '—' },
        { label: '反馈级别', value: this.levelLabel(d.feedbackLevel) },
        { label: '提交时间', value: d.createdAt || '—' },
        { label: '当前状态', value: d.statusLabel || d.status || '—' },
        { label: '受理人', value: d.acceptedByName || '—' },
        { label: '责任人', value: d.ownerName || '—' }
      ]
    },
    imageFiles() {
      return (this.detail.data?.imageFileIds || []).map((id, index) => ({
        id, name: `反馈图片 ${index + 1}`, sensitive: false
      }))
    },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((item, index) => ({
        id: index,
        action: item.action,
        actor: item.operator,
        reason: item.detail?.conclusion || item.detail?.feedbackLevel || '',
        at: item.occurredAt
      }))
    }
  },
  watch: {
    '$route.query': {
      immediate: true,
      deep: true,
      handler(query) {
        this.filters.feedbackLevel = ['COLLEGE', 'DEPARTMENT'].includes(String(query.feedbackLevel || '').toUpperCase())
          ? String(query.feedbackLevel).toUpperCase() : ''
        this.filters.status = STATUS_OPTIONS.some((item) => item.value === query.status) ? String(query.status || '') : ''
        this.page = Math.max(1, Number.parseInt(query.page, 10) || 1)
        if (query.id) this.loadDetail(query.id)
        else this.load()
      }
    },
    'batchStore.selectedBatchId'() {
      this.page = 1
      this.detail = { id: '', loading: false, error: '', data: null }
      this.syncQuery()
    }
  },
  methods: {
    levelLabel(value) {
      return value === 'COLLEGE' ? '学院级' : value === 'DEPARTMENT' ? '系部级' : '—'
    },
    statusTone(status) {
      if (['RESOLVED', 'CLOSED'].includes(status)) return 'success'
      if (status === 'REJECTED') return 'danger'
      if (['ACCEPTED', 'INVESTIGATING'].includes(status)) return 'info'
      if (status === 'WITHDRAWN') return 'default'
      return 'warning'
    },
    previewText(value) {
      const text = String(value || '').replace(/\s+/g, ' ').trim()
      return text.length > 46 ? `${text.slice(0, 46)}…` : (text || '—')
    },
    syncQuery(extra = {}) {
      const query = this.batchStore.withBatchQuery({
        page: String(this.page),
        feedbackLevel: this.filters.feedbackLevel || undefined,
        status: this.filters.status || undefined,
        ...extra
      })
      this.$router.replace({ path: '/admin/internship/feedback', query }).catch(() => {})
    },
    reload() {
      this.page = 1
      this.syncQuery()
    },
    onPageChange(page) {
      this.page = page
      this.syncQuery()
    },
    openDetail(id) {
      this.syncQuery({ id: String(id) })
    },
    backToList() {
      this.syncQuery({ id: undefined })
    },
    async load() {
      const ticket = ++this.listTicket
      const batchId = this.batchStore.selectedBatchId
      this.rows = []
      this.total = 0
      if (!batchId) {
        this.loading = false
        this.error = '请先选择实习批次'
        return
      }
      this.loading = true
      this.error = ''
      const res = await internshipApi.getStudentFeedback({
        batchId,
        page: this.page,
        pageSize: this.pageSize,
        feedbackLevel: this.filters.feedbackLevel || undefined,
        status: this.filters.status || undefined
      })
      if (ticket !== this.listTicket || batchId !== this.batchStore.selectedBatchId) return
      if (res.code === 0) {
        this.rows = res.data?.list || []
        this.total = Number(res.data?.total || 0)
      } else {
        this.error = res.message || '学生意见反馈加载失败'
      }
      this.loading = false
    },
    async loadDetail(id) {
      const ticket = ++this.detailTicket
      this.detail = { id: String(id), loading: true, error: '', data: null }
      const res = await internshipApi.getStudentFeedbackDetail(id)
      if (ticket !== this.detailTicket || String(id) !== String(this.$route.query.id || '')) return
      if (res.code === 0) {
        const data = res.data
        if (data?.category !== 'STUDENT_FEEDBACK') {
          this.detail.error = '该记录不是学生意见反馈'
        } else {
          this.detail.data = data
        }
      } else {
        this.detail.error = res.message || '反馈详情加载失败'
      }
      this.detail.loading = false
    },
    async transition(action) {
      if (!this.canHandle || !this.detail.data?.id) return
      const res = await internshipApi.transitionStudentFeedback(this.detail.data.id, {
        action,
        expectedVersion: this.detail.data.version
      })
      if (res.code !== 0) {
        toast.error(res.message || '处理失败，请刷新后重试')
        await this.loadDetail(this.detail.data.id)
        return
      }
      toast.success(action === 'ACCEPT' ? '已受理学生反馈' : '已进入处理')
      await this.loadDetail(this.detail.data.id)
    },
    askConclusion(action) {
      if (!this.canHandle) return
      this.confirm = { visible: true, action, submitting: false }
    },
    async submitConclusion(reason) {
      const conclusion = String(reason || '').trim()
      if (conclusion.length < 5) {
        toast.error('处理意见不少于5个字')
        return
      }
      this.confirm.submitting = true
      const action = this.confirm.action
      const res = await internshipApi.transitionStudentFeedback(this.detail.data.id, {
        action,
        conclusion,
        expectedVersion: this.detail.data.version
      })
      this.confirm.submitting = false
      if (res.code !== 0) {
        toast.error(res.message || '处理失败，请刷新后重试')
        await this.loadDetail(this.detail.data.id)
        return
      }
      this.confirm.visible = false
      toast.success(action === 'RESOLVE' ? '反馈已办结' : '处理意见已提交')
      await this.loadDetail(this.detail.data.id)
    },
    async previewImage(file) {
      try { await fileSdk.preview(String(file.id)) } catch { toast.error('反馈图片暂时无法预览，请重试。') }
    },
    async downloadImage(file) {
      try { await fileSdk.download(String(file.id), file.name || '反馈图片') } catch { toast.error('反馈图片下载失败，请重试。') }
    }
  }
}
</script>

<style scoped>
.ifb-card{padding:16px;border:1px solid var(--border-light);border-radius:12px;background:var(--card);box-shadow:var(--shadow-xs)}.ifb-toolbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:14px}.ifb-count{margin-left:auto;color:var(--t3);font-size:12px}.ifb-cell{display:flex;flex-direction:column;gap:3px;min-width:0}.ifb-cell strong{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ifb-cell span{color:var(--t3);font-size:12px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.ifb-workspace{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:16px}.ifb-main{display:flex;flex-direction:column;gap:16px;min-width:0}.ifb-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin-bottom:14px}.ifb-head h2,.ifb-card h2{margin:0;font-size:16px}.ifb-head p{margin:5px 0 0;color:var(--t3);font-size:12px}.ifb-content{margin:12px 0 0;white-space:pre-wrap;word-break:break-word;line-height:1.75;color:var(--t1)}.ifb-actions{align-self:start;position:sticky;top:16px;display:flex;flex-direction:column;gap:10px}.ifb-muted{margin:0;color:var(--t3);font-size:12px;line-height:1.6}.ifb-result{margin-top:6px;padding:10px;border-radius:8px;background:var(--bg-soft);font-size:13px;line-height:1.6}.ifb-result p{margin:5px 0 0;white-space:pre-wrap}@media(max-width:980px){.ifb-workspace{grid-template-columns:1fr}.ifb-actions{position:static}}
</style>
