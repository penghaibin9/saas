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
        <AppFundingProjectPicker v-model="projectId" :options="projectSelectOptions" placeholder="（选择项目）" @change="onProjectChange" />
      </label>
      <label class="fd-ctxsel"><span>批次</span>
        <AppFundingBatchPicker v-model="batchId" :options="batchSelectOptions" :query="{ projectId }" placeholder="（选择批次）" :disabled="!projectId" @change="onBatchChange" />
      </label>
      <div class="fd-ctxtools">
        <AppPermissionButton :allowed="canBtn('studentAffairs.funding.project.manage')" code="studentAffairs.funding.project.manage" variant="secondary" size="sm" @click="openProject">建项目</AppPermissionButton>
        <AppPermissionButton :allowed="canBtn('studentAffairs.funding.project.manage')" code="studentAffairs.funding.project.manage" variant="secondary" size="sm" :disabled="!projectId" @click="openBatch">建批次</AppPermissionButton>
        <AppPermissionButton :allowed="canBtn('studentAffairs.funding.publicity.manage')" code="studentAffairs.funding.publicity.manage" variant="secondary" size="sm" :loading="scanning" @click="onScan">公示扫描</AppPermissionButton>
        <AppPermissionButton :allowed="canBtn('studentAffairs.funding.create')" code="studentAffairs.funding.create" variant="primary" size="sm" :disabled="!currentBatchOpen" @click="openApply">受理申请</AppPermissionButton>
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
            <AppPermissionButton :allowed="canBtn(a.code)"
              v-for="a in detailActions"
              :key="a.key"
              :code="a.code"
              :variant="a.tone === 'primary' ? 'primary' : (a.tone === 'danger' ? 'danger' : 'secondary')"
              size="sm"
              :loading="acting"
              @click="onAction(a.key)"
            >{{ a.label }}</AppPermissionButton>
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
      :phrase-scene-key="dialogPhraseSceneKey"
      :submitting="acting"
      @confirm="onDialogConfirm"
    />

    <!-- 建项目 -->
    <AppDrawer v-model:visible="projectModal.visible" title="新建资助项目">
      <div class="sa-form">
        <AppFormItem label="项目类型" required>
          <AppSelect v-model="projectModal.projectType" :options="projectTypeOptions" />
        </AppFormItem>
        <AppFormItem label="项目名称" required>
          <AppTextInput v-model="projectModal.projectName" placeholder="如：国家励志奖学金 / 国家助学金" />
        </AppFormItem>
        <div class="fd-grid2">
          <AppFormItem label="金额（元）"><AppNumberInput v-model="projectModal.amount" :min="0" /></AppFormItem>
          <AppFormItem label="名额"><AppNumberInput v-model="projectModal.quota" :min="0" /></AppFormItem>
        </div>
        <p class="fd-modal__hint">助学金申请将硬校验困难库在库；奖学金将硬校验学籍/处分/成绩。</p>
        <AppInlineAlert v-if="projectModal.error" type="danger" :description="projectModal.error" />
      </div>
      <template #footer>
        <button type="button" class="fd-btn" @click="projectModal.visible = false">取消</button>
        <button type="button" class="fd-btn fd-btn--primary" :disabled="acting" @click="submitProject">创建</button>
      </template>
    </AppDrawer>

    <!-- 建批次 -->
    <AppDrawer v-model:visible="batchModal.visible" title="新建资助批次">
      <div class="sa-form">
        <AppFormItem label="学年" required>
          <AppTextInput v-model="batchModal.schoolYear" placeholder="如：2025-2026" />
        </AppFormItem>
        <div class="fd-grid2">
          <AppFormItem label="公示天数"><AppNumberInput v-model="batchModal.publicityDays" :min="0" placeholder="快测填 0" /></AppFormItem>
          <AppFormItem label="名额"><AppNumberInput v-model="batchModal.quota" :min="0" /></AppFormItem>
        </div>
        <label class="fd-check"><input v-model="batchModal.publish" type="checkbox" /> 立即发布（开放受理）</label>
        <AppInlineAlert v-if="batchModal.error" type="danger" :description="batchModal.error" />
      </div>
      <template #footer>
        <button type="button" class="fd-btn" @click="batchModal.visible = false">取消</button>
        <button type="button" class="fd-btn fd-btn--primary" :disabled="acting" @click="submitBatch">保存</button>
      </template>
    </AppDrawer>

    <!-- 受理申请 -->
    <AppDrawer v-model:visible="applyModal.visible" title="受理资助申请">
      <div class="sa-form">
        <AppFormItem label="学生" required>
          <AppStudentPicker v-model="applyModal.studentId" placeholder="按姓名 / 学号搜索学生" />
        </AppFormItem>
        <AppFormItem label="申请来源">
          <AppSelect v-model="applyModal.applySource" :options="applySourceOptions" />
        </AppFormItem>
        <AppFormItem label="申请金额（元）">
          <AppNumberInput v-model="applyModal.amount" :min="0" />
        </AppFormItem>
        <AppFormItem label="申请说明">
          <AppTextarea v-model="applyModal.statement" :rows="3" placeholder="选填" />
        </AppFormItem>
        <p class="fd-modal__hint">受理时将硬校验资格；不满足条件将被拒绝并提示原因。</p>
        <AppInlineAlert v-if="applyModal.error" type="danger" :description="applyModal.error" />
      </div>
      <template #footer>
        <button type="button" class="fd-btn" @click="applyModal.visible = false">取消</button>
        <button type="button" class="fd-btn fd-btn--primary" :disabled="acting" @click="submitApply">受理</button>
      </template>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
/**
 * 奖助管理工作台（/admin/student-affairs/funding）—— 13A P4 奖学金/助学金。
 * 真实对接 /api/v1/student-affairs/funding/*：项目 → 批次 → 受理(资格硬校验) → 辅导员/学院/学校三级评审 → 公示 → 获资助(进360)。
 * 助学金硬校验困难库在库，奖学金硬校验学籍/处分/成绩；不满足受理即被 409 拦截并透出原因。金额按角色脱敏。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppConfirmDialog, AppFormItem, AppInlineAlert, AppNumberInput, AppPermissionButton, AppSelect, AppStatusTag,
        AppStudentPicker, AppFundingProjectPicker, AppFundingBatchPicker, AppTextInput, AppTextarea } from '@/components/common'
import AppDrawer from '@/components/ui/AppDrawer.vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'
import { canCode } from '@/modules/studentAffairs/composables/permission'


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
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppConfirmDialog, AppDrawer, AppFormItem,
               AppInlineAlert, AppNumberInput, AppPermissionButton, AppSelect, StatusTag: AppStatusTag, AppStudentPicker, AppFundingProjectPicker, AppFundingBatchPicker, AppTextInput, AppTextarea },
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
    projectSelectOptions() {
      return this.projects.map((p) => ({ label: `${this.projectTypeLabel(p.projectType)} · ${p.projectName}`, value: p.projectId }))
    },
    batchSelectOptions() {
      return this.filteredBatches.map((b) => ({ label: `${b.schoolYear} · ${this.batchStatusLabel(b.status)}`, value: b.batchId }))
    },
    projectTypeOptions() {
      return [{ label: '奖学金', value: 'SCHOLARSHIP' }, { label: '助学金', value: 'GRANT' }]
    },
    applySourceOptions() {
      return [{ label: '自主申请', value: 'SELF' }, { label: '推荐', value: 'RECOMMEND' }]
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
    // 通用确认弹窗按当前动作切换快捷用语场景；仅“驳回”命中 sa.aid.reject（词库 §3.12：A8/B13 均归入 sa.aid.reject）
    dialogPhraseSceneKey() {
      return this.dialog.action === 'reject' ? 'sa.aid.reject' : ''
    },
    detailActions() {
      const s = this.selected && this.selected.status
      if (!s) return []
      if (FUND_NODES.includes(s)) {
        return [
          { key: 'approve', label: '审批通过', tone: 'primary', code: 'studentAffairs.funding.approve' },
          { key: 'return', label: '退回', tone: 'default', code: 'studentAffairs.funding.approve' },
          { key: 'reject', label: '驳回', tone: 'danger', code: 'studentAffairs.funding.approve' }
        ]
      }
      if (s === 'PUBLICITY') return [{ key: 'publicityConfirm', label: '确认公示通过', tone: 'primary', code: 'studentAffairs.funding.publicity.manage' }]
      return []
    }
  },
  created() {
    const q = this.$route.query || {}
    if (q.status) this.activeStatus = String(q.status)
    this.loadProjects()
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
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
      const projectName = (m.projectName || '').trim()
      if (!projectName) { m.error = '请填写项目名称'; return }
      const res = await studentAffairsApi.createFundingProject({ projectName, projectType: m.projectType, amount: m.amount || null, quota: m.quota || null })
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
      const schoolYear = (m.schoolYear || '').trim()
      if (!schoolYear) { m.error = '请填写学年'; return }
      const res = await studentAffairsApi.createFundingBatch({ projectId: String(this.projectId), schoolYear, publicityDays: Number(m.publicityDays) || 0, quota: m.quota || null, publish: !!m.publish })
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
    async submitApply() {
      const m = this.applyModal
      if (!m.studentId) { m.error = '请选择学生'; return }
      const body = { batchId: String(this.batchId), studentId: String(m.studentId), applySource: m.applySource, amount: m.amount || null, statement: (m.statement || '').trim() }
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
.fd-modal__hint {
  margin: 0 0 var(--space-3);
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
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
.sa-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
</style>
