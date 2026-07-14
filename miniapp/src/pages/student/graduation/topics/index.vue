<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="毕设选题" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="loaded">
        <MobileGlobalState v-if="!activeRound" state="empty" title="当前无进行中的选题轮次" description="学院/教务开放选题时会在这里提示。" />

        <template v-else>
          <view class="card">
            <view class="row-between"><text class="card-title">{{ activeRound.roundName }}</text><text class="t-xs t-tertiary">最多{{ activeRound.maxChoices }}志愿</text></view>
          </view>

          <template v-if="myChoices.length">
            <view class="section-head"><text class="section-head__title">我的志愿</text></view>
            <view class="card stack-sm">
              <view v-for="c in myChoices" :key="c.id" class="tp__row">
                <text class="flex-1 t-md">{{ c.topicTitle }}</text>
                <MobileStatusTag :label="choiceLabel(c.status)" :type="choiceTag(c.status)" />
              </view>
              <button v-if="canWithdraw" class="btn btn-ghost" :disabled="withdrawing" @click="withdrawChoices">
                {{ withdrawing ? '退选中…' : '退选（撤回志愿后可重填）' }}
              </button>
            </view>
          </template>

          <template v-if="!hasTopic">
            <view class="section-head"><text class="section-head__title">题目库</text></view>
            <text class="tp__hint">从题目库选择 1~{{ activeRound.maxChoices }} 个志愿，按点选顺序确定志愿序：</text>
            <view class="card stack-sm">
              <view v-for="t in topics" :key="t.id" class="tp__topic" @click="toggleChoice(t.id)">
                <view class="flex-1">
                  <text class="tp__topic-title">{{ t.title }}</text>
                  <text class="tp__topic-sub">{{ t.advisorName || '—' }} · 余量 {{ t.remaining }}/{{ t.capacity }}</text>
                </view>
                <text v-if="choiceRank(t.id)" class="tp__badge">志愿{{ choiceRank(t.id) }}</text>
              </view>
            </view>
          </template>

          <template v-else>
            <view class="section-head"><text class="section-head__title">申请更换课题</text></view>
            <view class="card stack-sm">
              <button class="btn btn-ghost" @click="showChangeForm = !showChangeForm">
                {{ showChangeForm ? '收起' : '申请更换课题' }}
              </button>
              <template v-if="showChangeForm">
                <text class="tp__hint">获批课题已锁定，更换须重新审核，请选择目标课题并说明理由：</text>
                <view v-for="t in topics" :key="t.id" class="tp__topic" @click="changeTargetTopicId = t.id">
                  <view class="flex-1">
                    <text class="tp__topic-title">{{ t.title }}</text>
                    <text class="tp__topic-sub">{{ t.advisorName || '—' }} · 余量 {{ t.remaining }}/{{ t.capacity }}</text>
                  </view>
                  <text v-if="changeTargetTopicId === t.id" class="tp__badge">已选</text>
                </view>
                <textarea class="tp__reason" v-model="changeReason" :maxlength="200" placeholder="变更理由（至少5个字）" placeholder-class="tp__ph" />
                <button class="btn btn-primary" :disabled="!changeTargetTopicId || changeSubmitting" @click="submitChangeRequest">
                  {{ changeSubmitting ? '提交中…' : '提交变更申请' }}
                </button>
              </template>
              <view v-if="changeRequests.length" class="stack-sm">
                <view v-for="r in changeRequests" :key="r.id" class="tp__row">
                  <text class="flex-1 t-md">{{ r.oldTopicTitle }} → {{ r.newTopicTitle }}</text>
                  <MobileStatusTag :label="r.statusLabel" :type="changeTag(r.status)" />
                </view>
              </view>
            </view>
          </template>
        </template>
      </view>
    </MobileGlobalState>

    <MobileSafeAreaBar v-if="loaded && activeRound && !hasTopic">
      <button class="btn btn-primary flex-1" :disabled="!selectedChoices.length || choiceSubmitting" @click="submitChoices">
        {{ choiceSubmitting ? '提交中…' : `提交志愿（已选${selectedChoices.length}）` }}
      </button>
    </MobileSafeAreaBar>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const choiceLock = createSubmitLock(1500)
const changeLock = createSubmitLock(1500)
const CHOICE_LABEL = { PENDING: '待处理', MATCHED: '已匹配', UNMATCHED: '未录取', CONFIRMED: '已确认', REJECTED: '已驳回' }
const CHOICE_TAG = { PENDING: 'warning', MATCHED: 'success', UNMATCHED: 'default', CONFIRMED: 'success', REJECTED: 'danger' }
const CHANGE_TAG = { PENDING: 'warning', APPROVED: 'success', REJECTED: 'danger', CANCELLED: 'default' }

export default {
  data() {
    return {
      state: 'loading', loaded: false, hasTopic: false,
      topics: [], activeRound: null, changeRequests: [],
      selectedChoices: [], choiceSubmitting: false, withdrawing: false,
      showChangeForm: false, changeTargetTopicId: '', changeReason: '', changeSubmitting: false
    }
  },
  computed: {
    myChoices() { return (this.activeRound && this.activeRound.myChoices) || [] },
    canWithdraw() {
      return this.activeRound && this.myChoices.some((c) => c.status === 'PENDING') &&
        !this.myChoices.some((c) => c.status === 'CONFIRMED' || c.status === 'MATCHED')
    }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getGraduation().then((g) => {
        this.hasTopic = !!(g && g.hasTopic)
        return studentApi.getGraduationActiveRound()
      }).then((r) => {
        this.activeRound = r || null
        this.loaded = true
        this.state = 'ready'
        if (r) studentApi.getGraduationTopics().then((t) => { this.topics = t || [] }).catch(() => {})
        if (this.hasTopic) studentApi.getMyGraduationChangeRequests().then((r2) => { this.changeRequests = r2 || [] }).catch(() => {})
      }).catch(() => { this.state = 'error' })
    },
    choiceRank(topicId) {
      const i = this.selectedChoices.indexOf(topicId)
      return i >= 0 ? i + 1 : 0
    },
    toggleChoice(topicId) {
      const i = this.selectedChoices.indexOf(topicId)
      if (i >= 0) { this.selectedChoices.splice(i, 1); return }
      const max = (this.activeRound && this.activeRound.maxChoices) || 3
      if (this.selectedChoices.length >= max) { toast(`最多选择 ${max} 个志愿`); return }
      this.selectedChoices.push(topicId)
    },
    submitChoices() {
      if (!this.selectedChoices.length || this.choiceSubmitting) return
      const choices = this.selectedChoices.map((topicId, i) => ({ topicId, choiceOrder: i + 1 }))
      this.choiceSubmitting = true
      choiceLock.run(() => studentApi.submitGraduationChoices(this.activeRound.id, choices)).then(() => {
        uni.showToast({ title: '志愿已提交', icon: 'success' })
        this.selectedChoices = []
        this.load()
      }).catch((e) => {
        if (e && e.code === 'LOCKED') return
        toast(e && e.biz ? normalizeError(e).text : '网络异常，提交未成功，请稍后重试')
      }).finally(() => { this.choiceSubmitting = false })
    },
    withdrawChoices() {
      if (this.withdrawing || !this.activeRound) return
      this.withdrawing = true
      studentApi.withdrawGraduationChoices(this.activeRound.id).then(() => {
        uni.showToast({ title: '已退选', icon: 'success' })
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '退选失败，请稍后重试'))
        .finally(() => { this.withdrawing = false })
    },
    submitChangeRequest() {
      if (!this.changeTargetTopicId || this.changeSubmitting) return
      const reason = this.changeReason.trim()
      if (reason.length < 5) { toast('变更理由至少 5 个字'); return }
      this.changeSubmitting = true
      changeLock.run(() => studentApi.requestGraduationTopicChange(this.changeTargetTopicId, reason)).then(() => {
        uni.showToast({ title: '变更申请已提交', icon: 'success' })
        this.showChangeForm = false
        this.changeTargetTopicId = ''
        this.changeReason = ''
        this.load()
      }).catch((e) => {
        if (e && e.code === 'LOCKED') return
        toast(e && e.biz ? normalizeError(e).text : '网络异常，提交未成功，请稍后重试')
      }).finally(() => { this.changeSubmitting = false })
    },
    choiceLabel(status) { return CHOICE_LABEL[status] || status },
    choiceTag(status) { return CHOICE_TAG[status] || 'default' },
    changeTag(status) { return CHANGE_TAG[status] || 'default' }
  }
}
</script>

<style scoped>
.tp__row { display: flex; align-items: center; }
.tp__hint { display: block; font-size: var(--font-size-sm); color: var(--text-tertiary); }
.tp__topic { display: flex; align-items: center; justify-content: space-between; padding: var(--space-3) 0; border-bottom: 1px solid var(--border-light); }
.tp__topic:last-of-type { border-bottom: none; }
.tp__topic-title { display: block; font-size: var(--font-size-base); color: var(--text-primary); font-weight: var(--font-weight-medium); }
.tp__topic-sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.tp__badge { flex-shrink: 0; font-size: var(--font-size-xs); color: #fff; background: var(--brand-primary); padding: 3px 10px; border-radius: var(--radius-full); }
.tp__reason { width: 100%; min-height: 60px; font-size: var(--font-size-base); color: var(--text-primary); border: 1px solid var(--border-base); border-radius: var(--radius-md); padding: var(--space-2); box-sizing: border-box; margin: var(--space-2) 0; }
.tp__ph { color: var(--text-tertiary); }
</style>
