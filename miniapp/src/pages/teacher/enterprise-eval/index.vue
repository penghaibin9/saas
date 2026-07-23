<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="企业评价" subtitle="学校录入纸质评价 · 来源标记「学校录入」" show-back />

    <view class="ee__tabs">
      <view class="ee__tab" :class="{ 'is-on': tab === 'list' }" @click="tab = 'list'">
        评价列表<text v-if="list && list.length" class="ee__tab-badge">{{ list.length }}</text>
        <text v-if="tab === 'list'" class="ee__tab-u" />
      </view>
      <view class="ee__tab" :class="{ 'is-on': tab === 'create' }" @click="onCreateTab">
        录入评价<text v-if="tab === 'create'" class="ee__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <!-- 列表 -->
      <view class="page-pad" v-if="tab === 'list'">
        <MobileGlobalState v-if="!list || !list.length" state="empty" title="暂无企业评价"
          description="学校录入的企业纸质评价会出现在这里（来源「学校录入」，非企业端登录提交）。" />
        <view class="stack" v-else>
          <view v-for="e in list" :key="e.id" class="card ee">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ e.studentName || '—' }}</text>
                <text class="ee__sub">{{ e.studentNo || '' }} · 企业导师 {{ e.mentorName || '—' }} · {{ e.sourceLabel }}</text>
              </view>
              <MobileStatusTag :label="e.reviewStatusLabel" :type="reviewTone(e.reviewStatus)" />
            </view>
            <view class="ee__scores">
              <text class="ee__avg">{{ e.avgScore }}<text class="ee__avg-unit">均分</text></text>
              <view class="ee__score-grid">
                <text class="ee__score-item">出勤 {{ e.attendanceScore }}</text>
                <text class="ee__score-item">技能 {{ e.skillScore }}</text>
                <text class="ee__score-item">态度 {{ e.attitudeScore }}</text>
                <text class="ee__score-item">协作 {{ e.collaborationScore }}</text>
                <text class="ee__score-item">安全 {{ e.safetyScore }}</text>
              </view>
            </view>
            <text class="ee__hire" v-if="e.recommendHire">✓ 企业建议留用</text>
            <view class="ee__actions" v-if="e.reviewStatus === 'PENDING'">
              <button class="ee__reject flex-1" :disabled="acting" @click="review(e, 'RETURN')">退回</button>
              <button class="ee__approve flex-1" :disabled="acting" @click="review(e, 'APPROVE')">通过</button>
            </view>
          </view>
        </view>
      </view>

      <!-- 录入 -->
      <view class="page-pad" v-if="tab === 'create'">
        <MobileGlobalState v-if="!students.length" state="empty" title="暂无可录入学生"
          description="仅可为本人指导的实习学生录入企业评价。" />
        <view class="card ee__form" v-else>
          <view class="ee__row">
            <text class="ee__label">实习学生</text>
            <picker class="ee__picker" mode="selector" :range="studentLabels" :value="studentIndex" @change="(e) => studentIndex = Number(e.detail.value)">
              <view class="ee__pick-val">{{ studentLabels[studentIndex] || '请选择' }}<text class="ee__arrow">▾</text></view>
            </picker>
          </view>
          <view class="ee__row">
            <text class="ee__label">企业导师姓名</text>
            <input class="ee__input" v-model="mentorName" placeholder="必填，学校录入须可追溯" maxlength="20" />
          </view>
          <view class="ee__row" v-for="f in SCORE_FIELDS" :key="f.key">
            <text class="ee__label">{{ f.label }}评分</text>
            <input class="ee__input" type="number" v-model="scores[f.key]" placeholder="0-100" />
          </view>
          <view class="ee__row ee__row--top">
            <text class="ee__label">总体评语</text>
            <textarea class="ee__textarea" v-model="overallComment" :maxlength="300" placeholder="可选" placeholder-class="ee__ph" />
          </view>
          <view class="ee__row" style="border-bottom:none;">
            <text class="ee__label">建议留用</text>
            <switch :checked="recommendHire" color="var(--teacher-600)" @change="(e) => recommendHire = e.detail.value" />
          </view>
        </view>

        <MobileSafeAreaBar v-if="students.length">
          <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '提交中…' : '保存企业评价' }}</button>
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
  { key: 'attendanceScore', label: '出勤' }, { key: 'skillScore', label: '技能' },
  { key: 'attitudeScore', label: '态度' }, { key: 'collaborationScore', label: '协作' },
  { key: 'safetyScore', label: '安全纪律' }
]

export default {
  data() {
    return {
      tab: 'list', list: null, state: 'loading', acting: false,
      students: [], studentIndex: 0, mentorName: '', overallComment: '', recommendHire: false,
      scores: { attendanceScore: '', skillScore: '', attitudeScore: '', collaborationScore: '', safetyScore: '' },
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
    reviewTone(s) { return s === 'APPROVED' ? 'success' : s === 'RETURNED' ? 'danger' : 'warning' },
    load(done) {
      this.state = 'loading'
      teacherApi.getEnterpriseEvalPending()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    onCreateTab() {
      this.tab = 'create'
      if (!this.students.length) {
        teacherApi.getInternshipMyStudents().then((d) => { this.students = (d && d.list) || [] }).catch(() => {})
      }
    },
    review(e, action) {
      if (this.acting) return
      const reject = action === 'RETURN'
      uni.showModal({
        title: reject ? '退回评价' : '通过评价',
        editable: true, placeholderText: reject ? '请填写退回原因（≥5 字）' : '可填写审核意见（可选）',
        content: '',
        success: (r) => {
          if (!r.confirm) return
          const comment = (r.content || '').trim()
          if (reject && comment.length < 5) { toast('退回原因至少 5 个字'); return }
          this.acting = true
          teacherApi.reviewEnterpriseEval(e.id, action, comment)
            .then(() => { toast(reject ? '已退回' : '已通过'); this.load() })
            .catch((err) => {
              const code = err && String(err.code)
              if (code === 'DATA_CONFLICT') { toast('该评价已被处理，正在刷新'); this.load() }
              else if (code && code.startsWith('403')) toast((err && err.message) || '不在你的数据范围内')
              else toast((err && err.message) || (reject ? '退回' : '通过') + '失败，请重试')
            })
            .finally(() => { this.acting = false })
        }
      })
    },
    submit() {
      if (this.submitting) return
      const stu = this.students[this.studentIndex]
      if (!stu) { toast('请选择实习学生'); return }
      if (!this.mentorName.trim()) { toast('企业导师姓名必填'); return }
      for (const f of SCORE_FIELDS) {
        const v = this.scores[f.key]
        if (v === '' || v === null || v === undefined || Number(v) < 0 || Number(v) > 100) {
          toast(`${f.label}评分必须是 0-100 的整数`); return
        }
      }
      this.submitting = true
      const body = {
        internshipId: stu.id, mentorName: this.mentorName.trim(),
        overallComment: this.overallComment.trim(), recommendHire: this.recommendHire
      }
      SCORE_FIELDS.forEach((f) => { body[f.key] = Number(this.scores[f.key]) })
      submitLock.run(() => teacherApi.createEnterpriseEval(body)).then(() => {
        uni.showToast({ title: '企业评价已保存', icon: 'success' })
        this.mentorName = ''; this.overallComment = ''; this.recommendHire = false
        this.scores = { attendanceScore: '', skillScore: '', attitudeScore: '', collaborationScore: '', safetyScore: '' }
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
.ee__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.ee__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.ee__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.ee__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.ee__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.ee { display: flex; flex-direction: column; gap: var(--space-2); }
.ee__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ee__scores { display: flex; align-items: center; gap: var(--space-3); background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.ee__avg { font-size: var(--font-size-metric-sm); font-weight: var(--font-weight-semibold); color: var(--teacher-700); flex-shrink: 0; }
.ee__avg-unit { font-size: var(--font-size-xs); color: var(--text-tertiary); margin-left: 2px; }
.ee__score-grid { display: flex; flex-wrap: wrap; gap: 4px 10px; flex: 1; }
.ee__score-item { font-size: var(--font-size-xs); color: var(--text-secondary); }
.ee__hire { font-size: var(--font-size-xs); color: var(--success-600); }
.ee__actions { display: flex; gap: var(--space-2); }
.ee__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.ee__reject::after { border: none; }
.ee__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.ee__approve::after { border: none; }
.ee__form { display: flex; flex-direction: column; }
.ee__row { display: flex; align-items: center; min-height: 48px; border-bottom: 1px solid var(--border-light); }
.ee__row--top { align-items: flex-start; padding-top: var(--space-3); border-bottom: none; }
.ee__label { width: 92px; flex-shrink: 0; font-size: var(--font-size-base); color: var(--text-secondary); }
.ee__picker { flex: 1; }
.ee__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.ee__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
.ee__input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.ee__textarea { flex: 1; min-height: 72px; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; }
.ee__ph { color: var(--text-tertiary); }
</style>
