<template>
  <ModulePageShell title="请假审批" subtitle="学生实习期请假 · 指导教师审批 · 证明附件留痕"
    role-name="指导教师 / 管理员" :data-scope-name="scopeHint" :watermark="false">
    <template #actions>
      <AppExportButton :export-fn="exportFn" @exported="onExported">⬇ 导出 Excel 台账</AppExportButton>
    </template>

    <div class="mp-stack">
      <ModuleSummaryStrip :metrics="summaryMetrics" :note="summaryMetrics.length ? '' : '暂无统计口径'" />

      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名搜索" @search="reload" />
        <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
      </div>

      <DualPaneWorkspace aside-title="请假单" :aside-count="total">
        <!-- 左栏：请假单队列（紧凑列表，连续处理） -->
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">当前筛选下暂无请假单</div>
          <ul v-else class="lv-list">
            <li v-for="r in rows" :key="r.id">
              <button type="button" class="lv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                <div class="lv-item__row">
                  <span class="lv-item__name">{{ r.studentName }}</span>
                  <AppStatusTag :status="r.status" />
                </div>
                <div class="lv-item__sub">{{ r.studentNo }}<template v-if="r.advisorName"> · {{ r.advisorName }}</template></div>
                <div class="lv-item__sub">
                  {{ r.startDate }} ~ {{ r.endDate }}<template v-if="r.days"> · {{ r.days }} 天</template><template v-if="r.leaveTypeLabel"> · {{ r.leaveTypeLabel }}</template>
                </div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <AppPagination v-model:page="page" :page-size="pageSize" :total="total"
                        :show-total="false" :show-size-changer="false" :disabled="loading" @change="load" />
        </template>

        <!-- 右栏：当前请假单详情与审批操作 -->
        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="本页请假单已全部处理"
              description="可翻页或切换筛选条件，继续处理其他请假单" />
            <EmptyState v-else title="从左侧选择一条请假单开始处理"
              description="点击列表项查看详情，通过或驳回后自动跳到下一条待审批" />
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
                <AppStatusTag :status="detail.data.status" />
              </div>

              <div class="sec-t">学生与申请摘要</div>
              <AppDescriptionList :items="summaryItems" :columns="2" />

              <div class="sec-t">请假时间与原因</div>
              <AppDescriptionList :items="leaveItems" :columns="2" />

              <template v-if="detail.data.attachment">
                <div class="sec-t">证明附件</div>
                <AppFilePreview :files="attachmentFiles" @download="downloadAtt" />
              </template>

              <template v-if="hasReview">
                <div class="sec-t">审批结果</div>
                <AppDescriptionList :items="reviewItems" :columns="2" />
              </template>

              <div class="sec-t">审批留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无审批记录" />
            </div>

            <div v-if="detail.data.status === 'PENDING'" class="lv-foot">
              <AppPermissionButton code="internship.leave.review" :allowed="canBtn('internship.leave.review')" variant="ghost" :danger="true"
                @click="openReview(detail.data, 'REJECT')">驳回</AppPermissionButton>
              <AppPermissionButton code="internship.leave.review" :allowed="canBtn('internship.leave.review')" variant="secondary"
                @click="openReview(detail.data, 'APPROVE')">通过</AppPermissionButton>
            </div>
          </template>
        </section>
      </DualPaneWorkspace>
    </div>

    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      :reason-chips="cd.requireReason ? REJECT_LEAVE : []"
      reason-label="审批意见" :submitting="cd.submitting" @confirm="onConfirm" />
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList,
  AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppFilePreview, AppPagination } from '@/components/common'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import ModuleSummaryStrip from './components/ModuleSummaryStrip.vue'
import { leaveApi } from '@/modules/internship/api/leave-risk.api'
import { guidanceVisitApi } from '@/modules/internship/api/guidance-visit.api'
import { canCode } from '@/modules/internship/composables/permission'
import { toast } from '@/utils/toast'
import { REJECT_LEAVE } from '@/modules/internship/constants/presetPrompts'
import { useInternshipBatchStore } from '@/stores/internshipBatch'

const STATUS_OPTIONS = [
  { label: '待审批', value: 'PENDING' }, { label: '已通过', value: 'APPROVED' },
  { label: '已驳回', value: 'REJECTED' }, { label: '已撤回', value: 'WITHDRAWN' }
]
/* 右栏只渲染 /internship/leaves/{id} 真实返回字段（见 internship_leave_service._row + get_leave） */
const SUMMARY_FIELDS = [
  { key: 'studentName', label: '学生' }, { key: 'studentNo', label: '学号' },
  { key: 'advisorName', label: '指导教师' }, { key: 'applyBy', label: '申请人' },
  { key: 'createdAt', label: '申请时间' }
]
const LEAVE_FIELDS = [
  { key: 'leaveTypeLabel', label: '类型' }, { key: 'days', label: '天数' },
  { key: 'startDate', label: '开始日期' }, { key: 'endDate', label: '结束日期' },
  { key: 'reason', label: '请假事由' }
]
const REVIEW_FIELDS = [
  { key: 'reviewBy', label: '审批人' }, { key: 'reviewAt', label: '审批时间' },
  { key: 'reviewComment', label: '审批意见' }
]
const PANEL_PRESETS = {
  all: () => ({ statusFilter: '' }),
  pending: () => ({ statusFilter: 'PENDING' }),
  approved: () => ({ statusFilter: 'APPROVED' })
}

export default {
  name: 'LeaveReviewView',
  props: { ctx: { type: Object, default: () => ({}) } },
  components: { ModulePageShell, EmptyState, DualPaneWorkspace, ModuleSummaryStrip, AppStatusTag,
    AppConfirmDialog, AppExportButton, AppPermissionButton, AppDescriptionList, AppAuditTrail,
    AppSearchBox, AppQuickFilterChips, AppFilePreview, AppPagination },
  data() {
    return {
      REJECT_LEAVE,
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', statusOptions: STATUS_OPTIONS,
      selectedId: '', doneHint: false,
      detail: { loading: false, error: '', data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, submitting: false },
      pending: null,
      scopeHint: '指导教师仅本人指导学生；管理员全校'
    }
  },
  computed: {
    batchStore() { return useInternshipBatchStore() },
    summaryMetrics() {
      if (this.loading || this.error) return []
      const cur = this.statusOptions.find((o) => o.value === this.statusFilter)
      return [{ label: '请假单 · ' + (cur ? cur.label : '全部'), value: this.total,
        tone: this.statusFilter === 'PENDING' && this.total ? 'warn' : undefined }]
    },
    summaryItems() { const d = this.detail.data || {}; return SUMMARY_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    leaveItems() { const d = this.detail.data || {}; return LEAVE_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    reviewItems() { const d = this.detail.data || {}; return REVIEW_FIELDS.map((f) => ({ label: f.label, value: d[f.key] })) },
    // BUG-013：待审批单据不得展示审批人/时间——脏数据里 PENDING 也带审批人时会误导教师
    // 以为已经有人批过。只有终态（已通过/已驳回）才渲染审批结论区。
    hasReview() {
      const d = this.detail.data || {}
      if (!['APPROVED', 'REJECTED'].includes(d.status)) return false
      return !!(d.reviewBy || d.reviewAt || d.reviewComment)
    },
    attachmentFiles() { const a = this.detail.data?.attachment; return a ? [{ id: a.fileId, name: a.fileName, sensitive: true }] : [] },
    auditRecords() {
      return (this.detail.data?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail && (t.detail.comment || ''), at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.query.panel': {
      immediate: true,
      handler(panel) {
        this.applyPanel((panel || 'pending').toString())
      }
    },
    '$route.query.id': {
      immediate: true,
      handler(id) {
        const sid = (id || '').toString()
        if (sid === this.selectedId) return
        this.selectedId = sid
        if (sid) { this.doneHint = false; this.loadDetail(sid) } else { this.detail = { loading: false, error: '', data: null } }
      }
    },
    'batchStore.selectedBatchId'() {
      this.page = 1
      this.clearSelection()
      this.load()
    }
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    applyPanel(panel) {
      const preset = PANEL_PRESETS[panel] || PANEL_PRESETS.pending
      this.statusFilter = preset().statusFilter
      this.keyword = ''
      this.page = 1
      this.load()
    },
    exportFn() {
      if (!this.batchStore.selectedBatchId) return Promise.resolve({ code: 1, message: '请先选择批次' })
      return leaveApi.exportLeaves({ keyword: this.keyword, status: this.statusFilter, batchId: this.batchStore.selectedBatchId })
    },
    onExported(data) { toast.success(`已导出 ${data.rowCount} 条（水印 + 导出留痕）`) },
    reload() { this.page = 1; this.load() },
    async load() {
      if (!this.batchStore.selectedBatchId) {
        this.loading = false; this.error = '请先选择批次'; this.rows = []; this.total = 0
        return
      }
      this.loading = true; this.error = ''
      const params = { page: this.page, pageSize: this.pageSize, keyword: this.keyword, batchId: this.batchStore.selectedBatchId }
      if (this.statusFilter) params.status = this.statusFilter
      const res = await leaveApi.getLeaves(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
      // 处理完当前页最后一条后翻页越界（如筛选=待审批时该页清空）：自动回到最后一个有效页
      const pc = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (!this.rows.length && this.total > 0 && this.page > pc) { this.page = pc; return this.load() }
    },
    select(id) {
      const sid = String(id)
      this.doneHint = false
      if (String(this.$route.query.id || '') === sid) {
        if (this.selectedId !== sid) { this.selectedId = sid; this.loadDetail(sid) }
        return
      }
      this.$router.replace({ query: this.batchStore.withBatchQuery({ ...this.$route.query, id: sid }) })
    },
    clearSelection() {
      const query = { ...this.$route.query }
      delete query.id
      this.$router.replace({ query: this.batchStore.withBatchQuery(query) })
    },
    async loadDetail(id) {
      this.detail = { loading: true, error: '', data: null }
      const res = await leaveApi.getLeaveDetail(id)
      if (String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
    },
    async downloadAtt() {
      const a = this.detail.data?.attachment
      if (!a) return
      try { await guidanceVisitApi.downloadAttachment(a.fileId, a.fileName) } catch (e) { toast.error('下载失败：' + (e.message || '')) }
    },
    openReview(r, action) {
      this.pending = { id: r.id, action, expectedVersion: r.version }
      const ap = action === 'APPROVE'
      this.cd = { visible: true, title: ap ? '请假 · 通过' : '请假 · 驳回',
        content: `${ap ? '通过' : '驳回'}「${r.studentName}」${r.startDate}~${r.endDate} 的请假，意见将写入审计。`,
        danger: !ap, confirmText: ap ? '通过' : '驳回', requireReason: !ap, submitting: false }
    },
    async onConfirm({ reason }) {
      this.cd.submitting = true
      const res = await leaveApi.review(this.pending.id, {
        action: this.pending.action, comment: reason || '',
        expectedVersion: this.pending.expectedVersion
      })
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false; toast.success('审批完成，已写审计')
      await this.advanceAfterReview(this.pending.id)
    },
    /** 动作成功后：刷新当前页并自动选中下一条待审批；无下一条则清空选中并提示本页已处理完 */
    async advanceAfterReview(oldId) {
      const oldIndex = Math.max(0, this.rows.findIndex((r) => String(r.id) === String(oldId)))
      await this.load()
      let after = null, before = null
      this.rows.forEach((r, i) => {
        if (r.status !== 'PENDING' || String(r.id) === String(oldId)) return
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
</style>
