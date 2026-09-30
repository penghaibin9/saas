<template>
  <ModulePageShell title="企业评价" subtitle="核对企业评分与扫描件，由授权审核人确认评价结果。"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppButton variant="ghost" @click="goStudentEvals">学生自评与教师评价</AppButton>
      <AppButton variant="ghost" @click="goScores">综合成绩</AppButton>
      <AppPermissionButton code="internship.eval.enterprise.manage" :allowed="canBtn('internship.eval.enterprise.manage')" variant="primary"
        @click="goCreate">录入企业评价</AppPermissionButton>
      <AppExportButton :export-fn="exportFn" :has-permission="canBtn('internship.eval.enterprise.export')" @exported="onExported">导出评价台账</AppExportButton>
    </template>

    <div class="mp-stack">
      <ActionReceipt :receipt="lastReceipt" @close="lastReceipt = null" />

      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
      </div>

      <DualPaneWorkspace aside-title="企业评价" :aside-count="total">
        <!-- 左栏：企业评价队列（紧凑列表，连续审核） -->
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">当前筛选下暂无企业评价记录</div>
          <ul v-else class="lv-list">
            <li v-for="r in rows" :key="r.id">
              <button type="button" class="lv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                <div class="lv-item__row">
                  <span class="lv-item__name">{{ r.studentName }}</span>
                  <AppStatusTag :type="reviewTone(r.reviewStatus)">{{ r.reviewStatusLabel }}</AppStatusTag>
                </div>
                <div class="lv-item__sub">{{ r.studentNo }}<template v-if="r.mentorName"> · 企业导师 {{ r.mentorName }}</template></div>
                <div class="lv-item__sub">
                  均分 {{ r.avgScore }} · {{ r.sourceLabel }}<template v-if="r.recommendHire"> · 建议录用</template>
                </div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <AppPagination :page="page" :page-size="pageSize" :total="total"
                        :show-size-changer="false" :disabled="loading" @change="onPageChange" />
        </template>

        <!-- 右栏：当前企业评价详情与审核操作 -->
        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="已处理到当前列表末尾"
              description="可翻页或调整筛选，核对其他评价"><template #actions><AppButton variant="ghost" @click="load">刷新列表</AppButton></template></EmptyState>
            <EmptyState v-else title="选择一条企业评价"
              description="在此核对评分、材料与审核结果"><template #actions><AppButton variant="ghost" @click="load">刷新列表</AppButton></template></EmptyState>
          </template>
          <div v-else-if="detail.loading" class="state lv-main__state">详情加载中…</div>
          <div v-else-if="detail.error" class="state is-err lv-main__state">
            {{ detail.error }} <button type="button" class="mp-link" @click="loadDetail(selectedId)">重试</button>
          </div>
          <template v-else-if="detail.data">
            <div class="lv-main__body">
              <div class="lv-head">
                <span class="lv-head__name">{{ detail.data.studentName }}</span>
                <span class="mp-note">{{ detail.data.studentNo }}</span>
                <AppStatusTag :type="reviewTone(detail.data.reviewStatus)">{{ detail.data.reviewStatusLabel }}</AppStatusTag>
              </div>

              <div class="sec-t">学生与企业岗位摘要</div>
              <AppDescriptionList :items="summaryItems" :columns="2" />

              <h2 class="sec-t">五维评分</h2>
              <dl class="score-grid"><div v-for="item in scoreItems" :key="item.label" class="score-item" :class="{ 'is-average': item.label === '均分' }"><dt>{{ item.label }}</dt><dd>{{ item.value ?? '—' }}<small v-if="item.value != null">分</small></dd></div></dl>

              <div class="sec-t">评语与建议</div>
              <AppDescriptionList :items="commentItems" :columns="1" />

              <template v-if="detail.data.attachment">
                <div class="sec-t">评价扫描件</div>
                <AppButton variant="secondary" :loading="downloading" @click="downloadAtt">下载评价扫描件</AppButton>
                <span class="mp-note">{{ detail.data.attachment.fileName }}</span>
                <p v-if="attachmentError" class="attachment-error" role="alert">{{ attachmentError }}</p>
              </template>

              <template v-if="hasReviewResult">
                <div class="sec-t">审核结果</div>
                <AppDescriptionList :items="reviewItems" :columns="2" />
              </template>

              <div class="sec-t">审核留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
            </div>

            <div v-if="detail.data.reviewStatus === 'PENDING'" class="lv-foot">
              <span class="mp-note lv-foot__hint">录入人与审核人须分离</span>
              <AppPermissionButton code="internship.eval.enterprise.review" :allowed="canBtn('internship.eval.enterprise.review')" variant="secondary" :disabled="cd.submitting"
                @click="openReview(detail.data, 'RETURN')">退回</AppPermissionButton>
              <AppPermissionButton code="internship.eval.enterprise.review" :allowed="canBtn('internship.eval.enterprise.review')" variant="primary" :disabled="cd.submitting"
                @click="openReview(detail.data, 'APPROVE')">通过</AppPermissionButton>
            </div>
          </template>
        </section>
      </DualPaneWorkspace>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      :reason-label="cd.requireReason ? '退回原因（至少 5 字）' : '审核意见'" :submitting="cd.submitting" :confirm-disabled="conflict.active" @confirm="onConfirm">
      <AppInlineAlert v-if="conflict.active" type="warning" title="评价已更新，本次审核已暂停" description="意见已保留。请取消后核对最新详情，再重新选择可用操作。">
        <p v-if="conflict.stale">最新详情暂时无法读取，请关闭后重试加载。</p>
        <AppDescriptionList v-else :items="conflict.latest" :columns="1" />
      </AppInlineAlert>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppPagination, AppInlineAlert } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ActionReceipt from './components/ActionReceipt.vue'
import { enterpriseEvalApi, downloadAttachment } from '@/modules/internship/api/enterprise-eval.api'
import { emptyConflict, isConflict, captureConflict } from '@/modules/internship/composables/conflictGuard'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const STATUS_OPTIONS = [{ label: '待审核', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' }, { label: '已退回', value: 'RETURNED' }]
/* 右栏只渲染 /internship/enterprise-evals/{id} 真实返回字段（见 internship_enterprise_eval_service._row + get_eval） */
const SUMMARY_FIELDS = [
  { key: 'advisorName', label: '指导教师' }, { key: 'mentorName', label: '企业导师' },
  { key: 'positionName', label: '岗位' }, { key: 'sourceLabel', label: '来源' },
  { key: 'createdAt', label: '录入时间' }, { key: 'recordedByName', label: '录入人' }
]
const SCORE_FIELDS = [
  { key: 'attendanceScore', label: '出勤' }, { key: 'skillScore', label: '技能' },
  { key: 'attitudeScore', label: '态度' }, { key: 'collaborationScore', label: '协作' },
  { key: 'safetyScore', label: '安全纪律' }, { key: 'avgScore', label: '均分' }
]
const COMMENT_FIELDS = [
  { key: 'overallComment', label: '综合评语' }, { key: 'recommendHire', label: '建议录用', bool: true }
]
const REVIEW_FIELDS = [
  { key: 'reviewStatusLabel', label: '审核状态' }, { key: 'reviewedByName', label: '审核人' }, { key: 'reviewComment', label: '审核意见' }
]

export default {
  name: 'EnterpriseEvalView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, EmptyState, DualPaneWorkspace, AppButton,
    AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
    AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppPagination, ActionReceipt, AppInlineAlert },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '', listSequence: 0,
      keyword: '', statusFilter: 'PENDING', statusOptions: STATUS_OPTIONS,
      selectedId: '', doneHint: false,
      detail: { loading: false, error: '', data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null, conflict: emptyConflict(), downloading: false, attachmentError: '',
      lastReceipt: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    summaryItems() { const d = this.detail.data || {}; return SUMMARY_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    scoreItems() { const d = this.detail.data || {}; return SCORE_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    commentItems() { const d = this.detail.data || {}; return COMMENT_FIELDS.map((f) => ({ label: f.label, value: f.bool ? (d[f.key] ? '是' : '否') : d[f.key] })) },
    reviewItems() { const d = this.detail.data || {}; return REVIEW_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    hasReviewResult() { const d = this.detail.data || {}; return !!d.reviewStatus && d.reviewStatus !== 'PENDING' },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.comment || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query': {
      deep: true,
      immediate: true,
      handler(query, previous) {
        if (!previous || ['keyword', 'reviewStatus', 'page', 'batchId'].some(key => Object.hasOwn(query, key) !== Object.hasOwn(previous, key) || String(query[key] ?? '') !== String(previous[key] ?? ''))) this.applyQuery()
        const sid = String(query.id || '')
        if (sid === this.selectedId) return
        this.resetDetail()
        this.selectedId = sid
        if (sid) { this.doneHint = false; this.loadDetail(sid) } else { this.detail = { loading: false, error: '', data: null } }
      }
    },
    'batchStore.selectedBatchId'() {
      this.page = 1
      this.lastReceipt = null
      this.clearSelection()
      this.load()
    }
  },
  beforeUnmount() { this.listSequence++; this.resetDetail() },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    reviewTone(s) { return s === 'APPROVED' ? 'success' : s === 'RETURNED' ? 'danger' : 'warning' },
    goStudentEvals() { this.$router.push({ path: '/admin/internship/student-evals', query: this.batchStore.withBatchQuery() }) },
    goScores() { this.$router.push({ path: '/admin/internship/scores', query: this.batchStore.withBatchQuery() }) },
    goCreate() { if (this.canBtn('internship.eval.enterprise.manage')) this.$router.push({ path: '/admin/internship/enterprise-evals/new', query: this.batchStore.withBatchQuery() }) },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      return enterpriseEvalApi.exportEvals({ keyword: this.keyword, reviewStatus: this.statusFilter, batchId: this.batchStore.selectedBatchId })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    applyQuery() {
      const q = this.$route.query || {}
      this.keyword = String(q.keyword || '')
      this.statusFilter = q.reviewStatus != null ? String(q.reviewStatus) : 'PENDING'
      this.page = Math.max(1, Number.parseInt(q.page, 10) || 1)
      this.doneHint = false; this.load()
    },
    syncQuery() {
      const query = this.batchStore.withBatchQuery({ ...this.$route.query, keyword: this.keyword, reviewStatus: this.statusFilter, page: String(this.page) })
      if (Object.keys(query).every(key => Object.hasOwn(this.$route.query, key) && String(query[key]) === String(this.$route.query[key]))) this.load()
      else this.$router.replace({ query })
    },
    reload() { this.page = 1; this.doneHint = false; this.syncQuery() },
    onPageChange({ page }) { this.page = page; this.syncQuery() },
    async load() {
      const sequence = ++this.listSequence
      const batchId = this.batchStore.selectedBatchId
      this.rows = []; this.total = 0
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.total = 0
        return
      }
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
      if (this.statusFilter) params.reviewStatus = this.statusFilter
      const res = await enterpriseEvalApi.getEvals(params)
      if (sequence !== this.listSequence || batchId !== this.batchStore.selectedBatchId) return
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
      // 处理完当前页最后一条后翻页越界（如筛选=待审核时该页清空）：自动回到最后一个有效页
      const pc = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (!this.rows.length && this.total > 0 && this.page > pc) { this.page = pc; this.syncQuery(); return false }
      return true
    },
    select(id) {
      if (id == null || id === '') return
      const sid = String(id)
      this.doneHint = false
      if (this.selectedId === sid) return
      this.resetDetail(); this.selectedId = sid; this.loadDetail(sid)
      this.$router.replace({ query: this.batchStore.withBatchQuery({ ...this.$route.query, id: sid, page: String(this.page) }) })
    },
    resetDetail() {
      this.detail = { loading: false, error: '', data: null }
      this.pending = null; this.cd = { ...this.cd, visible: false, submitting: false }; this.conflict = emptyConflict()
      this.downloading = false; this.attachmentError = ''
    },
    clearSelection() {
      this.resetDetail(); this.selectedId = ''
      const query = { ...this.$route.query, page: String(this.page) }
      delete query.id
      this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
    },
    async loadDetail(id) {
      if (!id || !this.batchStore.selectedBatchId) return
      const batchId = this.batchStore.selectedBatchId
      this.downloading = false; this.attachmentError = ''
      this.detail = { loading: true, error: '', data: null }
      const workspace = this.detail
      const res = await enterpriseEvalApi.getDetail(id)
      if (workspace !== this.detail || batchId !== this.batchStore.selectedBatchId || String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
    },
    async downloadAtt() {
      const workspace = this.detail
      const a = workspace.data?.attachment
      if (!a?.fileId || this.downloading || workspace.loading || workspace.error) return
      this.downloading = true; this.attachmentError = ''
      try { await downloadAttachment(String(a.fileId), a.fileName) }
      catch (e) { if (this.detail === workspace) this.attachmentError = e.message || '材料下载失败，请重试' }
      finally { if (this.detail === workspace) this.downloading = false }
    },
    openReview(r, action) {
      if (!r || this.detail.loading || this.detail.error || this.cd.submitting || !this.canBtn('internship.eval.enterprise.review') || r.reviewStatus !== 'PENDING' || String(r.id) !== this.selectedId || !['APPROVE', 'RETURN'].includes(action)) return
      const ap = action === 'APPROVE'
      this.conflict = emptyConflict()
      this.pending = { id: r.id, action, version: r.version, studentName: r.studentName }
      this.cd = { visible: true, title: ap ? '企业评价 · 通过' : '企业评价 · 退回',
        content: `${ap ? '通过' : '退回'}「${r.studentName}」的企业评价，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '退回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      const pending = this.pending
      if (!pending || this.cd.submitting || this.conflict.active || !this.canBtn('internship.eval.enterprise.review') || this.detail.loading || this.detail.error || this.detail.data?.reviewStatus !== 'PENDING' || String(pending.id) !== this.selectedId) return
      if (pending.action === 'RETURN' && String(reason || '').trim().length < 5) return toast.error('退回原因至少填写 5 字')
      const dialog = this.cd, batchId = this.batchStore.selectedBatchId
      dialog.submitting = true
      const res = await enterpriseEvalApi.review(pending.id, { action: pending.action,
        comment: reason || '', expectedVersion: pending.version })
      if (this.cd === dialog) dialog.submitting = false
      if (this.pending !== pending || this.cd !== dialog || batchId !== this.batchStore.selectedBatchId || String(pending.id) !== this.selectedId) return
      if (res.code !== 0) {
        if (isConflict(res)) {
          this.conflict = { ...emptyConflict(), active: true, kept: reason || '' }
          const conflict = await captureConflict({ res, kept: reason || '', refresh: async () => {
            await this.loadDetail(pending.id)
            if (this.detail.error || !this.detail.data) throw new Error('最新评价加载失败')
          }, latest: () => [{ label: '审核状态', value: this.detail.data?.reviewStatusLabel }, { label: '审核意见', value: this.detail.data?.reviewComment || '—' }] })
          if (this.pending === pending && this.cd === dialog) this.conflict = conflict
          return
        }
        return toast.error(res.message || '操作失败')
      }
      this.detail.data = { ...this.detail.data, ...res.data }
      this.lastReceipt = { actionLabel: pending.action === 'APPROVE' ? '企业评价已通过' : '企业评价已退回',
        objectLabel: pending.studentName, id: res.data.id, version: res.data.version,
        statusLabel: res.data.reviewStatusLabel || res.data.reviewStatus,
        auditText: '评价审核结果已保存', nextStep: pending.action === 'APPROVE' ? '可继续核对综合成绩' : '等待原录入人按意见修改重交' }
      this.cd.visible = false; toast.success('审核完成，已写审计')
      await this.advanceAfterReview(pending.id)
    },
    /** 审核成功后：刷新当前页并自动选中下一条待审核；无下一条则清空选中并提示已处理完 */
    async advanceAfterReview(oldId) {
      const batchId = this.batchStore.selectedBatchId, route = this.$route.fullPath
      const oldIndex = Math.max(0, this.rows.findIndex((r) => String(r.id) === String(oldId)))
      const loaded = await this.load()
      if (!loaded || this.error || batchId !== this.batchStore.selectedBatchId || route !== this.$route.fullPath || String(oldId) !== this.selectedId) return
      let after = null, before = null
      this.rows.forEach((r, i) => {
        if (r.reviewStatus !== 'PENDING' || String(r.id) === String(oldId)) return
        if (i >= oldIndex) { if (!after) after = r } else if (!before) before = r
      })
      const next = after || before
      if (next) { this.select(next.id); return }
      this.clearSelection()
      this.doneHint = true
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';

.bar { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; }
.state { padding: var(--space-6); text-align: center; color: var(--text-tertiary); font-size: var(--font-size-sm); border: 1px dashed var(--border-base); border-radius: var(--radius-base); margin: var(--space-3); }
.state.is-err { color: var(--danger-600); }
.sec-t { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-secondary); margin: var(--space-4) 0 var(--space-2); }

/* 左栏紧凑列表 */
.lv-list { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); }
.lv-item { display: block; width: 100%; text-align: left; font: inherit; cursor: pointer; background: transparent; border: 1px solid transparent; border-radius: var(--radius-md, 8px); padding: var(--space-2) var(--space-3); transition: background 0.12s ease, border-color 0.12s ease; }
.lv-item:hover { background: var(--primary-50, #eff6ff); }
.lv-item.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-600, #2563eb); }
.lv-item__row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.lv-item__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.lv-item__sub { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }

/* 右栏详情与固定操作区 */
.lv-main { display: flex; flex-direction: column; min-height: 320px; }
.lv-main__body { flex: 1; padding: var(--space-4); min-width: 0; }
.lv-main__state { margin: var(--space-4); }
.lv-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.lv-head__name { font-size: var(--font-size-md, 15px); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.lv-foot { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); background: var(--bg-card, #fff); border-radius: 0 0 var(--r, 12px) var(--r, 12px); }
.score-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; margin: 0; border: 1px solid var(--border-light); border-radius: 10px; overflow: hidden; background: var(--border-light); }
.score-item { background: var(--bg-card, #fff); padding: 12px 16px; }
.score-item dt { font-size: var(--font-size-xs); color: var(--text-secondary); }
.score-item dd { margin: 6px 0 0; font-size: 24px; font-weight: 600; font-variant-numeric: tabular-nums; }
.score-item small { font-size: 12px; font-weight: 400; margin-left: 6px; }
.score-item.is-average { background: var(--primary-50, #eff6ff); color: var(--primary-700); }
.lv-foot { align-items: center; flex-wrap: wrap; }
.lv-foot__hint { margin-right: auto; }
.lv-item:focus-visible { outline: 2px solid var(--primary-600); outline-offset: 2px; }
.attachment-error { color: var(--danger-600); font-size: var(--font-size-sm); }
@media (max-width: 600px) { .score-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }.lv-foot__hint { width: 100%; } }
</style>
