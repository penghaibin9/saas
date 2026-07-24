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
        <text class="ge__back" @click="active = null">‹ 返回任务列表</text>
        <MobileGlobalState v-if="rosterState === 'loading'" state="loading" />
        <MobileGlobalState v-else-if="rosterState === 'error'" state="error" title="名单加载失败" @retry="openTask(active)" />
        <MobileGlobalState v-else-if="!roster.length" state="empty" title="暂无名单" :description="rosterNote" />
        <view class="list-group" v-else>
          <view v-for="s in roster" :key="s.studentId" class="list-row ge__row">
            <view class="flex-1">
              <text class="t-md">{{ s.realName }}</text>
              <text class="ge__sub">{{ s.studentNo }}{{ scores[s.studentId] && scores[s.studentId].totalScore != null && scores[s.studentId].totalScore !== '' ? ' · 总评 ' + scores[s.studentId].totalScore : '' }}</text>
            </view>
            <view class="ge__scores">
              <input class="ge__score-input" type="digit" v-model="scores[s.studentId].usualScore" placeholder="平时" placeholder-class="ge__ph" />
              <input v-if="showMid" class="ge__score-input" type="digit" v-model="scores[s.studentId].midtermScore" placeholder="期中" placeholder-class="ge__ph" />
              <input class="ge__score-input" type="digit" v-model="scores[s.studentId].finalScore" placeholder="期末" placeholder-class="ge__ph" />
              <button class="btn btn-ghost ge__save" :disabled="!canEdit || saving === s.studentId" @click="saveScore(s)">
                {{ saving === s.studentId ? '…' : '保存' }}
              </button>
            </view>
          </view>
        </view>

        <MobileSafeAreaBar v-if="canEdit">
          <button class="btn btn-primary flex-1" :disabled="submitting" @click="submitTask">
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
      midtermRatio: 0, saving: null, submitting: false
    }
  },
  computed: {
    showMid() { return Number(this.midtermRatio || (this.active && this.active.midtermRatio) || 0) > 0 },
    canEdit() {
      const st = (this.active && this.active.status) || ''
      return ['NOT_STARTED', 'INPUTTING', 'RETURNED'].includes(st)
    },
    ratioText() { return this.active ? this.ratioOf(this.active) : '' }
  },
  onLoad() { this.load() },
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
    openTask(t) {
      this.active = t
      this.rosterState = 'loading'
      this.roster = []
      this.scores = {}
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
        })
        this.rosterState = 'ready'
      }).catch(() => { this.rosterState = 'error'; toast('名单加载失败') })
    },
    saveScore(s) {
      if (!this.canEdit || this.saving) return
      const sc = this.scores[s.studentId] || {}
      const body = {
        studentId: s.studentId,
        usualScore: sc.usualScore === '' ? null : Number(sc.usualScore),
        finalScore: sc.finalScore === '' ? null : Number(sc.finalScore)
      }
      if (this.showMid) body.midtermScore = sc.midtermScore === '' ? null : Number(sc.midtermScore)
      this.saving = s.studentId
      teacherApi.enterGradeScore(this.active.gradeTaskId, body).then((d) => {
        if (d && d.totalScore != null) this.scores[s.studentId].totalScore = d.totalScore
        if (this.active && this.active.status === 'NOT_STARTED') this.active.status = 'INPUTTING'
        toast('已保存')
      }).catch((e) => toast((e && e.message) || normalizeError(e).text || '保存失败'))
        .finally(() => { this.saving = null })
    },
    submitTask() {
      if (!this.canEdit || this.submitting) return
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
.ge__back { display: inline-block; margin-bottom: var(--space-3); color: var(--teacher-600); font-size: var(--font-size-sm); }
.ge__row { align-items: flex-start; }
.ge__scores { display: flex; align-items: center; gap: var(--space-1); flex-shrink: 0; flex-wrap: wrap; justify-content: flex-end; max-width: 62%; }
.ge__score-input { width: 48px; height: 32px; text-align: center; font-size: var(--font-size-sm); border: 1px solid var(--border-base); border-radius: var(--radius-sm); }
.ge__ph { color: var(--text-tertiary); }
.ge__save { min-width: 48px; padding: 0 8px; height: 32px; line-height: 32px; font-size: var(--font-size-xs); }
</style>
