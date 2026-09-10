<template>
  <ModulePageShell title="本人选课" subtitle="学生自助只允许自己的报名与退课，办理结果以服务器正式记录为准">
    <template #actions><AppButton variant="primary" :disabled="busy" @click="load">刷新正式状态</AppButton></template>
    <div class="mp-stack aasels-page">
      <AppInlineAlert type="info" title="学生自助视角" description="课程按钮来自服务端 allowedActions；提交前重新预检，提交后重新读取本人选课记录。" />
      <AppInlineAlert v-if="notice" :type="notice.type" :title="notice.title" :description="notice.description" />
      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />
      <EmptyState v-else-if="!groups.length" title="当前无可办理的选课批次" description="可能尚未开放，也可能读取失败；读取失败会单独显示错误。" />
      <template v-else>
        <section v-for="group in groups" :key="group.batch.batchId" class="aasels-group">
          <header class="aasels-group__head">
            <div><span>{{ group.batch.termName || '当前学期' }}</span><h3>{{ group.batch.batchName }}</h3></div>
            <StatusTag :type="batchType(group.batch.status)" :label="group.batch.statusLabel || batchLabel(group.batch.status)" dot />
          </header>
          <div class="aasels-grid">
            <article v-for="row in group.courses" :key="row.selectionCourseId" class="aasels-card">
              <p>{{ row.courseCode || row.teachingTaskCode || '课程' }} · {{ row.teacherName || '教师待确认' }}</p>
              <h4>{{ row.courseName }}</h4>
              <div class="aasels-meta"><span>{{ row.credit ?? '—' }}学分</span><span>{{ row.scheduleText || row.timeText || '课表时间待发布' }}</span></div>
              <div class="aasels-facts">
                <StatusTag :type="courseType(row.status)" :label="row.statusLabel || courseLabel(row.status)" dot />
                <span>名额 {{ displayCapacity(row) }}</span>
              </div>
              <p class="aasels-reason">{{ row.reason || row.howToResolve || actionReason(row) }}</p>
              <div class="aasels-actions">
                <AppButton v-if="allows(row, 'ENROLL')" size="small" variant="primary" :disabled="busy || isPending(row)" @click="prepare(row, row.reselect ? 'RESELECT' : 'ENROLL', group.batch.batchId)">
                  {{ isPending(row) ? '结果待确认' : row.reselect ? '补选预检' : '选课预检' }}
                </AppButton>
                <AppButton v-if="allows(row, 'DROP')" size="small" variant="ghost" :disabled="busy || isPending(row)" @click="prepare(row, 'DROP', group.batch.batchId)">{{ isPending(row) ? '结果待确认' : '退课预检' }}</AppButton>
                <span v-if="!allows(row, 'ENROLL') && !allows(row, 'DROP')" class="aasels-readonly">当前仅可查看</span>
              </div>
            </article>
          </div>
        </section>

        <AppSectionCard v-if="mine.length" title="我的正式选课记录" subtitle="抽签报名、取得名额、名单锁定与未中签分别显示">
          <DataTable :columns="mineColumns" :rows="mine" row-key="recordId">
            <template #cell-course="{ row }"><div class="mp-cell-main">{{ row.courseName }}</div><div class="mp-cell-sub">{{ row.courseCode || '—' }} · {{ row.credit ?? '—' }} 学分</div></template>
            <template #cell-status="{ row }"><StatusTag :type="courseType(row.status)" :label="mineLabel(row.status)" dot /></template>
            <template #cell-next="{ row }">{{ nextStep(row.status) }}</template>
          </DataTable>
        </AppSectionCard>
      </template>

      <section v-if="receipt" class="aasels-receipt" aria-live="polite">
        <header><span>{{ receipt.confirmed ? '业务回执' : '结果待确认' }}</span><strong>{{ receipt.courseName }}</strong></header>
        <dl><div><dt>实际状态</dt><dd>{{ mineLabel(receipt.status) }}</dd></div><div><dt>操作时间</dt><dd>{{ receipt.operatedAt || '服务器未返回' }}</dd></div><div><dt>下一步</dt><dd>{{ nextStep(receipt.status) }}</dd></div><div><dt>相关页面</dt><dd>我的正式选课记录 / 正式课表</dd></div></dl>
      </section>
    </div>

    <AppConfirmDialog v-model:visible="confirm.visible" :title="confirmTitle" :confirm-text="confirmText" :submitting="busy" :confirm-disabled="!confirm.preflight?.ready" @confirm="submitConfirmed">
      <div v-if="confirm.row" class="aasels-confirm">
        <strong>{{ confirm.row.courseName }}</strong><span>{{ confirm.row.teacherName || '教师待确认' }} · {{ confirm.row.credit ?? '—' }}学分</span>
        <AppInlineAlert v-if="confirm.loading" type="info" title="正在重新预检" description="请等待服务器核对当前轮次、冲突、资格与名单状态。" />
        <AppInlineAlert v-else-if="confirm.preflight" :type="confirm.preflight.ready ? 'success' : 'error'" :title="confirm.preflight.ready ? '当前允许办理' : '当前不可办理'" :description="confirm.preflight.message" />
      </div>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
/** 选课 · 学生自助（/admin/academic-affairs/my-selection）：可选课程+实时余量+选/退课+我的选课+补选指引（06号卡）。 */
import { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppConfirmDialog, AppInlineAlert, AppSectionCard } from '@/components/common'
import { academicAffairsSelectionApi as api } from '@/modules/academicAffairs/api/academic-affairs.api'
import { preflightStudentSelection } from '@/modules/academicAffairs/components/parallel-a/selectionStudentApi'
import { isDeniedResult, isConflictResult } from '@/modules/academicAffairs/components/parallel-a/resultState'

const LABELS = { OPEN: '候选可选', BLOCKED: '当前不可选', PENDING_LOTTERY: '已报名等待抽签', SELECTED: '已取得名额', LOCKED: '名单锁定', LOTTERY_LOST: '未中签', DROPPED: '已退', COURSE_CANCELLED: '课程取消' }

export default {
  name: 'AaSelectionStudentView',
  components: { ModulePageShell, DataTable, StatusTag, LoadingState, ErrorState, EmptyState, AppButton, AppConfirmDialog, AppInlineAlert, AppSectionCard },
  data() {
    return {
      loading: true, error: '', busy: false, requestSeq: 0,
      groups: [], mine: [], receipt: null, notice: null, pendingCommand: null,
      confirm: { visible: false, row: null, action: '', loading: false, preflight: null, token: 0 },
      mineColumns: [{ key: 'course', title: '课程' }, { key: 'status', title: '本人状态' }, { key: 'next', title: '下一步' }]
    }
  },
  computed: {
    confirmTitle() { return this.confirm.action === 'DROP' ? '确认退课对象' : (this.confirm.action === 'RESELECT' ? '确认补选对象' : '确认选课对象') },
    confirmText() { return this.confirm.action === 'DROP' ? '确认退课' : (this.confirm.action === 'RESELECT' ? '确认补选' : '确认报名') }
  },
  created() { this.load() },
  beforeUnmount() { this.requestSeq += 1; this.confirm.token += 1 },
  methods: {
    mineLabel(status) { return LABELS[status] || (status ? '状态待确认' : '—') },
    courseLabel(status) { return LABELS[status] || '状态待确认' },
    courseType(status) { return ['SELECTED', 'LOCKED'].includes(status) ? 'success' : ['BLOCKED', 'LOTTERY_LOST', 'COURSE_CANCELLED'].includes(status) ? 'error' : 'warning' },
    batchLabel(status) { return ({ OPEN: '选课中', CLOSED: '已结束', LOCKED: '名单已锁定' })[status] || '状态待确认' },
    batchType(status) { return status === 'OPEN' ? 'success' : status === 'LOCKED' ? 'default' : 'warning' },
    allows(row, action) { return Array.isArray(row.allowedActions) && row.allowedActions.includes(action) },
    isPending(row) { return String(this.pendingCommand?.selectionCourseId || '') === String(row?.selectionCourseId || '') },
    preflightAllowed(result, action, selectionCourseId) {
      if (result.code !== 0 || String(result.data?.selectionCourseId) !== String(selectionCourseId)) return false
      const actions = result.data?.allowedActions || []
      return result.data?.allowed === true && (action === 'DROP' ? result.data.action === 'DROP' && actions.includes('DROP') : actions.includes('ENROLL'))
    },
    displayCapacity(row) { return row.remain === null || row.remain === undefined ? '以提交预检为准' : `${row.remain} / ${row.capacity ?? '—'}` },
    actionReason(row) { return this.allows(row, 'ENROLL') ? '提交前将重新核对资格与冲突。' : this.allows(row, 'DROP') ? '可以申请退课，名单锁定后不可退。' : '请根据状态等待抽签、名单锁定或联系教务。' },
    nextStep(status) {
      return ({ PENDING_LOTTERY: '等待抽签，不代表已取得名额', SELECTED: '等待名单锁定，并在正式课表查看', LOCKED: '名额已锁定，到正式课表核对', LOTTERY_LOST: '关注补选安排', DROPPED: '无需继续办理', COURSE_CANCELLED: '按补选指引选择替代课程' })[status] || '刷新后核对服务器正式记录'
    },
    clearSensitive() { this.groups = []; this.mine = []; this.receipt = null; this.pendingCommand = null; this.confirm = { visible: false, row: null, action: '', loading: false, preflight: null, token: this.confirm.token + 1 } },
    findFormal(selectionCourseId, mine = this.mine, groups = this.groups) {
      const record = mine.find(item => String(item.selectionCourseId) === String(selectionCourseId))
      const course = groups.flatMap(group => group.courses || []).find(item => String(item.selectionCourseId) === String(selectionCourseId))
      return { record, course, status: record?.status || course?.status || 'UNKNOWN' }
    },
    targetStatus(action, status) { return action === 'DROP' ? status === 'DROPPED' : ['PENDING_LOTTERY', 'SELECTED', 'LOCKED'].includes(status) },
    reconcilePending() {
      if (!this.pendingCommand) return
      const formal = this.findFormal(this.pendingCommand.selectionCourseId)
      if (!this.targetStatus(this.pendingCommand.action, formal.status)) return
      const pending = this.pendingCommand
      this.pendingCommand = null
      this.receipt = { courseName: pending.courseName, status: formal.status, operatedAt: formal.record?.updatedAt || formal.record?.createdAt || '', confirmed: true }
      this.notice = { type: 'success', title: '办理结果已确认', description: '已从服务器本人正式选课记录确认到目标状态。' }
    },
    async load() {
      if (this.busy) return
      const seq = ++this.requestSeq
      this.loading = true; this.error = ''; this.notice = null
      const [courses, records] = await Promise.all([api.studentCourses(), api.mySelections()])
      if (seq !== this.requestSeq) return
      if (isDeniedResult(courses) || isDeniedResult(records)) {
        this.clearSensitive(); this.error = '无权读取本人选课数据，已清除先前显示内容。'; this.loading = false; return
      }
      if (courses.code !== 0 || records.code !== 0) {
        this.groups = []; this.mine = []; this.error = courses.message || records.message || '选课数据读取失败，请重试。'; this.loading = false; return
      }
      this.groups = courses.data?.items || []
      this.mine = records.data?.items || []
      this.reconcilePending()
      this.loading = false
    },
    async prepare(row, action, batchId = row.batchId) {
      if (this.isPending(row)) return
      const frozen = { ...row, batchId, allowedActions: [...(row.allowedActions || [])] }
      const token = ++this.confirm.token
      this.confirm = { visible: true, row: frozen, action, loading: true, preflight: null, token }
      const result = await preflightStudentSelection(frozen.selectionCourseId, action === 'RESELECT', action)
      if (token !== this.confirm.token || !this.confirm.visible || String(this.confirm.row?.selectionCourseId) !== String(frozen.selectionCourseId)) return
      if (isDeniedResult(result)) {
        this.clearSensitive(); this.error = '办理权限已失效，已清除先前显示内容。'; return
      }
      const allowed = this.preflightAllowed(result, action, frozen.selectionCourseId)
      this.confirm.loading = false
      this.confirm.preflight = {
        ready: allowed,
        message: allowed ? '服务器预检已通过；正式提交时仍会再次校验。' : (result.data?.reason || result.data?.howToResolve || result.message || '当前事实不允许办理，请刷新核对。')
      }
    },
    async rereadOutcome(frozen, commandResult, action, allowConfirmation = true) {
      const [records, courses] = await Promise.all([api.mySelections(frozen.batchId), api.studentCourses(frozen.batchId)])
      if (isDeniedResult(records) || isDeniedResult(courses)) {
        this.clearSensitive(); this.error = '办理权限已失效，已清除先前显示内容。'; return false
      }
      const mine = records.code === 0 ? (records.data?.items || []) : []
      const record = mine.find(item => String(item.selectionCourseId) === String(frozen.selectionCourseId))
      const course = courses.code === 0 ? (courses.data?.items || []).flatMap(group => group.courses || []).find(item => String(item.selectionCourseId) === String(frozen.selectionCourseId)) : null
      if (records.code === 0) this.mine = mine
      if (courses.code === 0) this.groups = courses.data?.items || []
      const status = record?.status || course?.status || 'UNKNOWN'
      const targetConfirmed = allowConfirmation && this.targetStatus(action, status)
      this.receipt = { courseName: frozen.courseName, status, operatedAt: record?.updatedAt || record?.createdAt || commandResult?.data?.updatedAt || '', confirmed: targetConfirmed }
      if (targetConfirmed) this.pendingCommand = null
      else if (allowConfirmation) this.notice = { type: 'warning', title: '结果待确认', description: '没有从服务器正式记录确认到目标状态。系统不会自动重复提交，请稍后刷新。' }
      return targetConfirmed
    },
    async submitConfirmed() {
      const frozen = this.confirm.row ? { ...this.confirm.row } : null
      const action = this.confirm.action
      const token = this.confirm.token
      if (!this.confirm.visible || !frozen || !this.confirm.preflight?.ready || this.busy || this.isPending(frozen)) return
      this.busy = true; this.notice = null
      this.confirm.loading = true
      const fresh = await preflightStudentSelection(frozen.selectionCourseId, action === 'RESELECT', action)
      if (token !== this.confirm.token || !this.confirm.visible || String(this.confirm.row?.selectionCourseId) !== String(frozen.selectionCourseId)) { this.busy = false; return }
      if (isDeniedResult(fresh)) {
        this.clearSensitive(); this.error = '办理权限已失效，已清除先前显示内容。'; this.busy = false; return
      }
      const allowed = this.preflightAllowed(fresh, action, frozen.selectionCourseId)
      this.confirm.loading = false
      this.confirm.preflight = { ready: allowed, message: allowed ? '提交前正式预检已通过。' : (fresh.data?.reason || fresh.data?.howToResolve || fresh.message || '当前事实不允许办理，请刷新核对。') }
      if (!allowed) { this.busy = false; return }
      this.requestSeq += 1
      this.pendingCommand = { selectionCourseId: frozen.selectionCourseId, batchId: frozen.batchId, action, courseName: frozen.courseName }
      const result = action === 'DROP' ? await api.drop(frozen.selectionCourseId) : await api.enroll(frozen.selectionCourseId, action === 'RESELECT')
      this.confirm.visible = false
      if (isDeniedResult(result)) {
        this.clearSensitive(); this.error = '办理权限已失效，已清除先前显示内容。'; this.busy = false; return
      }
      if (isConflictResult(result)) {
        this.pendingCommand = null
        this.notice = { type: 'warning', title: '事实已变化', description: result.message || '已保留当前课程对象，请重新核对最新状态。' }
        await this.rereadOutcome(frozen, result, action, false); this.busy = false; return
      }
      const knownRejected = result.code !== 0 && Number(result.code) !== 503001 && !!result.bizCode
      if (knownRejected) this.pendingCommand = null
      await this.rereadOutcome(frozen, result, action, !knownRejected)
      if (knownRejected) this.notice = { type: 'warning', title: '本次办理未提交', description: result.message || '服务器拒绝了本次请求，请核对最新事实后再办理。' }
      else if (result.code !== 0 && !this.notice) this.notice = { type: 'warning', title: '结果待确认', description: '请求未取得确定结果，已查询本人记录且不会自动再次提交。' }
      this.busy = false
    }
  }
}
</script>

<style scoped>
.aasels-page { padding-bottom: 72px; }
.aasels-group { margin-bottom: 20px; }
.aasels-group__head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.aasels-group__head span { color: #64748b; font-size: 12px; }
.aasels-group__head h3 { margin: 3px 0 0; color: #203450; font-size: 18px; }
.aasels-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.aasels-card { min-height: 230px; border: 1px solid #dbe4ef; border-radius: 10px; background: #fff; padding: 18px; display: flex; flex-direction: column; }
.aasels-card > p:first-child { margin: 0 0 14px; color: #64748b; font-size: 12px; }
.aasels-card h4 { margin: 0; color: #203450; font-size: 18px; }
.aasels-meta { display: flex; flex-wrap: wrap; gap: 8px 14px; margin-top: 12px; color: #566073; font-size: 13px; }
.aasels-facts { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-top: 18px; font-size: 12px; color: #64748b; }
.aasels-reason { margin: 10px 0 14px; color: #64748b; font-size: 12px; line-height: 1.6; }
.aasels-actions { margin-top: auto; min-height: 32px; display: flex; align-items: center; gap: 8px; }
.aasels-readonly { color: #94a3b8; font-size: 12px; }
.aasels-confirm { display: grid; gap: 8px; }
.aasels-confirm > span { color: #64748b; font-size: 13px; }
.aasels-receipt { border: 1px solid #bfdbfe; border-radius: 12px; background: #eff6ff; padding: 16px 18px; }
.aasels-receipt header { display: flex; justify-content: space-between; gap: 16px; color: #1d4ed8; }
.aasels-receipt dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin: 14px 0 0; }
.aasels-receipt dl div { border-left: 2px solid #93c5fd; padding-left: 10px; }
.aasels-receipt dt { color: #64748b; font-size: 12px; }
.aasels-receipt dd { margin: 4px 0 0; color: #203450; font-size: 13px; }
@media (max-width: 1100px) { .aasels-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .aasels-receipt dl { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) { .aasels-grid, .aasels-receipt dl { grid-template-columns: 1fr; } }
</style>
