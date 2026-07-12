<template>
  <ModulePageShell title="延期销假" subtitle="请假通过后的后续处理 · 续假审批 · 销假确认 · 逾期处置（连续处理双栏）"
    :role-name="roleName" :data-scope-name="scopeHint">
    <template #actions>
      <AppButton variant="ghost" size="sm" :loading="scanning" @click="onScan">扫描逾期未销</AppButton>
    </template>

    <div class="mp-stack">
      <div class="bar">
        <AppSearchBox v-model="keyword" placeholder="按学生姓名 / 学号搜索" @search="reload" />
        <AppQuickFilterChips v-model="statusFilter" :options="statusOptions" allow-clear @change="reload" />
      </div>

      <DualPaneWorkspace aside-title="后续处理队列" :aside-count="total">
        <template #aside>
          <div v-if="loading" class="state">加载中…</div>
          <div v-else-if="error" class="state is-err">{{ error }} <button type="button" class="mp-link" @click="load">重试</button></div>
          <div v-else-if="!rows.length" class="state">当前筛选下暂无待处理请假</div>
          <ul v-else class="lv-list">
            <li v-for="r in rows" :key="r.id">
              <button type="button" class="lv-item" :class="{ 'is-active': String(r.id) === selectedId }" @click="select(r.id)">
                <div class="lv-item__row">
                  <span class="lv-item__name">{{ r.studentName }}</span>
                  <AppStatusTag :status="r.affairsStatus" :label="r.affairsStatusLabel" />
                </div>
                <div class="lv-item__sub">{{ r.studentNo }} · {{ r.className }}</div>
                <div class="lv-item__sub">{{ fmt(r.startTime) }} ~ {{ fmt(r.endTime) }} · {{ r.leaveTypeLabel }} · {{ r.days }}天</div>
              </button>
            </li>
          </ul>
        </template>
        <template #aside-foot>
          <div class="lv-pager">
            <button type="button" class="mp-link" :disabled="page <= 1 || loading" @click="onPageChange(page - 1)">上一页</button>
            <span class="mp-note">第 {{ page }} / 共 {{ pageCount }} 页</span>
            <button type="button" class="mp-link" :disabled="page >= pageCount || loading" @click="onPageChange(page + 1)">下一页</button>
          </div>
        </template>

        <section class="mp-card lv-main">
          <template v-if="!selectedId">
            <EmptyState v-if="doneHint" title="本页请假已全部处理"
              description="可翻页或切换筛选条件，继续处理其他请假" />
            <EmptyState v-else title="从左侧选择一条请假开始处理"
              description="续假审批 / 销假确认 / 逾期处置，处理后自动跳到下一条" />
          </template>
          <div v-else-if="detail.loading" class="state lv-main__state">详情加载中…</div>
          <div v-else-if="detail.error" class="state is-err lv-main__state">
            {{ detail.error }} <button type="button" class="mp-link" @click="loadDetail(selectedId)">重试</button>
          </div>
          <template v-else-if="detail.data">
            <div class="lv-main__body">
              <div class="lv-head">
                <span class="lv-head__name">{{ detail.data.studentName }}</span>
                <span class="mp-note">{{ detail.data.studentNo }} · {{ detail.data.className }}</span>
                <AppStatusTag :status="detail.data.affairsStatus" :label="detail.data.affairsStatusLabel" />
              </div>

              <div class="sec-t">请假信息</div>
              <AppDescriptionList :items="leaveItems" :columns="2" />

              <template v-if="detail.data.extensions && detail.data.extensions.length">
                <div class="sec-t">续假记录</div>
                <ul class="rec-list">
                  <li v-for="e in detail.data.extensions" :key="e.id">
                    <AppStatusTag :status="e.status" :label="extLabel(e.status)" />
                    {{ fmt(e.oldEndTime) }} → {{ fmt(e.newEndTime) }}（+{{ e.extendDays }}天）
                    <span v-if="e.reason" class="mp-note"> · {{ e.reason }}</span>
                  </li>
                </ul>
              </template>

              <template v-if="detail.data.cancelRecords && detail.data.cancelRecords.length">
                <div class="sec-t">销假记录</div>
                <ul class="rec-list">
                  <li v-for="c in detail.data.cancelRecords" :key="c.id">
                    <AppStatusTag :status="c.status" :label="cancelLabel(c.status)" />
                    实际返校 {{ fmt(c.actualReturnAt) }}
                    <span v-if="c.confirmBy" class="mp-note"> · {{ c.confirmBy }} {{ fmt(c.confirmAt) }}</span>
                    <span v-if="c.confirmNote" class="mp-note"> · {{ c.confirmNote }}</span>
                  </li>
                </ul>
              </template>

              <div class="sec-t">审批留痕</div>
              <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无处理记录" />
            </div>

            <div v-if="actions.length" class="lv-foot">
              <AppPermissionButton v-for="a in actions" :key="a.key" :code="a.code" :variant="a.variant"
                :danger="a.danger" @click="openAction(a)">{{ a.label }}</AppPermissionButton>
            </div>
          </template>
        </section>
      </DualPaneWorkspace>
    </div>

    <!-- 简单确认（续假通过 / 驳回 / 销假退回：仅原因） -->
    <AppConfirmDialog v-model:visible="cd.visible" :title="cd.title" :content="cd.content"
      :danger="cd.danger" :confirm-text="cd.confirmText" :require-reason="cd.requireReason"
      reason-label="意见" :reason-placeholder="cd.reasonPlaceholder" :submitting="cd.submitting"
      @confirm="onConfirmSimple" />

    <!-- 表单动作弹窗（代登记销假 / 发起续假 / 逾期处置 / 销假确认） -->
    <div v-if="fm.visible" class="fm-mask" @click.self="closeForm">
      <div class="fm-dialog">
        <div class="fm-title">{{ fm.title }}</div>
        <div class="fm-body">
          <template v-for="f in fm.fields" :key="f.key">
            <div class="fm-item">
              <label class="fm-label">{{ f.label }}<i v-if="f.required">*</i></label>
              <AppDateTimePicker v-if="f.type === 'datetime'" v-model="fm.values[f.key]" :max="f.max || ''" />
              <AppSelect v-else-if="f.type === 'select'" v-model="fm.values[f.key]" :options="f.options" :placeholder="f.placeholder || '请选择'" />
              <AppTextarea v-else v-model="fm.values[f.key]" :placeholder="f.placeholder || ''" :rows="3" :maxlength="f.max || 500" show-count />
            </div>
          </template>
          <p v-if="fm.err" class="fm-err">{{ fm.err }}</p>
        </div>
        <div class="fm-foot">
          <AppButton variant="ghost" @click="closeForm">取消</AppButton>
          <AppButton :variant="fm.danger ? 'danger' : 'primary'" :loading="fm.submitting" @click="submitForm">{{ fm.confirmText }}</AppButton>
        </div>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 延期销假连续处理工作站（/admin/campus-service/leave-extensions）。
 * 覆盖 13A-05 状态机 §1 请假审批终态后分支：APPROVED/OVERDUE → 代登记销假/发起续假/逾期处置；
 * EXTENSION_REVIEW → 续假通过/驳回；WAIT_CANCEL_LEAVE → 销假确认/退回。真实对接 /student-affairs/leave/*。
 */
import { ModulePageShell, EmptyState } from '@/components/business'
import {
  AppStatusTag, AppConfirmDialog, AppPermissionButton, AppDescriptionList, AppAuditTrail,
  AppSearchBox, AppQuickFilterChips, AppDateTimePicker, AppSelect, AppTextarea
} from '@/components/common'
import { AppButton } from '@/components/ui'
import DualPaneWorkspace from './components/DualPaneWorkspace.vue'
import { leaveApi } from '@/modules/studentAffairs/api/leave.api'
import { toast } from '@/utils/toast'
import { formatDateTime } from '@/utils/dateUtils'

const STATUS_OPTIONS = [
  { label: '待续假审批', value: 'EXTENSION_REVIEW' },
  { label: '待销假确认', value: 'WAIT_CANCEL_LEAVE' },
  { label: '逾期未销', value: 'OVERDUE' },
  { label: '已通过', value: 'APPROVED' }
]
const EXT_LABEL = { SUBMITTED: '审批中', APPROVED: '已通过', REJECTED: '已驳回', CANCELLED: '已取消' }
const CANCEL_LABEL = { SUBMITTED: '待确认', CONFIRMED: '已销假', RETURNED: '已退回' }

export default {
  name: 'LeaveExtensionCancelView',
  components: {
    ModulePageShell, EmptyState, DualPaneWorkspace, AppStatusTag, AppConfirmDialog, AppPermissionButton,
    AppDescriptionList, AppAuditTrail, AppSearchBox, AppQuickFilterChips, AppDateTimePicker, AppSelect,
    AppTextarea, AppButton
  },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      rows: [], total: 0, page: 1, pageSize: 20, loading: false, error: '',
      keyword: '', statusFilter: '', statusOptions: STATUS_OPTIONS,
      selectedId: '', doneHint: false, scanning: false,
      detail: { loading: false, error: '', data: null },
      cd: { visible: false, title: '', content: '', danger: false, confirmText: '确认', requireReason: false, reasonPlaceholder: '', submitting: false, submit: null },
      fm: { visible: false, title: '', confirmText: '', danger: false, submitting: false, err: '', fields: [], values: {}, submit: null }
    }
  },
  computed: {
    roleName() { return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || '辅导员 / 学院学工 / 学工处' },
    scopeHint() { return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.name) || '按数据范围：辅导员本班 / 学院本院 / 学工处全校' },
    pageCount() { return Math.max(1, Math.ceil(this.total / this.pageSize)) },
    leaveItems() {
      const d = this.detail.data || {}
      return [
        { label: '请假类型', value: d.leaveTypeLabel },
        { label: '天数', value: d.days },
        { label: '开始时间', value: this.fmt(d.startTime) },
        { label: '结束时间', value: this.fmt(d.endTime) },
        { label: '应返校时间', value: this.fmt(d.expectedReturnAt) },
        { label: '实际返校时间', value: this.fmt(d.actualReturnAt) || '—' },
        { label: '请假事由', value: d.reason || '—' }
      ]
    },
    auditRecords() {
      return (this.detail.data && this.detail.data.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, reason: t.detail, at: t.occurredAt
      }))
    },
    actions() {
      const s = this.detail.data && this.detail.data.affairsStatus
      if (s === 'EXTENSION_REVIEW') {
        return [
          { key: 'extApprove', label: '续假通过', code: 'studentAffairs.leave.extension.approve', variant: 'secondary' },
          { key: 'extReject', label: '续假驳回', code: 'studentAffairs.leave.extension.approve', variant: 'ghost', danger: true }
        ]
      }
      if (s === 'WAIT_CANCEL_LEAVE') {
        return [
          { key: 'cancelConfirm', label: '销假确认', code: 'studentAffairs.leave.cancelLeaveConfirm', variant: 'secondary' },
          { key: 'cancelReturn', label: '销假退回', code: 'studentAffairs.leave.cancelLeaveConfirm', variant: 'ghost', danger: true }
        ]
      }
      if (s === 'OVERDUE') {
        return [
          { key: 'overdueHandle', label: '逾期处置', code: 'studentAffairs.leave.overdue.handle', variant: 'secondary' },
          { key: 'proxyCancel', label: '补登记销假', code: 'studentAffairs.leave.cancelLeaveConfirm', variant: 'ghost' }
        ]
      }
      if (s === 'APPROVED') {
        return [
          { key: 'proxyCancel', label: '代登记销假', code: 'studentAffairs.leave.cancelLeaveConfirm', variant: 'secondary' },
          { key: 'applyExtension', label: '发起续假', code: 'studentAffairs.leave.create', variant: 'ghost' }
        ]
      }
      return []
    },
    nowLocal() {
      const d = new Date()
      const p = (n) => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
    }
  },
  created() {
    if (this.$route.query.status) this.statusFilter = String(this.$route.query.status)
    this.load()
  },
  methods: {
    fmt(v) { return v ? formatDateTime(v) : '' },
    extLabel(v) { return EXT_LABEL[v] || v },
    cancelLabel(v) { return CANCEL_LABEL[v] || v },
    reload() { this.page = 1; this.load() },
    onPageChange(p) { if (p < 1 || p > this.pageCount || p === this.page) return; this.page = p; this.load() },
    async load() {
      this.loading = true; this.error = ''
      const params = { followupOnly: true, page: this.page, pageSize: this.pageSize }
      if (this.keyword) params.keyword = this.keyword
      if (this.statusFilter) params.status = this.statusFilter
      const res = await leaveApi.ledger(params)
      this.loading = false
      if (res.code !== 0) { this.error = res.message || '加载失败'; this.rows = []; this.total = 0; return }
      this.rows = res.data.list; this.total = res.data.total
      const pc = Math.max(1, Math.ceil(this.total / this.pageSize))
      if (!this.rows.length && this.total > 0 && this.page > pc) { this.page = pc; return this.load() }
    },
    select(id) {
      const sid = String(id)
      this.doneHint = false
      if (this.selectedId === sid) return
      this.selectedId = sid
      this.loadDetail(sid)
    },
    async loadDetail(id) {
      this.detail = { loading: true, error: '', data: null }
      const res = await leaveApi.detail(id)
      if (String(this.selectedId) !== String(id)) return
      this.detail.loading = false
      if (res.code !== 0) { this.detail.error = res.message || '详情加载失败'; return }
      this.detail.data = res.data
    },
    openAction(a) {
      const id = this.detail.data.id
      if (a.key === 'extApprove') {
        this.cd = { visible: true, title: '续假通过', content: '通过续假后将更新请假结束时间与到期提醒。', danger: false, confirmText: '通过续假', requireReason: false, reasonPlaceholder: '', submitting: false, submit: () => leaveApi.extensionReview(id, { action: 'APPROVE' }) }
        return
      }
      if (a.key === 'extReject') {
        this.cd = { visible: true, title: '续假驳回', content: '驳回后维持原假期与原到期日。', danger: true, confirmText: '驳回续假', requireReason: true, reasonPlaceholder: '请填写驳回原因（不少于 5 字）', submitting: false, submit: (r) => leaveApi.extensionReview(id, { action: 'REJECT', reason: r }) }
        return
      }
      if (a.key === 'cancelReturn') {
        this.cd = { visible: true, title: '销假退回', content: '退回后请假回到「已通过」，学生可重新销假。', danger: true, confirmText: '退回重办', requireReason: true, reasonPlaceholder: '请说明退回原因（如返校证明不符，不少于 5 字）', submitting: false, submit: (r) => leaveApi.cancelConfirm(id, { action: 'RETURN', reason: r }) }
        return
      }
      if (a.key === 'proxyCancel') {
        this.fm = { visible: true, title: '代登记销假', confirmText: '代登记销假', danger: false, submitting: false, err: '',
          fields: [
            { type: 'datetime', key: 'actualReturnAt', label: '实际返校时间', required: true, max: this.nowLocal },
            { type: 'textarea', key: 'note', label: '说明', placeholder: '如：本人已返校 / 家长代办', max: 500 }
          ], values: { actualReturnAt: '', note: '' },
          submit: (v) => leaveApi.proxyCancel(id, { actualReturnAt: v.actualReturnAt, note: v.note }) }
        return
      }
      if (a.key === 'cancelConfirm') {
        this.fm = { visible: true, title: '销假确认', confirmText: '确认销假', danger: false, submitting: false, err: '',
          fields: [
            { type: 'datetime', key: 'actualReturnAt', label: '实际返校时间（可校对，选填）', required: false, max: this.nowLocal },
            { type: 'textarea', key: 'note', label: '确认说明', placeholder: '选填', max: 500 }
          ], values: { actualReturnAt: '', note: '' },
          submit: (v) => leaveApi.cancelConfirm(id, { action: 'CONFIRM', actualReturnAt: v.actualReturnAt || null, note: v.note }) }
        return
      }
      if (a.key === 'applyExtension') {
        this.fm = { visible: true, title: '发起续假', confirmText: '提交续假', danger: false, submitting: false, err: '',
          fields: [
            { type: 'datetime', key: 'newEnd', label: '续假后新结束时间', required: true },
            { type: 'textarea', key: 'reason', label: '续假原因', required: true, minLen: 10, placeholder: '请说明续假原因（不少于 10 字）', max: 500 }
          ], values: { newEnd: '', reason: '' },
          submit: (v) => leaveApi.applyExtension(id, { newEnd: v.newEnd, reason: v.reason }) }
        return
      }
      if (a.key === 'overdueHandle') {
        this.fm = { visible: true, title: '逾期处置', confirmText: '登记处置', danger: false, submitting: false, err: '',
          fields: [
            { type: 'select', key: 'handleType', label: '处置方式', required: true, options: [
              { label: '联系学生（留痕）', value: 'CONTACT' },
              { label: '转家校联系（留痕）', value: 'TO_HOME_SCHOOL' },
              { label: '处置完毕关闭', value: 'CLOSE' }
            ] },
            { type: 'textarea', key: 'note', label: '处置说明', required: true, minLen: 5, placeholder: '请填写处置说明（不少于 5 字）', max: 500 }
          ], values: { handleType: '', note: '' },
          submit: (v) => leaveApi.overdueHandle(id, { handleType: v.handleType, note: v.note }) }
        return
      }
    },
    async onConfirmSimple({ reason }) {
      this.cd.submitting = true
      const res = await this.cd.submit(reason || '')
      this.cd.submitting = false
      if (res.code !== 0) return toast.error(res.message || '操作失败')
      this.cd.visible = false
      toast.success('处理完成，已写审批留痕')
      await this.advance()
    },
    closeForm() { this.fm.visible = false },
    async submitForm() {
      this.fm.err = ''
      for (const f of this.fm.fields) {
        const v = (this.fm.values[f.key] || '').toString().trim()
        if (f.required && !v) { this.fm.err = `请填写「${f.label}」`; return }
        if (f.minLen && v && v.length < f.minLen) { this.fm.err = `「${f.label}」不少于 ${f.minLen} 字`; return }
      }
      this.fm.submitting = true
      const res = await this.fm.submit(this.fm.values)
      this.fm.submitting = false
      if (res.code !== 0) { this.fm.err = res.message || '操作失败'; return }
      this.fm.visible = false
      toast.success('处理完成，已写审批留痕')
      await this.advance()
    },
    async advance() {
      const oldId = this.selectedId
      await this.load()
      const still = this.rows.find((r) => String(r.id) === String(oldId))
      if (still) { this.loadDetail(oldId); return }  // 状态变了但仍在队列（如 APPROVED→WAIT_CANCEL_LEAVE）
      const next = this.rows[0]
      if (next) { this.select(next.id); return }
      this.selectedId = ''
      this.detail = { loading: false, error: '', data: null }
      this.doneHint = true
    },
    async onScan() {
      this.scanning = true
      const res = await leaveApi.scanOverdue()
      this.scanning = false
      if (res.code !== 0) return toast.error(res.message || '扫描失败')
      toast.success(`已扫描，新增逾期 ${res.data.count} 条`)
      this.reload()
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
.rec-list { list-style: none; margin: 0; padding: 0; font-size: var(--font-size-sm); }
.rec-list li { padding: var(--space-1) 0; display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }

.lv-list { list-style: none; margin: 0; padding: var(--space-2); display: flex; flex-direction: column; gap: var(--space-1); }
.lv-item { display: block; width: 100%; text-align: left; font: inherit; cursor: pointer; background: transparent; border: 1px solid transparent; border-radius: var(--radius-md, 8px); padding: var(--space-2) var(--space-3); transition: background 0.12s ease, border-color 0.12s ease; }
.lv-item:hover { background: var(--primary-50, #eff6ff); }
.lv-item.is-active { background: var(--primary-50, #eff6ff); border-color: var(--primary-600, #2563eb); }
.lv-item__row { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }
.lv-item__name { font-size: var(--font-size-sm); font-weight: var(--font-weight-medium); color: var(--text-primary); }
.lv-item__sub { margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.lv-pager { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); }

.lv-main { display: flex; flex-direction: column; min-height: 320px; }
.lv-main__body { flex: 1; padding: var(--space-4); min-width: 0; }
.lv-main__state { margin: var(--space-4); }
.lv-head { display: flex; align-items: center; gap: var(--space-2); flex-wrap: wrap; }
.lv-head__name { font-size: var(--font-size-md, 15px); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.lv-foot { position: sticky; bottom: 0; display: flex; justify-content: flex-end; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-top: 1px solid var(--border-light); background: var(--bg-card, #fff); }

.fm-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.fm-dialog { width: 440px; max-width: calc(100vw - 32px); background: var(--bg-card, #fff); border-radius: 12px; box-shadow: var(--shadow-lg, 0 12px 40px rgba(0,0,0,0.18)); overflow: hidden; }
.fm-title { padding: 14px 18px; font-weight: 600; font-size: 15px; border-bottom: 1px solid var(--border-light); }
.fm-body { padding: 16px 18px; display: flex; flex-direction: column; gap: var(--space-3); }
.fm-item { display: flex; flex-direction: column; gap: 6px; }
.fm-label { font-size: var(--font-size-sm); color: var(--text-secondary); }
.fm-label i { color: var(--danger-600); font-style: normal; margin-left: 2px; }
.fm-err { color: var(--danger-600); font-size: var(--font-size-sm); margin: 0; }
.fm-foot { padding: 12px 18px; display: flex; justify-content: flex-end; gap: var(--space-2); border-top: 1px solid var(--border-light); }
</style>
