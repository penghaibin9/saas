<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="心理健康自评" show-back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="loaded">
        <template v-if="!result">
          <MobileInlineAlert type="info" title="温馨提示"
            description="用于了解近期情绪、睡眠和压力，不是医学诊断。只有主动求助或达到关注条件时，才登记人工关注。" />

          <view class="ms__sheet">
            <view class="ms__question" v-for="(q, i) in questions" :key="q.key">
              <text class="ms__q">{{ i + 1 }}. {{ q.text }}</text>
              <view class="ms__opts">
                <text v-for="(opt, oi) in q.options" :key="oi" class="ms__opt"
                      :class="{ 'is-on': answers[q.key] === oi }" @click="answers[q.key] = oi">{{ opt }}</text>
              </view>
            </view>
            <view class="ms__checkbox" @click="wantsContact = !wantsContact">
              <text class="ms__checkbox-box" :class="{ 'is-on': wantsContact }">{{ wantsContact ? '✓' : '' }}</text>
              <text class="t-md">希望近期有老师主动联系我聊聊</text>
            </view>
          </view>

          <button class="btn btn-primary btn-block" :disabled="submitting || !allAnswered" @click="submit">
            {{ submitting ? '提交中…' : '提交自评' }}
          </button>

          <view class="section-head"><text class="section-head__title">我的历史</text></view>
          <MobileGlobalState v-if="!history.length" state="empty" title="暂无自评记录" description="完成本次自评后会保存在这里。" />
          <view class="ms__history" v-else>
            <view v-for="h in history" :key="h.submissionId" class="ms__history-row">
              <view class="flex-1">
                <text class="t-md">{{ (h.submittedAt || '').slice(0, 10) }}</text>
                <text class="ms__sub">{{ h.wantsContact ? '已申请老师联系' : '本人自评记录' }}</text>
              </view>
              <MobileStatusTag :label="h.triggeredAttention ? '已登记人工关注' : '已保存'" :type="h.triggeredAttention ? 'processing' : 'success'" />
            </view>
          </view>
        </template>

        <template v-else>
          <view class="card ms__result">
            <text class="ms__result-title">已提交，谢谢你的如实作答</text>
            <text class="ms__result-desc" v-if="result.triggeredAttention">
              系统已为你登记一次人工关注，会有老师主动与你联系，请留意消息通知。
            </text>
            <text class="ms__result-desc" v-else>
              本次结果显示你目前状态较为平稳。如果之后有需要，随时可以再来做自评，或直接联系辅导员/学工处。
            </text>
          </view>
          <view class="card">
            <text class="t-sm t-secondary">如果你现在就想找人聊聊，可以：</text>
            <text class="ms__channel">· 联系你的辅导员（"我的"→"我的班级/联系学生"）</text>
            <text class="ms__channel">· 前往"在校服务"联系学工处或心理健康中心</text>
          </view>
          <button class="btn btn-ghost btn-block" @click="reset">再次填写</button>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  data() {
    return { state: 'loading', loaded: false, questions: [], answers: {}, wantsContact: false,
      submitting: false, result: null, history: [] }
  },
  computed: {
    allAnswered() { return this.questions.length && this.questions.every((q) => this.answers[q.key] != null) }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      Promise.all([studentApi.getPsySurveyQuestions(), studentApi.getPsySurveyHistory()]).then(([q, h]) => {
        this.questions = (q && q.questions) || []
        this.history = (h && h.items) || []
        this.answers = {}
        this.loaded = true
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    submit() {
      if (this.submitting || !this.allAnswered) return
      const answers = this.questions.map((q) => ({ qKey: q.key, score: this.answers[q.key] }))
      this.submitting = true
      studentApi.submitPsySurvey(answers, this.wantsContact).then((d) => {
        this.result = d
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '提交失败，请稍后重试'))
        .finally(() => { this.submitting = false })
    },
    reset() {
      this.result = null
      this.wantsContact = false
      this.load()
    }
  }
}
</script>

<style scoped>
.ms__sheet { overflow: hidden; border-top: 1px solid var(--border-base); border-bottom: 1px solid var(--border-base); }
.ms__question { padding: var(--space-4) 0; border-bottom: 1px solid var(--border-light); }
.ms__question:last-of-type { border-bottom: 0; }
.ms__q { display: block; font-size: var(--font-size-base); color: var(--text-primary); font-weight: var(--font-weight-medium); line-height: 1.55; }
.ms__opts { display: flex; flex-wrap: wrap; gap: var(--space-2); }
.ms__opt { padding: 8px 16px; border-radius: var(--radius-full); background: var(--bg-secondary); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }
.ms__opt.is-on { background: var(--brand-primary); color: #fff; border-color: var(--brand-primary); }
.ms__checkbox { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-4) 0; border-top: 1px solid var(--border-light); }
.ms__checkbox-box { width: 20px; height: 20px; border: 1px solid var(--border-base); border-radius: var(--radius-sm); display: flex; align-items: center; justify-content: center; color: #fff; flex-shrink: 0; }
.ms__checkbox-box.is-on { background: var(--brand-primary); border-color: var(--brand-primary); }
.ms__sub { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin-top: 2px; }
.ms__history { border-top: 1px solid var(--border-base); }
.ms__history-row { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-3) 0; border-bottom: 1px solid var(--border-light); }
.ms__result { text-align: center; }
.ms__result-title { display: block; font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: var(--text-primary); }
.ms__result-desc { display: block; font-size: var(--font-size-base); color: var(--text-secondary); line-height: 1.6; margin-top: var(--space-3); }
.ms__channel { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: var(--space-2); line-height: 1.6; }
</style>
