<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="毕设选题审核" subtitle="本人指导题目的志愿确认与变更审核" show-back />

    <view class="gt__tabs">
      <view class="gt__tab" :class="{ 'is-on': tab === 'choice' }" @click="switchTab('choice')">
        志愿确认<text v-if="choices && choices.length" class="gt__tab-badge">{{ choices.length }}</text>
        <text v-if="tab === 'choice'" class="gt__tab-u" />
      </view>
      <view class="gt__tab" :class="{ 'is-on': tab === 'change' }" @click="switchTab('change')">
        变更审核<text v-if="changes && changes.length" class="gt__tab-badge">{{ changes.length }}</text>
        <text v-if="tab === 'change'" class="gt__tab-u" />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <!-- 志愿确认 -->
      <view class="page-pad" v-if="tab === 'choice'">
        <MobileGlobalState v-if="!choices || !choices.length" state="empty" title="暂无待确认志愿"
          description="学生填报到你所指导题目的志愿会出现在这里，确认即录取该生到该题目。" />
        <view class="stack" v-else>
          <view v-for="c in choices" :key="c.id" class="card gt">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ c.studentName || '—' }}</text>
                <text class="gt__sub">{{ c.studentNo || '' }} · 第 {{ c.choiceOrder }} 志愿</text>
              </view>
              <MobileStatusTag :label="c.statusLabel || '待确认'" type="warning" />
            </view>
            <view class="gt__topic"><text class="gt__topic-label">题目</text><text class="flex-1 t-sm">{{ c.topicTitle || '—' }}</text></view>
            <view class="gt__actions">
              <button class="gt__reject flex-1" @click="reviewChoice(c, 'REJECT')">驳回</button>
              <button class="gt__approve flex-1" @click="reviewChoice(c, 'CONFIRM')">确认录取</button>
            </view>
          </view>
        </view>
      </view>

      <!-- 变更审核 -->
      <view class="page-pad" v-if="tab === 'change'">
        <MobileGlobalState v-if="!changes || !changes.length" state="empty" title="暂无待审变更"
          description="与你指导题目相关（原题目或新题目导师为本人）的换题申请会出现在这里。" />
        <view class="stack" v-else>
          <view v-for="r in changes" :key="r.id" class="card gt">
            <view class="row-between">
              <view class="flex-1">
                <text class="t-md t-bold">{{ r.studentName || '—' }}</text>
                <text class="gt__sub">{{ r.studentNo || '' }} · 申请于 {{ (r.requestedAt || '').slice(0, 16).replace('T', ' ') }}</text>
              </view>
              <MobileStatusTag :label="r.statusLabel || '待审'" :type="r.statusTone || 'warning'" />
            </view>
            <view class="gt__change">
              <view class="gt__change-row"><text class="gt__change-k">原题目</text><text class="flex-1 t-sm">{{ r.oldTopicTitle || '—' }}<text class="gt__change-adv">（{{ r.oldAdvisorName || '—' }}）</text></text></view>
              <view class="gt__change-arrow">↓</view>
              <view class="gt__change-row"><text class="gt__change-k">新题目</text><text class="flex-1 t-sm">{{ r.newTopicTitle || '—' }}<text class="gt__change-adv">（{{ r.newAdvisorName || '—' }}）</text></text></view>
            </view>
            <view class="gt__reason"><text class="gt__reason-k">变更理由</text><text class="flex-1 t-sm">{{ r.reason || '—' }}</text></view>
            <view class="gt__actions">
              <button class="gt__reject flex-1" @click="reviewChange(r, 'REJECT')">驳回</button>
              <button class="gt__approve flex-1" @click="reviewChange(r, 'APPROVE')">通过</button>
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

export default {
  data() { return { tab: 'choice', choices: null, changes: null, state: 'loading', acting: false } },
  onLoad() { this.load() },
  onPullDownRefresh() {
    if (this.state === 'loading') { uni.stopPullDownRefresh(); return }
    this.load(() => uni.stopPullDownRefresh())
  },
  methods: {
    switchTab(t) { if (this.tab !== t) { this.tab = t; if ((t === 'choice' && !this.choices) || (t === 'change' && !this.changes)) this.load() } },
    load(done) {
      this.state = 'loading'
      Promise.all([
        teacherApi.getGraduationChoicesPending().catch(() => []),
        teacherApi.getGraduationChangeRequestsPending().catch(() => [])
      ]).then(([choices, changes]) => {
        this.choices = Array.isArray(choices) ? choices : []
        this.changes = Array.isArray(changes) ? changes : []
        this.state = 'ready'
      }).catch(() => { this.state = 'error' }).finally(() => { if (done) done() })
    },
    reviewChoice(c, action) {
      if (this.acting) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回志愿' : '确认录取',
        editable: reject, placeholderText: reject ? '请填写驳回原因（学生可见）' : '',
        content: reject ? '' : `确认录取「${c.studentName}」到题目「${c.topicTitle}」？该生同轮其余志愿将自动关闭。`,
        success: (r) => {
          if (!r.confirm) return
          if (reject && !(r.content || '').trim()) { toast('请填写驳回原因'); return }
          this.acting = true
          teacherApi.reviewGraduationChoice(c.id, action, r.content || '')
            .then(() => { toast(reject ? '已驳回' : '已确认录取'); this.load() })
            .catch((e) => this._err(e, reject ? '驳回' : '确认'))
            .finally(() => { this.acting = false })
        }
      })
    },
    reviewChange(r0, action) {
      if (this.acting) return
      const reject = action === 'REJECT'
      uni.showModal({
        title: reject ? '驳回变更' : '通过变更',
        editable: true, placeholderText: reject ? '请填写驳回意见' : '可填写审核意见（可选）',
        content: '',
        success: (r) => {
          if (!r.confirm) return
          if (reject && !(r.content || '').trim()) { toast('请填写驳回意见'); return }
          this.acting = true
          teacherApi.reviewGraduationChangeRequest(r0.id, action, r.content || '')
            .then(() => { toast(reject ? '已驳回' : '已通过'); this.load() })
            .catch((e) => this._err(e, reject ? '驳回' : '通过'))
            .finally(() => { this.acting = false })
        }
      })
    },
    _err(e, label) {
      const code = e && String(e.code)
      if (code && (code.startsWith('409') || code === 'DATA_CONFLICT')) { toast('该记录已被处理，正在刷新'); this.load() }
      else if (code && code.startsWith('403')) toast((e && e.message) || '不在你的指导范围内')
      else toast((e && e.message) || label + '失败，请重试')
    }
  }
}
</script>

<style scoped>
.gt__tabs { display: flex; gap: var(--space-6); padding: var(--space-3) var(--page-padding-mobile) 0; background: var(--bg-card); }
.gt__tab { position: relative; font-size: var(--font-size-base); color: var(--text-tertiary); font-weight: var(--font-weight-medium); padding-bottom: var(--space-3); }
.gt__tab.is-on { color: var(--text-primary); font-weight: var(--font-weight-semibold); }
.gt__tab-u { position: absolute; left: 50%; bottom: 0; transform: translateX(-50%); width: 22px; height: 3px; border-radius: 2px; background: var(--teacher-600); }
.gt__tab-badge { margin-left: 4px; font-size: 10px; color: #fff; background: var(--danger-500); padding: 1px 5px; border-radius: var(--radius-full); }
.gt { display: flex; flex-direction: column; gap: var(--space-2); }
.gt__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.gt__topic { display: flex; gap: var(--space-3); background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.gt__topic-label { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 40px; flex-shrink: 0; }
.gt__change { background: var(--gray-50); border-radius: var(--radius-md); padding: var(--space-2) var(--space-3); }
.gt__change-row { display: flex; gap: var(--space-3); padding: 3px 0; }
.gt__change-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 48px; flex-shrink: 0; }
.gt__change-adv { color: var(--text-tertiary); font-size: var(--font-size-xs); }
.gt__change-arrow { text-align: center; color: var(--teacher-500); font-size: var(--font-size-sm); }
.gt__reason { display: flex; gap: var(--space-3); padding: 0 var(--space-1); }
.gt__reason-k { font-size: var(--font-size-sm); color: var(--text-tertiary); width: 56px; flex-shrink: 0; }
.gt__actions { display: flex; gap: var(--space-2); margin-top: var(--space-1); }
.gt__reject { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: 1px solid var(--danger-500); background: var(--bg-card); color: var(--danger-600); }
.gt__reject::after { border: none; }
.gt__approve { min-height: var(--touch-target-min); border-radius: var(--radius-md); font-size: var(--font-size-md); border: none; background: var(--teacher-600); color: #fff; }
.gt__approve::after { border: none; }
</style>
