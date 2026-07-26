<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="active ? active.courseName : '成绩录入'" :subtitle="active ? ratioText : '我的授课任务'" show-back />
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
          <text v-if="dirtyCount" class="ge__dirty">{{ dirtyCount }}人未保存</text>
          <text v-else-if="roster.length" class="ge__saved">全部已保存</text>
        </view>
        <view v-if="canEdit && roster.length" class="ge__notice">
          分数须为0—100。缺考、缓考、免修、作弊等特殊情况暂请在教师PC端标记，避免误填为0分。
        </view>
        <MobileGlobalState v-if="rosterState === 'loading'" state="loading" />
        <MobileGlobalState v-else-if="rosterState === 'error'" state="error" title="名单加载失败" @retry="openTask(active)" />
        <MobileGlobalState v-else-if="!roster.length" state="empty" title="暂无名单" :description="rosterNote" />
        <view class="list-group" v-else>
          <view v-for="s in roster" :key="s.studentId" class="list-row ge__row">
            <view class="flex-1">
              <text class="t-md">{{ s.realName }}</text>
              <text class="ge__sub">{{ s.studentNo }}{{ scores[s.studentId] && scores[s.studentId].totalScore != null && scores[s.studentId].totalScore !== '' ? ' · 总评 ' + scores[s.studentId].totalScore : '' }}</text>
              <text v-if="rowErrors[s.studentId]" class="ge__reason">{{ rowErrors[s.studentId] }}</text>
            </view>
            <view class="ge__scores">
              <input class="ge__score-input" type="digit" v-model="scores[s.studentId].usualScore" placeholder="平时" placeholder-class="ge__ph" :disabled="!canEdit" @input="markDirty(s.studentId)" @blur="validateStudent(s)" />
              <input v-if="showMid" class="ge__score-input" type="digit" v-model="scores[s.studentId].midtermScore" placeholder="期中" placeholder-class="ge__ph" :disabled="!canEdit" @input="markDirty(s.studentId)" @blur="validateStudent(s)" />
              <input class="ge__score-input" type="digit" v-model="scores[s.studentId].finalScore" placeholder="期末" placeholder-class="ge__ph" :disabled="!canEdit" @input="markDirty(s.studentId)" @blur="validateStudent(s)" />
              <button class="btn btn-ghost ge__save" :disabled="!canEdit || saving === s.studentId || savingAll" @click="saveScore(s, true)">
                {{ saving === s.studentId ? '…' : '保存' }}
              </button>
            </view>
          </view>
        </view>

        <MobileSafeAreaBar v-if="canEdit">
          <button class="btn btn-ghost ge__save-all" :disabled="savingAll || submitting || !dirtyCount" @click="saveAll">
            {{ savingAll ? '保存中…' : `保存全部${dirtyCount ? '（' + dirtyCount + '）' : ''}` }}
          </button>
          <button class="btn btn-primary flex-1" :disabled="submitting || savingAll" @click="submitTask">
            {{ submitting ? '提交中…' : '提交学院审核' }}
          </button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() {
    return {
      tasks: [], loaded: false, state: 'loading', active: null,
      roster: [], rosterState: 'loading', rosterNote: '', scores: {},
      midtermRatio: 0, saving: null, savingAll: false, submitting: false,
      dirty: {}, rowErrors: {}
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
  onLoad() { this.load() },
  onUnload() {
    if (this.dirtyCount) toast('仍有未保存成绩，请重新进入后检查')
  },
  methods: {
    ratioOf(t) {
      const mid = Number(t.midtermRatio || 0)
      return mid > 0
        ? `平时${t.usualRatio}% + 期中${mid}% + 期末${t.finalRatio}%`
        : `平时${t.usualRatio}% + 期末${t.finalRatio}%`
    },
    load() {
      this.state = 'loading'
      teacherApi.getGradeTasks().then((d) => {
        this.tasks = (d && d.items) || []
        this.loaded = true
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    backToTasks() {
      if (this.dirtyCount) {
        toast(`还有${this.dirtyCount}人成绩未保存`)
        return
      }
      this.active = null
    },
    openTask(t) {
      this.active = t
      this.rosterState = 'loading'
      this.roster = []
      this.scores = {}
      this.dirty = {}
      this.rowErrors = {}
      teacherApi.getGradeRoster(t.gradeTaskId).then((d) => {
        this.roster = (d && d.items) || []
        this.rosterNote = (d && d.note) || '暂无名单'
        this.midtermRatio = Number((d && d.midtermRatio) != null ? d.midtermRatio : (t.midtermRatio || 0))
        if (d && d.status) this.active = { ...t, status: d.status, midtermRatio: this.midtermRatio }
        this.scores = {}
        this.roster.forEach((s) => {
          this.scores[s.studentId] = {
            usualScore: s.usualScore != null ? String(s.usualScore) : '',
            midtermScore: s.midtermScore != null ? String(s.midtermScore) : '',
            finalScore: s.finalScore != null ? String(s.finalScore) : '',
            totalScore: s.totalScore != null ? s.totalScore : ''
          }
          this.dirty[s.studentId] = false
        })
        this.rosterState = 'ready'
      }).catch(() => { this.rosterState = 'error'; toast('名单加载失败') })
    },
    markDirty(studentId) {
      this.dirty[studentId] = true
      this.rowErrors[studentId] = ''
    },
    parseScore(value, label) {
      if (value === '' || value == null) return { value: null }
      const n = Number(value)
      if (!Number.isFinite(n) || n < 0 || n > 100) return { error: `${label}成绩须为0—100` }
      return { value: n }
    },
    buildScoreBody(s) {
      const sc = this.scores[s.studentId] || {}
      const usual = this.parseScore(sc.usualScore, '平时')
      const mid = this.parseScore(sc.midtermScore, '期中')
      const finalScore = this.parseScore(sc.finalScore, '期末')
      const error = usual.error || (this.showMid && mid.error) || finalScore.error
      if (error) return { error }
      const body = { studentId: s.studentId, usualScore: usual.value, finalScore: finalScore.value }
      if (this.showMid) body.midtermScore = mid.value
      return { body }
    },
    validateStudent(s) {
      const result = this.buildScoreBody(s)
      this.rowErrors[s.studentId] = result.error || ''
      return !result.error
    },
    async saveScore(s, notify = false) {
      if (!this.canEdit || this.saving) return false
      const built = this.buildScoreBody(s)
      if (built.error) {
        this.rowErrors[s.studentId] = built.error
        if (notify) toast(built.error)
        return false
      }
      this.saving = s.studentId
      try {
        const d = await teacherApi.enterGradeScore(this.active.gradeTaskId, built.body)
        if (d && d.totalScore != null) this.scores[s.studentId].totalScore = d.totalScore
        if (this.active && this.active.status === 'NOT_STARTED') this.active.status = 'INPUTTING'
        this.dirty[s.studentId] = false
        this.rowErrors[s.studentId] = ''
        if (notify) toast('已保存')
        return true
      } catch (e) {
        const message = (e && e.message) || normalizeError(e).text || '保存失败'
        this.rowErrors[s.studentId] = message
        if (notify) toast(message)
        return false
      } finally {
        this.saving = null
      }
    },
    async saveAll() {
      if (!this.canEdit || this.savingAll || !this.dirtyCount) return true
      this.savingAll = true
      let failed = 0
      try {
        for (const s of this.roster) {
          if (!this.dirty[s.studentId]) continue
          const ok = await this.saveScore(s, false)
          if (!ok) failed += 1
        }
      } finally {
        this.savingAll = false
      }
      if (failed) {
        toast(`${failed}人成绩保存失败，请查看红色提示`)
        return false
      }
      toast('全部成绩已保存')
      return true
    },
    async submitTask() {
      if (!this.canEdit || this.submitting || this.savingAll) return
      const saved = await this.saveAll()
      if (!saved || this.dirtyCount) return
      const invalid = this.roster.filter((s) => !this.validateStudent(s))
      if (invalid.length) {
        toast(`${invalid.length}人成绩格式不正确`)
        return
      }
      this.submitting = true
      teacherApi.submitGradeTask(this.active.gradeTaskId).then(() => {
        toast('已提交学院审核')
        this.active = null
        this.load()
      }).catch((e) => toast((e && e.message) || '提交失败')).finally(() => { this.submitting = false })
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
.ge__row { align-items: flex-start; }
.ge__scores { display: flex; align-items: center; gap: var(--space-1); flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; max-width: 62%; }
.ge__score-input { width: 48px; height: 32px; text-align: center; font-size: var(--font-size-sm); border: 1px solid var(--border-base); border-radius: var(--radius-sm); }
.ge__ph { color: var(--text-tertiary); }
.ge__save { min-width: 48px; padding: 0 8px; height: 32px; line-height: 32px; font-size: var(--font-size-xs); }
.ge__save-all { min-width: 112px; }
</style>
