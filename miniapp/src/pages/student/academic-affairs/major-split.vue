<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="专业分流志愿" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="d">
        <template v-if="d.openBatches && d.openBatches.length">
          <view v-for="b in d.openBatches" :key="b.batchId" class="card stack-sm ms__batch">
            <text class="ms__title">{{ b.batchName }}</text>
            <text class="ms__hint">{{ b.grade }} 级 · 至多填 {{ b.maxChoices }} 个志愿 · 按顺序点选专业(先点=第一志愿)</text>
            <view class="ms__opts">
              <view v-for="o in b.options" :key="o.majorId"
                    :class="['ms__opt', { 'is-picked': pickRank(b, o.majorId) > 0 }]"
                    @click="toggle(b, o)">
                <text class="ms__opt-name">{{ o.majorName }}</text>
                <text class="ms__opt-cap">余 {{ o.remain }}/{{ o.capacity }}</text>
                <text v-if="pickRank(b, o.majorId) > 0" class="ms__opt-rank">第{{ pickRank(b, o.majorId) }}志愿</text>
              </view>
            </view>
            <button class="btn btn-primary" :disabled="!(picks[b.batchId] && picks[b.batchId].length) || submitting" @click="submit(b)">
              {{ submitting ? '提交中…' : (myVolFor(b.batchId) ? '更新志愿' : '提交志愿') }}
            </button>
          </view>
        </template>
        <MobileGlobalState v-else-if="!(d.myVolunteers && d.myVolunteers.length)" state="empty"
                           title="暂无开放中的分流批次" description="专业分流开放填报后在此选择志愿。" />

        <template v-if="d.myVolunteers && d.myVolunteers.length">
          <view class="section-head"><text class="section-head__title">我的志愿与结果</text></view>
          <view class="list-group">
            <view v-for="v in d.myVolunteers" :key="v.volunteerId" class="list-row ms__item">
              <view class="flex-1">
                <text class="t-md">志愿：{{ (v.choices || []).map(majorName).join(' / ') || '—' }}</text>
                <text v-if="v.resultMajorId" class="ms__result">录取：{{ majorName(v.resultMajorId) }}<text v-if="v.resultChoiceRank">（{{ v.resultChoiceRank === 0 ? '调剂' : '第' + v.resultChoiceRank + '志愿' }}）</text></text>
              </view>
              <MobileStatusTag :status="v.status" />
            </view>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { createSubmitLock, normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const submitLock = createSubmitLock(1500)

export default {
  data() {
    return { d: null, state: 'loading', submitting: false, picks: {}, majorNames: {} }
  },
  onLoad() { this.load() },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getMyMajorSplit().then((d) => {
        this.d = d
        // 建 majorId→名 映射（含开放批次可选专业）
        const nm = {}
        ;(d.openBatches || []).forEach((b) => (b.options || []).forEach((o) => { nm[String(o.majorId)] = o.majorName }))
        this.majorNames = nm
        // 预填已提交志愿
        const picks = {}
        ;(d.openBatches || []).forEach((b) => {
          const mine = (d.myVolunteers || []).find((v) => v.batchId ? String(v.batchId) === String(b.batchId) : false)
          picks[b.batchId] = mine && mine.choices ? mine.choices.map(String) : []
        })
        this.picks = picks
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    majorName(id) { return this.majorNames[String(id)] || ('专业#' + id) },
    myVolFor(batchId) { return (this.d.myVolunteers || []).find((v) => String(v.batchId) === String(batchId)) },
    pickRank(b, majorId) {
      const arr = this.picks[b.batchId] || []
      return arr.indexOf(String(majorId)) + 1
    },
    toggle(b, o) {
      const key = b.batchId
      const arr = (this.picks[key] || []).slice()
      const mid = String(o.majorId)
      const i = arr.indexOf(mid)
      if (i >= 0) { arr.splice(i, 1) }
      else {
        if (arr.length >= b.maxChoices) { toast(`最多填 ${b.maxChoices} 个志愿`); return }
        arr.push(mid)
      }
      this.picks = { ...this.picks, [key]: arr }
    },
    submit(b) {
      const choices = this.picks[b.batchId] || []
      if (!choices.length || this.submitting) return
      this.submitting = true
      submitLock.run(() => studentApi.submitMajorSplit(b.batchId, choices))
        .then(() => { uni.showToast({ title: '志愿已提交', icon: 'success' }); this.load() })
        .catch((e) => { if (e && e.code === 'LOCKED') return; toast(e && e.biz ? normalizeError(e).text : '提交失败') })
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.ms__batch { border: 1px solid var(--border-base); }
.ms__title { font-size: var(--font-size-base); font-weight: 600; color: var(--text-primary); }
.ms__hint { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); margin: 2px 0 var(--space-2); }
.ms__opts { display: flex; flex-direction: column; gap: var(--space-2); }
.ms__opt { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2) var(--space-3); border: 1px solid var(--border-base); border-radius: var(--radius-md); }
.ms__opt.is-picked { border-color: var(--brand-600, #2563eb); background: var(--brand-50, #eff6ff); }
.ms__opt-name { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); }
.ms__opt-cap { font-size: var(--font-size-xs); color: var(--text-tertiary); }
.ms__opt-rank { font-size: var(--font-size-xs); color: var(--brand-600, #2563eb); font-weight: 600; }
.ms__item { align-items: flex-start; }
.ms__result { display: block; font-size: var(--font-size-xs); color: var(--success-600); margin-top: 4px; }
</style>
