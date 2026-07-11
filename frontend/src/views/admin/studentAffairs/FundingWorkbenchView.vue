<template>
  <ModulePageShell
    title="奖助管理工作台"
    subtitle="奖学金 / 助学金 · 资格硬校验 · 逐级评审 · 公示与发放"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="奖助管理"
  >
    <div class="fd-ctxbar">
      <label class="fd-ctxsel"><span>资助项目</span>
        <select v-model="projectId" class="fd-input" @change="onProjectChange">
          <option value="">（选择项目）</option>
          <option v-for="p in projects" :key="p.projectId" :value="p.projectId">
            {{ projectTypeLabel(p.projectType) }} · {{ p.projectName }}
          </option>
        </select>
      </label>
      <label class="fd-ctxsel"><span>批次</span>
        <select v-model="batchId" class="fd-input" :disabled="!projectId" @change="onBatchChange">
          <option value="">（选择批次）</option>
          <option v-for="b in filteredBatches" :key="b.batchId" :value="b.batchId">
            {{ b.schoolYear }} · {{ batchStatusLabel(b.status) }}
          </option>
        </select>
      </label>
      <div class="fd-ctxtools">
        <button type="button" class="fd-btn" @click="openProject">建项目</button>
        <button type="button" class="fd-btn" :disabled="!projectId" @click="openBatch">建批次</button>
        <button type="button" class="fd-btn" :disabled="scanning" @click="onScan">公示扫描</button>
        <button type="button" class="fd-btn fd-btn--primary" :disabled="!currentBatchOpen" @click="openApply">受理申请</button>
      </div>
    </div>

    <div class="fd-toolbar">
      <div class="fd-filters">
        <button
          v-for="f in statusFilters"
          :key="f.key"
          type="button"
          class="fd-chip"
          :class="{ 'is-on': activeStatus === f.key }"
          @click="activeStatus = f.key"
        >{{ f.label }}<em>{{ f.count }}</em></button>
      </div>
    </div>

    <div class="fd-workspace">
      <div class="fd-list">
        <LoadingState v-if="loading" text="正在加载资助申请…" />
        <ErrorState v-else-if="listError" :description="listError" @retry="loadApplications" />
        <EmptyState v-else-if="!batchId" title="请先选择项目与批次" description="从上方选择，或点「建项目」「建批次」" />
        <EmptyState v-else-if="!filteredList.length" title="该批次暂无申请" description="可点「受理申请」，或调整筛选" />
        <ul v-else class="fd-queue">
          <li
            v-for="it in filteredList"
            :key="it.applicationId"
            class="fd-qitem"
            :class="{ 'is-active': selected && selected.applicationId === it.applicationId }"
            @click="select(it)"
          >
            <div class="fd-qitem__top">
              <span class="fd-qitem__name">{{ it.realName || ('学生#' + it.studentId) }}</span>
              <StatusTag :type="statusType(it.status)" :label="it.statusLabel" dot />
            </div>
            <div class="fd-qitem__meta">{{ projectTypeLabel(it.projectType) }} · 金额：{{ amountText(it.amount) }}</div>
          </li>
        </ul>
      </div>

      <div class="fd-detail">
        <EmptyState v-if="!selected" title="请从左侧选择一条申请" description="查看详情、评审、公示确认" />
        <template v-else>
          <div class="fd-dhead">
            <div>
              <h3 class="fd-dname">{{ selected.realName || ('学生#' + selected.studentId) }}</h3>
              <StatusTag :type="statusType(selected.status)" :label="selected.statusLabel" dot />
            </div>
            <button type="button" class="fd-refresh" title="刷新详情" @click="reloadDetail">↻</button>
          </div>

          <dl class="fd-kv">
            <div><dt>资助类型</dt><dd>{{ projectTypeLabel(selected.projectType) }}</dd></div>
            <div><dt>申请来源</dt><dd>{{ selected.applySource === 'RECOMMEND' ? '推荐' : '自主申请' }}</dd></div>
            <div><dt>金额</dt><dd>{{ amountText(selected.amount) }}</dd></div>
            <div><dt>学号</dt><dd>{{ selected.studentNo || '—' }}</dd></div>
          </dl>
          <p v-if="selected.checkSnapshot" class="fd-snap">资格校验：{{ snapshotText(selected.checkSnapshot) }}</p>

          <div v-if="detailActions.length" class="fd-actions">
            <button
              v-for="a in detailActions"
              :key="a.key"
              type="button"
              class="fd-btn"
              :class="{ 'fd-btn--primary': a.tone === 'primary', 'fd-btn--danger': a.tone === 'danger' }"
              :disabled="acting"
              @click="onAction(a.key)"
            >{{ a.label }}</button>
          </div>
          <p v-else class="fd-terminal">该申请已处于终态（{{ selected.statusLabel }}），仅可查看。</p>
        </template>
      </div>
    </div>

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

    <!-- 建项目 modal -->
    <div v-if="projectModal.visible" class="fd-mask" @click.self="projectModal.visible = false">
      <div class="fd-modal">
        <h3 class="fd-modal__title">新建资助项目</h3>
        <label class="fd-field"><span>项目类型 <i>*</i></span>
          <select v-model="projectModal.projectType" class="fd-input">
            <option value="SCHOLARSHIP">奖学金</option>
            <option value="GRANT">助学金</option>
          </select>
        </label>
        <label class="fd-field"><span>项目名称 <i>*</i></span>
          <input v-model.trim="projectModal.projectName" class="fd-input" placeholder="如：国家励志奖学金 / 国家助学金" />
        </label>
        <div class="fd-grid2">
          <label class="fd-field"><span>金额（元）</span><input v-model.number="projectModal.amount" type="number" class="fd-input" /></label>
          <label class="fd-field"><span>名额</span><input v-model.number="projectModal.quota" type="number" class="fd-input" /></label>
        </div>
        <p class="fd-modal__hint">助学金申请将硬校验困难库在库；奖学金将硬校验学籍/处分/成绩。</p>
        <p v-if="projectModal.error" class="fd-err">{{ projectModal.error }}</p>
        <div class="fd-modal__foot">
          <button type="button" class="fd-btn" @click="projectModal.visible = false">取消</button>
          <button type="button" class="fd-btn fd-btn--primary" :disabled="acting" @click="submitProject">创建</button>
        </div>
      </div>
    </div>

    <!-- 建批次 modal -->
    <div v-if="batchModal.visible" class="fd-mask" @click.self="batchModal.visible = false">
      <div class="fd-modal">
        <h3 class="fd-modal__title">新建资助批次</h3>
        <label class="fd-field"><span>学年 <i>*</i></span><input v-model.trim="batchModal.schoolYear" class="fd-input" placeholder="如：2025-2026" /></label>
        <div class="fd-grid2">
          <label class="fd-field"><span>公示天数</span><input v-model.number="batchModal.publicityDays" type="number" min="0" class="fd-input" placeholder="快测填 0" /></label>
          <label class="fd-field"><span>名额</span><input v-model.number="batchModal.quota" type="number" class="fd-input" /></label>
        </div>
        <label class="fd-check"><input v-model="batchModal.publish" type="checkbox" /> 立即发布（开放受理）</label>
        <p v-if="batchModal.error" class="fd-err">{{ batchModal.error }}</p>
        <div class="fd-modal__foot">
          <button type="button" class="fd-btn" @click="batchModal.visible = false">取消</button>
          <button type="button" class="fd-btn fd-btn--primary" :disabled="acting" @click="submitBatch">保存</button>
        </div>
      </div>
    </div>

    <!-- 受理申请 modal -->
    <div v-if="applyModal.visible" class="fd-mask" @click.self="applyModal.visible = false">
      <div class="fd-modal">
        <h3 class="fd-modal__title">受理资助申请</h3>
        <div class="fd-field"><span>学生 <i>*</i></span>
          <AppStudentPicker v-model="applyModal.studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生" />
        </div>
        <label class="fd-field"><span>申请来源</span>
          <select v-model="applyModal.applySource" class="fd-input">
            <option value="SELF">自主申请</option>
            <option value="RECOMMEND">推荐</option>
          </select>
        </label>
        <label class="fd-field"><span>申请金额（元）</span><input v-model.number="applyModal.amount" type="number" class="fd-input" /></label>
        <label class="fd-field"><span>申请说明</span><textarea v-model.trim="applyModal.statement" class="fd-textarea" rows="3" placeholder="选填" /></label>
        <p class="fd-modal__hint">受理时将硬校验资格；不满足条件将被拒绝并提示原因。</p>
        <p v-if="applyModal.error" class="fd-err">{{ applyModal.error }}</p>
        <div class="fd-modal__foot">
          <button type="button" class="fd-btn" @click="applyModal.visible = false">取消</button>
          <button type="button" class="fd-btn fd-btn--primary" :disabled="acting" @click="submitApply">受理</button>
        </div>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
/**
 * 奖助管理工作台（/admin/student-affairs/funding）—— 13A P4 奖学金/助学金。
 * 真实对接 /api/v1/student-affairs/funding/*：项目 → 批次 → 受理(资格硬校验) → 辅导员/学院/学校三级评审 → 公示 → 获资助(进360)。
 * 助学金硬校验困难库在库，奖学金硬校验学籍/处分/成绩；不满足受理即被 409 拦截并透出原因。金额按角色脱敏。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppConfirmDialog, AppStatusTag, AppStudentPicker } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

const FUND_NODES = ['COUNSELOR_REVIEW', 'COLLEGE_REVIEW', 'SCHOOL_REVIEW']
const STATUS_TYPE = {
  DRAFT: 'default', SUBMITTED: 'processing', COUNSELOR_REVIEW: 'warning', COLLEGE_REVIEW: 'warning',
  SCHOOL_REVIEW: 'warning', PUBLICITY: 'processing', GRANTED: 'success', REJECTED: 'danger',
  RETURNED: 'warning', CANCELLED: 'default', ARCHIVED: 'default'
}
const PROJECT_TYPE = { SCHOLARSHIP: '奖学金', GRANT: '助学金' }
const BATCH_STATUS = { DRAFT: '草稿', OPEN: '开放中', CLOSED: '已截止' }

export default {
  name: 'FundingWorkbenchView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppConfirmDialog, StatusTag: AppStatusTag, AppStudentPicker },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      projects: [], batches: [], projectId: '', batchId: '',
      loading: false, listError: '', list: [], selected: null,
      acting: false, scanning: false, activeStatus: 'ALL',
      dialog: { visible: false, action: '', title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '', reasonPlaceholder: '' },
      projectModal: { visible: false, projectType: 'GRANT', projectName: '', amount: null, quota: null, error: '' },
      batchModal: { visible: false, schoolYear: '', publicityDays: 0, quota: null, publish: true, error: '' },
      applyModal: { visible: false, studentId: '', applySource: 'SELF', amount: null, statement: '', error: '' }
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    filteredBatches() {
      return this.batches.filter((b) => b.projectId === this.projectId)
    },
    currentBatchOpen() {
      const b = this.batches.find((x) => x.batchId === this.batchId)
      return !!b && b.status === 'OPEN'
    },
    statusFilters() {
      const c = (arr) => this.list.filter((x) => arr.includes(x.status)).length
      return [
        { key: 'ALL', label: '全部', count: this.list.length },
        { key: 'REVIEW', label: '评审中', count: c(FUND_NODES) },
        { key: 'PUBLICITY', label: '公示中', count: c(['PUBLICITY']) },
        { key: 'GRANTED', label: '已获资助', count: c(['GRANTED']) },
        { key: 'REJECTED', label: '已驳回', count: c(['REJECTED']) }
      ]
    },
    filteredList() {
      let arr = this.list
      if (this.activeStatus === 'REVIEW') arr = arr.filter((x) => FUND_NODES.includes(x.status))
      else if (this.activeStatus !== 'ALL') arr = arr.filter((x) => x.status === this.activeStatus)
      return arr
    },
    detailActions() {
      const s = this.selected && this.selected.status
      if (!s) return []
      if (FUND_NODES.includes(s)) {
        return [
          { key: 'approve', label: '审批通过', tone: 'primary' },
          { key: 'return', label: '退回', tone: 'default' },
          { key: 'reject', label: '驳回', tone: 'danger' }
        ]
      }
      if (s === 'PUBLICITY') return [{ key: 'publicityConfirm', label: '确认公示通过', tone: 'primary' }]
      return []
    }
  },
  created() {
    this.loadProjects()
  },
  methods: {
    projectTypeLabel(t) {
      return PROJECT_TYPE[t] || t || '—'
    },
    batchStatusLabel(s) {
      return BATCH_STATUS[s] || s
    },
    statusType(s) {
      return STATUS_TYPE[s] || 'default'
    },
    amountText(a) {
      if (a === null || a === undefined || a === '') return '—'
      return typeof a === 'number' ? `${a} 元` : String(a)
    },
    snapshotText(snap) {
      if (!snap) return ''
      if (snap.type === 'GRANT') return snap.inDifficultLibrary ? `困难库在库（${snap.aidLevel || ''}）` : '未在困难库'
      const parts = []
      parts.push(snap.statusOk ? '学籍正常' : '学籍异常')
      parts.push(snap.disciplineOk ? '无未解除处分' : '有未解除处分')
      parts.push(snap.gradeOk ? '无挂科' : '有挂科')
      return parts.join(' · ')
    },
    async loadProjects() {
      const res = await studentAffairsApi.getFundingProjects({ page: 1, pageSize: 100 })
      if (res.code === 0 && res.data) {
        this.projects = res.data.items || []
        await this.loadBatches()
        if (!this.projectId && this.projects.length) { this.projectId = this.projects[0].projectId; this.autoPickBatch() }
      } else {
        this.listError = res.message || '项目加载失败'
      }
    },
    async loadBatches() {
      const res = await studentAffairsApi.getFundingBatches({ page: 1, pageSize: 100 })
      if (res.code === 0 && res.data) this.batches = res.data.items || []
    },
    autoPickBatch() {
      const bs = this.filteredBatches
      if (bs.length) { this.batchId = bs[0].batchId; this.loadApplications() }
      else { this.batchId = ''; this.list = [] }
    },
    onProjectChange() {
      this.batchId = ''
      this.selected = null
      this.autoPickBatch()
    },
    onBatchChange() {
      this.selected = null
      if (this.batchId) this.loadApplications()
      else this.list = []
    },
    async loadApplications() {
      if (!this.batchId) return
      this.loading = true
      this.listError = ''
      const res = await studentAffairsApi.getFundingApplications({ batchId: this.batchId, page: 1, pageSize: 200 })
      this.loading = false
      if (res.code === 0 && res.data) {
        this.list = res.data.items || []
        if (this.selected) {
          const hit = this.list.find((x) => x.applicationId === this.selected.applicationId)
          if (hit) this.selected = hit
        }
      } else {
        this.listError = res.message || '申请加载失败'
      }
    },
    select(it) {
      this.selected = it
    },
    async reloadDetail() {
      if (!this.selected) return
      const res = await studentAffairsApi.getFundingDetail(this.selected.applicationId)
      if (res.code === 0 && res.data) this.selected = res.data
      else toast.error(res.message || '刷新详情失败')
    },
    onAction(key) {
      const map = {
        approve: { action: 'approve', title: '审批通过', message: '通过后推进到下一评审节点，终审通过将进入公示。', type: 'primary', confirmText: '审批通过', requireReason: false },
        return: { action: 'return', title: '退回申请', message: '退回后本次申请需重新处理。', type: 'warning', confirmText: '退回', requireReason: true, reasonLabel: '退回原因（≥5字）', reasonPlaceholder: '请说明退回原因，不少于 5 字' },
        reject: { action: 'reject', title: '驳回申请', message: '驳回为终态，本次不予资助。', type: 'danger', confirmText: '驳回', requireReason: true, reasonLabel: '驳回原因（≥5字）', reasonPlaceholder: '请说明驳回原因，不少于 5 字' },
        publicityConfirm: { action: 'publicityConfirm', title: '确认公示通过', message: '确认公示期满无异议，获得资助并写入学生 360。', type: 'primary', confirmText: '确认通过', requireReason: false }
      }
      const d = map[key]
      if (!d) return
      this.dialog = { visible: true, reasonLabel: '原因', reasonPlaceholder: '', ...d }
    },
    async onDialogConfirm(payload) {
      const reason = (payload && payload.reason) || ''
      const id = this.selected.applicationId
      const a = this.dialog.action
      const call = {
        approve: () => studentAffairsApi.reviewFunding(id, 'APPROVE'),
        return: () => studentAffairsApi.reviewFunding(id, 'RETURN', reason),
        reject: () => studentAffairsApi.reviewFunding(id, 'REJECT', reason),
        publicityConfirm: () => studentAffairsApi.confirmFundingPublicity(id)
      }[a]
      if (!call) return
      await this.runAction(call, { approve: '已审批通过', return: '已退回', reject: '已驳回', publicityConfirm: '已获资助' }[a])
      this.dialog.visible = false
    },
    openProject() {
      this.projectModal = { visible: true, projectType: 'GRANT', projectName: '', amount: null, quota: null, error: '' }
    },
    async submitProject() {
      const m = this.projectModal
      if (!m.projectName) { m.error = '请填写项目名称'; return }
      const res = await studentAffairsApi.createFundingProject({ projectName: m.projectName, projectType: m.projectType, amount: m.amount || null, quota: m.quota || null })
      if (res.code === 0) {
        toast.success('项目已创建')
        this.projectModal.visible = false
        await this.loadProjects()
        if (res.data && res.data.projectId) { this.projectId = res.data.projectId; this.onProjectChange() }
      } else { m.error = res.message || '创建失败' }
    },
    openBatch() {
      this.batchModal = { visible: true, schoolYear: '', publicityDays: 0, quota: null, publish: true, error: '' }
    },
    async submitBatch() {
      const m = this.batchModal
      if (!m.schoolYear) { m.error = '请填写学年'; return }
      const res = await studentAffairsApi.createFundingBatch({ projectId: String(this.projectId), schoolYear: m.schoolYear, publicityDays: Number(m.publicityDays) || 0, quota: m.quota || null, publish: !!m.publish })
      if (res.code === 0) {
        toast.success('批次已保存')
        this.batchModal.visible = false
        await this.loadBatches()
        if (res.data && res.data.batchId) { this.batchId = res.data.batchId; this.loadApplications() }
      } else { m.error = res.message || '保存失败' }
    },
    openApply() {
      this.applyModal = { visible: true, studentId: '', applySource: 'SELF', amount: null, statement: '', error: '' }
    },
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
    },
    async submitApply() {
      const m = this.applyModal
      if (!m.studentId) { m.error = '请选择学生'; return }
      const body = { batchId: String(this.batchId), studentId: String(m.studentId), applySource: m.applySource, amount: m.amount || null, statement: m.statement || '' }
      const ok = await this.runAction(() => studentAffairsApi.applyFunding(body), '申请已受理')
      if (ok) this.applyModal.visible = false
      else this.applyModal.error = this._lastErr || '受理失败（可能资格校验未通过）'
    },
    async onScan() {
      this.scanning = true
      const res = await studentAffairsApi.scanFundingPublicity()
      this.scanning = false
      if (res.code === 0) { toast.info(`公示扫描完成：${res.data.count} 条获资助`); this.loadApplications() }
      else toast.error(res.message || '扫描失败')
    },
    async runAction(call, okMsg) {
      this.acting = true
      this._lastErr = ''
      const res = await call()
      if (res.code === 0) {
        toast.success(okMsg)
        if (res.data && res.data.applicationId) this.selected = res.data
        else await this.reloadDetail()
        await this.loadApplications()
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
.fd-ctxbar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  padding: var(--space-3);
  margin-bottom: var(--space-3);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-lg);
}
.fd-ctxsel {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.fd-ctxtools {
  display: flex;
  gap: var(--space-2);
  margin-left: auto;
  flex-wrap: wrap;
}
.fd-toolbar {
  margin-bottom: var(--space-3);
}
.fd-filters {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.fd-chip {
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
.fd-chip.is-on {
  border-color: var(--primary-400);
  color: var(--primary-700);
  background: var(--primary-50);
}
.fd-chip em {
  font-style: normal;
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.fd-btn {
  height: 30px;
  padding: 0 var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  cursor: pointer;
}
.fd-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.fd-btn--primary {
  background: var(--primary-600);
  border-color: var(--primary-600);
  color: #fff;
}
.fd-btn--danger {
  background: var(--danger-600, #dc2626);
  border-color: var(--danger-600, #dc2626);
  color: #fff;
}
.fd-workspace {
  display: grid;
  grid-template-columns: minmax(300px, 380px) 1fr;
  gap: var(--space-4);
  align-items: start;
}
.fd-list {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-2);
}
.fd-queue {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.fd-qitem {
  padding: var(--space-3);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  cursor: pointer;
}
.fd-qitem:hover {
  border-color: var(--primary-300);
}
.fd-qitem.is-active {
  border-color: var(--primary-500);
  background: var(--primary-50);
}
.fd-qitem__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
}
.fd-qitem__name {
  font-weight: 600;
  color: var(--text-primary);
}
.fd-qitem__meta {
  margin-top: var(--space-1);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.fd-detail {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  min-height: 320px;
  padding: var(--space-4);
}
.fd-dhead {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}
.fd-dname {
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.fd-refresh {
  border: 1px solid var(--border-base);
  background: var(--bg-card);
  border-radius: var(--radius-base);
  width: 28px;
  height: 28px;
  cursor: pointer;
  color: var(--text-secondary);
}
.fd-kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-4);
  margin: 0 0 var(--space-3);
}
.fd-kv > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.fd-kv dt {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.fd-kv dd {
  margin: 0;
  font-size: var(--font-size-sm);
  color: var(--text-primary);
}
.fd-snap {
  font-size: var(--font-size-xs);
  color: var(--success-700, #15803d);
  background: var(--success-50, #f0fdf4);
  border: 1px solid var(--success-100, #dcfce7);
  border-radius: var(--radius-base);
  padding: var(--space-2);
  margin: 0 0 var(--space-3);
}
.fd-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
}
.fd-terminal {
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.fd-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.fd-modal {
  width: 460px;
  max-width: calc(100vw - 32px);
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-lg, 0 10px 40px rgba(0, 0, 0, 0.2));
}
.fd-modal__title {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-lg);
  color: var(--text-primary);
}
.fd-modal__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.fd-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  margin-bottom: var(--space-3);
}
.fd-field > span {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.fd-field i {
  color: var(--danger-600, #dc2626);
  font-style: normal;
}
.fd-grid2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}
.fd-check {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}
.fd-input,
.fd-textarea {
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  padding: var(--space-2);
  outline: none;
}
.fd-textarea {
  resize: vertical;
}
.fd-err {
  margin: 0 0 var(--space-2);
  color: var(--danger-600, #dc2626);
  font-size: var(--font-size-xs);
}
.fd-modal__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
</style>
