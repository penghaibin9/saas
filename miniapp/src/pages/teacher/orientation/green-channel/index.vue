<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="绿色通道审核" show-back />
    <view class="page-pad gc__context">
      <text class="t-md t-bold">{{ batchName || (batchId ? '当前迎新批次' : '全部授权批次') }}</text>
      <view class="gc__tabs"><button size="mini" :disabled="acting" :class="{ active: queue === 'pending' }" @click="changeQueue('pending')">待审核</button><button size="mini" :disabled="acting" :class="{ active: queue === 'all' }" @click="changeQueue('all')">全部申请</button></view>
      <text v-if="!canManage && state === 'ready'" class="gc__class">当前身份仅可查看，审核需学校授权。</text>
    </view>

    <MobileGlobalState :state="state" :description="loadError" @retry="load">
      <view class="page-pad">
        <MobileGlobalState v-if="!list || !list.length" state="empty" :title="queue === 'pending' ? '暂无待审申请' : '暂无绿色通道申请'"
          :description="queue === 'pending' ? '可切换全部申请，查看此前的办理结果。' : '学生提交后，可在当前批次继续审核。'" />
        <view v-else class="stack">
          <view v-for="a in list" :key="a.id" class="gc card">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ a.name || '（未命名）' }}</text>
                <text class="gc__class">{{ a.className }}</text>
              </view>
              <MobileStatusTag :status="a.status" />
            </view>

            <view class="gc__fields">
              <view class="gc__field"><text class="gc__field-k">申请类型</text><text class="gc__field-v flex-1">{{ applyTypeLabel(a.applyType) }}</text></view>
              <view class="gc__field"><text class="gc__field-k">申请金额</text><text class="gc__field-v flex-1">{{ a.applyAmount || '—' }}</text></view>
              <view v-if="a.remark" class="gc__field"><text class="gc__field-k">申请说明</text><text class="gc__field-v flex-1">{{ a.remark }}</text></view>
              <view class="gc__field"><text class="gc__field-k">提交时间</text><text class="gc__field-v flex-1">{{ formatDateTime(a.submitTime) }}</text></view>
              <view v-if="a.rejectReason" class="gc__field"><text class="gc__field-k">办理意见</text><text class="gc__field-v flex-1">{{ a.rejectReason }}</text></view>
            </view>

            <view v-if="canManage && (a.status === 'SUBMITTED' || a.status === 'REVIEWING')" class="gc__actions">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="openReview(a, 'RETURN')">退回</button>
              <button class="gc__reject flex-1" :disabled="acting" @click="openReview(a, 'REJECT')">驳回</button>
              <button class="gc__approve flex-1" :disabled="acting" @click="openReview(a, 'APPROVE')">通过</button>
            </view>
            <view v-else class="gc__done">
              <text class="gc__done-text">{{ statusLabel(a.status, a.statusLabel) }}</text>
            </view>
          </view>
        </view>
        <view class="gc__pages"><button size="mini" :disabled="page <= 1 || acting" @click="turnPage(page - 1)">上一页</button><text>{{ page }} / {{ Math.max(1, Math.ceil(total / pageSize)) }} · 共 {{ total }} 条</text><button size="mini" :disabled="page * pageSize >= total || acting" @click="turnPage(page + 1)">下一页</button></view>
      </view>
    </MobileGlobalState>
    <view v-if="reviewDialog.visible" class="gc__dialog-mask" @click.self="closeReview">
      <view class="gc__dialog">
        <text class="gc__dialog-title">{{ reviewDialog.label }}绿色通道</text>
        <text class="gc__dialog-copy">{{ reviewDialog.studentName }} · {{ applyTypeLabel(reviewDialog.applyType) }}</text>
        <textarea
          v-if="reviewDialog.needsComment"
          v-model="reviewDialog.comment"
          class="gc__dialog-input"
          maxlength="1000"
          :placeholder="'请填写' + reviewDialog.label + '意见（不少于5字）'"
        />
        <text v-else class="gc__dialog-description">确认通过该学生的绿色通道申请？通过后将自动更新缴费办理进度。</text>
        <text v-if="reviewDialog.error" class="gc__dialog-error">{{ reviewDialog.error }}</text>
        <view class="gc__dialog-actions">
          <button class="gc__dialog-cancel" :disabled="acting" @click="closeReview">{{ reviewDialog.conflicted ? '关闭并刷新' : '取消' }}</button>
          <button class="gc__dialog-confirm" :disabled="acting || reviewDialog.conflicted" @click="submitReview">{{ acting ? '提交中…' : '确认' + reviewDialog.label }}</button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { normalizeError, realRequest } from '@/services/request'
import { toast, decodeQueryText } from '@/utils/nav'
import { formatDateTime } from '@/utils/format'
export default {
  data() { return { list: [], state: 'loading', loadError: '', acting: false, canManage: false,
    batchId: '', batchName: '', page: 1, pageSize: 30, total: 0, queue: 'pending', loadSerial: 0, actionSerial: 0, permissionSerial: 0,
    reviewDialog: { visible: false, target: null, action: '', label: '', needsComment: false, studentName: '', applyType: '', comment: '', error: '', conflicted: false } } },
  onLoad(query = {}) {
    this.batchId = String(query.batchId || '')
    this.batchName = decodeQueryText(query.batchName)
  },
  onShow() { return Promise.all([this.loadPermissions(), this.load()]) },
  onHide() { this.loadSerial++; this.permissionSerial++; this.canManage = false },
  onUnload() { this.loadSerial++; this.actionSerial++; this.permissionSerial++; this.canManage = false },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    formatDateTime,
    async loadPermissions() {
      const serial = ++this.permissionSerial
      this.canManage = false
      try {
        const ctx = await realRequest('/rbac/current-context')
        if (serial !== this.permissionSerial) return
        const code = 'studentAffairs.orientation.manage'
        this.canManage = ctx.moduleAccessHealthy !== false && !ctx.readonlyTenant && (ctx.permissionPatterns || []).some(p => p === '*' || p === code || (p.endsWith('.*') && code.startsWith(p.slice(0, -1))) || (p.startsWith('*.') && code.endsWith(p.slice(1))))
      } catch { if (serial === this.permissionSerial) this.canManage = false }
    },
    applyTypeLabel(value) {
      if (!value) return '绿色通道'
      if (/[一-鿿]/.test(value)) return value
      return ({ STUDENT_LOAN: '助学贷款', TUITION_DEFERMENT: '学费缓缴', TUITION_REDUCTION: '学费减免', INSTALLMENT: '分期缴费', OTHER: '其他困难申请' })[value] || '申请类型待确认'
    },
    statusLabel(value, label) {
      if (label && /[一-鿿]/.test(label)) return label
      return ({ PENDING: '待审核', SUBMITTED: '待审核', REVIEWING: '审核中', APPROVED: '已通过', REJECTED: '已驳回', RETURNED: '已退回' })[value] || '状态待确认'
    },
    async load(done) {
      const serial = ++this.loadSerial
      this.state = 'loading'; this.loadError = ''; this.list = []; this.total = 0
      try {
        const d = await realRequest('/mobile/teacher/orientation/green-channels', { data: { batchId: this.batchId || undefined, page: this.page, pageSize: this.pageSize, queue: this.queue } })
        if (serial !== this.loadSerial) return
        if (this.page > 1 && !d.list?.length && d.total <= (this.page - 1) * this.pageSize) {
          this.page = Math.max(1, Math.ceil(d.total / this.pageSize))
          return this.load()
        }
        this.list = d.list || []; this.total = d.total || 0; this.state = 'ready'
      } catch (error) {
        if (serial === this.loadSerial) { this.loadError = error.message || '申请读取失败，请重试'; this.state = normalizeError(error).pageState || 'error' }
      } finally { if (typeof done === 'function') done() }
    },
    changeQueue(queue) { if (this.acting) return; this.queue = queue; this.page = 1; return this.load() },
    turnPage(page) { if (this.acting || this.state === 'loading') return; this.page = page; return this.load() },
    openReview(a, type) {
      if (this.acting || !this.canManage || !['SUBMITTED', 'REVIEWING'].includes(a.status)) return
      const label = { APPROVE: '通过', REJECT: '驳回', RETURN: '退回' }[type]
      const previous = this.reviewDialog
      const comment = previous.conflicted && previous.target?.id === a.id && previous.action === type ? previous.comment : ''
      this.reviewDialog = {
        visible: true, target: { id: a.id, version: a.version }, action: type, label,
        needsComment: type !== 'APPROVE', studentName: a.name || '该学生',
        applyType: a.applyType || '绿色通道', comment, error: '', conflicted: false
      }
    },
    closeReview() {
      if (this.acting) return
      this.reviewDialog.visible = false
      if (this.reviewDialog.conflicted) return this.load()
      this.reviewDialog.target = null
    },
    async submitReview() {
      if (this.acting || !this.reviewDialog.target || !this.canManage || this.reviewDialog.conflicted) return
      const serial = this.actionSerial
      const dialog = this.reviewDialog
      const comment = String(dialog.comment || '').trim()
      if (dialog.needsComment && comment.length < 5) {
        dialog.error = dialog.label + '意见不少于5字'
        return
      }
      dialog.error = ''
      this.acting = true
      const target = dialog.target
      try {
        await realRequest('/mobile/teacher/orientation/green-channels/' + target.id + '/review', {
        method: 'POST',
        data: { action: dialog.action, comment, expectedVersion: target.version }
        })
        if (serial !== this.actionSerial) return
        toast('已' + dialog.label)
        this.reviewDialog.visible = false
        this.reviewDialog.target = null
        await this.load()
      } catch (e) {
        if (serial !== this.actionSerial) return
        const code = e && String(e.code)
        if (code && code.startsWith('409')) {
          dialog.conflicted = true
          dialog.error = '申请已变化，意见已保留。请关闭并刷新后，重新打开该申请核对最新状态。'
        } else {
          dialog.error = (e && e.message) || (code && code.startsWith('403')
            ? '没有权限处理该申请'
            : dialog.label + '失败，请重试')
        }
      } finally { this.acting = false }
    }
  }
}
</script>

<style scoped>
.gc__context { padding-bottom: 0; }
.gc__tabs,.gc__pages { display: flex; align-items: center; gap: 12px; margin-top: 16px; }
.gc__tabs button { margin: 0; }
.gc__tabs .active { color: var(--teacher-700); background: var(--teacher-50); }
.gc__pages { justify-content: space-between; font-size: var(--font-size-sm); }
.gc__class { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; }
.gc__fields { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); margin-top: var(--space-3); }
.gc__field { display: flex; gap: var(--space-3); padding: 5px 0; }
.gc__field-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 76px; flex-shrink: 0; }
.gc__field-v { font-size: var(--font-size-sm); color: var(--text-primary); }
.gc__actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); }
.gc__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.gc__reject::after { border: none; }
.gc__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.gc__approve::after { border: none; }
.gc__done { text-align: center; padding: var(--space-2); margin-top: var(--space-2); }
.gc__done-text { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.gc__dialog-mask { position: fixed; inset: 0; z-index: 2000; display: flex; align-items: center; justify-content: center; padding: 24px; background: rgba(15,23,42,.45); }
.gc__dialog { width: 100%; max-width: 360px; box-sizing: border-box; padding: 20px; border-radius: 16px; background: #fff; box-shadow: 0 20px 60px rgba(15,23,42,.25); }
.gc__dialog-title,.gc__dialog-copy,.gc__dialog-description,.gc__dialog-error { display: block; }
.gc__dialog-title { color: #0f172a; font-size: 18px; font-weight: 700; }
.gc__dialog-copy { margin-top: 8px; color: #475569; font-size: 13px; }
.gc__dialog-description { margin-top: 14px; color: #475569; font-size: 13px; line-height: 1.65; }
.gc__dialog-input { width: 100%; min-height: 100px; box-sizing: border-box; margin-top: 14px; padding: 10px; border: 1px solid #cbd5e1; border-radius: 10px; background: #fff; }
.gc__dialog-error { margin-top: 8px; color: #dc2626; font-size: 12px; }
.gc__dialog-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 18px; }
.gc__dialog-cancel,.gc__dialog-confirm { border-radius: 10px; font-size: 14px; }
.gc__dialog-cancel { background: #f1f5f9; color: #334155; }
.gc__dialog-confirm { background: var(--teacher-600); color: #fff; }
</style>
