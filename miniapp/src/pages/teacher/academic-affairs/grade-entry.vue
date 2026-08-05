<template>
  <view class="page-wrap">
    <MobileNavBar
      variant="teacher"
      :title="active ? active.courseName : '成绩录入'"
      :subtitle="active ? ratioText : '我的授课任务'"
      :before-back="beforePageBack"
      show-back
    />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="!active && loaded">
        <MobileGlobalState v-if="!tasks.length" state="empty" title="暂无成绩录入任务" description="教务处下达录入任务后会显示在这里。" />
        <view class="list-group" v-else>
          <view v-for="t in tasks" :key="t.gradeTaskId" class="list-row" @click="openTask(t)">
            <view class="flex-1">
              <text class="t-md">{{ t.courseName || '—' }}</text>
              <text class="ge__sub">{{ t.termCode || '—' }} · {{ ratioOf(t) }} · 及格线{{ t.passLine }}</text>
              <text v-if="t.returnReason" class="ge__reason">退回原因：{{ t.returnReason }}</text>
            </view>
            <MobileStatusTag :status="t.status" />
          </view>
        </view>
      </view>

      <view class="page-pad" v-if="active">
        <view class="ge__task-head">
          <text class="ge__back" @click="backToTasks">‹ 返回任务列表</text>
          <text v-if="dirtyCount" class="ge__dirty">{{ dirtyCount }}人待保存</text>
          <text v-else-if="roster.length" class="ge__saved">服务器已同步</text>
        </view>

        <view v-if="canEdit && roster.length" class="ge__notice">
          正常成绩填写0—100整数；缺考、缓考、免修、作弊请选择特殊状态，系统不会把它们误记为0分。
          修改仅保留在当前页面内存中，点击“保存全部”后才写入学校服务器。
        </view>
        <AppInlineAlert
          v-else-if="active && !canEdit"
          type="warning"
          :description="`任务当前为${statusLabel(active.status)}，移动端只读；已提交或已发布成绩不得直接修改。`"
        />

        <view v-if="qualityReport" class="ge__quality" :class="qualityReport.ready ? 'is-ready' : 'is-blocked'">
          <view class="ge__quality-head">
            <text class="ge__quality-title">{{ qualityReport.ready ? '提交检查通过' : '提交检查未通过' }}</text>
            <text class="ge__quality-state">{{ qualityReport.ready ? '可提交' : '需处理' }}</text>
          </view>
          <text class="ge__quality-summary">{{ qualityReport.summary }}</text>
          <view class="ge__quality-stats">
            <text>名单 {{ qualityReport.rosterCount }}</text>
            <text>未录 {{ qualityReport.missingCount }}</text>
            <text>未录全 {{ qualityReport.incompleteCount }}</text>
            <text>特殊状态 {{ qualityReport.specialCount }}</text>
          </view>
          <view v-if="qualityReport.issues && qualityReport.issues.length" class="ge__issues">
            <text v-for="issue in qualityReport.issues.slice(0, 5)" :key="issue.studentId + issue.code" class="ge__issue">
              {{ issue.realName || issue.studentNo || issue.studentId }}：{{ issue.message }}
            </text>
            <text v-if="qualityReport.issues.length > 5" class="ge__issue-more">另有 {{ qualityReport.issues.length - 5 }} 项，请继续核对名单。</text>
          </view>
        </view>

        <MobileGlobalState v-if="rosterState === 'loading'" state="loading" />
        <MobileGlobalState v-else-if="rosterState === 'error'" state="error" title="名单加载失败" @retry="openTask(active)" />
        <MobileGlobalState v-else-if="!roster.length" state="empty" title="暂无名单" :description="rosterNote" />
        <view class="list-group" v-else>
          <view v-for="s in roster" :key="s.studentId" class="list-row ge__row">
            <view class="flex-1 ge__student">
              <text class="t-md">{{ s.realName }}</text>
              <text class="ge__sub">
                {{ s.studentNo }}
                <template v-if="scoreOf(s).exceptionFlag !== 'NORMAL'"> · {{ exceptionLabel(scoreOf(s).exceptionFlag) }}</template>
                <template v-else-if="scoreOf(s).totalScore !== null && scoreOf(s).totalScore !== ''"> · 总评 {{ scoreOf(s).totalScore }}</template>
              </text>
              <text v-if="rowErrors[s.studentId]" class="ge__reason">{{ rowErrors[s.studentId] }}</text>
            </view>
            <view class="ge__editor">
              <picker
                class="ge__picker"
                :disabled="!canEdit"
                :range="exceptionOptions"
                range-key="label"
                :value="exceptionIndex(scoreOf(s).exceptionFlag)"
                @change="changeException(s, $event)"
              >
                <view class="ge__picker-value" :class="{ 'is-special': scoreOf(s).exceptionFlag !== 'NORMAL' }">
                  {{ exceptionLabel(scoreOf(s).exceptionFlag) }}⌄
                </view>
              </picker>
              <view class="ge__scores" :class="{ 'is-disabled': scoreOf(s).exceptionFlag !== 'NORMAL' }">
                <input class="ge__score-input" type="number" v-model="scores[s.studentId].usualScore" placeholder="平时" placeholder-class="ge__ph" :disabled="!canEdit || scoreOf(s).exceptionFlag !== 'NORMAL'" @input="markDirty(s.studentId)" @blur="validateStudent(s)" />
                <input v-if="showMid" class="ge__score-input" type="number" v-model="scores[s.studentId].midtermScore" placeholder="期中" placeholder-class="ge__ph" :disabled="!canEdit || scoreOf(s).exceptionFlag !== 'NORMAL'" @input="markDirty(s.studentId)" @blur="validateStudent(s)" />
                <input class="ge__score-input" type="number" v-model="scores[s.studentId].finalScore" placeholder="期末" placeholder-class="ge__ph" :disabled="!canEdit || scoreOf(s).exceptionFlag !== 'NORMAL'" @input="markDirty(s.studentId)" @blur="validateStudent(s)" />
                <button class="btn btn-ghost ge__save" :disabled="!canEdit || saving === s.studentId || savingAll" @click="saveScore(s, true)">
                  {{ saving === s.studentId ? '…' : '保存' }}
                </button>
              </view>
            </view>
          </view>
        </view>

        <MobileSafeAreaBar v-if="canEdit">
          <button class="btn btn-ghost ge__save-all" :disabled="savingAll || submitting || !dirtyCount" @click="saveAll">
            {{ savingAll ? '保存中…' : `保存全部${dirtyCount ? '（' + dirtyCount + '）' : ''}` }}
          </button>
          <button class="btn btn-primary flex-1" :disabled="submitting || savingAll || qualityLoading" @click="submitTask">
            {{ submitting ? '提交中…' : qualityLoading ? '检查中…' : '提交学院审核' }}
          </button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
/** V2 R5 教师微信成绩录入：名单分组 + 内存编辑 + 整批事务保存 + 提交前质量报告。 */
import { teacherApi } from '@/services/teacherApi'
import { academicGradeEntryApi } from '@/services/academicGradeEntryApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const EXCEPTION_OPTIONS = [
  { value: 'NORMAL', label: '正常' },
  { value: 'ABSENT', label: '缺考' },
  { value: 'DEFERRED', label: '缓考' },
  { value: 'EXEMPT', label: '免修' },
  { value: 'CHEAT', label: '作弊' }
]

const STATUS_LABELS = {
  NOT_STARTED: '未开始', INPUTTING: '录入中', RETURNED: '已退回', SUBMITTED: '已提交',
  COLLEGE_REVIEW: '学院审核中', ACADEMIC_REVIEW: '教务审核中', PUBLISHED: '已发布', ARCHIVED: '已归档'
}

export default {
  data() {
    return {
      tasks: [], loaded: false, state: 'loading', active: null, requestedTaskId: '',
      roster: [], rosterState: 'loading', rosterNote: '', scores: {},
      midtermRatio: 0, saving: null, savingAll: false, submitting: false,
      dirty: {}, rowErrors: {}, exceptionOptions: EXCEPTION_OPTIONS,
      qualityReport: null, qualityLoading: false,
      draftTimer: null, draftSavedAt: '', draftRestoredCount: 0
    }
  },
  computed: {
    showMid() { return Number(this.midtermRatio || (this.active && this.active.midtermRatio) || 0) > 0 },
    canEdit() {
      const st = (this.active && this.active.status) || ''
      return ['NOT_STARTED', 'INPUTTING', 'RETURNED'].includes(st)
    },
    ratioText() { return this.active ? this.ratioOf(this.active) : '' },
    dirtyCount() { return Object.values(this.dirty).filter(Boolean).length }
  },
  onLoad(options = {}) {
    this.requestedTaskId = String(options.id || options.taskId || '')
    this.load()
  },
  onUnload() {
    if (this.draftTimer) clearTimeout(this.draftTimer)
  },
  onBackPress() {
    if (!this.active) return false
    this.leaveActiveTask()
    return true
  },
  methods: {
    statusLabel(status) { return STATUS_LABELS[status] || status || '未知状态' },
    ratioOf(t) {
      const mid = Number(t.midtermRatio || 0)
      return mid > 0
        ? `平时${t.usualRatio}% + 期中${mid}% + 期末${t.finalRatio}%`
        : `平时${t.usualRatio}% + 期末${t.finalRatio}%`
    },
    scoreOf(s) {
      return this.scores[s.studentId] || { exceptionFlag: 'NORMAL', totalScore: '' }
    },
    exceptionIndex(flag) {
      const index = this.exceptionOptions.findIndex((item) => item.value === String(flag || 'NORMAL').toUpperCase())
      return index >= 0 ? index : 0
    },
    exceptionLabel(flag) {
      const item = this.exceptionOptions[this.exceptionIndex(flag)]
      return item ? item.label : '正常'
    },
    async load() {
      this.state = 'loading'
      try {
        const data = await teacherApi.getGradeTasks()
        this.tasks = (data && data.items) || []
        this.loaded = true
        this.state = 'ready'
        if (this.requestedTaskId) {
          const id = this.requestedTaskId
          this.requestedTaskId = ''
          const target = this.tasks.find((item) => String(item.gradeTaskId) === id)
          if (target) await this.openTask(target)
          else toast('该成绩任务不存在、已失效或不在本人授课范围内')
        }
      } catch (e) {
        this.loaded = true
        this.state = 'error'
      }
    },
    async confirmModal(title, content, confirmText = '确定') {
      return new Promise((resolve) => {
        uni.showModal({
          title, content, confirmText, cancelText: '取消',
          success: (result) => resolve(!!result.confirm),
          fail: () => resolve(false)
        })
      })
    },
    async beforePageBack() {
      if (!this.active) return true
      await this.leaveActiveTask()
      return false
    },
    async backToTasks() {
      await this.leaveActiveTask()
    },
    async leaveActiveTask() {
      if (!this.active) return true
      if (this.dirtyCount) {
        const leave = await this.confirmModal(
          '仍有未保存成绩',
          `还有${this.dirtyCount}人的修改尚未写入学校服务器，离开后将丢失。确认返回任务列表？`,
          '放弃修改并返回'
        )
        if (!leave) return false
      }
      this.active = null
      this.roster = []
      this.scores = {}
      this.dirty = {}
      this.rowErrors = {}
      this.qualityReport = null
      this.draftRestoredCount = 0
      this.draftSavedAt = ''
      return true
    },
    async openTask(task) {
      this.active = task
      this.rosterState = 'loading'
      this.roster = []
      this.scores = {}
      this.dirty = {}
      this.rowErrors = {}
      this.qualityReport = null
      this.draftRestoredCount = 0
      this.draftSavedAt = ''
      try {
        const data = await teacherApi.getGradeRoster(task.gradeTaskId)
        this.roster = (data && data.items) || []
        this.rosterNote = (data && data.note) || '暂无名单'
        this.midtermRatio = Number((data && data.midtermRatio) != null ? data.midtermRatio : (task.midtermRatio || 0))
        if (data && data.status) this.active = { ...task, status: data.status, midtermRatio: this.midtermRatio }
        this.roster.forEach((student) => {
          const flag = String(student.exceptionFlag || 'NORMAL').toUpperCase()
          this.scores[student.studentId] = {
            usualScore: student.usualScore != null ? String(student.usualScore) : '',
            midtermScore: student.midtermScore != null ? String(student.midtermScore) : '',
            finalScore: student.finalScore != null ? String(student.finalScore) : '',
            totalScore: student.totalScore != null ? student.totalScore : '',
            exceptionFlag: this.exceptionOptions.some((item) => item.value === flag) ? flag : 'NORMAL'
          }
          this.dirty[student.studentId] = false
        })
        this.clearDraft()
        this.rosterState = 'ready'
      } catch (e) {
        this.rosterState = 'error'
        toast((e && e.message) || '名单加载失败')
      }
    },
    clearDraft() {
      // 成绩属于敏感教务数据：生产端禁止写入uni本地持久化存储。
      this.draftSavedAt = ''
      this.draftRestoredCount = 0
    },
    markDirty(studentId) {
      this.dirty[studentId] = true
      this.rowErrors[studentId] = ''
      this.qualityReport = null
      this.draftRestoredCount = 0
    },
    changeException(student, event) {
      if (!this.canEdit) return
      const index = Number(event && event.detail && event.detail.value)
      const option = this.exceptionOptions[index] || this.exceptionOptions[0]
      const score = this.scoreOf(student)
      score.exceptionFlag = option.value
      if (option.value !== 'NORMAL') {
        score.usualScore = ''
        score.midtermScore = ''
        score.finalScore = ''
        score.totalScore = ''
      }
      this.markDirty(student.studentId)
      this.validateStudent(student)
    },
    parseScore(value, label) {
      if (value === '' || value == null) return { value: null }
      const number = Number(value)
      if (!Number.isInteger(number) || number < 0 || number > 100) return { error: `${label}成绩须为0—100整数` }
      return { value: number }
    },
    buildScoreBody(student) {
      const score = this.scoreOf(student)
      const exceptionFlag = String(score.exceptionFlag || 'NORMAL').toUpperCase()
      if (exceptionFlag !== 'NORMAL') {
        return {
          body: {
            studentId: Number(student.studentId),
            usualScore: null,
            midtermScore: null,
            finalScore: null,
            exceptionFlag
          }
        }
      }
      const usual = this.parseScore(score.usualScore, '平时')
      const midterm = this.parseScore(score.midtermScore, '期中')
      const finalScore = this.parseScore(score.finalScore, '期末')
      const error = usual.error || (this.showMid && midterm.error) || finalScore.error
      if (error) return { error }
      return {
        body: {
          studentId: Number(student.studentId),
          usualScore: usual.value,
          midtermScore: this.showMid ? midterm.value : null,
          finalScore: finalScore.value,
          exceptionFlag: 'NORMAL'
        }
      }
    },
    validateStudent(student) {
      const result = this.buildScoreBody(student)
      this.rowErrors[student.studentId] = result.error || ''
      return !result.error
    },
    async saveScore(student, notify = false) {
      if (!this.canEdit || this.saving || this.savingAll) return false
      const built = this.buildScoreBody(student)
      if (built.error) {
        this.rowErrors[student.studentId] = built.error
        if (notify) toast(built.error)
        return false
      }
      this.saving = student.studentId
      try {
        const data = await teacherApi.enterGradeScore(this.active.gradeTaskId, built.body)
        const score = this.scoreOf(student)
        score.totalScore = data && data.totalScore != null ? data.totalScore : ''
        score.exceptionFlag = String((data && data.exceptionFlag) || built.body.exceptionFlag || 'NORMAL').toUpperCase()
        if (score.exceptionFlag !== 'NORMAL') {
          score.usualScore = ''
          score.midtermScore = ''
          score.finalScore = ''
        }
        if (this.active && this.active.status === 'NOT_STARTED') this.active.status = 'INPUTTING'
        this.dirty[student.studentId] = false
        this.rowErrors[student.studentId] = ''
        this.qualityReport = null
        this.persistDraftNow()
        if (notify) toast(score.exceptionFlag === 'NORMAL' ? '成绩已保存' : `${this.exceptionLabel(score.exceptionFlag)}状态已保存`)
        return true
      } catch (error) {
        const message = (error && error.message) || normalizeError(error).text || '保存失败'
        this.rowErrors[student.studentId] = message
        if (notify) toast(message)
        return false
      } finally {
        this.saving = null
      }
    },
    async saveAll() {
      if (!this.canEdit || this.savingAll) return false
      const pending = this.roster.filter((student) => this.dirty[student.studentId])
      if (!pending.length) return true
      const rows = []
      let invalid = 0
      pending.forEach((student) => {
        const built = this.buildScoreBody(student)
        if (built.error) {
          this.rowErrors[student.studentId] = built.error
          invalid += 1
        } else rows.push(built.body)
      })
      if (invalid) {
        toast(`${invalid}人成绩格式不正确，请查看红色提示`)
        return false
      }

      this.savingAll = true
      try {
        const data = await academicGradeEntryApi.batchSave(this.active.gradeTaskId, rows)
        ;((data && data.items) || []).forEach((record) => {
          const score = this.scores[record.studentId]
          if (!score) return
          score.totalScore = record.totalScore != null ? record.totalScore : ''
          score.exceptionFlag = String(record.exceptionFlag || 'NORMAL').toUpperCase()
        })
        pending.forEach((student) => {
          this.dirty[student.studentId] = false
          this.rowErrors[student.studentId] = ''
        })
        if (this.active.status === 'NOT_STARTED') this.active.status = 'INPUTTING'
        this.qualityReport = (data && data.qualityReport) || null
        this.clearDraft()
        toast(`已一次保存${rows.length}人成绩`)
        return true
      } catch (error) {
        const message = (error && error.message) || normalizeError(error).text || '批量保存失败'
        toast(message)
        this.persistDraftNow()
        return false
      } finally {
        this.savingAll = false
      }
    },
    async loadQualityReport() {
      if (!this.active || this.qualityLoading) return null
      this.qualityLoading = true
      try {
        const report = await academicGradeEntryApi.qualityReport(this.active.gradeTaskId)
        this.qualityReport = report
        return report
      } catch (error) {
        toast((error && error.message) || '提交检查失败')
        return null
      } finally {
        this.qualityLoading = false
      }
    },
    async submitTask() {
      if (!this.canEdit || this.submitting || this.savingAll || this.qualityLoading) return
      if (this.dirtyCount) {
        const saved = await this.saveAll()
        if (!saved || this.dirtyCount) return
      }
      const report = await this.loadQualityReport()
      if (!report) return
      if (!report.canSubmit) {
        toast(report.summary || '成绩尚未录全，暂不可提交')
        return
      }
      const confirmed = await this.confirmModal(
        '提交学院审核',
        `${report.summary}。提交后教师端将只读，退回后方可继续修改。确认提交？`,
        '确认提交'
      )
      if (!confirmed) return

      this.submitting = true
      try {
        await teacherApi.submitGradeTask(this.active.gradeTaskId)
        this.clearDraft()
        toast('已提交学院审核')
        this.active = null
        this.roster = []
        this.qualityReport = null
        await this.load()
      } catch (error) {
        toast((error && error.message) || '提交失败')
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
.ge__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ge__reason { display: block; font-size: var(--font-size-xs); color: var(--danger-600); margin-top: 4px; }
.ge__task-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--space-3); }
.ge__back { color: var(--teacher-600); font-size: var(--font-size-sm); }
.ge__dirty { color: var(--warning-600); font-size: var(--font-size-xs); }
.ge__saved { color: var(--success-600); font-size: var(--font-size-xs); }
.ge__notice { padding: var(--space-3); margin-bottom: var(--space-3); background: var(--warning-50); color: var(--text-secondary); border-radius: var(--radius-md); font-size: var(--font-size-xs); line-height: 1.6; }
.ge__quality { margin: var(--space-3) 0; padding: var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-md); background: var(--surface-base); }
.ge__quality.is-ready { border-color: var(--success-300); background: var(--success-50); }
.ge__quality.is-blocked { border-color: var(--warning-300); background: var(--warning-50); }
.ge__quality-head { display: flex; align-items: center; justify-content: space-between; }
.ge__quality-title { font-size: var(--font-size-sm); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.ge__quality-state { font-size: var(--font-size-xs); color: var(--text-secondary); }
.ge__quality-summary { display: block; margin-top: var(--space-1); font-size: var(--font-size-xs); color: var(--text-secondary); line-height: 1.5; }
.ge__quality-stats { display: flex; gap: var(--space-3); flex-wrap: wrap; margin-top: var(--space-2); font-size: var(--font-size-xs); color: var(--text-secondary); }
.ge__issues { margin-top: var(--space-2); padding-top: var(--space-2); border-top: 1px dashed var(--border-base); }
.ge__issue, .ge__issue-more { display: block; font-size: var(--font-size-xs); line-height: 1.6; color: var(--danger-600); }
.ge__issue-more { color: var(--text-secondary); }
.ge__row { align-items: flex-start; gap: var(--space-2); }
.ge__student { min-width: 92px; padding-top: 2px; }
.ge__editor { display: flex; flex-direction: column; align-items: flex-end; gap: var(--space-1); max-width: 68%; }
.ge__picker { min-width: 88px; }
.ge__picker-value { height: 28px; padding: 0 9px; line-height: 28px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); font-size: var(--font-size-xs); color: var(--text-secondary); text-align: center; background: var(--surface-base); }
.ge__picker-value.is-special { color: var(--warning-700); border-color: var(--warning-300); background: var(--warning-50); font-weight: 600; }
.ge__scores { display: flex; align-items: center; gap: var(--space-1); flex-wrap: wrap; justify-content: flex-end; }
.ge__scores.is-disabled .ge__score-input { opacity: .5; }
.ge__score-input { width: 48px; height: 32px; text-align: center; font-size: var(--font-size-sm); border: 1px solid var(--border-base); border-radius: var(--radius-sm); }
.ge__ph { color: var(--text-tertiary); }
.ge__save { min-width: 48px; padding: 0 8px; height: 32px; line-height: 32px; font-size: var(--font-size-xs); }
.ge__save-all { min-width: 112px; }
</style>
