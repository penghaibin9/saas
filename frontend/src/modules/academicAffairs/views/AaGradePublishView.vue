<template>
  <ModulePageShell
    title="成绩发布"
    subtitle="核对终审任务并发布正式成绩；发布结果与后续预警扫描分别确认。"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <div class="mp-stack">
      <div v-if="focusTaskId" class="aa-focus-note">当前入口指定成绩任务 {{ focusTaskId }} <button class="mp-btn mp-btn--sm" @click="returnToQueue">返回原队列</button></div>
      <section v-if="receipt" class="aa-review-receipt" :class="{ 'is-warning': receipt.tone === 'warning' }" role="status">
        <div><strong>{{ receipt.tone === 'warning' ? '!' : '✓' }} {{ receipt.title }}</strong><span>{{ receipt.courseName }} · 任务 {{ receipt.taskId }}</span></div>
        <div><small>当前结果</small><b>{{ receipt.primary === 'REJECTED' ? '本次未发布' : statusLabel(receipt.status) }}</b></div>
        <div><small>正式投影</small><b>{{ receipt.projectedText }}</b></div>
        <div v-if="receipt.action === 'publish'" class="aa-review-receipt__followup">
          <p>预警扫描：{{ scanStatusLabel(receipt.warningRefresh) }}；预警条数：未提供。通知结果待核对。</p>
          <p v-if="receipt.warningScanJobId">扫描任务 {{ receipt.warningScanJobId }}</p>
          <p>{{ receipt.nextStep }}</p>
          <button class="mp-btn mp-btn--sm" :disabled="receipt.checking" @click="checkReceiptStatus">{{ receipt.checking ? '正在核对…' : '核对该任务正式状态' }}</button>
          <p v-if="receipt.observedText">{{ receipt.observedText }}</p>
        </div>
      </section>
      <div class="aa-tabs">
        <button class="aa-tab" :class="{ 'is-active': tab === 'ACADEMIC_REVIEW' }" @click="switchTab('ACADEMIC_REVIEW')">待终审</button>
        <button class="aa-tab" :class="{ 'is-active': tab === 'PUBLISHED' }" @click="switchTab('PUBLISHED')">已发布（可归档）</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!rows.length" :title="tab === 'ACADEMIC_REVIEW' ? '暂无待终审任务' : '暂无已发布任务'" description="" />
      <template v-else>
        <section v-if="selectedTask" class="aa-publish-context" aria-label="当前成绩发布任务">
          <div><h2>{{ selectedTask.courseName }}<template v-if="selectedTask.teachingClassName"> · {{ selectedTask.teachingClassName }}</template></h2><p>{{ selectedTask.termCode }} · 任务 {{ selectedTask.gradeTaskId }}</p><p>来源：{{ selectedTask.teachingTaskId ? `正式教学任务 ${selectedTask.teachingTaskId}` : '任务来源待核对' }}</p></div>
          <div><small>当前状态</small><strong>{{ statusLabel(selectedTask.status) }}</strong></div>
          <div><small>下一责任</small><strong>{{ selectedTask.status === 'ACADEMIC_REVIEW' ? '教务成绩发布岗' : '后置扫描处理岗 / 受控更正' }}</strong></div>
        </section>
        <div class="aa-publish-workspace">
          <aside class="aa-publish-queue" aria-label="发布责任队列">
            <h3>责任队列 <small>{{ pagination.total }} 项</small></h3>
            <button v-for="row in rows" :key="row.gradeTaskId" :class="['aa-publish-queue-item', { 'is-active': String(selectedTask?.gradeTaskId) === String(row.gradeTaskId) }]" :disabled="dlg.submitting" @click="selectTask(row)"><strong>{{ row.courseName }}</strong><span>{{ row.teachingClassName || row.termCode }} · 任务 {{ row.gradeTaskId }}</span><AppStatusTag :type="row.status === 'PUBLISHED' ? 'success' : 'primary'">{{ statusLabel(row.status) }}</AppStatusTag></button>
            <div class="aa-publish-pages"><button class="mp-btn mp-btn--sm" :disabled="pagination.page <= 1" @click="onPageChange(pagination.page - 1)">上一页</button><span>{{ pagination.page }}</span><button class="mp-btn mp-btn--sm" :disabled="pagination.page * pagination.pageSize >= pagination.total" @click="onPageChange(pagination.page + 1)">下一页</button></div>
          </aside>
          <section v-if="selectedTask" class="aa-publish-evidence" aria-label="发布前核对">
            <h3>正式任务与发布核对</h3>
            <table><thead><tr><th>核验对象</th><th>当前正式事实</th><th>核对说明</th></tr></thead><tbody>
              <tr><th>课程身份</th><td>{{ selectedTask.courseName }} · {{ selectedTask.courseId || '课程版本未关联' }}</td><td>以任务绑定的课程版本为准</td></tr>
              <tr><th>正式教学班</th><td>{{ selectedTask.teachingClassName || '待核对' }}</td><td>{{ selectedTask.teachingClassId || '教学班身份未返回' }}</td></tr>
              <tr><th>任课教师</th><td>{{ selectedTask.teacherAuthorityReady && selectedTask.teacherNames?.length ? selectedTask.teacherNames.join('、') : '正式任课关系待核对' }}</td><td>以正式教学任务的任课关系为准</td></tr>
              <tr><th>提交时间</th><td>{{ selectedTask.submittedAt || '未返回' }}</td><td>{{ statusLabel(selectedTask.status) }}</td></tr>
              <tr><th>名单与成绩方案</th><td>发布时由服务器再次核验</td><td>当前任务摘要不提供完整审核证据</td></tr>
              <tr><th>后置预警扫描</th><td>与正式发布分别回执</td><td>不及格人数不能替代预警条数</td></tr>
            </tbody></table>
            <p class="aa-publish-note">发布产生正式成绩。名单、课程版本、计分方案及当前状态由正式发布命令核验；失败时按具体阻断处理。</p>
            <footer>
              <template v-if="selectedTask.status === 'ACADEMIC_REVIEW'">
                <button class="mp-btn mp-btn--primary" :disabled="publishPendingVerification(selectedTask) || dlg.submitting" @click="openPublish(selectedTask)">核验并正式发布</button>
                <button v-if="publishPendingVerification(selectedTask)" class="mp-btn" @click="showUnconfirmedReceipt(selectedTask)">核对上次发布结果</button>
                <button class="mp-btn" :disabled="dlg.submitting" @click="openReturn(selectedTask)">退回修改</button>
              </template>
              <template v-else-if="selectedTask.status === 'PUBLISHED'"><button class="mp-btn" @click="showUnconfirmedReceipt(selectedTask)">查询发布后扫描</button><button class="mp-btn" :disabled="dlg.submitting" @click="openArchive(selectedTask)">归档</button></template>
              <span v-else>当前状态只读</span>
            </footer>
          </section>
          <EmptyState v-else title="请选择成绩任务" description="指定任务不在当前页时，请返回来源队列或使用任务深链" />
        </div>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="dlg.visible"
      :title="dlg.title"
      :type="dlg.type"
      :confirm-text="dlg.confirmText"
      :require-reason="dlg.requireReason"
      phrase-scene-key="aa.grade.return"
      reason-label="退回原因"
      :submitting="dlg.submitting"
      @confirm="doAction"
    >
      <p v-if="dlg.action === 'publish'">确认后提交该任务的正式成绩并更新学业汇总。预警扫描在发布提交后执行，可能失败或暂时无法确认；请按回执核对，勿重复发布。</p>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 教务发布（/admin/academic-affairs/grade-publish）：终审发布/退回/归档。仅 ACADEMIC_ADMIN/SCHOOL_ADMIN 可执行。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppStatusTag, AppConfirmDialog } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'
import { academicRouteState, academicIdentity, createAcademicRequestGate } from '../academicFlowContext.js'
import { currentUserFromToken } from '@/services/http/client'
import { buildGradePublishReceipt, gradeWarningEffectState } from '../gradePublishReceipt.js'

export default {
  name: 'AaGradePublishView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, AppStatusTag, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  inject: { academicFlow: { default: null } },
  computed: {
    selectedTask() {
      const id = this.focusTaskId || String(this.$route.query.selectedTaskId || '')
      return id ? this.rows.find(row => String(row.gradeTaskId) === id) || null : this.rows[0] || null
    }
  },
  data() {
    return {
      tab: 'ACADEMIC_REVIEW', loading: true, error: '', rows: [], focusTaskId: '', receipt: null, unconfirmedPublishKeys: [],
      pagination: { page: 1, pageSize: 20, total: 0 },
      dlg: { visible: false, title: '', type: 'primary', confirmText: '确认', requireReason: false, submitting: false, taskId: '', action: '' },
      columns: [
        { key: 'courseName', title: '课程' },
        { key: 'termCode', title: '学期' },
        { key: 'status', title: '状态' },
        { key: 'actions', title: '操作', width: '160px' }
      ]
    }
  },
  watch: {
    '$route.fullPath'() { this.syncRoute() },
    ctx() { this.syncRoute() }
  },
  created() {
    this.readGate = createAcademicRequestGate(() => this.contextKey())
    this.syncRoute()
  },
  beforeUnmount() { this.readGate.invalidate(); this.dlg = { ...this.dlg, visible: false } },
  methods: {
    selectTask(row) {
      if (this.dlg.submitting) return
      this.$router.replace({ path: this.$route.path, query: { ...this.$route.query, selectedTaskId: String(row.gradeTaskId) } })
    },
    identity() { return this.academicFlow?.identity() || academicIdentity(currentUserFromToken(), this.ctx) },
    publishLockKey(taskId, identity = this.identity()) { return JSON.stringify([identity, String(taskId)]) },
    publishPendingVerification(row) { return !!row && this.unconfirmedPublishKeys.includes(this.publishLockKey(row.gradeTaskId)) },
    contextKey() { return JSON.stringify([this.identity(), this.$route?.fullPath, this.tab, this.focusTaskId, this.pagination.page]) },
    syncRoute() {
      if (!this.readGate) return
      this.readGate.invalidate(); this.rows = []; this.receipt = null; this.dlg = { ...this.dlg, visible: false, submitting: false }
      const state = academicRouteState(this.$route, { tabs: ['ACADEMIC_REVIEW', 'PUBLISHED'], defaultTab: 'ACADEMIC_REVIEW' })
      this.focusTaskId = state.taskId; this.tab = state.tab
      this.pagination.page = state.page; this.pagination.pageSize = state.pageSize; this.pagination.total = 0
      this.error = state.error
      if (state.error) { this.loading = false; return }
      return this.load()
    },
    statusLabel(s) { return ({ ACADEMIC_REVIEW: '待教务终审', PUBLISHED: '已发布', ARCHIVED: '已归档', RETURNED: '已退回', INPUTTING: '录入中', NOT_STARTED: '未开始', COLLEGE_REVIEW: '待学院审核' })[s] || '状态待确认' },
    switchTab(tab) { const query = { ...this.$route.query, tab, page: '1' }; delete query.selectedTaskId; this.$router.push({ path: this.$route.path, query }) },
    onPageChange(page) { const query = { ...this.$route.query, page: String(page) }; delete query.selectedTaskId; this.$router.push({ path: this.$route.path, query }) },
    returnToQueue() {
      const target = this.academicFlow?.returns.resolve(this.$route.query.returnToken, this.identity())
      if (target) return this.academicFlow.back(this.$route.query.returnToken, this.$route.path)
      const query = { ...this.$route.query }; delete query.taskId; delete query.returnToken
      this.$router.push({ path: this.$route.path, query })
    },
    openPublish(row) {
      if (this.publishPendingVerification(row)) return
      this.dlg = { visible: true, taskId: row.gradeTaskId, courseName: row.courseName, action: 'publish', title: `发布「${row.courseName}」成绩`, type: 'danger', confirmText: '确认发布（不可撤销）', requireReason: false, submitting: false }
      this.dlg.contextKey = this.contextKey()
    },
    openReturn(row) {
      this.dlg = { visible: true, taskId: row.gradeTaskId, courseName: row.courseName, action: 'return', title: `退回「${row.courseName}」`, type: 'warning', confirmText: '确认退回', requireReason: true, submitting: false }
      this.dlg.contextKey = this.contextKey()
    },
    openArchive(row) {
      this.dlg = { visible: true, taskId: row.gradeTaskId, courseName: row.courseName, action: 'archive', title: `归档「${row.courseName}」`, type: 'warning', confirmText: '确认归档', requireReason: false, submitting: false }
      this.dlg.contextKey = this.contextKey()
    },
    async doAction(payload) {
      const command = this.dlg
      if (command.submitting) return
      if (!command.visible || command.contextKey !== this.contextKey()) { command.visible = false; return }
      const reason = (payload && payload.reason) || ''
      command.submitting = true
      let res
      try {
        if (command.action === 'publish') res = await academicAffairsApi.publishGrades(command.taskId)
        else if (command.action === 'return') res = await academicAffairsApi.returnGradeTask(command.taskId, reason)
        else res = await academicAffairsApi.archiveGradeTask(command.taskId)
      } catch (error) { res = { code: 1, message: error?.message || '请求结果待确认，请刷新当前任务核对' } }
      if (this.dlg !== command || command.contextKey !== this.contextKey()) return
      command.submitting = false
      if (command.action === 'publish') {
        // Validate the captured command target before adapting a success-looking envelope.
        const sameTarget = String(res?.data?.gradeTaskId || '') === String(command.taskId)
        const result = buildGradePublishReceipt(res?.code !== 0 || sameTarget ? res : null)
        this.receipt = { ...result, action: 'publish', taskId: command.taskId, courseName: command.courseName,
          status: result.primary === 'COMMITTED' ? 'PUBLISHED' : null,
          projectedText: result.primary === 'REJECTED' ? '本次未生成正式成绩' : `正式成绩 ${result.projectedCount ?? '未提供'} 条 · 不及格人数 ${result.failedGradeCount ?? '未提供'}`,
          checking: false, observedText: '', contextKey: command.contextKey }
        if (result.primary === 'UNKNOWN') this.unconfirmedPublishKeys = [...new Set([...this.unconfirmedPublishKeys, this.publishLockKey(command.taskId)])]
        command.visible = false
        toast[result.tone](result.title)
        if (result.primary === 'COMMITTED') await this.load()
        return
      }
      if (res.code === 0) {
        const action = this.dlg.action
        this.receipt = {
          taskId: this.dlg.taskId, courseName: this.dlg.courseName, status: res.data.status,
          title: action === 'return' ? '成绩已退回任课教师' : '成绩任务已归档',
          projectedText: '未产生新的正式成绩投影'
        }
        this.dlg.visible = false
        toast.success('已处理')
        this.load()
      } else toast.error(res.message || '操作失败')
    },
    scanStatusLabel(status) { return ({ NOT_STARTED: '本次未启动', SUCCEEDED: '已完成', FAILED: '刷新失败', PENDING: '等待扫描', RUNNING: '正在扫描', RETRY: '等待恢复', NOT_RECORDED: '没有持久化记录', UNKNOWN: '状态未知' })[status] || '状态未知' },
    showUnconfirmedReceipt(row) {
      this.receipt = { ...buildGradePublishReceipt(null), action: 'publish', taskId: row.gradeTaskId, courseName: row.courseName,
        status: null, projectedText: '正式成绩条数与不及格人数待核对', checking: false, observedText: '',
        observingOnly: !this.publishPendingVerification(row), contextKey: this.contextKey() }
      return this.checkReceiptStatus()
    },
    async checkReceiptStatus() {
      const receipt = this.receipt
      if (!receipt || receipt.checking || receipt.contextKey !== this.contextKey()) return
      receipt.checking = true; receipt.observedText = ''
      try {
        const [response, effect] = await Promise.all([
          academicAffairsApi.getGradeTasks({ taskId: receipt.taskId, page: 1, pageSize: 1 }),
          academicAffairsApi.getGradePublicationEffect(receipt.taskId)
        ])
        if (this.receipt !== receipt || receipt.contextKey !== this.contextKey()) return
        const denied = result => [401, 403, 401001, 403001, 403002].includes(Number(result?.code)) || ['NO_PERMISSION', 'NO_DATA_SCOPE', 'NOT_AUTHENTICATED', 'SESSION_CHANGED'].includes(result?.bizCode)
        if (denied(response) || denied(effect)) { this.receipt = null; this.rows = []; this.error = '当前任务权限已失效，已清除原显示内容。'; return }
        const rows = response?.data?.list || []
        if (response.code !== 0 || rows.length !== 1 || String(rows[0].gradeTaskId) !== String(receipt.taskId)) throw new Error('任务状态暂时无法核对，请稍后查询或联系教务负责人。')
        const status = rows[0].status
        receipt.status = status
        this.rows = this.rows.map(row => String(row.gradeTaskId) === String(receipt.taskId) ? rows[0] : row)
        if (receipt.observingOnly) receipt.title = `任务正式状态：${this.statusLabel(status)}`
        const sameEffect = effect?.code === 0 && String(effect.data?.gradeTaskId) === String(receipt.taskId)
        if (sameEffect) {
          receipt.warningRefresh = gradeWarningEffectState(effect.data)
          receipt.warningScanJobId = effect.data.warningScanJobId || null
          receipt.nextStep = '以上为持久化扫描任务的当前状态；扫描完成不代表已通知或已处置，不要重复发布成绩。'
        }
        receipt.observedText = `当前任务状态：${this.statusLabel(status)}。${receipt.primary === 'UNKNOWN' && !receipt.observingOnly ? '这是当前正式状态，不能据此认定上次发布请求成功。' : ''}${sameEffect ? '' : '扫描任务状态暂时无法读取，请稍后查询。'}`
      } catch {
        if (this.receipt === receipt && receipt.contextKey === this.contextKey()) receipt.observedText = '任务状态暂时无法核对，请稍后查询或联系教务负责人。'
      } finally {
        if (this.receipt === receipt) receipt.checking = false
      }
    },
    async load() {
      const current = this.readGate.begin()
      const taskId = this.focusTaskId
      this.loading = true
      this.error = ''
      this.rows = []
      try {
        const res = await academicAffairsApi.getGradeTasks({
          status: taskId ? undefined : this.tab, taskId: taskId || undefined,
          page: taskId ? 1 : this.pagination.page, pageSize: this.pagination.pageSize
        })
        if (!current()) return
        if (res.code !== 0) throw new Error(res.message || '成绩任务读取失败')
        const rows = res.data?.list || []
        if (taskId && (rows.length !== 1 || String(rows[0].gradeTaskId) !== taskId)) throw new Error('指定任务不存在或不在当前身份范围内，请返回原队列核对。')
        this.rows = rows; this.pagination.total = res.data.total
      } catch (error) { if (current()) this.error = error?.message || '成绩任务读取失败' }
      finally { if (current()) { this.loading = false; this.academicFlow?.restorePosition() } }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-publish-context { display: grid; grid-template-columns: minmax(0,1fr) auto auto; gap: 24px; align-items: center; padding: 16px; background: var(--bg-card); border: 1px solid var(--border-base); border-left: 3px solid var(--pri); border-radius: 10px; }
.aa-publish-context h2 { margin: 0 0 6px; font-size: 15px; }.aa-publish-context p { margin: 4px 0 0; font-size: 12px; color: var(--text-secondary); }.aa-publish-context small,.aa-publish-context strong { display: block; }.aa-publish-context small { font-size: 11px; color: var(--text-secondary); }.aa-publish-context strong { margin-top: 5px; font-size: 12px; }
.aa-publish-workspace { display: grid; grid-template-columns: 250px minmax(0,1fr); gap: 16px; align-items: start; }
.aa-publish-queue,.aa-publish-evidence { min-width: 0; border: 1px solid var(--border-base); border-radius: 10px; background: var(--bg-card); overflow: hidden; }
.aa-publish-queue h3,.aa-publish-evidence h3 { margin: 0; padding: 16px; font-size: 15px; }.aa-publish-queue h3 small { color: var(--text-secondary); font-size: 12px; font-weight: 400; }
.aa-publish-queue-item { display: grid; gap: 8px; width: 100%; padding: 16px 14px; text-align: left; border: 0; border-top: 1px solid var(--border-base); background: transparent; color: var(--text-primary); cursor: pointer; }.aa-publish-queue-item strong { font-size: 13px; }.aa-publish-queue-item span { font-size: 11px; color: var(--text-secondary); }.aa-publish-queue-item.is-active { background: var(--pri-bg); box-shadow: inset 3px 0 var(--pri); }.aa-publish-pages { display: flex; justify-content: space-between; gap: 8px; align-items: center; padding: 12px; font-size: 12px; }
.aa-publish-evidence table { width: 100%; border-collapse: collapse; table-layout: fixed; }.aa-publish-evidence th,.aa-publish-evidence td { padding: 16px; text-align: left; font-size: 12px; border-top: 1px solid var(--border-base); overflow-wrap: anywhere; }.aa-publish-evidence thead { background: var(--pri-bg); color: var(--text-secondary); }.aa-publish-evidence th:first-child { width: 23%; }.aa-publish-note { margin: 16px; padding: 12px; border-radius: 8px; background: var(--pri-bg); color: var(--text-secondary); font-size: 12px; line-height: 1.7; }.aa-publish-evidence footer { display: flex; flex-wrap: wrap; gap: 10px; padding: 16px; border-top: 1px solid var(--border-base); }
@media(max-width: 900px) { .aa-publish-workspace,.aa-publish-context { grid-template-columns: 1fr; }.aa-publish-evidence th,.aa-publish-evidence td { padding: 10px; } }
.aa-tabs { display: flex; gap: 4px; border-bottom: 1px solid var(--border-200, #e5e6eb); }
.aa-tab { padding: 8px 16px; border: none; background: none; cursor: pointer; font-size: 14px; color: var(--text-500, #646a73); border-bottom: 2px solid transparent; }
.aa-tab.is-active { color: var(--primary-600, #2563eb); border-bottom-color: var(--primary-500, #3b82f6); font-weight: 500; }
.aa-focus-note { padding: 9px 12px; border: 1px solid #bfdbfe; border-radius: 8px; background: var(--pri-bg); color: var(--pri); font-size: 12px; }
.aa-review-receipt { display: grid; grid-template-columns: minmax(0,1fr) auto auto; gap: 18px; padding: 12px 14px; border: 1px solid #a7d7b4; border-radius: 9px; background: var(--aa-success-bg, #f3fbf5); }
.aa-review-receipt strong, .aa-review-receipt span, .aa-review-receipt small, .aa-review-receipt b { display: block; }.aa-review-receipt strong { color: var(--success-color, #16803c); }.aa-review-receipt span, .aa-review-receipt small { margin-top: 3px; color: var(--text-secondary); font-size: 12px; }.aa-review-receipt b { margin-top: 3px; font-size: 12px; }
.aa-review-receipt.is-warning { border-color: var(--warning-300, #e6bd73); background: var(--warning-50, #fff8e8); }
.aa-review-receipt.is-warning strong { color: var(--warning-700, #8a5900); }
.aa-review-receipt__followup { grid-column: 1 / -1; font-size: 13px; }
.aa-review-receipt__followup p { margin: 0 0 8px; }
@media (max-width: 760px) { .aa-review-receipt { grid-template-columns: 1fr; gap: 10px; } }
</style>
