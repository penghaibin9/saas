<template>
  <section class="sel-special" :aria-busy="loading ? 'true' : 'false'">
    <header class="sel-special__head">
      <div>
        <h2>{{ title }}</h2>
        <p>{{ description }}</p>
      </div>
      <StatusTag :type="batchStatusType" :label="batchStatusLabel" dot />
    </header>

    <AaOperationReceipt :receipt="receipt" />
    <AppInlineAlert v-if="ruleRecoveryError" type="warning" description="待确认规则状态无法读取，已暂停保存；请恢复浏览器存储后重新进入本批次。" />
    <AppInlineAlert v-if="error" type="danger" :description="error" />
    <AppButton v-if="error && !loading && !saving" size="small" variant="ghost" @click="mode === 'rule' ? loadRule() : load()">重新读取</AppButton>
    <LoadingState v-if="loading" />

    <template v-else-if="mode === 'rule'">
      <div class="sel-special__facts">
        <article><span>当前批次</span><strong>{{ batch.batchName }}</strong></article>
        <article><span>适用范围</span><strong>{{ scopeText }}</strong></article>
        <article><span>规则版本</span><strong>{{ ruleVersion }}</strong></article>
        <article><span>当前轮次</span><strong>{{ roundText }}</strong></article>
      </div>
      <div class="sel-special__form">
        <AppFormItem label="累计选课学分上限" required>
          <AppNumberInput v-model="ruleDraft.maxCredits" :min="0" :disabled="saving || !ruleWritable" />
        </AppFormItem>
        <p class="sel-special__hint">0 表示不设置批次级学分上限。最终能否选课，仍由提交前的正式预检查和系统校验决定。</p>
        <AppInlineAlert v-if="!ruleWritable" type="warning" :description="canManageRule ? '当前批次已经进入开选或后续阶段，规则只读；如需调整须新建批次或走正式变更流程。' : '当前账号只可查阅正式规则；规则调整由有权限的选课管理岗办理。'" />
        <AppInlineAlert v-else-if="pendingRule" type="warning" description="上次保存结果尚未由正式批次确认。当前只允许查询正式规则，系统不会自动重复提交保存请求。" />
        <div class="sel-special__actions">
          <AppButton v-if="pendingRule" :loading="loading" @click="loadRule">查询正式规则</AppButton>
          <AppButton v-if="canManageRule" variant="primary" :loading="saving" :disabled="!ruleWritable || !!pendingRule || !ruleChanged" @click="saveRule">{{ pendingRule ? '等待正式确认' : ruleChanged ? '保存本批次规则' : '规则未变化' }}</AppButton>
        </div>
      </div>
    </template>

    <template v-else-if="mode === 'reselect'">
      <AppInlineAlert
        v-if="batch.status !== 'CLOSED'"
        type="warning"
        :description="['LOCKED', 'ARCHIVED'].includes(batch.status) ? '本批次补选已结束，请在选课结果或归档中核对名单。' : '补选指引在批次截止后生成；当前请先完成正常选课。'"
      />
      <template v-else-if="reselectGuide">
        <div class="sel-special__facts">
          <article><span>取消课程</span><strong>{{ reselectGuide.cancelledPagination.total }}</strong></article>
          <article><span>仍可补选课程</span><strong>{{ reselectGuide.availablePagination.total }}</strong></article>
          <article><span>批次状态</span><strong>{{ batchStatusLabel }}</strong></article>
        </div>
        <section class="sel-special__block">
          <h3>取消课程</h3>
          <p>核对取消课程及受影响学生，再通知学生查看本人可选课程。</p>
          <EmptyState v-if="!cancelledCourses.length" title="没有取消课程" description="当前批次没有触发补选的课程。" />
          <DataTable :columns="courseColumns" :rows="cancelledCourses" row-key="selectionCourseId" :pagination="reselectGuide.cancelledPagination" @page-change="changeCancelledPage">
            <template #cell-course="{ row }"><strong>{{ row.courseName }}</strong><small>{{ row.courseCode || '课程代码未提供' }}</small></template>
            <template #cell-capacity="{ row }">{{ row.selectedCount ?? '—' }} / {{ row.capacity ?? '—' }}</template>
            <template #cell-state="{ row }"><StatusTag type="warning" :label="row.statusLabel || '课程已取消'" dot /></template>
          </DataTable>
        </section>
        <section class="sel-special__block">
          <h3>受影响选课记录</h3>
          <p>每取消一门课程可在本批次补选一门；成功后关联替代记录并结束该次补选资格。历史未关联记录仍需核对。</p>
          <EmptyState v-if="!affectedRecords.length" title="当前范围没有受影响记录" description="学生身份按管理范围或本人授课关系返回。" />
          <DataTable :columns="affectedColumns" :rows="affectedRecords" row-key="recordId" :pagination="affectedPagination" @page-change="changeAffectedPage">
            <template #cell-student="{ row }"><strong>{{ row.studentName }}</strong><small>{{ row.studentNo }}</small></template>
            <template #cell-state="{ row }"><StatusTag :type="row.resolutionStatus === 'REPLACED' ? 'success' : 'warning'" :label="row.resolutionStatus === 'REPLACED' ? '已完成补选' : '待补选 / 待核对'" /></template>
            <template #cell-replacement="{ row }">{{ row.replacementCourseName || (row.replacementRecordId ? '替代记录待核对' : '尚未关联替代课程') }}</template>
            <template #cell-next="{ row }">{{ row.nextOwner }}<small>{{ row.note }}</small></template>
          </DataTable>
        </section>
        <section class="sel-special__block">
          <h3>可补选课程</h3>
          <p>余量用于说明当前读取时点的资源情况，不作为补选成功判断。学生提交后仍须重新读取正式记录。</p>
          <EmptyState v-if="!availableCourses.length" title="暂无可补选课程" description="请由选课管理岗补充供给或发布后续安排。" />
          <DataTable :columns="courseColumns" :rows="availableCourses" row-key="selectionCourseId" :pagination="reselectGuide.availablePagination" @page-change="changeAvailablePage">
            <template #cell-course="{ row }"><strong>{{ row.courseName }}</strong><small>{{ row.courseCode || '课程代码未提供' }}</small></template>
            <template #cell-capacity="{ row }">{{ row.selectedCount ?? '—' }} / {{ row.capacity ?? '—' }}</template>
            <template #cell-state><StatusTag type="success" label="可供补选" dot /></template>
          </DataTable>
        </section>
      </template>
    </template>

    <template v-else>
      <div class="sel-special__search">
        <AppFormItem label="按学号核对">
          <AppTextInput v-model="studentNo" placeholder="留空查看本批次汇总" :disabled="loading" @keyup.enter="searchConflict" />
        </AppFormItem>
        <AppButton variant="primary" :disabled="loading" @click="searchConflict">查询冲突</AppButton>
      </div>
      <template v-if="conflictReport">
        <div class="sel-special__facts">
          <article><span>冲突课程</span><strong>{{ conflictSummary.length }}</strong></article>
          <article><span>拒绝记录</span><strong>{{ conflictReport.total ?? '—' }}</strong></article>
          <article><span>查询范围</span><strong>{{ conflictStudentNo || '当前批次全部可见范围' }}</strong></article>
        </div>
        <section class="sel-special__block">
          <h3>冲突汇总</h3>
          <EmptyState v-if="!conflictSummary.length" title="未发现冲突记录" description="这是本次正式查询结果，不代表后续提交一定通过。" />
          <DataTable v-else :columns="summaryColumns" :rows="conflictSummary" row-key="courseName" />
        </section>
        <section class="sel-special__block">
          <h3>冲突明细</h3>
          <DataTable :columns="conflictColumns" :rows="conflictItems" row-key="rowKey" :pagination="conflictPagination" @page-change="changeConflictPage" />
        </section>
      </template>
    </template>
  </section>
</template>

<script>
import { matchPermission } from '@/config/navPlan'
import { DataTable, EmptyState, LoadingState, StatusTag } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppFormItem, AppInlineAlert, AppNumberInput, AppTextInput } from '@/components/common'
import { academicAffairsSelectionApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import AaOperationReceipt from './AaOperationReceipt.vue'
import { isConflictResult, isDeniedResult } from './resultState'
import { currentUserFromToken } from '@/services/http/client'
import { academicIdentity } from '../../academicFlowContext.js'

const STATUS_LABEL = { DRAFT: '草稿', PUBLISHED: '已发布', OPEN: '选课中', CLOSED: '已截止', LOCKED: '已锁定', ARCHIVED: '已归档' }

export default {
  name: 'AaSelectionSpecialWorkspace',
  components: { AaOperationReceipt, AppButton, AppFormItem, AppInlineAlert, AppNumberInput, AppTextInput, DataTable, EmptyState, LoadingState, StatusTag },
  props: {
    ctx: { type: Object, required: true },
    mode: { type: String, required: true },
    batch: { type: Object, required: true },
    rounds: { type: Array, default: () => [] }
  },
  emits: ['batch-updated', 'denied'],
  data() {
    return {
      disposed: false, requestSeq: 0, loading: false, saving: false, error: '', receipt: null, pendingRule: null, ruleRecoveryError: false,
      ruleDraft: { maxCredits: 0 }, reselectGuide: null, affectedPage: 1, cancelledPage: 1, availablePage: 1, conflictReport: null, studentNo: '', conflictStudentNo: '', conflictPage: 1,
      affectedColumns: [{ key: 'student', title: '受影响学生' }, { key: 'courseName', title: '原选课程' }, { key: 'replacement', title: '替代课程' }, { key: 'state', title: '正式状态 / 处理结果' }, { key: 'next', title: '下一责任 / 核对事项' }],
      courseColumns: [{ key: 'course', title: '课程' }, { key: 'teacherName', title: '授课教师' }, { key: 'capacity', title: '已选 / 容量' }, { key: 'state', title: '状态' }],
      summaryColumns: [{ key: 'courseName', title: '课程' }, { key: 'conflictRejectCount', title: '冲突拒绝次数' }],
      conflictColumns: [{ key: 'occurredAt', title: '发生时间' }, { key: 'courseName', title: '候选课程' }, { key: 'detail', title: '冲突情况' }]
    }
  },
  computed: {
    eyebrow() { return { rule: '选课规则', reselect: '补选收口', conflict: '冲突检测' }[this.mode] || '选课管理' },
    title() { return { rule: '规则与适用范围', reselect: '取消课程与补选 · 责任队列', conflict: '冲突与可解决路径' }[this.mode] || '选课管理' },
    description() { return { rule: '核对适用范围与学分上限，开选后规则只读。', reselect: '截止后核对取消课程、受影响学生及剩余名额。', conflict: '查看学生提交选课时被拒绝的时间冲突记录。' }[this.mode] || '' },
    batchStatusLabel() { return STATUS_LABEL[this.batch.status] || '状态待确认' },
    batchStatusType() { return ['LOCKED', 'ARCHIVED'].includes(this.batch.status) ? 'default' : this.batch.status === 'OPEN' ? 'success' : this.batch.status === 'CLOSED' ? 'warning' : 'primary' },
    canManageRule() { return matchPermission(this.ctx.permissionPatterns || [], 'academicAffairs.selection.rule.manage') },
    ruleWritable() { return this.canManageRule && !this.ruleRecoveryError && ['DRAFT', 'PUBLISHED'].includes(this.batch.status) },
    scopeText() {
      const scope = this.batch.applyScope
      if (!scope) return '当前批次正式范围'
      if (Array.isArray(scope)) return `${scope.length} 个范围对象`
      if (scope.scopeName || scope.name) return scope.scopeName || scope.name
      const parts = [['collegeIds', '个学院'], ['majorIds', '个专业'], ['gradeYears', '个年级'], ['classIds', '个行政班']]
        .filter(([key]) => Array.isArray(scope[key]) && scope[key].length)
        .map(([key, label]) => `${scope[key].length} ${label}`)
      return parts.join('、') || '全校学生（仍需满足学籍与选课条件）'
    },
    ruleVersion() { return this.batch.rule?.version ? `第 ${this.batch.rule.version} 版` : '随当前批次保存' },
    roundText() { const active = this.rounds.find(row => row.status === 'OPEN'); return active ? `第${active.roundNo}轮 · ${active.roundName}` : this.rounds.length ? `${this.rounds.length} 个轮次，当前无开放轮次` : '系统未提供正式轮次' },
    ruleChanged() { return Number(this.ruleDraft.maxCredits || 0) !== Number(this.batch.rule?.maxCredits || 0) },
    cancelledCourses() { return this.reselectGuide?.cancelledCourses || [] },
    availableCourses() { return this.reselectGuide?.availableCourses || [] },
    affectedRecords() { return this.reselectGuide?.affectedRecords?.items || [] },
    affectedPagination() { return { page: this.affectedPage, pageSize: 20, total: this.reselectGuide?.affectedRecords?.total ?? 0 } },
    conflictSummary() { return this.conflictReport?.summary || [] },
    conflictItems() { return (this.conflictReport?.items || []).map((row, index) => ({ ...row, rowKey: `${this.conflictPage}-${index}` })) },
    conflictPagination() { return { page: this.conflictPage, pageSize: 20, total: this.conflictReport?.total ?? 0 } }
  },
  watch: {
    mode: 'resetAndLoad',
    'batch.batchId': 'resetAndLoad'
  },
  created() { this.resetAndLoad() },
  beforeUnmount() { this.disposed = true; this.requestSeq += 1 },
  methods: {
    pendingRuleKey() { return `aa-selection-rule-pending:${academicIdentity(currentUserFromToken(), this.ctx)}:${this.batch.batchId}` },
    storePendingRule(value) {
      try { sessionStorage.setItem(this.pendingRuleKey(), JSON.stringify(value)); this.pendingRule = value; return true }
      catch { this.error = '无法保存待确认操作，请恢复浏览器存储后再办理'; return false }
    },
    clearPendingRule() {
      try { sessionStorage.removeItem(this.pendingRuleKey()); this.pendingRule = null; return true }
      catch { this.error = '正式结果已读取，但待确认标记尚未清除，请继续查询'; return false }
    },
    changeCancelledPage(page) { if (this.loading) return; this.cancelledPage = page; return this.load() },
    changeAvailablePage(page) { if (this.loading) return; this.availablePage = page; return this.load() },
    changeAffectedPage(page) { if (this.loading) return; this.affectedPage = page; this.load() },
    searchConflict() { if (this.loading) return; this.conflictPage = 1; this.conflictStudentNo = this.studentNo.trim(); this.load() },
    changeConflictPage(page) { if (this.loading) return; this.conflictPage = page; this.load() },
    resetAndLoad() {
      this.ruleRecoveryError = false
      this.cancelledPage = 1; this.availablePage = 1
      this.affectedPage = 1
      this.requestSeq += 1; this.loading = false; this.saving = false; this.error = ''; this.receipt = null; this.pendingRule = null; this.reselectGuide = null; this.conflictReport = null
      this.conflictPage = 1; this.conflictStudentNo = ''; this.studentNo = ''
      this.ruleDraft = { maxCredits: Number(this.batch.rule?.maxCredits || 0) }
      if (this.mode === 'rule') {
        try {
          const pending = JSON.parse(sessionStorage.getItem(this.pendingRuleKey()) || 'null')
          if (pending) {
            if (String(pending.batchId) !== String(this.batch.batchId) || !Number.isFinite(pending.requestedMaxCredits) || !Number.isFinite(pending.beforeMaxCredits)) throw Error('invalid pending rule')
            this.pendingRule = pending; this.ruleDraft.maxCredits = pending.requestedMaxCredits
          }
        } catch { this.ruleRecoveryError = true; this.error = '无法读取待确认规则，请恢复浏览器存储后再保存' }
      }
      if (this.mode === 'rule') this.loadRule()
      else this.load()
    },
    clearDenied(message) {
      this.affectedPage = 1
      this.requestSeq += 1; this.loading = false; this.saving = false; this.pendingRule = null; this.reselectGuide = null; this.conflictReport = null; this.receipt = null
      this.conflictPage = 1; this.conflictStudentNo = ''; this.studentNo = ''
      this.error = message || '无权读取当前批次数据，已清除先前显示内容'
      this.$emit('denied', this.error)
    },
    requestCurrent(seq, batchId, mode) {
      return !this.disposed && seq === this.requestSeq && String(batchId) === String(this.batch?.batchId) && mode === this.mode
    },
    exceptionResult(error, fallback) {
      return { code: error?.code || 503001, status: error?.status, bizCode: error?.bizCode, message: error?.message || fallback }
    },
    async load() {
      if (!this.batch?.batchId || this.loading || this.mode === 'rule') return
      if (this.mode === 'reselect' && this.batch.status !== 'CLOSED') return
      const seq = ++this.requestSeq, batchId = this.batch.batchId, mode = this.mode
      this.loading = true; this.error = ''
      if (mode === 'reselect') this.reselectGuide = null
      else this.conflictReport = null
      try {
        const result = mode === 'reselect' ? await api.reselectGuide(batchId, { page: this.affectedPage, pageSize: 20, cancelledPage: this.cancelledPage, availablePage: this.availablePage }) : await api.conflictReport(batchId, this.conflictStudentNo, { page: this.conflictPage, pageSize: 20 })
        if (!this.requestCurrent(seq, batchId, mode)) return
        if (result.code === 0) {
          if (mode === 'reselect') {
            const affected = result.data?.affectedRecords
            const validPage = (pagination, expected) => pagination?.page === expected && pagination.pageSize === 20 && Number.isSafeInteger(pagination.total) && pagination.total >= 0
            if (!validPage(result.data?.cancelledPagination, this.cancelledPage) || !validPage(result.data?.availablePagination, this.availablePage)) { this.error = '补选课程分页信息不匹配，请重新读取'; return }
            if (String(result.data?.batchId) !== String(batchId) || !Array.isArray(affected?.items) || !Number.isSafeInteger(affected?.total) || affected.total < 0 || affected.page !== this.affectedPage) {
              this.error = '补选指引的对象或分页信息未完整返回，请重新读取'; return
            }
            this.reselectGuide = result.data
          }
          else {
            if (String(result.data?.batchId) !== String(batchId) || !Array.isArray(result.data?.items) || !Number.isSafeInteger(result.data?.total) || result.data.total < 0) {
              this.error = '冲突报告的批次或分页信息不匹配，请重新查询'; return
            }
            this.conflictReport = result.data
          }
          return
        }
        if (isDeniedResult(result)) return this.clearDenied(result.message)
        this.error = result.message || (mode === 'reselect' ? '补选指引读取失败，请重试' : '冲突记录读取失败，请重试')
      } catch (exception) {
        if (!this.requestCurrent(seq, batchId, mode)) return
        const failure = this.exceptionResult(exception, mode === 'reselect' ? '补选指引读取失败，请重试' : '冲突记录读取失败，请重试')
        if (isDeniedResult(failure)) return this.clearDenied(failure.message)
        this.error = failure.message
      } finally {
        if (this.requestCurrent(seq, batchId, mode)) this.loading = false
      }
    },
    async loadRule() {
      if (!this.batch?.batchId || this.loading || this.saving || this.mode !== 'rule') return
      const seq = ++this.requestSeq, batchId = this.batch.batchId, mode = this.mode
      this.loading = true; this.error = ''
      try {
        const formal = await api.getBatch(batchId)
        if (!this.requestCurrent(seq, batchId, mode)) return
        if (isDeniedResult(formal)) return this.clearDenied(formal.message)
        if (formal.code !== 0 || String(formal.data?.batchId) !== String(batchId)) {
          this.error = formal.message || '正式批次规则读取失败，请重试'
          return
        }
        const formalMax = Number(formal.data?.rule?.maxCredits || 0)
        this.$emit('batch-updated', formal.data)
        if (!this.pendingRule) {
          this.ruleDraft.maxCredits = formalMax
          return
        }
        if (formalMax === this.pendingRule.requestedMaxCredits && this.pendingRule.beforeMaxCredits !== this.pendingRule.requestedMaxCredits) {
          this.receipt = { title: '规则保存结果已通过正式批次确认', object: `${formal.data.batchName}（${batchId}）`, status: `学分上限 ${formalMax || '不限制'}`, time: formal.data.updatedAt || '', next: '下一步：核对正式轮次和课程供给，再按批次状态进入发布或开选。' }
          if (!this.clearPendingRule()) return
          this.ruleDraft.maxCredits = formalMax
        } else {
          this.error = '正式规则仍未匹配上次请求；系统不会自动重复保存，请稍后继续查询。'
        }
      } catch (exception) {
        if (!this.requestCurrent(seq, batchId, mode)) return
        const failure = this.exceptionResult(exception, '正式批次规则读取失败，请重试')
        if (isDeniedResult(failure)) return this.clearDenied(failure.message)
        this.error = failure.message
      } finally {
        if (this.requestCurrent(seq, batchId, mode)) this.loading = false
      }
    },
    async saveRule() {
      if (!this.ruleWritable || this.ruleRecoveryError || this.loading || this.saving || this.pendingRule || !this.ruleChanged) return
      const seq = ++this.requestSeq, batchId = this.batch.batchId, mode = this.mode
      const requestedMaxCredits = Number(this.ruleDraft.maxCredits || 0)
      if (!Number.isFinite(requestedMaxCredits) || requestedMaxCredits < 0) { this.error = '选课学分上限须为不小于零的有效数字'; return }
      this.saving = true; this.error = ''; this.receipt = null
      try {
        const before = await api.getBatch(batchId)
        if (!this.requestCurrent(seq, batchId, mode)) return
        if (isDeniedResult(before)) return this.clearDenied(before.message)
        if (before.code !== 0 || String(before.data?.batchId) !== String(batchId)) {
          this.error = before.message || '保存前无法读取正式批次，未发送保存请求'
          return
        }
        if (!['DRAFT', 'PUBLISHED'].includes(before.data.status)) {
          this.error = '批次状态已变化，当前规则只读；输入已保留，请重新核对。'
          this.$emit('batch-updated', before.data)
          return
        }
        const beforeMaxCredits = Number(before.data?.rule?.maxCredits || 0)
        if (beforeMaxCredits !== Number(this.batch.rule?.maxCredits || 0)) {
          this.error = '选课规则已被其他人员修改，输入已保留，请核对最新规则后再保存。'
          this.$emit('batch-updated', before.data)
          return
        }
        if (beforeMaxCredits === requestedMaxCredits) {
          this.ruleDraft.maxCredits = beforeMaxCredits
          this.$emit('batch-updated', before.data)
          return
        }
        if (!this.canManageRule) return
        const requested = { ...before.data.rule, maxCredits: requestedMaxCredits }
        if (!this.storePendingRule({ batchId, beforeMaxCredits, requestedMaxCredits })) return
        let result
        try { result = await api.saveRule(batchId, requested, before.data.rule || {}) }
        catch (exception) { result = this.exceptionResult(exception, '规则保存请求结果未知') }
        if (!this.requestCurrent(seq, batchId, mode)) return
        let formal
        try { formal = await api.getBatch(batchId) }
        catch (exception) { formal = this.exceptionResult(exception, '正式规则读取失败') }
        if (!this.requestCurrent(seq, batchId, mode)) return
        if (isDeniedResult(result) || isDeniedResult(formal)) return this.clearDenied(result.message || formal.message)
        const exactFormal = formal.code === 0 && String(formal.data?.batchId) === String(batchId)
        const formalMax = exactFormal ? Number(formal.data?.rule?.maxCredits || 0) : null
        const knownRejected = isConflictResult(result) || (result.code !== 0 && result.bizCode && Number(result.code) !== 503001)
        if (!knownRejected && exactFormal && formalMax === requestedMaxCredits) {
          if (!this.clearPendingRule()) return
          this.ruleDraft.maxCredits = formalMax
          this.receipt = { title: '规则已保存并由正式批次确认', object: `${formal.data.batchName}（${batchId}）`, status: `学分上限 ${formalMax || '不限制'}`, time: formal.data.updatedAt || '', next: '下一步：核对正式轮次和课程供给，再按批次状态进入发布或开选。' }
          this.$emit('batch-updated', formal.data)
          return
        }
        if (knownRejected) {
          if (!this.clearPendingRule()) return
          if (exactFormal) this.$emit('batch-updated', formal.data)
          this.error = `${result.message || '批次数据已变化'}；输入已保留，请重新核对后再提交。`
          this.receipt = { pending: true, title: '规则未保存', object: `${this.batch.batchName}（${batchId}）`, status: exactFormal ? `当前正式学分上限 ${formalMax || '不限制'}` : '正式规则读取失败', time: '', next: '请核对当前批次；系统没有自动重复提交保存请求。' }
          return
        }
        this.error = formal.message || result.message || '规则保存结果待确认'
        this.receipt = { pending: true, title: '规则保存结果待确认', object: `${this.batch.batchName}（${batchId}）`, status: exactFormal ? `当前正式学分上限 ${formalMax || '不限制'}` : '尚未获得匹配的正式规则', time: '', next: '当前只允许查询正式规则；确认前不要重复提交。' }
      } finally {
        if (this.requestCurrent(seq, batchId, mode)) this.saving = false
      }
    }
  }
}
</script>

<style scoped>
.sel-special{display:grid;gap:14px}.sel-special__head{display:flex;justify-content:space-between;align-items:center;gap:20px;padding:14px 16px;border:1px solid #dfe7f1;border-radius:12px 12px 0 0;background:#fff}.sel-special__head h2{margin:0 0 5px;font-size:15px;color:var(--text-primary)}.sel-special__head p,.sel-special__block p,.sel-special__hint{margin:0;color:var(--text-secondary);font-size:12px;line-height:1.65}.sel-special__facts{display:flex;align-items:stretch;gap:0;border:1px solid #dfe7f1;border-radius:10px;background:#fff}.sel-special__facts article{flex:1;min-width:0;padding:12px 16px;border-right:1px solid #edf1f6}.sel-special__facts article:last-child{border-right:0}.sel-special__facts span{display:block;color:var(--text-tertiary);font-size:11px}.sel-special__facts strong{display:block;margin-top:5px;overflow:hidden;color:var(--text-primary);font-size:13px;text-overflow:ellipsis;white-space:nowrap}.sel-special__form,.sel-special__block{padding:16px;border:1px solid #dfe7f1;border-radius:12px;background:#fff}.sel-special__block h3{margin:0 0 6px;font-size:15px}.sel-special__block :deep(.data-table){margin-top:12px}.sel-special__actions{display:flex;justify-content:flex-end;margin-top:14px}.sel-special__search{display:flex;align-items:flex-end;gap:12px;padding:14px 16px;border:1px solid #dfe7f1;border-radius:10px;background:#fff}.sel-special__search :deep(.app-form-item){flex:1;margin:0}.sel-special small{display:block;margin-top:4px;color:var(--text-tertiary)}
.sel-special__facts { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.sel-special__facts strong { white-space: normal; overflow-wrap: anywhere; }
.sel-special__block { min-width: 0; overflow-x: auto; }
@media(max-width:960px){.sel-special__facts{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:640px){.sel-special__head,.sel-special__search{align-items:stretch;flex-direction:column}.sel-special__facts{grid-template-columns:1fr}.sel-special__facts article{border-right:0;border-bottom:1px solid var(--border-color, #edf1f6)}}
</style>
