<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="教学评价" subtitle="自评 · 同行 · 督导" show-back />

    <view class="ev__tabs">
      <view class="ev__tab" :class="{ 'is-on': tab === 'tasks' }" @click="switchTab('tasks')">
        我的任务<text v-if="tasks.length" class="ev__tab-badge">{{ tasks.length }}</text>
        <text v-if="tab === 'tasks'" class="ev__tab-u" />
      </view>
      <view class="ev__tab" :class="{ 'is-on': tab === 'results' }" @click="switchTab('results')">
        我的结果
        <text v-if="tab === 'results'" class="ev__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <!-- 我的任务 -->
      <view class="page-pad" v-if="tab === 'tasks'">
        <view class="card ev__type-row">
          <text class="ev__row-k">评价类型</text>
          <picker class="ev__picker" mode="selector" :range="typeLabels" :value="typeIndex" @change="onType">
            <view class="ev__pick-val">{{ typeLabels[typeIndex] }}<text class="ev__arrow">▾</text></view>
          </picker>
        </view>

        <MobileGlobalState v-if="!tasks.length" state="empty" :title="taskError || '暂无待评价任务'"
          :description="taskError ? '请下拉重试或切换评价类型。' : '轮到你评价的任务会出现在这里。'" />
        <view class="stack" v-else>
          <view v-for="t in tasks" :key="t.taskId" class="card ev">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ t.courseName || '—' }}</text>
                <text class="ev__sub">{{ t.teacherName || '' }}</text>
              </view>
              <MobileStatusTag :label="t.status === 'SUBMITTED' ? '已提交' : '待提交'"
                :type="t.status === 'SUBMITTED' ? 'success' : 'warning'" />
            </view>
            <view class="ev__actions" v-if="t.status !== 'SUBMITTED'">
              <button class="btn btn-primary flex-1" :disabled="acting" @click="openSubmit(t)">去评价</button>
            </view>
          </view>
        </view>

        <!-- 提交表单 -->
        <template v-if="submitTarget">
          <view class="section-head"><text class="section-head__title">评价「{{ submitTarget.courseName }}」</text></view>
          <view class="card ev__form">
            <view class="ev__row">
              <text class="ev__row-k">评分</text>
              <input class="ev__input" type="number" v-model="score" placeholder="0-100" />
            </view>
            <view class="ev__row" style="border-bottom:none; align-items:flex-start;">
              <text class="ev__row-k" style="padding-top:10px;">评语</text>
              <textarea class="ev__textarea" v-model="comment" placeholder="可选，填写具体评价意见" />
            </view>
          </view>
          <MobileSafeAreaBar>
            <button class="btn btn-ghost flex-1" :disabled="submitting" @click="submitTarget = null">取消</button>
            <button class="btn btn-primary flex-1" :disabled="submitting" @click="doSubmitEvaluation">{{ submitting ? '提交中…' : '提交评价' }}</button>
          </MobileSafeAreaBar>
        </template>
      </view>

      <!-- 我的结果 -->
      <view class="page-pad" v-if="tab === 'results'">
        <MobileGlobalState v-if="!results.length" state="empty" title="暂无已发布结果"
          description="批次出结果并发布后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="r in results" :key="r.resultId" class="card ev">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ r.courseName || '—' }}</text>
                <text class="ev__sub">{{ r.batchName || '' }}</text>
              </view>
              <text class="ev__score">{{ r.studentAvg != null ? r.studentAvg : '—' }}</text>
            </view>
            <view class="ev__row"><text class="ev__row-k">等级</text><text class="flex-1 t-sm">{{ levelLabel(r.level) }}（{{ r.studentCount }} 人评）</text></view>
            <view class="ev__actions">
              <button class="btn btn-ghost flex-1" :disabled="acting" @click="doAppeal(r)">对结果申诉</button>
            </view>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { toast } from '@/utils/nav'

const TYPES = [{ key: 'SELF', label: '自评' }, { key: 'PEER', label: '同行评价' }, { key: 'SUPERVISOR', label: '督导评价' }]
const LEVEL_LABELS = { EXCELLENT: '优秀', GOOD: '良好', QUALIFIED: '合格', UNQUALIFIED: '不合格' }

export default {
  data() {
    return {
      tab: 'tasks', state: 'loading', tasks: null, results: null, taskError: '',
      typeIndex: 0, acting: false, submitTarget: null, score: '', comment: '', submitting: false
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    typeLabels() { return TYPES.map((t) => t.label) }
  },
  methods: {
    levelLabel(l) { return LEVEL_LABELS[l] || l || '—' },
    switchTab(t) {
      this.tab = t
      if (t === 'results' && !this.results) this.loadResults()
    },
    onType(e) { this.typeIndex = Number(e.detail.value); this.loadTasks() },
    load(done) {
      this.state = 'loading'
      this.loadTasks(() => { this.state = 'ready'; done && done() })
    },
    loadTasks(done) {
      this.taskError = ''
      teacherApi.getAcademicEvaluationMyTasks(TYPES[this.typeIndex].key).then((d) => {
        this.tasks = (d && d.list) || []
        this.state = 'ready'
      }).catch((e) => {
        this.tasks = []
        this.taskError = (e && e.message) || '任务加载失败'
        this.state = 'error'
      }).finally(() => { done && done() })
    },
    loadResults() {
      teacherApi.getAcademicEvaluationResults().then((d) => {
        this.results = (d && d.list) || []
      }).catch((e) => {
        this.results = []
        toast((e && e.message) || '结果加载失败')
      })
    },
    openSubmit(t) { this.submitTarget = t; this.score = ''; this.comment = '' },
    doSubmitEvaluation() {
      if (this.submitting || !this.submitTarget) return
      const score = this.score === '' ? null : Number(this.score)
      if (score === null || Number.isNaN(score) || score < 0 || score > 100) {
        toast('请填写 0-100 的评分'); return
      }
      this.submitting = true
      teacherApi.submitAcademicEvaluation(this.submitTarget.taskId, {
        answers: [{ q: '综合评分', score }], objectiveScore: score, comment: this.comment.trim() || null
      }).then(() => {
        toast('已提交')
        this.submitTarget = null
        this.loadTasks()
      }).catch((e) => {
        const code = e && String(e.code)
        if (code === 'DATA_CONFLICT') toast((e && e.message) || '该任务已提交，不可重复提交')
        else toast((e && e.message) || '提交失败，请重试')
      }).finally(() => { this.submitting = false })
    },
    doAppeal(r) {
      if (this.acting) return
      uni.showModal({
        title: '对结果申诉', editable: true, placeholderText: '请填写申诉理由（≥5 字）', content: '',
        success: (resp) => {
          if (!resp.confirm) return
          const reason = (resp.content || '').trim()
          if (reason.length < 5) { toast('申诉理由至少 5 个字'); return }
          this.acting = true
          teacherApi.appealAcademicEvaluation(r.resultId, reason)
            .then(() => toast('申诉已提交'))
            .catch((e) => toast((e && e.message) || '申诉失败，请重试'))
            .finally(() => { this.acting = false })
        }
      })
    }
  }
}
</script>

<style scoped>
.ev__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.ev__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.ev__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.ev__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.ev__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.ev__type-row { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-3); }
.ev__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); flex-shrink: 0; width: 64px; }
.ev__picker { flex: 1; }
.ev__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.ev__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
.ev { display: flex; flex-direction: column; gap: var(--space-2); }
.ev__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ev__score { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--teacher-600); }
.ev__row { display: flex; align-items: center; gap: var(--space-3); min-height: 44px; border-bottom: 1px solid var(--border-light); }
.ev__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.ev__form { display: flex; flex-direction: column; }
.ev__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.ev__textarea { flex: 1; min-height: 72px; font-size: var(--font-size-base); color: var(--text-primary); padding: 10px 0; }
</style>
