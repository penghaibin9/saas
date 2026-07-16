<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习成绩" subtitle="五项加权核算 · 发布" show-back />

    <view class="is__tabs">
      <view class="is__tab" :class="{ 'is-on': tab === 'list' }" @click="tab = 'list'">
        成绩列表<text v-if="list && list.length" class="is__tab-badge">{{ list.length }}</text>
        <text v-if="tab === 'list'" class="is__tab-u" />
      </view>
      <view class="is__tab" :class="{ 'is-on': tab === 'compute' }" @click="onComputeTab">
        核算成绩<text v-if="tab === 'compute'" class="is__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <!-- 列表 -->
      <view class="page-pad" v-if="tab === 'list'">
        <MobileGlobalState v-if="!list || !list.length" state="empty" title="暂无实习成绩"
          description="核算后的学生实习成绩会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="s in list" :key="s.id" class="card is">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ s.studentName || '—' }}</text>
                <text class="is__sub">{{ s.studentNo || '' }}</text>
              </view>
              <MobileStatusTag :label="s.statusLabel" :type="statusTone(s)" />
            </view>
            <view class="is__scores">
              <text class="is__total">{{ s.totalScore != null ? s.totalScore : '—' }}<text class="is__total-unit">总分</text></text>
              <view class="is__score-grid">
                <text class="is__score-item">打卡 {{ s.checkinScore != null ? s.checkinScore : '—' }}</text>
                <text class="is__score-item">周报 {{ s.weeklyScore != null ? s.weeklyScore : '—' }}</text>
                <text class="is__score-item">月报 {{ s.monthlyScore != null ? s.monthlyScore : '—' }}</text>
                <text class="is__score-item">企业 {{ s.enterpriseScore != null ? s.enterpriseScore : '—' }}</text>
                <text class="is__score-item">学校 {{ s.schoolScore != null ? s.schoolScore : '—' }}</text>
              </view>
            </view>
            <text class="is__incomplete" v-if="s.incomplete">缺项：{{ s.incompleteReason }}</text>
            <button v-if="s.status === 'PENDING_REVIEW' && !s.incomplete" class="btn btn-primary"
              :disabled="acting" @click="publish(s)">发布成绩</button>
          </view>
        </view>
      </view>

      <!-- 核算 -->
      <view class="page-pad" v-if="tab === 'compute'">
        <MobileGlobalState v-if="!students.length" state="empty" title="暂无可核算学生"
          description="仅可为本人指导的实习学生核算成绩。" />
        <view class="card is__form" v-else>
          <view class="is__row">
            <text class="is__label">实习学生</text>
            <picker class="is__picker" mode="selector" :range="studentLabels" :value="studentIndex" @change="(e) => studentIndex = Number(e.detail.value)">
              <view class="is__pick-val">{{ studentLabels[studentIndex] || '请选择' }}<text class="is__arrow">▾</text></view>
            </picker>
          </view>
          <view class="is__row" v-for="f in SCORE_FIELDS" :key="f.key">
            <text class="is__label">{{ f.label }}</text>
            <input class="is__input" type="number" v-model="scores[f.key]" placeholder="0-100" />
          </view>
          <view class="is__row" style="border-bottom:none;">
            <text class="is__label">企业评价分</text>
            <input class="is__input" type="number" v-model="scores.enterpriseScore" placeholder="留空自动取已通过均分" />
          </view>
        </view>
        <MobileInlineAlert type="info" description="企业评价分留空时自动取该生已通过企业评价的均分；四项手填分数需 0-100。" />

        <MobileSafeAreaBar v-if="students.length">
          <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '核算中…' : '提交核算' }}</button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)
const SCORE_FIELDS = [
  { key: 'checkinScore', label: '打卡分' }, { key: 'weeklyScore', label: '周报分' },
  { key: 'monthlyScore', label: '月报总结分' }, { key: 'schoolScore', label: '学校评价分' }
]

export default {
  data() {
    return {
      tab: 'list', list: null, state: 'loading', acting: false,
      students: [], studentIndex: 0,
      scores: { checkinScore: '', weeklyScore: '', monthlyScore: '', schoolScore: '', enterpriseScore: '' },
      submitting: false, SCORE_FIELDS
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    studentLabels() { return this.students.map((s) => `${s.name}（${s.studentNo}）· ${s.enterpriseName || '未落实企业'}`) }
  },
  methods: {
    statusTone(s) { return s.status === 'PUBLISHED' ? 'success' : s.incomplete ? 'danger' : 'warning' },
    load(done) {
      this.state = 'loading'
      teacherApi.getInternshipScoreList()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    onComputeTab() {
      this.tab = 'compute'
      if (!this.students.length) {
        teacherApi.getInternshipMyStudents().then((d) => { this.students = (d && d.list) || [] }).catch(() => {})
      }
    },
    publish(s) {
      if (this.acting) return
      uni.showModal({
        title: '发布成绩', content: `确认发布「${s.studentName}」的实习成绩（总分 ${s.totalScore}）？发布后学生可查看。`,
        success: (r) => {
          if (!r.confirm) return
          this.acting = true
          teacherApi.publishInternshipScore(s.id)
            .then(() => { toast('已发布'); this.load() })
            .catch((e) => {
              const code = e && String(e.code)
              if (code === 'DATA_CONFLICT') { toast((e && e.message) || '当前状态不可发布，正在刷新'); this.load() }
              else toast((e && e.message) || '发布失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    },
    submit() {
      if (this.submitting) return
      const stu = this.students[this.studentIndex]
      if (!stu) { toast('请选择实习学生'); return }
      for (const f of SCORE_FIELDS) {
        const v = this.scores[f.key]
        if (v === '' || v === null || v === undefined || Number(v) < 0 || Number(v) > 100) {
          toast(`${f.label}必须是 0-100 的数字`); return
        }
      }
      const ent = this.scores.enterpriseScore
      if (ent !== '' && ent !== null && ent !== undefined && (Number(ent) < 0 || Number(ent) > 100)) {
        toast('企业评价分必须是 0-100 的数字'); return
      }
      this.submitting = true
      const body = { internshipId: stu.id }
      SCORE_FIELDS.forEach((f) => { body[f.key] = Number(this.scores[f.key]) })
      if (ent !== '' && ent !== null && ent !== undefined) body.enterpriseScore = Number(ent)
      submitLock.run(() => teacherApi.computeInternshipScore(body)).then((r) => {
        uni.showToast({ title: r && r.incomplete ? `已保存，缺：${r.incompleteReason}` : `核算完成，总分 ${r.total}`, icon: 'none' })
        this.scores = { checkinScore: '', weeklyScore: '', monthlyScore: '', schoolScore: '', enterpriseScore: '' }
        this.tab = 'list'; this.load()
      }).catch((e) => {
        if (e && e.code === 'LOCKED') return
        if (e && e.biz) toast(normalizeError(e).text)
        else toast('网络异常，提交未成功，请稍后重试')
      }).finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.is__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.is__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.is__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.is__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.is__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.is { display: flex; flex-direction: column; gap: var(--space-2); }
.is__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.is__scores { display: flex; align-items: center; gap: var(--space-3); background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.is__total { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--teacher-700); flex-shrink: 0; }
.is__total-unit { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: 2px; }
.is__score-grid { display: flex; flex-wrap: wrap; gap: 4px 10px; flex: 1; }
.is__score-item { font-size: var(--font-size-xs); color: var(--text-secondary); }
.is__incomplete { font-size: var(--font-size-xs); color: var(--danger-600); }
.is__form { display: flex; flex-direction: column; }
.is__row { display: flex; align-items: center; min-height: 48px; border-bottom: 1px solid var(--border-light); }
.is__label { width: 100px; flex-shrink: 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.is__picker { flex: 1; }
.is__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.is__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
.is__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
</style>
