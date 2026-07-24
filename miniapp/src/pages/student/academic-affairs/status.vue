<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学籍与异动" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="stx__cur" :class="data.enrolled ? 'is-ok' : 'is-warn'">
          <text class="stx__cur-t">当前学籍</text>
          <text class="stx__cur-v">{{ statusText(data.studentStatus) }}</text>
        </view>

        <view class="stx__sec-t">异动记录</view>
        <view class="stx__empty" v-if="!(data.changes || []).length"><text>暂无异动记录</text></view>
        <view v-for="c in data.changes" :key="c.changeId" class="stx__ch">
          <text class="stx__ch-t">{{ ctText(c.changeType) }}</text>
          <text class="stx__ch-s" :class="c.status === 'EFFECTIVE' ? 'is-ok' : ''">{{ statusLabel(c.status) }}</text>
        </view>

        <view class="stx__sec-t">发起异动申请</view>
        <view class="stx__form">
          <view class="stx__chips">
            <view v-for="t in TYPES" :key="t.v" class="stx__chip" :class="{ 'is-on': form.changeType === t.v }"
              @click="onType(t.v)">{{ t.l }}</view>
          </view>

          <view v-if="form.changeType === 'TRANSFER_MAJOR'" class="stx__pick">
            <text class="stx__pick-l">目标专业（必选）</text>
            <picker mode="selector" :range="majorLabels" :value="majorIndex" @change="onMajorPick">
              <view class="stx__pick-v">{{ majorLabels[majorIndex] || '请选择目标专业' }}</view>
            </picker>
            <text class="stx__pick-l">目标班级（可选）</text>
            <picker mode="selector" :range="targetClassLabels" :value="targetClassIndex" @change="onTargetClassPick" :disabled="!form.toMajorId">
              <view class="stx__pick-v">{{ targetClassLabels[targetClassIndex] || '暂不指定，由教务编班' }}</view>
            </picker>
          </view>

          <view v-if="form.changeType === 'TRANSFER_CLASS'" class="stx__pick">
            <text class="stx__pick-l">目标班级（必选，同专业）</text>
            <picker mode="selector" :range="sameMajorClassLabels" :value="sameClassIndex" @change="onSameClassPick">
              <view class="stx__pick-v">{{ sameMajorClassLabels[sameClassIndex] || '请选择目标班级' }}</view>
            </picker>
          </view>

          <textarea class="stx__reason" v-model="form.reason" placeholder="申请原因（不少于5字）" maxlength="200" />
          <button class="stx__btn" :disabled="submitting || !canSubmit" @click="submit">提交申请</button>
          <button class="stx__btn stx__btn--ghost" :disabled="submitting || !canSubmit" @click="submitAndPrint" style="margin-top:8px">提交并打印申请表</button>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { safeToast, toastError, createSubmitLock } from '@/services/request'

const ST = {
  REGISTERED: '在籍注册', NORMAL: '在籍', SUSPENDED: '休学中', PRESERVED: '保留学籍',
  RETAINED: '留级', WITHDRAWN: '已退学', GRADUATED: '已毕业', TRANSFERRED: '已转学'
}
const CT = {
  SUSPEND: '休学', PRESERVE: '保留学籍', RESUME: '复学', WITHDRAW: '退学',
  RETAIN: '留级', TRANSFER_MAJOR: '转专业', TRANSFER_CLASS: '转班'
}
const SL = { SUBMITTED: '已提交', IN_REVIEW: '审批中', EFFECTIVE: '已生效', REJECTED: '已驳回', RETURNED: '已退回' }

export default {
  data() {
    return {
      data: null, state: 'loading', submitting: false, _lock: createSubmitLock(),
      form: { changeType: '', reason: '', toMajorId: '', toClassId: '' },
      transferOptions: { majors: [], classes: [], majorClasses: {} },
      majorIndex: 0, targetClassIndex: 0, sameClassIndex: 0,
      TYPES: [
        { v: 'SUSPEND', l: '休学' }, { v: 'PRESERVE', l: '保留学籍' }, { v: 'RESUME', l: '复学' },
        { v: 'TRANSFER_MAJOR', l: '转专业' }, { v: 'TRANSFER_CLASS', l: '转班' },
        { v: 'RETAIN', l: '留级' }, { v: 'WITHDRAW', l: '退学' }
      ]
    }
  },
  computed: {
    majors() { return (this.transferOptions && this.transferOptions.majors) || [] },
    majorLabels() { return this.majors.map((m) => `${m.collegeName ? m.collegeName + ' · ' : ''}${m.majorName}`) },
    targetClasses() {
      const mid = this.form.toMajorId
      if (!mid) return []
      return ((this.transferOptions.majorClasses || {})[mid]) || []
    },
    targetClassLabels() {
      return ['暂不指定班级'].concat(this.targetClasses.map((c) => `${c.className}${c.grade ? ' · ' + c.grade : ''}`))
    },
    sameMajorClasses() { return (this.transferOptions && this.transferOptions.classes) || [] },
    sameMajorClassLabels() {
      return this.sameMajorClasses.map((c) => `${c.className}${c.grade ? ' · ' + c.grade : ''}`)
    },
    canSubmit() {
      if (!this.form.changeType || (this.form.reason || '').trim().length < 5) return false
      if (this.form.changeType === 'TRANSFER_MAJOR' && !this.form.toMajorId) return false
      if (this.form.changeType === 'TRANSFER_CLASS' && !this.form.toClassId) return false
      return true
    }
  },
  onLoad() { this.load() },
  methods: {
    statusText(s) { return ST[s] || s },
    ctText(c) { return CT[c] || c },
    statusLabel(s) { return SL[s] || s },
    onType(v) {
      this.form.changeType = v
      this.form.toMajorId = ''
      this.form.toClassId = ''
      this.majorIndex = 0
      this.targetClassIndex = 0
      this.sameClassIndex = 0
    },
    onMajorPick(e) {
      this.majorIndex = Number(e.detail.value)
      const m = this.majors[this.majorIndex]
      this.form.toMajorId = m ? m.majorId : ''
      this.form.toClassId = ''
      this.targetClassIndex = 0
    },
    onTargetClassPick(e) {
      this.targetClassIndex = Number(e.detail.value)
      if (this.targetClassIndex <= 0) { this.form.toClassId = ''; return }
      const c = this.targetClasses[this.targetClassIndex - 1]
      this.form.toClassId = c ? c.classId : ''
    },
    onSameClassPick(e) {
      this.sameClassIndex = Number(e.detail.value)
      const c = this.sameMajorClasses[this.sameClassIndex]
      this.form.toClassId = c ? c.classId : ''
    },
    load() {
      this.state = 'loading'
      Promise.all([
        studentApi.getMyAcadStatus(),
        studentApi.getTransferOptions().catch(() => ({ majors: [], classes: [], majorClasses: {} }))
      ]).then(([d, opt]) => {
        this.data = d
        this.transferOptions = opt || { majors: [], classes: [], majorClasses: {} }
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    submit() {
      if (!this.canSubmit) return safeToast('请完整填写申请信息')
      const body = {
        changeType: this.form.changeType,
        reason: this.form.reason.trim(),
        toMajorId: this.form.changeType === 'TRANSFER_MAJOR' ? (this.form.toMajorId || undefined) : undefined,
        toClassId: (this.form.changeType === 'TRANSFER_MAJOR' || this.form.changeType === 'TRANSFER_CLASS')
          ? (this.form.toClassId || undefined) : undefined
      }
      this.submitting = true
      this._lock.run(() => studentApi.submitStatusChange(body))
        .then(() => {
          safeToast('已提交', 'success')
          this.form = { changeType: '', reason: '', toMajorId: '', toClassId: '' }
          this.load()
        })
        .catch((e) => { if (e && e.code === 'LOCKED') return; toastError(e) })
        .finally(() => { this.submitting = false })
    },
    submitAndPrint() {
      if (!this.canSubmit) return safeToast('请完整填写申请信息')
      const body = {
        changeType: this.form.changeType,
        reason: this.form.reason.trim(),
        toMajorId: this.form.changeType === 'TRANSFER_MAJOR' ? (this.form.toMajorId || undefined) : undefined,
        toClassId: (this.form.changeType === 'TRANSFER_MAJOR' || this.form.changeType === 'TRANSFER_CLASS')
          ? (this.form.toClassId || undefined) : undefined
      }
      this.submitting = true
      this._lock.run(() => studentApi.submitStatusChange(body)
        .then(() => studentApi.printStatusChange(body)))
        .then((res) => {
          const doc = (res && res.document) || {}
          const hist = (doc.history || []).map((h) =>
            `${this.ctText(h.changeType)} ${this.statusLabel(h.status)}`
          ).join('\n')
          const text = [
            '学籍异动申请表摘要',
            `姓名：${doc.realName || '—'}`,
            `学号：${doc.studentNo || '—'}`,
            `当前学籍：${this.statusText(doc.studentStatus || (this.data && this.data.studentStatus))}`,
            `申请类型：${this.ctText(doc.changeType || body.changeType)}`,
            `申请原因：${doc.reason || body.reason || ''}`,
            `留痕：${(res && res.loggedAt) || ''}`,
            '',
            '近期异动：',
            hist || '无'
          ].join('\n')
          uni.setClipboardData({
            data: text,
            success: () => safeToast('已提交并复制申请摘要', 'success'),
            fail: () => safeToast('已提交并留痕打印', 'success')
          })
          this.form = { changeType: '', reason: '', toMajorId: '', toClassId: '' }
          this.load()
        })
        .catch((e) => { if (e && e.code === 'LOCKED') return; toastError(e) })
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
.stx__pick { margin-bottom: var(--space-3); }
.stx__pick-l { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin: 8px 0 4px; }
.stx__pick-v { background: var(--bg-page); border-radius: var(--radius-md); padding: 10px 12px; font-size: var(--font-size-base); }
.stx__reason { width: 100%; min-height: 80px; background: var(--bg-page); border-radius: var(--radius-md); padding: var(--space-3); font-size: var(--font-size-base); box-sizing: border-box; }
.stx__btn { margin-top: var(--space-3); background: var(--brand-primary); color: #fff; border-radius: var(--radius-full); padding: 12px; }
.stx__btn[disabled] { opacity: 0.5; }
</style>
