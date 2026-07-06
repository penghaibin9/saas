<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学籍与异动" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="stx__cur" :class="data.enrolled ? 'is-ok' : 'is-warn'">
          <text class="stx__cur-t">当前学籍</text>
          <text class="stx__cur-v">{{ statusText(data.studentStatus) }}</text>
        </view>

        <!-- 异动记录 -->
        <view class="stx__sec-t">异动记录</view>
        <view class="stx__empty" v-if="!data.changes.length"><text>暂无异动记录</text></view>
        <view v-for="c in data.changes" :key="c.changeId" class="stx__ch">
          <text class="stx__ch-t">{{ ctText(c.changeType) }}</text>
          <text class="stx__ch-s" :class="c.status === 'EFFECTIVE' ? 'is-ok' : ''">{{ statusLabel(c.status) }}</text>
        </view>

        <!-- 发起异动申请 -->
        <view class="stx__sec-t">发起异动申请</view>
        <view class="stx__form">
          <view class="stx__chips">
            <view v-for="t in TYPES" :key="t.v" class="stx__chip" :class="{ 'is-on': form.changeType === t.v }"
              @click="form.changeType = t.v">{{ t.l }}</view>
          </view>
          <textarea class="stx__reason" v-model="form.reason" placeholder="申请原因（不少于5字）" maxlength="200" />
          <button class="stx__btn" :disabled="submitting || !form.changeType" @click="submit">提交申请</button>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { safeToast, toastError, createSubmitLock } from '@/services/request'
const ST = { REGISTERED: '在籍注册', NORMAL: '在籍', SUSPENDED: '休学中', RETAINED: '留级',
  WITHDRAWN: '已退学', GRADUATED: '已毕业' }
const CT = { SUSPEND: '休学', RESUME: '复学', WITHDRAW: '退学', RETAIN: '留级', TRANSFER_MAJOR: '转专业' }
const SL = { SUBMITTED: '已提交', IN_REVIEW: '审批中', EFFECTIVE: '已生效', REJECTED: '已驳回', RETURNED: '已退回' }
export default {
  data() {
    return {
      data: null, state: 'loading', submitting: false, _lock: createSubmitLock(),
      form: { changeType: '', reason: '' },
      TYPES: [{ v: 'SUSPEND', l: '休学' }, { v: 'RESUME', l: '复学' }, { v: 'WITHDRAW', l: '退学' },
        { v: 'TRANSFER_MAJOR', l: '转专业' }]
    }
  },
  onLoad() { this.load() },
  methods: {
    statusText(s) { return ST[s] || s },
    ctText(c) { return CT[c] || c },
    statusLabel(s) { return SL[s] || s },
    load() {
      this.state = 'loading'
      studentApi.getMyAcadStatus().then((d) => { this.data = d; this.state = 'ready' })
        .catch(() => { this.state = 'error' })
    },
    submit() {
      if ((this.form.reason || '').trim().length < 5) return safeToast('请填写申请原因（≥5字）')
      if (!this._lock.acquire()) return
      this.submitting = true
      studentApi.submitStatusChange({ changeType: this.form.changeType, reason: this.form.reason.trim() })
        .then(() => { safeToast('已提交', 'success'); this.form = { changeType: '', reason: '' }; this.load() })
        .catch(toastError)
        .finally(() => { this.submitting = false })
    }
  }
}
</script>

<style scoped>
.stx__cur { border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); color: #fff; }
.stx__cur.is-ok { background: var(--brand-primary); }
.stx__cur.is-warn { background: #d97706; }
.stx__cur-t { display: block; font-size: var(--font-size-sm); opacity: 0.85; }
.stx__cur-v { display: block; font-size: 20px; font-weight: 700; margin-top: 4px; }
.stx__sec-t { font-weight: 700; margin: var(--space-4) 0 var(--space-2); }
.stx__empty { color: var(--text-tertiary); font-size: var(--font-size-sm); padding: var(--space-2) 0; }
.stx__ch { display: flex; justify-content: space-between; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-3) var(--space-4); margin-bottom: var(--space-2); box-shadow: var(--shadow-card); }
.stx__ch-s.is-ok { color: #16a34a; }
.stx__form { background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); }
.stx__chips { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-3); }
.stx__chip { padding: 8px 16px; border-radius: var(--radius-full); background: var(--bg-page); border: 1px solid var(--border-base); font-size: var(--font-size-sm); }
.stx__chip.is-on { background: var(--brand-primary); color: #fff; border-color: var(--brand-primary); }
.stx__reason { width: 100%; min-height: 80px; background: var(--bg-page); border-radius: var(--radius-md); padding: var(--space-3); font-size: var(--font-size-base); box-sizing: border-box; }
.stx__btn { margin-top: var(--space-3); background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); padding: 12px; }
</style>
