<template>
  <ModulePageShell
    title="请假审批工作台"
    subtitle="辅导员 / 学院 / 学工处 多级审批 · 销假续假闭环"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="请假审批"
  >
    <!-- 工具条：状态筛选 + 搜索 + 逾期扫描 + 代录请假 -->
    <div class="lv-toolbar">
      <div class="lv-filters">
        <button
          v-for="f in statusFilters"
          :key="f.key"
          type="button"
          class="lv-chip"
          :class="{ 'is-on': activeFilter === f.key }"
          @click="activeFilter = f.key"
        >
          {{ f.label }}<em>{{ f.count }}</em>
        </button>
      </div>
      <div class="lv-tools">
        <input v-model.trim="keyword" class="lv-search" type="text" placeholder="搜学生姓名" />
        <button type="button" class="lv-btn" :disabled="scanning" @click="onScanOverdue">
          {{ scanning ? '扫描中…' : '逾期扫描' }}
        </button>
        <button type="button" class="lv-btn lv-btn--primary" @click="openApply">代录请假</button>
      </div>
    </div>

    <div class="lv-workspace">
      <!-- 左：待审批队列 -->
      <div class="lv-list">
        <LoadingState v-if="loading" text="正在加载待审批请假…" />
        <ErrorState v-else-if="listError" :description="listError" @retry="loadList" />
        <EmptyState v-else-if="!filteredList.length" title="暂无待审批请假" description="可点「代录请假」为学生发起，或调整筛选条件" />
        <ul v-else class="lv-queue">
          <li
            v-for="it in filteredList"
            :key="it.id"
            class="lv-qitem"
            :class="{ 'is-active': selected && selected.id === it.id }"
            @click="select(it)"
          >
            <div class="lv-qitem__top">
              <span class="lv-qitem__name">{{ it.studentName || ('学生#' + it.studentId) }}</span>
              <StatusTag :type="statusType(it.affairsStatus)" :label="it.affairsStatusLabel" dot />
            </div>
            <div class="lv-qitem__meta">
              <span>{{ leaveTypeLabel(it.leaveType) }} · {{ it.days }}天</span>
              <span class="lv-qitem__time">{{ fmt(it.startTime) }} → {{ fmt(it.endTime) }}</span>
            </div>
          </li>
        </ul>
      </div>

      <!-- 右：详情 + 动作 -->
      <div class="lv-detail">
        <EmptyState v-if="!selected" title="请从左侧选择一条请假" description="查看详情并进行审批 / 销假 / 续假等操作" />
        <template v-else>
          <div class="lv-dhead">
            <div>
              <h3 class="lv-dname">{{ selected.studentName || ('学生#' + selected.studentId) }}</h3>
              <StatusTag :type="statusType(selected.affairsStatus)" :label="selected.affairsStatusLabel" dot />
            </div>
            <button type="button" class="lv-refresh" title="刷新详情" @click="reloadDetail">↻</button>
          </div>

          <dl class="lv-kv">
            <div><dt>请假类型</dt><dd>{{ leaveTypeLabel(selected.leaveType) }}</dd></div>
            <div><dt>请假天数</dt><dd>{{ selected.days }} 天</dd></div>
            <div><dt>开始时间</dt><dd>{{ fmt(selected.startTime) }}</dd></div>
            <div><dt>结束时间</dt><dd>{{ fmt(selected.endTime) }}</dd></div>
            <div><dt>应返校</dt><dd>{{ fmt(selected.expectedReturnAt) || '—' }}</dd></div>
            <div><dt>实际返校</dt><dd>{{ fmt(selected.actualReturnAt) || '—' }}</dd></div>
            <div class="lv-kv--full"><dt>请假事由</dt><dd>{{ selected.reason || '（未填写）' }}</dd></div>
          </dl>

          <div v-if="detailActions.length" class="lv-actions">
            <button
              v-for="a in detailActions"
              :key="a.key"
              type="button"
              class="lv-btn"
              :class="{ 'lv-btn--primary': a.tone === 'primary', 'lv-btn--danger': a.tone === 'danger' }"
              :disabled="acting"
              @click="onAction(a.key)"
            >
              {{ a.label }}
            </button>
          </div>
          <p v-else class="lv-terminal">该请假已处于终态（{{ selected.affairsStatusLabel }}），仅可查看。</p>
        </template>
      </div>
    </div>

    <!-- 通用确认（通过/退回/驳回/重提/销假/销假确认/续假通过） -->
    <AppConfirmDialog
      v-model:visible="dialog.visible"
      :title="dialog.title"
      :message="dialog.message"
      :type="dialog.type"
      :confirm-text="dialog.confirmText"
      :require-reason="dialog.requireReason"
      :reason-label="dialog.reasonLabel"
      :reason-placeholder="dialog.reasonPlaceholder"
      :submitting="acting"
      @confirm="onDialogConfirm"
    />

    <!-- 续假 modal（需新结束时间） -->
    <div v-if="extModal.visible" class="lv-mask" @click.self="extModal.visible = false">
      <div class="lv-modal">
        <h3 class="lv-modal__title">发起续假</h3>
        <p class="lv-modal__hint">原结束时间：{{ fmt(selected && selected.endTime) }}，续假结束须晚于该时间。</p>
        <label class="lv-field"><span>新结束时间 <i>*</i></span>
          <input v-model="extModal.newEnd" type="datetime-local" class="lv-input" />
        </label>
        <label class="lv-field"><span>续假事由</span>
          <textarea v-model.trim="extModal.reason" class="lv-textarea" rows="3" placeholder="选填" />
        </label>
        <p v-if="extModal.error" class="lv-err">{{ extModal.error }}</p>
        <div class="lv-modal__foot">
          <button type="button" class="lv-btn" @click="extModal.visible = false">取消</button>
          <button type="button" class="lv-btn lv-btn--primary" :disabled="acting" @click="submitExtension">提交续假</button>
        </div>
      </div>
    </div>

    <!-- 代录请假 modal -->
    <div v-if="applyModal.visible" class="lv-mask" @click.self="applyModal.visible = false">
      <div class="lv-modal">
        <h3 class="lv-modal__title">代录请假</h3>
        <div class="lv-field"><span>学生 <i>*</i></span>
          <AppStudentPicker v-model="applyModal.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生" />
        </div>
        <label class="lv-field"><span>请假类型 <i>*</i></span>
          <select v-model="applyModal.leaveType" class="lv-input">
            <option value="PERSONAL">事假</option>
            <option value="SICK">病假</option>
            <option value="GOOUT">外出</option>
          </select>
        </label>
        <label class="lv-field"><span>开始时间 <i>*</i></span>
          <input v-model="applyModal.startTime" type="datetime-local" class="lv-input" />
        </label>
        <label class="lv-field"><span>结束时间 <i>*</i></span>
          <input v-model="applyModal.endTime" type="datetime-local" class="lv-input" />
        </label>
        <label class="lv-field"><span>请假事由</span>
          <textarea v-model.trim="applyModal.reason" class="lv-textarea" rows="3" placeholder="选填" />
        </label>
        <p v-if="applyModal.error" class="lv-err">{{ applyModal.error }}</p>
        <div class="lv-modal__foot">
          <button type="button" class="lv-btn" @click="applyModal.visible = false">取消</button>
          <button type="button" class="lv-btn lv-btn--primary" :disabled="acting" @click="submitApply">提交请假</button>
        </div>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 请假审批工作台（/admin/student-affairs/leave）—— 13A P3 核心示范。
 * 真实对接 /api/v1/student-affairs/leave/*：待审队列 + 多级审批 + 退回/驳回 + 销假/续假闭环 + 逾期扫描 + 代录。
 * 后端仅提供 /leave/pending（三个审批节点态）列表；APPROVED/OVERDUE 等在动作后的详情面板内继续闭环。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppConfirmDialog, AppStatusTag, AppStudentPicker } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const REVIEW_NODES = ['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'STUDENT_AFFAIRS_REVIEW']
const STATUS_TYPE = {
  COUNSELOR_REVIEW: 'warning', COLLEGE_REVIEW: 'warning', STUDENT_AFFAIRS_REVIEW: 'warning',
  APPROVED: 'success', CLOSED: 'success', REJECTED: 'danger', OVERDUE: 'danger',
  RETURNED: 'warning', CANCELLED: 'default', EXTENSION_REVIEW: 'processing',
  WAIT_CANCEL_LEAVE: 'processing', DRAFT: 'default', SUBMITTED: 'processing', ARCHIVED: 'default'
}
const LEAVE_TYPE = { SICK: '病假', PERSONAL: '事假', GOOUT: '外出' }

export default {
  name: 'LeaveWorkbenchView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppConfirmDialog, StatusTag: AppStatusTag, AppStudentPicker },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, listError: '', list: [],
      selected: null, acting: false, scanning: false,
      activeFilter: 'ALL', keyword: '',
      dialog: { visible: false, action: '', title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', reasonPlaceholder: '' },
      extModal: { visible: false, newEnd: '', reason: '', error: '' },
      applyModal: { visible: false, studentId: '', leaveType: 'PERSONAL', startTime: '', endTime: '', reason: '', error: '' }
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    statusFilters() {
      const c = (node) => this.list.filter((x) => x.affairsStatus === node).length
      return [
        { key: 'ALL', label: '全部待审', count: this.list.length },
        { key: 'COUNSELOR_REVIEW', label: '辅导员审批', count: c('COUNSELOR_REVIEW') },
        { key: 'COLLEGE_REVIEW', label: '学院审批', count: c('COLLEGE_REVIEW') },
        { key: 'STUDENT_AFFAIRS_REVIEW', label: '学工处审批', count: c('STUDENT_AFFAIRS_REVIEW') }
      ]
    },
    filteredList() {
      let arr = this.list
      if (this.activeFilter !== 'ALL') arr = arr.filter((x) => x.affairsStatus === this.activeFilter)
      if (this.keyword) arr = arr.filter((x) => (x.studentName || '').includes(this.keyword))
      return arr
    },
    detailActions() {
      const s = this.selected && this.selected.affairsStatus
      if (!s) return []
      if (REVIEW_NODES.includes(s)) {
        return [
          { key: 'approve', label: '审批通过', tone: 'primary' },
          { key: 'return', label: '退回重提', tone: 'default' },
          { key: 'reject', label: '驳回', tone: 'danger' }
        ]
      }
      if (s === 'RETURNED') return [{ key: 'resubmit', label: '重新提交', tone: 'primary' }]
      if (s === 'APPROVED' || s === 'OVERDUE') {
        return [
          { key: 'cancel', label: '发起销假', tone: 'primary' },
          { key: 'extend', label: '发起续假', tone: 'default' }
        ]
      }
      if (s === 'WAIT_CANCEL_LEAVE') return [{ key: 'cancelConfirm', label: '销假确认', tone: 'primary' }]
      if (s === 'EXTENSION_REVIEW') return [{ key: 'extApprove', label: '续假审批通过', tone: 'primary' }]
      return []
    }
  },
  created() {
    this.loadList()
  },
  methods: {
    fmt(t) {
      return t ? String(t).replace('T', ' ').slice(0, 16) : ''
    },
    leaveTypeLabel(t) {
      return LEAVE_TYPE[t] || t || '—'
    },
    statusType(s) {
      return STATUS_TYPE[s] || 'default'
    },
    async loadList() {
      this.loading = true
      this.listError = ''
      const res = await studentAffairsApi.getPendingLeaves({ page: 1, pageSize: 100 })
      this.loading = false
      if (res.code === 0 && res.data) {
        this.list = res.data.items || []
        // 保持选中项同步（若仍在列表中则用最新数据）
        if (this.selected) {
          const hit = this.list.find((x) => x.id === this.selected.id)
          if (hit) this.selected = hit
        }
      } else {
        this.listError = res.message || '加载失败'
      }
    },
    select(it) {
      this.selected = it
    },
    async reloadDetail() {
      if (!this.selected) return
      const res = await studentAffairsApi.getLeaveDetail(this.selected.id)
      if (res.code === 0 && res.data) this.selected = res.data
      else toast.error(res.message || '刷新详情失败')
    },
    // ── 动作分发 ──
    onAction(key) {
      if (key === 'extend') { this.openExtension(); return }
      const map = {
        approve: { action: 'approve', title: '审批通过', message: '确认通过该请假申请？多级审批将推进到下一节点。', type: 'primary', confirmText: '审批通过', requireReason: false },
        return: { action: 'return', title: '退回重提', message: '退回后学生可修改重新提交。', type: 'warning', confirmText: '退回重提', requireReason: true, reasonLabel: '退回原因（≥5字）', reasonPlaceholder: '请说明退回原因，不少于 5 字' },
        reject: { action: 'reject', title: '驳回请假', message: '驳回为终态，学生不可再修改本单。', type: 'danger', confirmText: '驳回请假', requireReason: true, reasonLabel: '驳回原因（≥5字）', reasonPlaceholder: '请说明驳回原因，不少于 5 字' },
        resubmit: { action: 'resubmit', title: '重新提交', message: '将该退回的请假重新提交进入审批。', type: 'primary', confirmText: '重新提交', requireReason: false },
        cancel: { action: 'cancel', title: '发起销假', message: '为该生发起销假，进入辅导员销假确认。', type: 'primary', confirmText: '发起销假', requireReason: false },
        cancelConfirm: { action: 'cancelConfirm', title: '销假确认', message: '确认该生已按时返校？确认后请假闭环并写入学生 360。', type: 'primary', confirmText: '确认销假', requireReason: false },
        extApprove: { action: 'extApprove', title: '续假审批通过', message: '通过后请假结束时间将顺延到续假结束时间。', type: 'primary', confirmText: '续假通过', requireReason: false }
      }
      const d = map[key]
      if (!d) return
      this.dialog = { visible: true, reasonLabel: '原因', reasonPlaceholder: '', ...d }
    },
    async onDialogConfirm(payload) {
      const reason = (payload && payload.reason) || ''
      const id = this.selected.id
      const a = this.dialog.action
      const call = {
        approve: () => studentAffairsApi.approveLeave(id, ''),
        return: () => studentAffairsApi.returnLeave(id, reason),
        reject: () => studentAffairsApi.rejectLeave(id, reason),
        resubmit: () => studentAffairsApi.resubmitLeave(id),
        cancel: () => studentAffairsApi.cancelLeave(id),
        cancelConfirm: () => studentAffairsApi.confirmCancelLeave(id),
        extApprove: () => studentAffairsApi.approveExtension(id)
      }[a]
      if (!call) return
      await this.runAction(call, {
        approve: '已审批通过', return: '已退回', reject: '已驳回', resubmit: '已重新提交',
        cancel: '销假已发起', cancelConfirm: '已销假', extApprove: '续假已通过'
      }[a])
      this.dialog.visible = false
    },
    openExtension() {
      this.extModal = { visible: true, newEnd: '', reason: '', error: '' }
    },
    async submitExtension() {
      if (!this.extModal.newEnd) { this.extModal.error = '请选择新结束时间'; return }
      const newEnd = this.extModal.newEnd.replace('T', ' ') + ':00'
      const ok = await this.runAction(
        () => studentAffairsApi.extendLeave(this.selected.id, newEnd, this.extModal.reason),
        '续假已提交'
      )
      if (ok) this.extModal.visible = false
      else this.extModal.error = this._lastErr || '提交失败'
    },
    openApply() {
      this.applyModal = { visible: true, studentId: '', leaveType: 'PERSONAL', startTime: '', endTime: '', reason: '', error: '' }
    },
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
    },
    async submitApply() {
      const m = this.applyModal
      if (!m.studentId) { m.error = '请选择学生'; return }
      if (!m.startTime || !m.endTime) { m.error = '请填写起止时间'; return }
      if (m.endTime <= m.startTime) { m.error = '结束时间必须晚于开始时间'; return }
      const body = {
        studentId: String(m.studentId),
        leaveType: m.leaveType,
        startTime: m.startTime.replace('T', ' ') + ':00',
        endTime: m.endTime.replace('T', ' ') + ':00',
        reason: m.reason || ''
      }
      const ok = await this.runAction(() => studentAffairsApi.applyLeave(body), '请假已提交')
      if (ok) this.applyModal.visible = false
      else this.applyModal.error = this._lastErr || '提交失败'
    },
    async onScanOverdue() {
      this.scanning = true
      const res = await studentAffairsApi.scanOverdueLeaves()
      this.scanning = false
      if (res.code === 0) {
        toast.info(`逾期扫描完成，本次新增逾期 ${res.data.count} 条`)
        this.loadList()
      } else {
        toast.error(res.message || '扫描失败')
      }
    },
    /** 统一执行写动作：置 acting、调后端、成功刷新详情+列表、失败透出后端 message。返回是否成功。 */
    async runAction(call, okMsg) {
      this.acting = true
      this._lastErr = ''
      const res = await call()
      if (res.code === 0) {
        toast.success(okMsg)
        if (res.data && res.data.id) this.selected = res.data
        else await this.reloadDetail()
        await this.loadList()
        this.acting = false
        return true
      }
      this._lastErr = res.message || '操作失败'
      toast.error(this._lastErr)
      this.acting = false
      return false
    }
  }
}
</script>

<style scoped>
.lv-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}
.lv-filters {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.lv-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.lv-chip.is-on {
  border-color: var(--primary-400);
  color: var(--primary-700);
  background: var(--primary-50);
}
.lv-chip em {
  font-style: normal;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.lv-chip.is-on em {
  color: var(--primary-600);
}
.lv-tools {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.lv-search {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  outline: none;
}
.lv-btn {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.lv-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.lv-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.lv-btn--danger {
  background: var(--danger-600, #dc2626);
  border-color: var(--danger-600, #dc2626);
  color: #fff;
}
.lv-workspace {
  display: grid;
  grid-template-columns: minmax(280px, 360px) 1fr;
  gap: var(--space-4);
  align-items: start;
}
.lv-list {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-2);
}
.lv-queue {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.lv-qitem {
  padding: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
}
.lv-qitem:hover {
  border-color: var(--primary-300);
}
.lv-qitem.is-active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.lv-qitem__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.lv-qitem__name {
  font-weight: 600;
  color: var(--text-primary);
}
.lv-qitem__meta {
  display: flex;
  justify-content: space-between;
  gap: var(--space-2);
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.lv-detail {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-4);
}
.lv-dhead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.lv-dname {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.lv-refresh {
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  border-radius: var(--radius-base);
  width: 28px;
  height: 28px;
  cursor: pointer;
  color: var(--text-secondary);
}
.lv-kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-4);
  margin: 0 0 var(--space-4);
}
.lv-kv > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.lv-kv--full {
  grid-column: 1 / -1;
}
.lv-kv dt {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.lv-kv dd {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.lv-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
}
.lv-terminal {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.lv-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.lv-modal {
  width: 440px;
  max-width: calc(100vw - 32px);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-lg, 0 10px 40px rgba(0, 0, 0, 0.2));
}
.lv-modal__title {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.lv-modal__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.lv-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}
.lv-field > span {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.lv-field i {
  color: var(--danger-600, #dc2626);
  font-style: normal;
}
.lv-input,
.lv-textarea {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: var(--space-2);
  outline: none;
}
.lv-textarea {
  resize: vertical;
}
.lv-err {
  margin: 0 0 var(--space-2);
  color: var(--danger-600, #dc2626);
  font-size: var(--font-size-xs);
}
.lv-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
</style>
