<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" :title="active ? active.courseName : '成绩录入'" :subtitle="active ? active.termCode : '我的授课任务'" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <!-- 任务列表 -->
      <view class="page-pad" v-if="!active && loaded">
        <MobileGlobalState v-if="!tasks.length" state="empty" title="暂无成绩录入任务" description="教务处下达录入任务后会显示在这里。" />
        <view class="list-group" v-else>
          <view v-for="t in tasks" :key="t.gradeTaskId" class="list-row" @click="openTask(t)">
            <view class="flex-1">
              <text class="t-md">{{ t.courseName || '—' }}</text>
              <text class="ge__sub">{{ t.termCode || '—' }} · 平时{{ t.usualRatio }}% + 期末{{ t.finalRatio }}% · 及格线{{ t.passLine }}</text>
              <text v-if="t.returnReason" class="ge__reason">退回原因：{{ t.returnReason }}</text>
            </view>
            <MobileStatusTag :status="t.status" />
          </view>
        </view>
      </view>

      <!-- 名单 + 录入 -->
      <view class="page-pad" v-if="active">
        <text class="ge__back" @click="active = null">‹ 返回任务列表</text>
        <MobileGlobalState v-if="rosterState === 'loading'" state="loading" />
        <MobileGlobalState v-else-if="!roster.length" state="empty" title="暂无名单" :description="rosterNote" />
        <view class="list-group" v-else>
          <view v-for="s in roster" :key="s.studentId" class="list-row ge__row">
            <view class="flex-1">
              <text class="t-md">{{ s.realName }}</text>
              <text class="ge__sub">{{ s.studentNo }}</text>
            </view>
            <view class="ge__scores">
              <input class="ge__score-input" type="digit" v-model="scores[s.studentId].usualScore" placeholder="平时" placeholder-class="ge__ph" />
              <input class="ge__score-input" type="digit" v-model="scores[s.studentId].finalScore" placeholder="期末" placeholder-class="ge__ph" />
              <button class="btn btn-ghost ge__save" :disabled="saving === s.studentId" @click="saveScore(s)">
                {{ saving === s.studentId ? '…' : '保存' }}
              </button>
            </view>
          </view>
        </view>

        <MobileSafeAreaBar v-if="active.status !== 'SUBMITTED' && active.status !== 'PUBLISHED'">
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
      roster: [], rosterState: 'loading', rosterNote: '', scores: {}, saving: null, submitting: false
    }
  },
  onLoad() { this.load() },
  methods: {
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
      teacherApi.getGradeRoster(t.gradeTaskId).then((d) => {
        this.roster = (d && d.items) || []
        this.rosterNote = (d && d.note) || '暂无名单'
        this.scores = {}
        this.roster.forEach((s) => { this.scores[s.studentId] = { usualScore: '', finalScore: '' } })
        this.rosterState = 'ready'
      }).catch(() => { this.rosterState = 'error'; toast('名单加载失败') })
    },
    saveScore(s) {
      if (this.saving) return
      const sc = this.scores[s.studentId]
      this.saving = s.studentId
      teacherApi.enterGradeScore(this.active.gradeTaskId, {
        studentId: s.studentId,
        usualScore: sc.usualScore === '' ? null : Number(sc.usualScore),
        finalScore: sc.finalScore === '' ? null : Number(sc.finalScore)
      }).then(() => {
        uni.showToast({ title: '已保存', icon: 'success' })
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '保存失败，请稍后重试'))
        .finally(() => { this.saving = null })
    },
    submitTask() {
      if (this.submitting || !this.active) return
      this.submitting = true
      teacherApi.submitGradeTask(this.active.gradeTaskId).then(() => {
        uni.showToast({ title: '已提交学院审核', icon: 'success' })
        this.active = null
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试'))
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.ge__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ge__reason { display: block; font-size: var(--font-size-xs); color: var(--danger-600); margin-top: 4px; }
.ge__back { display: inline-block; font-size: var(--font-size-sm); color: var(--brand-primary); margin-bottom: var(--space-3); }
.ge__row { align-items: center; }
.ge__scores { display: flex; align-items: center; gap: var(--space-2); flex-shrink: 0; }
.ge__score-input { width: 52px; height: 32px; text-align: center; font-size: var(--font-size-sm); border: 1px solid var(--border-base); border-radius: var(--radius-sm); }
.ge__ph { color: var(--text-tertiary); }
.ge__save { min-height: 32px; padding: 0 var(--space-3); font-size: var(--font-size-sm); }
</style>
