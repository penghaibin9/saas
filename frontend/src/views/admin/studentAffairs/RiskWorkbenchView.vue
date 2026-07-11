<template>
  <ModulePageShell
    title="风险预警处置工作台"
    subtitle="多来源风险 · 分派 / 处置 / 升级 / 关闭闭环"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="风险处置"
  >
    <div class="rk-toolbar">
      <div class="rk-filters">
        <button
          v-for="f in statusFilters"
          :key="f.key"
          type="button"
          class="rk-chip"
          :class="{ 'is-on': activeStatus === f.key }"
          @click="activeStatus = f.key"
        >
          {{ f.label }}<em>{{ f.count }}</em>
        </button>
      </div>
      <div class="rk-tools">
        <select v-model="levelFilter" class="rk-input" title="按等级筛选">
          <option value="">全部等级</option>
          <option value="CRITICAL">紧急</option>
          <option value="HIGH">高</option>
          <option value="MEDIUM">中</option>
          <option value="LOW">低</option>
        </select>
        <button type="button" class="rk-btn" :disabled="scanning" @click="onScanTimeout">
          {{ scanning ? '扫描中…' : '超时扫描' }}
        </button>
        <button type="button" class="rk-btn rk-btn--primary" @click="openCreate">建风险单</button>
      </div>
    </div>

    <div class="rk-workspace">
      <div class="rk-list">
        <LoadingState v-if="loading" text="正在加载风险记录…" />
        <ErrorState v-else-if="listError" :description="listError" @retry="loadList" />
        <EmptyState v-else-if="!filteredList.length" title="暂无风险记录" description="可点「建风险单」登记，或调整筛选条件" />
        <ul v-else class="rk-queue">
          <li
            v-for="it in filteredList"
            :key="it.riskId"
            class="rk-qitem"
            :class="{ 'is-active': selected && selected.riskId === it.riskId }"
            @click="select(it)"
          >
            <div class="rk-qitem__top">
              <span class="rk-qitem__name">{{ it.realName || ('学生#' + it.studentId) }}</span>
              <RiskTag :level="it.riskLevel" />
            </div>
            <div class="rk-qitem__mid">{{ sourceLabel(it.source) }} · {{ it.title || '（无标题）' }}</div>
            <div class="rk-qitem__meta">
              <StatusTag :type="statusType(it.status)" :label="it.statusLabel" dot />
              <span v-if="it.mentalMasked" class="rk-lock" title="心理关注·明细受限">🔒 涉密</span>
            </div>
          </li>
        </ul>
      </div>

      <div class="rk-detail">
        <EmptyState v-if="!selected" title="请从左侧选择一条风险" description="查看详情并进行分派 / 处置 / 升级 / 关闭等操作" />
        <template v-else>
          <div class="rk-dhead">
            <div>
              <h3 class="rk-dname">{{ selected.realName || ('学生#' + selected.studentId) }}</h3>
              <div class="rk-dtags">
                <RiskTag :level="selected.riskLevel" />
                <StatusTag :type="statusType(selected.status)" :label="selected.statusLabel" dot />
              </div>
            </div>
            <button type="button" class="rk-refresh" title="刷新详情" @click="reloadDetail">↻</button>
          </div>

          <dl class="rk-kv">
            <div><dt>风险来源</dt><dd>{{ sourceLabel(selected.source) }}</dd></div>
            <div><dt>学号</dt><dd>{{ selected.studentNo || '—' }}</dd></div>
            <div><dt>责任人ID</dt><dd>{{ selected.ownerId || '未分派' }}</dd></div>
            <div><dt>是否归档</dt><dd>{{ selected.isArchived ? '已归档' : '否' }}</dd></div>
            <div class="rk-kv--full"><dt>风险标题</dt><dd>{{ selected.title || '（无）' }}</dd></div>
            <div class="rk-kv--full">
              <dt>风险明细</dt>
              <dd :class="{ 'rk-masked': selected.mentalMasked }">{{ selected.detail || '（无）' }}</dd>
            </div>
          </dl>

          <div v-if="detailActions.length" class="rk-actions">
            <button
              v-for="a in detailActions"
              :key="a.key"
              type="button"
              class="rk-btn"
              :class="{ 'rk-btn--primary': a.tone === 'primary', 'rk-btn--danger': a.tone === 'danger' }"
              :disabled="acting"
              @click="onAction(a.key)"
            >
              {{ a.label }}
            </button>
          </div>
          <p v-else class="rk-terminal">该风险当前状态（{{ selected.statusLabel }}）暂无可执行操作。</p>
        </template>
      </div>
    </div>

    <!-- 通用确认（认领/处置/跟进/升级/接管/关闭/重开） -->
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

    <!-- 转办 modal -->
    <div v-if="transferModal.visible" class="rk-mask" @click.self="transferModal.visible = false">
      <div class="rk-modal">
        <h3 class="rk-modal__title">转办风险</h3>
        <p class="rk-modal__hint">转办后风险回到「已分派」，由新责任人处置。</p>
        <label class="rk-field"><span>新责任人用户ID <i>*</i></span>
          <input v-model.trim="transferModal.ownerId" class="rk-input" placeholder="填写新责任人的用户ID" />
        </label>
        <label class="rk-field"><span>转办说明</span>
          <textarea v-model.trim="transferModal.reason" class="rk-textarea" rows="3" placeholder="选填" />
        </label>
        <p v-if="transferModal.error" class="rk-err">{{ transferModal.error }}</p>
        <div class="rk-modal__foot">
          <button type="button" class="rk-btn" @click="transferModal.visible = false">取消</button>
          <button type="button" class="rk-btn rk-btn--primary" :disabled="acting" @click="submitTransfer">确认转办</button>
        </div>
      </div>
    </div>

    <!-- 建风险单 modal -->
    <div v-if="createModal.visible" class="rk-mask" @click.self="createModal.visible = false">
      <div class="rk-modal">
        <h3 class="rk-modal__title">建风险单</h3>
        <div class="rk-field"><span>学生 <i>*</i></span>
          <AppStudentPicker v-model="createModal.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生" />
        </div>
        <label class="rk-field"><span>风险来源 <i>*</i></span>
          <select v-model="createModal.source" class="rk-input">
            <option v-for="s in sourceOptions" :key="s.value" :value="s.value">{{ s.label }}</option>
          </select>
        </label>
        <label class="rk-field"><span>风险等级 <i>*</i></span>
          <select v-model="createModal.riskLevel" class="rk-input">
            <option value="LOW">低</option>
            <option value="MEDIUM">中</option>
            <option value="HIGH">高</option>
            <option value="CRITICAL">紧急</option>
          </select>
        </label>
        <label class="rk-field"><span>风险标题</span>
          <input v-model.trim="createModal.title" class="rk-input" placeholder="简述风险，如「连续旷课3天」" />
        </label>
        <label class="rk-field"><span>风险明细</span>
          <textarea v-model.trim="createModal.detail" class="rk-textarea" rows="3" placeholder="选填" />
        </label>
        <p v-if="createModal.error" class="rk-err">{{ createModal.error }}</p>
        <div class="rk-modal__foot">
          <button type="button" class="rk-btn" @click="createModal.visible = false">取消</button>
          <button type="button" class="rk-btn rk-btn--primary" :disabled="acting" @click="submitCreate">建单</button>
        </div>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 风险预警处置工作台（/admin/student-affairs/risk）—— 13A P5 风险中枢。
 * 真实对接 /api/v1/student-affairs/risk/*：多来源风险登记 + 分派/处置/跟进/转办/升级/接管/关闭/重开 8 态闭环。
 * 列表端点支持 source/status/riskLevel 服务端过滤；心理(MENTAL)来源明细对非授权角色脱敏。
 * 关闭需≥1条处置记录（后端 409 拦截并透出）。分派责任人=当前登录用户（认领），转办支持指定用户ID。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppConfirmDialog, AppStatusTag, AppRiskTag, AppStudentPicker } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { currentUserFromToken } from '@/services/http/client'
import { toast } from '@/utils/toast'

const STATUS_TYPE = {
  NEW: 'warning', ASSIGNED: 'processing', PROCESSING: 'processing', FOLLOWING: 'processing',
  TRANSFERRED: 'warning', ESCALATED: 'danger', CLOSED: 'success', REOPENED: 'warning'
}
const SOURCE_LABEL = {
  LEAVE_OVERDUE: '请假逾期', ACADEMIC_WARNING: '学业预警', DORM: '宿舍异常', MENTAL: '心理关注',
  DISCIPLINE: '违纪', INTERNSHIP: '实习异常', GRADUATION_DESIGN: '毕设', EMPLOYMENT: '就业',
  FAMILY: '家庭', MANUAL: '手动登记'
}

export default {
  name: 'RiskWorkbenchView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppConfirmDialog, StatusTag: AppStatusTag, RiskTag: AppRiskTag, AppStudentPicker },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      loading: true, listError: '', list: [],
      selected: null, acting: false, scanning: false,
      activeStatus: 'ALL', levelFilter: '',
      dialog: { visible: false, action: '', title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '', reasonPlaceholder: '' },
      transferModal: { visible: false, ownerId: '', reason: '', error: '' },
      createModal: { visible: false, studentId: '', source: 'MANUAL', riskLevel: 'MEDIUM', title: '', detail: '', error: '' },
      sourceOptions: Object.entries(SOURCE_LABEL).map(([value, label]) => ({ value, label }))
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
      const c = (st) => this.list.filter((x) => x.status === st).length
      const open = this.list.filter((x) => x.status !== 'CLOSED').length
      return [
        { key: 'ALL', label: '全部', count: this.list.length },
        { key: 'OPEN', label: '在办', count: open },
        { key: 'NEW', label: '待分派', count: c('NEW') },
        { key: 'PROCESSING', label: '处置中', count: c('PROCESSING') },
        { key: 'ESCALATED', label: '已升级', count: c('ESCALATED') },
        { key: 'CLOSED', label: '已关闭', count: c('CLOSED') }
      ]
    },
    filteredList() {
      let arr = this.list
      if (this.activeStatus === 'OPEN') arr = arr.filter((x) => x.status !== 'CLOSED')
      else if (this.activeStatus !== 'ALL') arr = arr.filter((x) => x.status === this.activeStatus)
      if (this.levelFilter) arr = arr.filter((x) => x.riskLevel === this.levelFilter)
      return arr
    },
    detailActions() {
      const s = this.selected && this.selected.status
      if (!s) return []
      if (['NEW', 'REOPENED', 'TRANSFERRED'].includes(s)) return [{ key: 'assign', label: '认领处置', tone: 'primary' }]
      if (s === 'ASSIGNED') return [{ key: 'process', label: '处置', tone: 'primary' }]
      if (s === 'PROCESSING') {
        return [
          { key: 'process', label: '追加处置', tone: 'primary' },
          { key: 'follow', label: '转跟进', tone: 'default' },
          { key: 'transfer', label: '转办', tone: 'default' },
          { key: 'escalate', label: '升级', tone: 'danger' },
          { key: 'close', label: '关闭', tone: 'default' }
        ]
      }
      if (s === 'FOLLOWING') {
        return [
          { key: 'transfer', label: '转办', tone: 'default' },
          { key: 'escalate', label: '升级', tone: 'danger' },
          { key: 'close', label: '关闭', tone: 'primary' }
        ]
      }
      if (s === 'ESCALATED') {
        return [
          { key: 'takeover', label: '接管', tone: 'primary' },
          { key: 'close', label: '关闭', tone: 'default' }
        ]
      }
      if (s === 'CLOSED') return [{ key: 'reopen', label: '复发重开', tone: 'default' }]
      return []
    }
  },
  created() {
    this.loadList()
  },
  methods: {
    sourceLabel(s) {
      return SOURCE_LABEL[s] || s || '—'
    },
    statusType(s) {
      return STATUS_TYPE[s] || 'default'
    },
    async loadList() {
      this.loading = true
      this.listError = ''
      const res = await studentAffairsApi.getRisks({ page: 1, pageSize: 200 })
      this.loading = false
      if (res.code === 0 && res.data) {
        this.list = res.data.items || []
        if (this.selected) {
          const hit = this.list.find((x) => x.riskId === this.selected.riskId)
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
      const res = await studentAffairsApi.getRiskDetail(this.selected.riskId)
      if (res.code === 0 && res.data) this.selected = res.data
      else toast.error(res.message || '刷新详情失败')
    },
    onAction(key) {
      if (key === 'transfer') { this.openTransfer(); return }
      const map = {
        assign: { action: 'assign', title: '认领处置', message: '将该风险分派给你本人并进入处置。', type: 'primary', confirmText: '认领处置', requireReason: false },
        process: { action: 'process', title: '登记处置', message: '', type: 'primary', confirmText: '提交处置', requireReason: true, reasonLabel: '处置记录（≥5字）', reasonPlaceholder: '记录本次处置措施，不少于 5 字' },
        follow: { action: 'follow', title: '转持续跟进', message: '将该风险转入持续跟进状态。', type: 'primary', confirmText: '转跟进', requireReason: false, reasonLabel: '跟进说明', reasonPlaceholder: '选填' },
        escalate: { action: 'escalate', title: '升级风险', message: '升级后风险等级+1并进入已升级，等待上级接管。', type: 'danger', confirmText: '升级', requireReason: false, reasonLabel: '升级原因', reasonPlaceholder: '选填' },
        takeover: { action: 'takeover', title: '上级接管', message: '接管后风险回到处置中，由你继续处置。', type: 'primary', confirmText: '接管', requireReason: false, reasonLabel: '接管说明', reasonPlaceholder: '选填' },
        close: { action: 'close', title: '关闭风险', message: '关闭需已有至少一条处置记录，结论将写入学生 360。', type: 'primary', confirmText: '关闭风险', requireReason: true, reasonLabel: '关闭结论（≥5字）', reasonPlaceholder: '填写处置结论，不少于 5 字' },
        reopen: { action: 'reopen', title: '复发重开', message: '将已关闭的风险重新打开。', type: 'warning', confirmText: '重开', requireReason: false, reasonLabel: '重开原因', reasonPlaceholder: '选填' }
      }
      const d = map[key]
      if (!d) return
      this.dialog = { visible: true, reasonLabel: '原因', reasonPlaceholder: '', ...d }
    },
    async onDialogConfirm(payload) {
      const reason = (payload && payload.reason) || ''
      const id = this.selected.riskId
      const a = this.dialog.action
      const call = {
        assign: () => {
          const uid = this.myUserId()
          if (!uid) return Promise.resolve({ code: 1, data: null, message: '无法识别你的数字用户ID，请改用「转办」指定责任人' })
          return studentAffairsApi.assignRisk(id, uid)
        },
        process: () => studentAffairsApi.processRisk(id, reason),
        follow: () => studentAffairsApi.followRisk(id, reason),
        escalate: () => studentAffairsApi.escalateRisk(id, reason),
        takeover: () => studentAffairsApi.takeoverRisk(id, reason),
        close: () => studentAffairsApi.closeRisk(id, reason),
        reopen: () => studentAffairsApi.reopenRisk(id, reason)
      }[a]
      if (!call) return
      await this.runAction(call, {
        assign: '已认领并分派给你', process: '处置已登记', follow: '已转持续跟进',
        escalate: '风险已升级', takeover: '已接管', close: '风险已关闭', reopen: '风险已重开'
      }[a])
      this.dialog.visible = false
    },
    myUserId() {
      // 真实登录 token userId 形如 "db-5"（后端 int(owner_id) 需数字）；抽出末尾数字=真实 t_user.id。
      const u = currentUserFromToken()
      const raw = String((u && (u.userId || u.id)) || '')
      const m = raw.match(/(\d+)$/)
      return m ? m[1] : ''
    },
    openTransfer() {
      this.transferModal = { visible: true, ownerId: '', reason: '', error: '' }
    },
    async submitTransfer() {
      if (!this.transferModal.ownerId) { this.transferModal.error = '请填写新责任人用户ID'; return }
      const ok = await this.runAction(
        () => studentAffairsApi.transferRisk(this.selected.riskId, this.transferModal.ownerId, this.transferModal.reason),
        '已转办'
      )
      if (ok) this.transferModal.visible = false
      else this.transferModal.error = this._lastErr || '转办失败'
    },
    openCreate() {
      this.createModal = { visible: true, studentId: '', source: 'MANUAL', riskLevel: 'MEDIUM', title: '', detail: '', error: '' }
    },
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
    },
    async submitCreate() {
      const m = this.createModal
      if (!m.studentId) { m.error = '请选择学生'; return }
      const body = {
        studentId: String(m.studentId), source: m.source, riskLevel: m.riskLevel,
        title: m.title || '', detail: m.detail || ''
      }
      const ok = await this.runAction(() => studentAffairsApi.createRisk(body), '风险单已创建')
      if (ok) this.createModal.visible = false
      else this.createModal.error = this._lastErr || '建单失败'
    },
    async onScanTimeout() {
      this.scanning = true
      const res = await studentAffairsApi.scanRiskTimeout()
      this.scanning = false
      if (res.code === 0) {
        toast.info(`超时扫描完成：自动升级 ${res.data.escalated} 条`)
        this.loadList()
      } else {
        toast.error(res.message || '扫描失败')
      }
    },
    async runAction(call, okMsg) {
      this.acting = true
      this._lastErr = ''
      const res = await call()
      if (res.code === 0) {
        toast.success(okMsg)
        if (res.data && res.data.riskId) this.selected = res.data
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
.rk-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}
.rk-filters {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.rk-chip {
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
.rk-chip.is-on {
  border-color: var(--primary-400);
  color: var(--primary-700);
  background: var(--primary-50);
}
.rk-chip em {
  font-style: normal;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.rk-tools {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.rk-btn {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.rk-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.rk-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.rk-btn--danger {
  background: var(--danger-600, #dc2626);
  border-color: var(--danger-600, #dc2626);
  color: #fff;
}
.rk-workspace {
  display: grid;
  grid-template-columns: minmax(300px, 380px) 1fr;
  gap: var(--space-4);
  align-items: start;
}
.rk-list {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-2);
}
.rk-queue {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.rk-qitem {
  padding: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  cursor: pointer;
}
.rk-qitem:hover {
  border-color: var(--primary-300);
}
.rk-qitem.is-active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.rk-qitem__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.rk-qitem__name {
  font-weight: 600;
  color: var(--text-primary);
}
.rk-qitem__mid {
  margin-top: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rk-qitem__meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-top: var(--space-1);
}
.rk-lock {
  font-size: var(--font-size-xs);
  color: var(--danger-600, #dc2626);
}
.rk-detail {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-4);
}
.rk-dhead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.rk-dname {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.rk-dtags {
  display: flex;
  gap: var(--space-2);
}
.rk-refresh {
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  border-radius: var(--radius-base);
  width: 28px;
  height: 28px;
  cursor: pointer;
  color: var(--text-secondary);
}
.rk-kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-4);
  margin: 0 0 var(--space-4);
}
.rk-kv > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rk-kv--full {
  grid-column: 1 / -1;
}
.rk-kv dt {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.rk-kv dd {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.rk-masked {
  color: var(--text-tertiary);
  font-style: italic;
}
.rk-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
}
.rk-terminal {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.rk-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.rk-modal {
  width: 460px;
  max-width: calc(100vw - 32px);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-lg, 0 10px 40px rgba(0, 0, 0, 0.2));
}
.rk-modal__title {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.rk-modal__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.rk-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}
.rk-field > span {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.rk-field i {
  color: var(--danger-600, #dc2626);
  font-style: normal;
}
.rk-input,
.rk-textarea {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: var(--space-2);
  outline: none;
}
.rk-textarea {
  resize: vertical;
}
.rk-err {
  margin: 0 0 var(--space-2);
  color: var(--danger-600, #dc2626);
  font-size: var(--font-size-xs);
}
.rk-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
</style>
