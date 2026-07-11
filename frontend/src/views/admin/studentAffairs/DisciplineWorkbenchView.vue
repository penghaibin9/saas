<template>
  <ModulePageShell
    title="违纪处分工作台"
    subtitle="登记 · 学院初审 / 学工处复核 / 校级 · 生效与解除闭环"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="违纪处分"
  >
    <div class="dp-toolbar">
      <div class="dp-filters">
        <button
          v-for="f in statusFilters"
          :key="f.key"
          type="button"
          class="dp-chip"
          :class="{ 'is-on': activeStatus === f.key }"
          @click="activeStatus = f.key"
        >
          {{ f.label }}<em>{{ f.count }}</em>
        </button>
      </div>
      <div class="dp-tools">
        <select v-model="typeFilter" class="dp-input" title="按处分类型筛选">
          <option value="">全部类型</option>
          <option v-for="t in discTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
        </select>
        <button type="button" class="dp-btn" :disabled="reconciling" @click="onReconcile">投影对账</button>
        <button type="button" class="dp-btn dp-btn--primary" @click="openRegister">登记处分</button>
      </div>
    </div>

    <div class="dp-workspace">
      <div class="dp-list">
        <LoadingState v-if="loading" text="正在加载处分记录…" />
        <ErrorState v-else-if="listError" :description="listError" @retry="loadList" />
        <EmptyState v-else-if="!filteredList.length" title="暂无处分记录" description="可点「登记处分」录入，或调整筛选条件" />
        <ul v-else class="dp-queue">
          <li
            v-for="it in filteredList"
            :key="it.caseId"
            class="dp-qitem"
            :class="{ 'is-active': selected && selected.caseId === it.caseId }"
            @click="select(it)"
          >
            <div class="dp-qitem__top">
              <span class="dp-qitem__name">{{ it.realName || ('学生#' + it.studentId) }}</span>
              <StatusTag :type="statusType(it.status)" :label="it.statusLabel" dot />
            </div>
            <div class="dp-qitem__mid">{{ discTypeLabel(it.discType) }} · {{ it.reason }}</div>
          </li>
        </ul>
      </div>

      <div class="dp-detail">
        <EmptyState v-if="!selected" title="请从左侧选择一条处分" description="查看详情并进行提交 / 审批 / 生效 / 解除等操作" />
        <template v-else>
          <div class="dp-dhead">
            <div>
              <h3 class="dp-dname">{{ selected.realName || ('学生#' + selected.studentId) }}</h3>
              <StatusTag :type="statusType(selected.status)" :label="selected.statusLabel" dot />
            </div>
            <button type="button" class="dp-refresh" title="刷新详情" @click="reloadDetail">↻</button>
          </div>

          <dl class="dp-kv">
            <div><dt>处分类型</dt><dd>{{ discTypeLabel(selected.discType) }}</dd></div>
            <div><dt>学号</dt><dd>{{ selected.studentNo || '—' }}</dd></div>
            <div><dt>文号</dt><dd>{{ selected.docNo || '—' }}</dd></div>
            <div><dt>生效时间</dt><dd>{{ fmt(selected.effectiveAt) || '—' }}</dd></div>
            <div><dt>解除时间</dt><dd>{{ fmt(selected.removedAt) || '—' }}</dd></div>
            <div><dt>投影ID</dt><dd>{{ selected.csDisciplineId || '—' }}</dd></div>
            <div class="dp-kv--full"><dt>违纪事实</dt><dd>{{ selected.reason || '—' }}</dd></div>
          </dl>

          <div v-if="detailActions.length" class="dp-actions">
            <button
              v-for="a in detailActions"
              :key="a.key"
              type="button"
              class="dp-btn"
              :class="{ 'dp-btn--primary': a.tone === 'primary', 'dp-btn--danger': a.tone === 'danger' }"
              :disabled="acting"
              @click="onAction(a.key)"
            >
              {{ a.label }}
            </button>
          </div>
          <p v-else class="dp-terminal">该处分已处于终态（{{ selected.statusLabel }}），仅可查看。</p>
        </template>
      </div>
    </div>

    <!-- 通用确认（提交/撤销/审批/退回/驳回/发起解除/解除审批） -->
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

    <!-- 登记处分 modal -->
    <div v-if="registerModal.visible" class="dp-mask" @click.self="registerModal.visible = false">
      <div class="dp-modal">
        <h3 class="dp-modal__title">登记违纪处分</h3>
        <div class="dp-field"><span>学生 <i>*</i></span>
          <AppStudentPicker v-model="registerModal.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生" />
        </div>
        <label class="dp-field"><span>处分类型 <i>*</i></span>
          <select v-model="registerModal.discType" class="dp-input">
            <option v-for="t in discTypes" :key="t.value" :value="t.value">{{ t.label }}</option>
          </select>
        </label>
        <label class="dp-field"><span>违纪事实（≥5字） <i>*</i></span>
          <textarea v-model.trim="registerModal.reason" class="dp-textarea" rows="3" placeholder="客观描述违纪事实，不少于 5 字" />
        </label>
        <label class="dp-field"><span>文号</span>
          <input v-model.trim="registerModal.docNo" class="dp-input" placeholder="选填，如「校学字〔2026〕12号」" />
        </label>
        <p class="dp-modal__hint">留校察看 / 开除需经校级审批；其余处分学工处复核后即生效。</p>
        <p v-if="registerModal.error" class="dp-err">{{ registerModal.error }}</p>
        <div class="dp-modal__foot">
          <button type="button" class="dp-btn" @click="registerModal.visible = false">取消</button>
          <button type="button" class="dp-btn dp-btn--primary" :disabled="acting" @click="submitRegister">登记</button>
        </div>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 违纪处分工作台（/admin/student-affairs/discipline）—— 13A P5 处分闭环。
 * 真实对接 /api/v1/student-affairs/discipline/*：登记 → 学院初审 / 学工处复核 /（严重）校级 → 生效（投影 t_cs_discipline 进360）→ 解除子流程（辅→院→处）。
 * 列表端点服务端 status/discType 过滤；review 单端点带 action=APPROVE/REJECT/RETURN；解除 remove-review 带 action=APPROVE/REJECT。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppConfirmDialog, AppStatusTag, AppStudentPicker } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const REVIEW_NODES = ['COLLEGE_REVIEW', 'STUDENT_AFFAIRS_REVIEW', 'SCHOOL_REVIEW']
const STATUS_TYPE = {
  REGISTERED: 'default', COLLEGE_REVIEW: 'warning', STUDENT_AFFAIRS_REVIEW: 'warning', SCHOOL_REVIEW: 'warning',
  EFFECTIVE: 'danger', REJECTED: 'info', RETURNED: 'warning', CANCELLED: 'default',
  REMOVE_REVIEW: 'processing', REMOVED: 'success', ARCHIVED: 'default'
}
const DISC_TYPE = {
  WARNING: '警告', SERIOUS_WARNING: '严重警告', DEMERIT: '记过', PROBATION: '留校察看', EXPEL: '开除学籍'
}

export default {
  name: 'DisciplineWorkbenchView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppConfirmDialog, StatusTag: AppStatusTag, AppStudentPicker },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, listError: '', list: [],
      selected: null, acting: false, reconciling: false,
      activeStatus: 'ALL', typeFilter: '',
      dialog: { visible: false, action: '', title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '', reasonPlaceholder: '' },
      registerModal: { visible: false, studentId: '', discType: 'WARNING', reason: '', docNo: '', error: '' },
      discTypes: Object.entries(DISC_TYPE).map(([value, label]) => ({ value, label }))
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
      const c = (arr) => this.list.filter((x) => arr.includes(x.status)).length
      return [
        { key: 'ALL', label: '全部', count: this.list.length },
        { key: 'REVIEW', label: '审批中', count: c(REVIEW_NODES) },
        { key: 'REGISTERED', label: '待提交', count: c(['REGISTERED', 'RETURNED']) },
        { key: 'EFFECTIVE', label: '已生效', count: c(['EFFECTIVE']) },
        { key: 'REMOVE_REVIEW', label: '解除审批', count: c(['REMOVE_REVIEW']) },
        { key: 'REMOVED', label: '已解除', count: c(['REMOVED']) }
      ]
    },
    filteredList() {
      let arr = this.list
      if (this.activeStatus === 'REVIEW') arr = arr.filter((x) => REVIEW_NODES.includes(x.status))
      else if (this.activeStatus === 'REGISTERED') arr = arr.filter((x) => ['REGISTERED', 'RETURNED'].includes(x.status))
      else if (this.activeStatus !== 'ALL') arr = arr.filter((x) => x.status === this.activeStatus)
      if (this.typeFilter) arr = arr.filter((x) => x.discType === this.typeFilter)
      return arr
    },
    detailActions() {
      const s = this.selected && this.selected.status
      if (!s) return []
      if (['REGISTERED', 'RETURNED'].includes(s)) {
        return [
          { key: 'submit', label: '提交初审', tone: 'primary' },
          { key: 'cancel', label: '撤销登记', tone: 'default' }
        ]
      }
      if (REVIEW_NODES.includes(s)) {
        return [
          { key: 'approve', label: '审批通过', tone: 'primary' },
          { key: 'return', label: '退回重登', tone: 'default' },
          { key: 'reject', label: '驳回', tone: 'danger' }
        ]
      }
      if (s === 'EFFECTIVE') return [{ key: 'remove', label: '发起解除', tone: 'primary' }]
      if (s === 'REMOVE_REVIEW') {
        return [
          { key: 'removeApprove', label: '解除通过', tone: 'primary' },
          { key: 'removeReject', label: '解除驳回', tone: 'danger' }
        ]
      }
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
    discTypeLabel(t) {
      return DISC_TYPE[t] || t || '—'
    },
    statusType(s) {
      return STATUS_TYPE[s] || 'default'
    },
    async loadList() {
      this.loading = true
      this.listError = ''
      const res = await studentAffairsApi.getDisciplineCases({ page: 1, pageSize: 200 })
      this.loading = false
      if (res.code === 0 && res.data) {
        this.list = res.data.items || []
        if (this.selected) {
          const hit = this.list.find((x) => x.caseId === this.selected.caseId)
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
      const res = await studentAffairsApi.getDisciplineDetail(this.selected.caseId)
      if (res.code === 0 && res.data) this.selected = res.data
      else toast.error(res.message || '刷新详情失败')
    },
    onAction(key) {
      const map = {
        submit: { action: 'submit', title: '提交学院初审', message: '提交后进入学院初审，登记信息不可再改。', type: 'primary', confirmText: '提交初审', requireReason: false },
        cancel: { action: 'cancel', title: '撤销登记', message: '撤销后该处分作废。', type: 'warning', confirmText: '撤销登记', requireReason: false },
        approve: { action: 'approve', title: '审批通过', message: '通过后推进到下一审批节点，末节点将生效并投影到学生处分记录。', type: 'primary', confirmText: '审批通过', requireReason: false },
        return: { action: 'return', title: '退回重登', message: '退回后回到登记，可修改后重新提交。', type: 'warning', confirmText: '退回重登', requireReason: true, reasonLabel: '退回原因（≥5字）', reasonPlaceholder: '请说明退回原因，不少于 5 字' },
        reject: { action: 'reject', title: '驳回处分', message: '驳回为终态，不予立案。', type: 'danger', confirmText: '驳回处分', requireReason: true, reasonLabel: '驳回原因（≥5字）', reasonPlaceholder: '请说明驳回原因，不少于 5 字' },
        remove: { action: 'remove', title: '发起处分解除', message: '发起解除申请，进入辅导员→学院→学工处三级解除审批。', type: 'primary', confirmText: '发起解除', requireReason: true, reasonLabel: '解除理由（≥5字）', reasonPlaceholder: '请说明解除理由，不少于 5 字' },
        removeApprove: { action: 'removeApprove', title: '解除审批通过', message: '通过后推进解除流程，学工处终审通过将解除处分并恢复评优资格。', type: 'primary', confirmText: '解除通过', requireReason: false },
        removeReject: { action: 'removeReject', title: '解除驳回', message: '驳回后处分回到已生效，可再次申请解除。', type: 'danger', confirmText: '解除驳回', requireReason: true, reasonLabel: '驳回原因（≥5字）', reasonPlaceholder: '请说明驳回原因，不少于 5 字' }
      }
      const d = map[key]
      if (!d) return
      this.dialog = { visible: true, reasonLabel: '原因', reasonPlaceholder: '', ...d }
    },
    async onDialogConfirm(payload) {
      const reason = (payload && payload.reason) || ''
      const id = this.selected.caseId
      const a = this.dialog.action
      const call = {
        submit: () => studentAffairsApi.submitDiscipline(id),
        cancel: () => studentAffairsApi.cancelDiscipline(id),
        approve: () => studentAffairsApi.reviewDiscipline(id, 'APPROVE'),
        return: () => studentAffairsApi.reviewDiscipline(id, 'RETURN', reason),
        reject: () => studentAffairsApi.reviewDiscipline(id, 'REJECT', reason),
        remove: () => studentAffairsApi.submitRemoveDiscipline(id, reason),
        removeApprove: () => studentAffairsApi.reviewRemoveDiscipline(id, 'APPROVE'),
        removeReject: () => studentAffairsApi.reviewRemoveDiscipline(id, 'REJECT', reason)
      }[a]
      if (!call) return
      await this.runAction(call, {
        submit: '已提交初审', cancel: '已撤销', approve: '已审批通过', return: '已退回',
        reject: '已驳回', remove: '解除已发起', removeApprove: '解除审批已通过', removeReject: '解除已驳回'
      }[a])
      this.dialog.visible = false
    },
    openRegister() {
      this.registerModal = { visible: true, studentId: '', discType: 'WARNING', reason: '', docNo: '', error: '' }
    },
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
    },
    async submitRegister() {
      const m = this.registerModal
      if (!m.studentId) { m.error = '请选择学生'; return }
      if (!m.reason || m.reason.length < 5) { m.error = '违纪事实不少于 5 字'; return }
      const body = { studentId: String(m.studentId), discType: m.discType, reason: m.reason, docNo: m.docNo || '' }
      const ok = await this.runAction(() => studentAffairsApi.registerDiscipline(body), '处分已登记')
      if (ok) this.registerModal.visible = false
      else this.registerModal.error = this._lastErr || '登记失败'
    },
    async onReconcile() {
      this.reconciling = true
      const res = await studentAffairsApi.reconcileDiscipline()
      this.reconciling = false
      if (res.code === 0) {
        const d = res.data
        toast.info(`投影对账：生效 ${d.effectiveCases} 条 / 投影 ${d.activeProjections} 行 · ${d.consistent ? '一致 ✓' : '不一致 ✗'}`)
      } else {
        toast.error(res.message || '对账失败')
      }
    },
    async runAction(call, okMsg) {
      this.acting = true
      this._lastErr = ''
      const res = await call()
      if (res.code === 0) {
        toast.success(okMsg)
        if (res.data && res.data.caseId) this.selected = res.data
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
.dp-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}
.dp-filters {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.dp-chip {
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
.dp-chip.is-on {
  border-color: var(--primary-400);
  color: var(--primary-700);
  background: var(--primary-50);
}
.dp-chip em {
  font-style: normal;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.dp-tools {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.dp-btn {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.dp-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.dp-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.dp-btn--danger {
  background: var(--danger-600, #dc2626);
  border-color: var(--danger-600, #dc2626);
  color: #fff;
}
.dp-workspace {
  display: grid;
  grid-template-columns: minmax(300px, 380px) 1fr;
  gap: var(--space-4);
  align-items: start;
}
.dp-list {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-2);
}
.dp-queue {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.dp-qitem {
  padding: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  cursor: pointer;
}
.dp-qitem:hover {
  border-color: var(--primary-300);
}
.dp-qitem.is-active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.dp-qitem__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.dp-qitem__name {
  font-weight: 600;
  color: var(--text-primary);
}
.dp-qitem__mid {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.dp-detail {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-4);
}
.dp-dhead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.dp-dname {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.dp-refresh {
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  border-radius: var(--radius-base);
  width: 28px;
  height: 28px;
  cursor: pointer;
  color: var(--text-secondary);
}
.dp-kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-4);
  margin: 0 0 var(--space-4);
}
.dp-kv > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dp-kv--full {
  grid-column: 1 / -1;
}
.dp-kv dt {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.dp-kv dd {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.dp-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
}
.dp-terminal {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.dp-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.dp-modal {
  width: 460px;
  max-width: calc(100vw - 32px);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-lg, 0 10px 40px rgba(0, 0, 0, 0.2));
}
.dp-modal__title {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.dp-modal__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.dp-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}
.dp-field > span {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.dp-field i {
  color: var(--danger-600, #dc2626);
  font-style: normal;
}
.dp-input,
.dp-textarea {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: var(--space-2);
  outline: none;
}
.dp-textarea {
  resize: vertical;
}
.dp-err {
  margin: 0 0 var(--space-2);
  color: var(--danger-600, #dc2626);
  font-size: var(--font-size-xs);
}
.dp-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
</style>
