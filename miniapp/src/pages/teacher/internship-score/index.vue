<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="实习成绩" subtitle="查看核算结果 · 补齐缺项 · 提交学校复核" show-back />

    <view class="is__tabs">
      <view class="is__tab" :class="{ 'is-on': tab === 'list' }" @click="tab = 'list'">
        成绩列表<text v-if="list && list.length" class="is__tab-badge">{{ list.length }}</text>
        <text v-if="tab === 'list'" class="is__tab-u" />
      </view>
      <view v-if="canCompute" class="is__tab" :class="{ 'is-on': tab === 'compute' }" @click="onComputeTab">
        核算成绩<text v-if="tab === 'compute'" class="is__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad is__page" v-if="tab === 'list'">
        <view class="card is__batch" v-if="batches.length">
          <view class="is__batch-copy">
            <text class="is__eyebrow">当前成绩批次</text>
            <text class="is__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          </view>
          <picker class="is__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="submitting" @change="onBatch">
            <view class="is__pick-val">切换批次 <text class="is__arrow">▾</text></view>
          </picker>
        </view>

        <view v-if="batches.length && list" class="card is__summary">
          <view class="is__summary-main">
            <text class="is__summary-label">本批次已核算</text>
            <view class="is__summary-value"><text>{{ list.length }}</text><text>人</text></view>
            <text class="is__summary-note">{{ summaryConclusion }}</text>
          </view>
          <view class="is__summary-metrics">
            <view class="is__metric is-danger"><text>{{ incompleteCount }}</text><text>存在缺项</text></view>
            <view class="is__metric is-warning"><text>{{ pendingReviewCount }}</text><text>待学校复核</text></view>
            <view class="is__metric is-success"><text>{{ completedCount }}</text><text>已发布/归档</text></view>
          </view>
        </view>

        <MobileInlineAlert type="info" description="企业评价分只读取已审核评价；教师端负责核算与补齐缺项，最终发布仍由学校管理端完成。" />
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可查看的实习批次。" />
        <MobileGlobalState v-else-if="!list || !list.length" state="empty" title="当前批次尚未核算成绩"
          description="有核算权限的教师可进入“核算成绩”，选择学生并填写评分。" />

        <view class="stack" v-else>
          <view v-for="s in list" :key="s.id" class="card is">
            <view class="row-between is__head">
              <view class="flex-1 is__identity">
                <text class="t-md t-bold">{{ s.studentName || '—' }}</text>
                <text class="is__sub">{{ s.studentNo || '' }}</text>
              </view>
              <MobileStatusTag :label="s.statusLabel" :type="statusTone(s)" />
            </view>

            <view class="is__score-overview">
              <view class="is__total-block">
                <text class="is__total-value">{{ s.totalScore != null ? s.totalScore : '—' }}</text>
                <text class="is__total-label">加权总分</text>
              </view>
              <view class="is__score-grid">
                <view><text>打卡</text><text>{{ scoreText(s.checkinScore) }}</text></view>
                <view><text>周报</text><text>{{ scoreText(s.weeklyScore) }}</text></view>
                <view><text>月报总结</text><text>{{ scoreText(s.monthlyScore) }}</text></view>
                <view><text>企业评价</text><text>{{ s.enterpriseScore != null ? s.enterpriseScore : '待审核' }}</text></view>
                <view><text>学校评价</text><text>{{ scoreText(s.schoolScore) }}</text></view>
              </view>
            </view>

            <view v-if="s.incomplete" class="is__issue">
              <text class="is__issue-title">成绩存在缺项</text>
              <text class="is__issue-text">{{ s.incompleteReason || '请检查各评分来源' }}</text>
            </view>
            <view v-else-if="s.status === 'PENDING_REVIEW'" class="is__pending-box">
              <text class="is__pending-title">已提交学校复核</text>
              <text class="is__pending-text">教师端不能直接发布，请等待学校管理端完成复核。</text>
            </view>

            <view class="is__next" :class="{ 'is-danger': s.incomplete }">
              <text class="is__next-label">下一步</text>
              <text class="is__next-text">{{ nextStepText(s) }}</text>
            </view>
          </view>
        </view>
      </view>

      <view class="page-pad is__page" v-if="tab === 'compute' && canCompute">
        <view class="card is__batch" v-if="batches.length">
          <view class="is__batch-copy">
            <text class="is__eyebrow">当前核算批次</text>
            <text class="is__batch-name">{{ batches[batchIndex]?.name || '请选择批次' }}</text>
          </view>
          <picker class="is__picker" mode="selector" :range="batchLabels" :value="batchIndex" :disabled="submitting" @change="onBatch">
            <view class="is__pick-val">切换批次 <text class="is__arrow">▾</text></view>
          </picker>
        </view>

        <MobileInlineAlert type="info" description="企业评价分由系统读取已审核结果，不能手工覆盖。已有未发布成绩再次核算会携带当前版本，防止覆盖他人修改。" />
        <MobileGlobalState v-if="!batches.length" state="empty" title="暂无实习批次"
          description="当前身份的数据范围内没有可核算的实习批次。" />
        <MobileGlobalState v-else-if="!students.length" state="empty" title="暂无可核算学生"
          description="当前批次仅可为本人指导的实习学生核算成绩。" />

        <template v-else>
          <view class="card is__selected">
            <view class="is__selected-copy">
              <text class="is__selected-label">当前核算学生</text>
              <text class="is__selected-name">{{ selectedStudent?.name || '请选择学生' }}</text>
              <text class="is__selected-meta">{{ selectedStudent?.studentNo || '—' }} · {{ selectedStudent?.enterpriseName || '企业待落实' }}</text>
            </view>
            <MobileStatusTag v-if="selectedExisting" :label="selectedExisting.statusLabel || selectedExisting.status" :type="statusTone(selectedExisting)" />
          </view>

          <view class="card is__form-section">
            <view class="is__section-head">
              <text class="is__step">1</text>
              <view><text class="is__section-title">选择学生</text><text class="is__section-hint">切换学生后自动带出可编辑的已有成绩</text></view>
            </view>
            <view class="is__row">
              <text class="is__label">实习学生 <text class="is__required">*</text></text>
              <picker class="is__picker" mode="selector" :range="studentLabels" :value="studentIndex" @change="onStudent">
                <view class="is__field-value">{{ studentLabels[studentIndex] || '请选择' }}<text class="is__arrow">▾</text></view>
              </picker>
            </view>
          </view>

          <view class="card is__form-section">
            <view class="is__section-head">
              <text class="is__step">2</text>
              <view><text class="is__section-title">录入学校侧评分</text><text class="is__section-hint">所有分值均为0-100整数</text></view>
            </view>
            <view class="is__score-form">
              <view class="is__score-field" v-for="f in SCORE_FIELDS" :key="f.key">
                <view><text class="is__score-name">{{ f.label }}</text><text class="is__score-help">0-100</text></view>
                <input type="number" v-model="scores[f.key]" placeholder="请输入" />
              </view>
            </view>
          </view>

          <view class="card is__source-note">
            <text class="is__source-title">系统自动参与核算</text>
            <text class="is__source-text">企业评价分来自已通过的企业评价；最终总分按照当前批次权重计算。</text>
          </view>
        </template>

        <MobileSafeAreaBar v-if="students.length">
          <button class="btn btn-primary flex-1" :disabled="submitting" @click="submit">{{ submitting ? '核算中…' : (selectedExisting ? '按当前版本重新核算' : '提交核算') }}</button>
        </MobileSafeAreaBar>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { teacherInternshipMyStudents, teacherInternshipScores } from '@/services/internshipApi'
import { useInternshipContextStore } from '@/stores/internshipContext'
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
      tab: 'list', list: null, state: 'loading',
      students: [], studentIndex: 0,
      batches: [], batchId: '', batchIndex: 0,
      scores: { checkinScore: '', weeklyScore: '', monthlyScore: '', schoolScore: '' },
      submitting: false, SCORE_FIELDS
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    studentLabels() { return this.students.map((s) => `${s.name}（${s.studentNo}）· ${s.enterpriseName || '未落实企业'}`) },
    batchLabels() { return this.batches.map((b) => `${b.name} · ${b.status} · ${b.studentCount}人`) },
    canCompute() { return useInternshipContextStore().can('internship.score.manage') },
    incompleteCount() { return (this.list || []).filter((item) => item.incomplete).length },
    pendingReviewCount() { return (this.list || []).filter((item) => item.status === 'PENDING_REVIEW').length },
    completedCount() { return (this.list || []).filter((item) => ['PUBLISHED', 'ARCHIVED'].includes(item.status)).length },
    selectedStudent() { return this.students[this.studentIndex] || null },
    selectedExisting() { return this.findExisting(this.selectedStudent) },
    summaryConclusion() {
      if (!this.list?.length) return '当前批次尚未核算成绩。'
      if (this.incompleteCount) return `优先处理 ${this.incompleteCount} 名学生的成绩缺项。`
      if (this.pendingReviewCount) return `${this.pendingReviewCount} 份成绩等待学校复核。`
      return '当前已核算成绩没有明显缺项。'
    }
  },
  methods: {
    scoreText(value) { return value != null ? value : '—' },
    statusTone(s) { return ['PUBLISHED', 'ARCHIVED'].includes(s.status) ? 'success' : s.incomplete ? 'danger' : 'warning' },
    nextStepText(s) {
      if (s.incomplete) return this.canCompute ? '进入“核算成绩”，选择该学生补齐缺项后重新核算。' : '联系有核算权限的教师补齐缺项。'
      if (s.status === 'PENDING_REVIEW') return '等待学校管理端复核并发布成绩。'
      if (['PUBLISHED', 'ARCHIVED'].includes(s.status)) return '成绩已发布或归档，教师端仅查看。'
      return this.canCompute ? '如评分来源有更新，可按当前版本重新核算。' : '等待学校复核或后续状态更新。'
    },
    async load(done) {
      this.state = 'loading'
      try {
        const context = useInternshipContextStore()
        context.restore()
        await context.load(true)
        this.batches = context.batches || []
        this.batchId = context.selectedBatchId || ''
        this.batchIndex = Math.max(0, this.batches.findIndex((b) => String(b.id) === String(this.batchId)))
        await this.loadScores()
        this.state = 'ready'
      } catch (e) {
        this.state = 'error'
      } finally { if (done) done() }
    },
    async loadScores() {
      if (!this.batchId) { this.list = []; return }
      const data = await teacherInternshipScores(this.batchId)
      this.list = (data && data.list) || []
    },
    async onComputeTab() {
      this.tab = 'compute'
      if (!this.canCompute) return
      await this.loadStudents()
    },
    async onBatch(e) {
      this.batchIndex = Number(e.detail.value)
      const batch = this.batches[this.batchIndex]
      const context = useInternshipContextStore()
      context.selectBatch(batch && batch.id)
      this.batchId = context.selectedBatchId
      this.students = []
      this.studentIndex = 0
      this.state = 'loading'
      try {
        await this.loadScores()
        if (this.tab === 'compute') await this.loadStudents()
        this.state = 'ready'
      } catch (err) {
        this.state = 'error'
        toast((err && err.message) || '批次数据加载失败')
      }
    },
    onStudent(e) {
      this.studentIndex = Number(e.detail.value)
      const stu = this.students[this.studentIndex]
      const existing = this.findExisting(stu)
      if (existing && !['PUBLISHED', 'ARCHIVED'].includes(existing.status)) {
        SCORE_FIELDS.forEach((f) => { this.scores[f.key] = existing[f.key] == null ? '' : String(existing[f.key]) })
      } else {
        this.scores = { checkinScore: '', weeklyScore: '', monthlyScore: '', schoolScore: '' }
      }
    },
    async loadStudents() {
      if (!this.batchId) { this.students = []; return }
      try {
        const data = await teacherInternshipMyStudents(this.batchId)
        this.students = (data && data.list) || []
        this.studentIndex = 0
        this.onStudent({ detail: { value: 0 } })
      } catch (e) {
        this.students = []
        toast((e && e.message) || '学生名单加载失败')
      }
    },
    findExisting(stu) {
      if (!stu) return null
      return (this.list || []).find((x) => String(x.internshipId || x.internId) === String(stu.id)) || null
    },
    submit() {
      if (this.submitting) return
      const stu = this.students[this.studentIndex]
      if (!stu) { toast('请选择实习学生'); return }
      for (const f of SCORE_FIELDS) {
        const v = this.scores[f.key]
        if (v === '' || v === null || v === undefined || !Number.isInteger(Number(v)) || Number(v) < 0 || Number(v) > 100) {
          toast(`${f.label}必须是 0-100 的整数`); return
        }
      }
      const existing = this.findExisting(stu)
      if (existing && ['PUBLISHED', 'ARCHIVED'].includes(existing.status)) {
        toast('该生成绩已发布或归档，不能在教师端直接重算'); return
      }
      this.submitting = true
      const body = { internshipId: stu.id, batchId: this.batchId }
      SCORE_FIELDS.forEach((f) => { body[f.key] = Number(this.scores[f.key]) })
      if (existing) body.expectedVersion = existing.version
      submitLock.run(() => teacherApi.computeInternshipScore(body)).then((result) => {
        uni.showToast({ title: result && result.incomplete ? `已保存，缺：${result.incompleteReason}` : `核算完成，总分 ${result.total}`, icon: 'none' })
        this.scores = { checkinScore: '', weeklyScore: '', monthlyScore: '', schoolScore: '' }
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
.is__tabs{display:flex;gap:var(--space-6);padding:var(--space-3) var(--page-padding-mobile) 0;background:var(--bg-card)}.is__tab{position:relative;font-size:var(--font-size-base);color:var(--text-tertiary);font-weight:var(--font-weight-medium);padding-bottom:var(--space-3)}.is__tab.is-on{color:var(--text-primary);font-weight:var(--font-weight-semibold)}.is__tab-u{position:absolute;left:50%;bottom:0;transform:translateX(-50%);width:22px;height:3px;border-radius:2px;background:var(--teacher-600)}.is__tab-badge{margin-left:4px;font-size:10px;color:#fff;background:var(--danger-500);padding:1px 5px;border-radius:var(--radius-full)}.is__page{display:flex;flex-direction:column;gap:var(--space-3);padding-bottom:calc(var(--safe-bottom) + 88px)}.is__batch{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3)}.is__batch-copy{min-width:0;display:flex;flex-direction:column;gap:3px}.is__eyebrow{font-size:var(--font-size-xs);color:var(--text-tertiary)}.is__batch-name{font-size:var(--font-size-md);font-weight:600;color:var(--text-primary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.is__picker{flex-shrink:0}.is__pick-val{color:var(--teacher-700);font-size:var(--font-size-sm);white-space:nowrap}.is__arrow{margin-left:4px;color:var(--text-tertiary)}.is__summary{display:flex;align-items:stretch;gap:var(--space-3);padding:var(--space-3)}.is__summary-main{flex:1;min-width:0}.is__summary-label{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary)}.is__summary-value{display:flex;align-items:baseline;gap:4px;margin-top:4px}.is__summary-value text:first-child{font-size:34px;line-height:1;font-weight:700;color:var(--teacher-700)}.is__summary-value text:last-child{font-size:var(--font-size-sm);color:var(--text-secondary)}.is__summary-note{display:block;margin-top:8px;font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.is__summary-metrics{width:52%;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));background:var(--gray-50);border-radius:var(--radius-md);overflow:hidden}.is__metric{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;padding:10px 3px;border-left:1px solid var(--border-light);text-align:center}.is__metric:first-child{border-left:0}.is__metric text:first-child{font-size:var(--font-size-lg);font-weight:700;color:var(--text-primary)}.is__metric.is-danger text:first-child{color:var(--danger-600)}.is__metric.is-warning text:first-child{color:var(--warning-700)}.is__metric.is-success text:first-child{color:var(--success-700)}.is__metric text:last-child{font-size:10px;line-height:1.25;color:var(--text-tertiary)}.is{display:flex;flex-direction:column;gap:var(--space-3);padding:var(--space-3)}.is__head{align-items:flex-start}.is__identity{min-width:0}.is__sub{display:block;font-size:var(--font-size-xs);color:var(--text-tertiary);margin-top:3px}.is__score-overview{display:flex;align-items:center;gap:var(--space-3);padding:var(--space-2);background:var(--gray-50);border-radius:var(--radius-md)}.is__total-block{width:82px;flex-shrink:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:8px;border-right:1px solid var(--border-light)}.is__total-value{font-size:30px;line-height:1;font-weight:700;color:var(--teacher-700)}.is__total-label{margin-top:5px;font-size:10px;color:var(--text-tertiary)}.is__score-grid{flex:1;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px 12px}.is__score-grid>view{display:flex;justify-content:space-between;gap:8px;min-width:0}.is__score-grid text:first-child{font-size:10px;color:var(--text-tertiary)}.is__score-grid text:last-child{font-size:var(--font-size-xs);font-weight:600;color:var(--text-primary);word-break:break-word}.is__issue,.is__pending-box{padding:var(--space-2) var(--space-3);border-radius:var(--radius-md)}.is__issue{border:1px solid var(--danger-200,#fecaca);background:var(--danger-50)}.is__pending-box{border:1px solid var(--warning-200,#fed7aa);background:var(--warning-50,#fff7ed)}.is__issue-title,.is__pending-title{display:block;font-size:var(--font-size-sm);font-weight:600}.is__issue-title{color:var(--danger-700)}.is__pending-title{color:var(--warning-800,#9a3412)}.is__issue-text,.is__pending-text{display:block;margin-top:4px;font-size:var(--font-size-xs);line-height:1.5}.is__issue-text{color:var(--danger-600)}.is__pending-text{color:var(--warning-700)}.is__next{display:flex;gap:10px;padding:10px 12px;border-radius:var(--radius-md);background:var(--teacher-50,#eff6ff)}.is__next.is-danger{background:var(--warning-50,#fff7ed)}.is__next-label{flex-shrink:0;font-size:var(--font-size-xs);font-weight:600;color:var(--text-secondary)}.is__next-text{font-size:var(--font-size-xs);line-height:1.5;color:var(--text-secondary)}.is__selected{display:flex;align-items:center;justify-content:space-between;gap:var(--space-3);padding:var(--space-3);background:var(--teacher-50,#eff6ff);border-color:var(--teacher-200,#bfdbfe)}.is__selected-copy{min-width:0}.is__selected-label{display:block;font-size:10px;color:var(--text-tertiary)}.is__selected-name{display:block;margin-top:3px;font-size:var(--font-size-md);font-weight:600;color:var(--text-primary)}.is__selected-meta{display:block;margin-top:3px;font-size:var(--font-size-xs);color:var(--text-secondary);word-break:break-word}.is__form-section{display:flex;flex-direction:column;padding:var(--space-3)}.is__section-head{display:flex;align-items:center;gap:10px;padding-bottom:var(--space-2);border-bottom:1px solid var(--border-light)}.is__step{display:flex;align-items:center;justify-content:center;width:26px;height:26px;flex-shrink:0;border-radius:50%;background:var(--teacher-600);color:#fff;font-size:var(--font-size-sm);font-weight:700}.is__section-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--text-primary)}.is__section-hint{display:block;margin-top:2px;font-size:var(--font-size-xs);color:var(--text-tertiary)}.is__row{display:flex;align-items:center;min-height:52px;border-bottom:1px solid var(--border-light);gap:var(--space-3)}.is__label{width:100px;flex-shrink:0;font-size:var(--font-size-sm);color:var(--text-secondary)}.is__required{color:var(--danger-600)}.is__field-value{min-width:0;font-size:var(--font-size-sm);color:var(--text-primary);text-align:right;word-break:break-word}.is__score-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;padding-top:var(--space-3)}.is__score-field{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:11px 12px;border:1px solid var(--border-light);border-radius:var(--radius-md);background:var(--gray-50)}.is__score-name{display:block;font-size:var(--font-size-sm);color:var(--text-secondary)}.is__score-help{display:block;margin-top:2px;font-size:10px;color:var(--text-tertiary)}.is__score-field input{width:74px;text-align:right;font-size:var(--font-size-lg);color:var(--text-primary)}.is__source-note{padding:var(--space-3);border-color:var(--success-200,#bbf7d0);background:var(--success-50)}.is__source-title{display:block;font-size:var(--font-size-sm);font-weight:600;color:var(--success-800,#166534)}.is__source-text{display:block;margin-top:4px;font-size:var(--font-size-xs);line-height:1.5;color:var(--success-700)}@media(max-width:360px){.is__summary{flex-direction:column}.is__summary-metrics{width:100%}.is__score-overview{align-items:flex-start}.is__score-grid,.is__score-form{grid-template-columns:1fr}.is__batch{align-items:flex-start}}
</style>
