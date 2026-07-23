<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="毕设任务书" subtitle="下达 · 变更" show-back />

    <view class="tb__tabs">
      <view class="tb__tab" :class="{ 'is-on': tab === 'list' }" @click="tab = 'list'">
        任务书列表<text v-if="list && list.length" class="tb__tab-badge">{{ list.length }}</text>
        <text v-if="tab === 'list'" class="tb__tab-u" />
      </view>
      <view class="tb__tab" :class="{ 'is-on': tab === 'issue' }" @click="onIssueTab">
        下达任务书<text v-if="tab === 'issue'" class="tb__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <!-- 列表 -->
      <view class="page-pad" v-if="tab === 'list'">
        <MobileGlobalState v-if="!list || !list.length" state="empty" title="暂无任务书"
          description="为本人指导学生下达任务书后会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="t in list" :key="t.id" class="card tb">
            <view class="row-between" @click="toggle(t)">
              <view class="flex-1">
                <text class="t-md t-bold">{{ t.studentName || '—' }}</text>
                <text class="tb__sub">{{ t.studentNo || '' }} · v{{ t.taskbookVersion }}</text>
              </view>
              <MobileStatusTag :label="t.statusLabel" :type="t.statusTone || 'default'" />
            </view>
            <view class="tb__row"><text class="tb__row-k">培养目标</text><text class="flex-1 t-sm">{{ t.objective || '—' }}</text></view>

            <template v-if="expanded === t.id && t.status === 'CONFIRMED'">
              <view class="tb__row tb__row--top">
                <text class="tb__row-k">任务内容</text>
                <textarea class="tb__textarea" v-model="drafts[t.id].content" :maxlength="1000" placeholder-class="tb__ph" />
              </view>
              <view class="tb__row tb__row--top">
                <text class="tb__row-k">进度计划</text>
                <textarea class="tb__textarea tb__textarea--sm" v-model="drafts[t.id].progressPlan" :maxlength="500" placeholder-class="tb__ph" />
              </view>
              <view class="tb__row tb__row--top">
                <text class="tb__row-k">成果要求</text>
                <textarea class="tb__textarea tb__textarea--sm" v-model="drafts[t.id].outcomeRequirement" :maxlength="500" placeholder-class="tb__ph" />
              </view>
              <view class="tb__row tb__row--top">
                <text class="tb__row-k">变更原因</text>
                <textarea class="tb__textarea tb__textarea--sm" v-model="drafts[t.id].reason" :maxlength="200" placeholder="请填写变更原因（≥5 字，必填）" placeholder-class="tb__ph" />
              </view>
              <button class="btn btn-primary" :disabled="acting" @click="submitChange(t)">提交变更（学生需重新确认）</button>
            </template>
            <text class="tb__hint" v-else-if="t.status === 'CONFIRMED'" @click="toggle(t)">点击发起变更 ›</text>
            <text class="tb__hint" v-else-if="t.status === 'PENDING_CONFIRM'">等待学生确认</text>
            <text class="tb__hint" v-else-if="t.status === 'CHANGE_PENDING'">变更已提交，等待学生重新确认</text>
          </view>
        </view>
      </view>

      <!-- 下达 -->
      <view class="page-pad" v-if="tab === 'issue'">
        <MobileGlobalState v-if="!students.length" state="empty" title="暂无可下达学生"
          description="仅可为本人指导的毕设学生下达任务书。" />
        <view class="card tb__form" v-else>
          <view class="tb__row">
            <text class="tb__row-k">指导学生</text>
            <picker class="tb__picker" mode="selector" :range="studentLabels" :value="studentIndex" @change="(e) => studentIndex = Number(e.detail.value)">
              <view class="tb__pick-val">{{ studentLabels[studentIndex] || '请选择' }}<text class="tb__arrow">▾</text></view>
            </picker>
          </view>
          <view class="tb__row tb__row--top">
            <text class="tb__row-k">培养目标</text>
            <textarea class="tb__textarea" v-model="issueForm.objective" :maxlength="500" placeholder="请填写培养目标（必填）" placeholder-class="tb__ph" />
          </view>
          <view class="tb__row tb__row--top">
            <text class="tb__row-k">任务内容</text>
            <textarea class="tb__textarea" v-model="issueForm.content" :maxlength="1000" placeholder="请填写任务内容（必填）" placeholder-class="tb__ph" />
          </view>
          <view class="tb__row tb__row--top">
            <text class="tb__row-k">进度计划</text>
            <textarea class="tb__textarea tb__textarea--sm" v-model="issueForm.progressPlan" :maxlength="500" placeholder="可选" placeholder-class="tb__ph" />
          </view>
          <view class="tb__row tb__row--top" style="border-bottom:none;">
            <text class="tb__row-k">成果要求</text>
            <textarea class="tb__textarea tb__textarea--sm" v-model="issueForm.outcomeRequirement" :maxlength="500" placeholder="可选" placeholder-class="tb__ph" />
          </view>
        </view>
        <MobileSafeAreaBar v-if="students.length">
          <button class="btn btn-primary flex-1" :disabled="submitting" @click="submitIssue">{{ submitting ? '下达中…' : '下达任务书' }}</button>
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

export default {
  data() {
    return {
      tab: 'list', list: null, state: 'loading', expanded: null, drafts: {}, acting: false,
      students: [], studentIndex: 0,
      issueForm: { objective: '', content: '', progressPlan: '', outcomeRequirement: '' },
      submitting: false
    }
  },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  computed: {
    studentLabels() { return this.students.map((s) => `${s.name}（${s.studentNo}）· ${s.topicTitle || '未选题'}`) }
  },
  methods: {
    load(done) {
      this.state = 'loading'
      teacherApi.getGraduationTaskbookList()
        .then((d) => { this.list = (d && d.list) || []; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
        .finally(() => { if (done) done() })
    },
    onIssueTab() {
      this.tab = 'issue'
      if (!this.students.length) {
        teacherApi.getGraduationMyStudents().then((d) => { this.students = d || [] }).catch(() => {})
      }
    },
    toggle(t) {
      if (t.status !== 'CONFIRMED') return
      if (this.expanded === t.id) { this.expanded = null; return }
      this.expanded = t.id
      if (!this.drafts[t.id]) {
        const draft = { content: t.content || '', progressPlan: t.progressPlan || '',
          outcomeRequirement: t.outcomeRequirement || '', reason: '' }
        this.$set ? this.$set(this.drafts, t.id, draft) : (this.drafts[t.id] = draft)
      }
    },
    submitChange(t) {
      if (this.acting) return
      const draft = this.drafts[t.id] || {}
      if ((draft.reason || '').trim().length < 5) { toast('变更原因至少 5 个字'); return }
      this.acting = true
      teacherApi.changeGraduationTaskbook(t.gdStudentId, {
        content: draft.content, progressPlan: draft.progressPlan,
        outcomeRequirement: draft.outcomeRequirement, reason: draft.reason.trim()
      }).then(() => { toast('已提交变更'); this.expanded = null; this.load() })
        .catch((e) => {
          const code = e && String(e.code)
          if (code === 'DATA_CONFLICT') { toast((e && e.message) || '当前状态不可变更，正在刷新'); this.load() }
          else toast((e && e.message) || '提交失败，请重试')
        })
        .finally(() => { this.acting = false })
    },
    submitIssue() {
      if (this.submitting) return
      const stu = this.students[this.studentIndex]
      if (!stu) { toast('请选择指导学生'); return }
      if (!this.issueForm.objective.trim()) { toast('培养目标必填'); return }
      if (!this.issueForm.content.trim()) { toast('任务内容必填'); return }
      this.submitting = true
      submitLock.run(() => teacherApi.issueGraduationTaskbook(stu.gdStudentId, {
        objective: this.issueForm.objective.trim(), content: this.issueForm.content.trim(),
        progressPlan: this.issueForm.progressPlan.trim(), outcomeRequirement: this.issueForm.outcomeRequirement.trim()
      })).then(() => {
        uni.showToast({ title: '任务书已下达', icon: 'success' })
        this.issueForm = { objective: '', content: '', progressPlan: '', outcomeRequirement: '' }
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
.tb__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.tb__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.tb__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.tb__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.tb__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.tb { display: flex; flex-direction: column; gap: var(--space-2); }
.tb__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.tb__row { display: flex; align-items: center; gap: var(--space-3); min-height: 40px; }
.tb__row--top { flex-direction: column; align-items: stretch; gap: 4px; min-height: 0; }
.tb__row-k { font-size: var(--font-size-sm); color: var(--text-tertiary); flex-shrink: 0; }
.tb__hint { font-size: var(--font-size-xs); color: var(--teacher-600); }
.tb__textarea { min-height: 64px; font-size: var(--font-size-base); color: var(--text-primary); line-height: 1.6; background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2); }
.tb__textarea--sm { min-height: 48px; }
.tb__ph { color: var(--text-tertiary); }
.tb__form { display: flex; flex-direction: column; gap: var(--space-3); }
.tb__picker { flex: 1; }
.tb__pick-val { font-size: var(--font-size-base); color: var(--text-primary); text-align: right; }
.tb__arrow { color: var(--text-tertiary); font-size: var(--font-size-xs); margin-left: 4px; }
</style>
