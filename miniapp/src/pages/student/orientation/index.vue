<template>
  <view class="page-wrap">
    <MobileGlobalState :state="state" @retry="load">
      <view v-if="o" class="page-pad stack">
        <view class="or__hero" :class="{ 'is-done': reportDone }">
          <text class="or__hero-batch">{{ o.batch }}</text>
          <view class="or__hero-main">
            <text class="or__hero-icon">{{ reportDone ? '✓' : '迎' }}</text>
            <view class="flex-1">
              <text class="or__hero-title">{{ arrivalHold ? arrivalHold.title : reportDone ? (finalConfirmed ? '报到完成' : '现场报到成功') : '你好，' + (o.identity.name || '新同学') }}</text>
              <text class="or__hero-sub">{{ heroSub }}</text>
            </view>
          </view>
          <view class="or__identity-line">
            <text>{{ o.identity.collegeName || '学院待分配' }}</text>
            <text>·</text>
            <text>{{ o.identity.majorName || '专业待分配' }}</text>
            <text v-if="o.identity.className">· {{ o.identity.className }}</text>
          </view>
        </view>

        <view v-if="!reportDone && !arrivalHold && hasDormArrangement" class="or__housing-summary">
          <view class="flex-1">
            <text class="or__arrangement-label">{{ o.dorm.statusLabel || (o.dorm.status === 'ACTIVE' ? '已入住' : '已预留 · 待入住') }}</text>
            <text class="or__arrangement-value">{{ dormArrangement }}</text>
          </view>
          <button plain @click="go('/pages/student/affairs/dorm')">查看住宿</button>
        </view>

        <view v-if="!finalConfirmed" class="or__next card">
          <view class="row-between"><text class="or__eyebrow">你现在只需要做</text><text class="or__next-tag">{{ nextAction.owner }}</text></view>
          <text class="or__next-title">{{ nextAction.title }}</text>
          <text class="or__next-desc">{{ nextAction.description }}</text>
          <button v-if="nextAction.path" class="btn btn-primary" @click="go(nextAction.path)">{{ nextAction.button }}</button>
        </view>
        <view v-if="o.hasData !== false" class="card or__checklist">
          <view class="row-between"><text class="or__fold-title">我的迎新清单</text><text class="or__fold-sub">{{ completedStepCount }}/{{ o.steps.length }} 项已完成</text></view>
          <view v-for="task in taskList" :key="task.key" class="or__task">
            <view class="flex-1"><text class="or__task-title">{{ task.title }}</text><text class="or__task-state">{{ task.statusText }}</text><text v-if="task.reason" class="or__task-reason">{{ task.reason }}</text></view>
            <button v-if="task.path" plain @click="go(task.path)">{{ task.action }}</button>
          </view>
          <view v-if="!arrivalHold && !finalConfirmed && o.selfService?.available" class="or__task">
            <view class="flex-1"><text class="or__task-title">到校计划</text><text class="or__task-state">{{ o.selfService.arrivalPlan ? '已登记，可修改' : '便民登记，不影响领取报到码' }}</text></view>
            <button plain @click="go('/pages/student/orientation/arrival/index')">{{ o.selfService.arrivalPlan ? '查看' : '登记' }}</button>
          </view>
        </view>

        <template v-if="reportDone">
          <view v-if="!finalConfirmed && o.selfService?.canSubmitMaterials" class="or__after-item" @click="go('/pages/student/orientation/materials/index')"><text>查看待补材料与审核结果</text><text> →</text></view>
          <view class="or__result card">
            <view class="row-between">
              <text class="or__result-title">{{ finalConfirmed ? '手续已经办妥' : '现场核验已经完成' }}</text>
              <text class="or__done-tag">已完成</text>
            </view>
            <text class="or__result-desc">{{ finalConfirmed ? '不用再提交迎新材料或刷新报到状态，接下来按下面的安排入校即可。' : '现场报到已完成；如有待补材料或缴费事项，请继续办理，完成后由学院确认入学。' }}</text>
            <view v-if="checkinSummary" class="or__result-meta">{{ checkinSummary }}</view>
          </view>

          <view class="section-head"><text class="section-head__title">你的入学安排</text></view>
          <view class="card stack-sm">
            <view class="or__arrangement">
              <text class="or__arrangement-icon">🏠</text>
              <view class="flex-1">
                <text class="or__arrangement-label">住宿安排</text>
                <text class="or__arrangement-value">{{ dormArrangement }}</text><text class="or__arrangement-label">{{ o.dorm.statusLabel }}</text>
              </view>
            </view>
            <view class="or__arrangement">
              <text class="or__arrangement-icon">🎓</text>
              <view class="flex-1">
                <text class="or__arrangement-label">班级</text>
                <text class="or__arrangement-value">{{ o.identity.className || '学校分班后会自动更新' }}</text>
              </view>
            </view>
            <view v-for="c in o.contacts" :key="c.role + c.name" class="or__arrangement">
              <text class="or__arrangement-icon">👤</text>
              <view class="flex-1">
                <text class="or__arrangement-label">{{ c.role }}</text>
                <text class="or__arrangement-value">{{ c.name }}</text>
              </view>
              <view v-if="c.phone" class="or__contact-call" @click="call(c)">联系</view>
            </view>
          </view>

          <view class="section-head"><text class="section-head__title">接下来</text><text @click="go('/pages/student/affairs/dorm')">我的住宿 →</text></view>
          <view class="card or__after-list">
            <view v-if="hasDormArrangement" class="or__after-item">
              <text class="or__after-no">1</text>
              <text>{{ o.dorm.status === 'ACTIVE' ? '已入住：' : '已预留，请前往办理入住：' }}{{ o.dorm.label }}</text>
            </view>
            <view class="or__after-item">
              <text class="or__after-no">{{ hasDormArrangement ? '2' : '1' }}</text>
              <text>留意学校消息，按通知参加班级报到、体检和入学教育。</text>
            </view>
            <view class="or__after-item">
              <text class="or__after-no">{{ hasDormArrangement ? '3' : '2' }}</text>
              <text>遇到问题直接联系辅导员，不需要重新走迎新流程。</text>
            </view>
          </view>
        </template>

        <template v-else>
          <view v-if="!arrivalHold && schoolItems.length" class="or__fold card" @click="showSchool = !showSchool">
            <view class="row-between">
              <view>
                <text class="or__fold-title">学校正在办理</text>
                <text class="or__fold-sub">{{ schoolItems.length }} 项后台事项，不需要你重复提交</text>
              </view>
              <text class="or__fold-arrow">{{ showSchool ? '收起' : '查看' }}</text>
            </view>
            <view v-if="showSchool" class="or__fold-content">
              <view v-for="item in schoolItems" :key="item" class="or__school-item">
                <text class="or__school-dot">✓</text><text>{{ item }}</text>
              </view>
            </view>
          </view>

          <view v-if="!arrivalHold" class="or__fold card" @click="showSubmitted = !showSubmitted">
            <view class="row-between">
              <view>
                <text class="or__fold-title">已填内容与便民服务</text>
                <text class="or__fold-sub">需要修改时再打开</text>
              </view>
              <text class="or__fold-arrow">{{ showSubmitted ? '收起' : '查看' }}</text>
            </view>
            <view v-if="showSubmitted" class="or__tool-list" @click.stop>
              <view class="or__tool" @click="go('/pages/student/orientation/collect/index')">个人信息</view>
              <view class="or__tool" @click="go('/pages/student/orientation/arrival/index')">到校计划</view>
              <view class="or__tool" @click="go('/pages/student/orientation/materials/index')">迎新材料</view>
              <view v-if="showGreenChannel" class="or__tool is-help" @click="go('/pages/student/orientation/green-channel/index')">缴费困难绿色通道</view>
            </view>
          </view>

          <view class="or__fold card" @click="showProgress = !showProgress">
            <view class="row-between">
              <view>
                <text class="or__fold-title">全部办理进度</text>
                <text class="or__fold-sub">{{ completedStepCount }}/{{ o.steps.length }} 项已完成</text>
              </view>
              <text class="or__fold-arrow">{{ showProgress ? '收起' : '查看' }}</text>
            </view>
            <view v-if="showProgress" class="or__timeline" @click.stop><MobileTimeline :nodes="o.steps" /></view>
          </view>

          <view v-if="o.contacts.length" class="card stack-sm">
            <view v-for="c in o.contacts" :key="c.role + c.name" class="or__contact">
              <view class="or__contact-avatar">{{ c.name.slice(0, 1) }}</view>
              <view class="flex-1">
                <text class="t-md">{{ c.name }}</text>
                <text class="or__contact-role">{{ c.role }}</text>
              </view>
              <view v-if="c.phone" class="or__contact-call" @click="call(c)">联系</view>
            </view>
          </view>
        </template>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { go, toast } from '@/utils/nav'
import { formatDateTime } from '@/utils/format'

const DONE = ['DONE', 'WAIVED', 'NOT_REQUIRED']

export default {
  data() {
    return { o: null, state: 'loading', showSchool: true, showSubmitted: false, showProgress: false, requestSerial: 0 }
  },
  onShow() { this.load() },
  onUnload() { ++this.requestSerial },
  computed: {
    arrivalHold() {
      return ({
        DEFERRED: { title: '已延期报到', description: '请与学校确认新的到校时间。已有预留床位继续保留，实际安排以住宿信息为准。' },
        NO_SHOW: { title: '已登记未到校', description: '原预留床位已释放。如仍需入学，请联系学校恢复报到并重新安排住宿。' },
        CANCELLED: { title: '已取消入学', description: '本次迎新办理已停止，原预留床位已释放。如登记有误，请联系学校核实。' },
      })[this.o?.stage] || null
    },
    reportDone() {
      return ['CHECKED_IN', 'COLLEGE_CONFIRMED', 'REGISTERED'].includes(this.o?.overallStatus)
    },
    finalConfirmed() {
      return ['COLLEGE_CONFIRMED', 'REGISTERED'].includes(this.o?.overallStatus)
    },
    stepMap() {
      return Object.fromEntries((this.o?.steps || []).map((item) => [item.key, item.status]))
    },
    completedStepCount() {
      return (this.o?.steps || []).filter((item) => DONE.includes(item.status)).length
    },
    requiredMaterialFacts() {
      return this.o?.qualification?.facts?.materials?.required || []
    },
    materialsWaitingReview() {
      return this.requiredMaterialFacts.length > 0 && this.requiredMaterialFacts.every((item) => ['UPLOADED', 'APPROVED'].includes(item.status)) && this.requiredMaterialFacts.some((item) => item.status === 'UPLOADED')
    },
    nextAction() {
      if (this.arrivalHold) return { owner: '报到安排有调整', ...this.arrivalHold, button: '', path: '' }
      if (this.finalConfirmed) return { owner: '办理完成', title: '迎新手续已完成', description: '学院已确认入学，可在下方查看办理结果与住宿信息。', path: '' }
      if (this.o?.hasData === false) return { owner: '待学校安排', title: '暂无可办理的迎新记录', description: this.o.overallText || '请联系学校核对录取与账号关联。', path: '' }
      const actionable = this.taskList.filter(task => task.path && task.needsAction)
      const correction = actionable.find(task => task.returned)
      const task = correction || actionable[0]
      if (task) return { owner: '需要你完成', title: task.title, description: task.reason || task.statusText, button: task.action, path: task.path }
      if (this.o?.reportCode?.canIssue && !this.reportDone) return { owner: '到校时使用', title: '出示你的报到二维码', description: '到校后由辅导员或现场核验人员扫码。清单中的未办事项仍需继续办理。', button: '打开报到二维码', path: '/pages/student/orientation/code/index' }
      if (this.reportDone) return { owner: '学校处理中', title: '查看待办，等待学院确认', description: this.o?.selfService?.reason || '现场核验已完成。请查看下方未办事项，全部手续齐全后由学院确认入学。', path: '' }
      return { owner: '查看办理情况', title: '请查看下方清单', description: this.o?.selfService?.reason || this.o?.reportCode?.note || '学校正在核验办理条件。如有退回意见，请按要求补充。', path: '' }
    },
    taskList() {
      const stopped = !!this.arrivalHold || this.finalConfirmed
      const service = this.o?.selfService || {}
      const prefix = '/pages/student/orientation/'
      return (this.o?.steps || []).map(step => {
        const done = DONE.includes(step.status)
        const task = { ...step, statusText: ({ DONE: '已完成', WAIVED: '已减免', NOT_REQUIRED: '无需办理', DOING: '办理中', BLOCKED: '需处理', TODO: '待办理' })[step.status] || '待核实', reason: '', path: '', action: '查看', needsAction: false, returned: false }
        if (step.key === 'INFO') {
          task.returned = this.o?.blocked?.step === 'INFO'
          task.reason = task.returned ? this.o.blocked.reason : '学生确认信息，学校核验身份'
          if (!stopped && service.available) task.path = prefix + 'collect/index'
          task.needsAction = !!task.path && (!done || task.returned)
          if (step.status === 'DOING' && service.information?.complete && !task.returned) {
            task.needsAction = false
            task.path = ''
            task.statusText = '补充已提交，等待老师复核'
          }
          task.action = task.returned ? '补充信息' : '确认信息'
        }
        if (step.key === 'MATERIAL') {
          const returned = (service.materials || []).filter(item => item.isCurrent && ['RETURNED', 'REJECTED'].includes(item.status))
          task.returned = returned.length > 0
          task.reason = returned.map(item => item.returnReason).filter(Boolean).join('；')
          if (this.materialsWaitingReview) task.statusText = '已提交，等待老师审核'
          if (!stopped && service.canSubmitMaterials) task.path = prefix + 'materials/index'
          task.needsAction = !!task.path && !done && !this.materialsWaitingReview
          task.action = task.returned ? '补充材料' : done || this.materialsWaitingReview ? '查看材料' : '上传材料'
        }
        if (step.key === 'PAYMENT') {
          const green = this.o?.greenChannelStatus
          task.statusText = ({ PAID: '已缴清', WAIVED: '已减免', DEFERRED: '已批准缓缴', GREEN_CHANNEL: '绿色通道已通过', PARTIAL: '部分缴费，需继续办理', UNPAID: '待缴费', MISSING: '学校尚未登记缴费事实', UNAVAILABLE: '缴费结果待核实' })[this.o?.payStatus] || task.statusText
          if (['SUBMITTED', 'REVIEWING'].includes(green)) task.statusText = '绿色通道待审核'
          task.returned = green === 'RETURNED'
          task.reason = this.o?.greenChannel?.rejectReason || (!done ? '按学校通知缴费；有困难可申请绿色通道。缴费到账后由学校核验。' : '')
          if (!stopped && this.showGreenChannel) task.path = prefix + 'green-channel/index'
          task.action = task.returned ? '补充申请' : green === 'NOT_APPLIED' ? '申请缓缴' : '查看申请'
          task.needsAction = !!task.path && task.returned
        }
        if (step.key === 'DORM') { task.reason = this.dormArrangement; if (!this.arrivalHold) task.path = '/pages/student/affairs/dorm'; task.action = '查看住宿' }
        if (step.key === 'CHECKIN') { task.statusText = this.reportDone ? '已现场报到' : this.o?.reportCode?.canIssue ? '可出示报到码' : '报到码暂不可用'; task.reason = this.reportDone ? this.checkinSummary : this.o?.reportCode?.note || ''; if (!stopped && !this.reportDone && this.o?.reportCode?.canIssue) { task.path = prefix + 'code/index'; task.action = '报到码' } }
        if (step.key === 'CONFIRM' && !done) task.reason = '全部手续齐全后，由学院确认入学'
        return task
      })
    },
    heroSub() {
      if (this.arrivalHold) return '报到安排已更新'
      if (this.finalConfirmed) return '欢迎入学，下面是你的入学安排'
      if (this.reportDone && this.nextAction.owner === '需要你完成') return '请继续完成待办事项，办齐后由学院确认入学'
      if (this.reportDone) return this.qualificationBlockers.length ? '请关注审核进度与待补办事项' : '等待学院确认入学'
      return this.nextAction.owner === '学校处理中' ? '你的线上事项已提交' : this.nextAction.title
    },
    qualificationBlockers() {
      return this.o?.qualification?.blockers || []
    },
    qualificationVerdict() {
      return this.o && this.o.qualification ? this.o.qualification.verdict : ''
    },
    schoolItems() {
      if (this.finalConfirmed) return []
      if (this.qualificationVerdict === 'QUALIFIED') return []
      const messages = this.qualificationBlockers
        .filter((item) => !this.isStudentAction(item))
        .map((item) => this.friendlySchoolMessage(item))
      return [...new Set(messages)]
    },
    showGreenChannel() {
      return (this.o?.greenChannelStatus && this.o.greenChannelStatus !== 'NOT_APPLIED') || (['UNPAID', 'PARTIAL', 'MISSING', 'UNAVAILABLE'].includes(this.o?.payStatus) && this.o?.selfService?.canSubmitMaterials)
    },
    hasDormArrangement() {
      const status = this.o?.dorm?.status
      return !!this.o?.dorm?.label && ['RESERVED', 'ACTIVE'].includes(status)
    },
    dormArrangement() {
      if (this.hasDormArrangement) return this.o.dorm.label
      if (this.o?.dorm?.status === 'NOT_REQUIRED') return '无需住宿'
      if (this.o?.dorm?.statusLabel) return this.o.dorm.statusLabel
      return '学校正在安排，确定后会自动显示'
    },
    checkinSummary() {
      const parts = []
      if (this.o?.checkin?.pointName) parts.push(this.o.checkin.pointName)
      if (this.o?.checkin?.completedAt) parts.push(formatDateTime(this.o.checkin.completedAt))
      return parts.join(' · ')
    }
  },
  methods: {
    go,
    isStudentAction(item) {
      if (item.step === 'INFO') return true
      return item.step === 'MATERIAL' && !this.materialsWaitingReview
    },
    friendlySchoolMessage(item) {
      const mapped = {
        MATERIAL_EVIDENCE_NOT_READY: '迎新材料正在审核',
        PAYMENT_FACT_MISSING: '缴费结果正在同步',
        PAYMENT_INCOMPLETE: '缴费或绿色通道状态正在确认',
        DORM_NOT_CONFIRMED: '宿舍正在安排',
        MATERIAL_REQUIREMENTS_MISSING: '学校正在核对材料要求'
      }[item.code]
      if (mapped) return mapped
      if (String(item.code || '').startsWith('OPEN_EXCEPTION')) return '学校正在复核一项迎新事项'
      return '学校正在处理相关迎新事项'
    },
    load() {
      this.state = 'loading'
      const serial = ++this.requestSerial
      this.o = null
      studentApi.getOrientation().then((d) => { if (serial === this.requestSerial) { this.o = d; this.state = 'ready' } }).catch(() => { if (serial === this.requestSerial) this.state = 'error' })
    },
    call(c) {
      uni.makePhoneCall({ phoneNumber: c.phone, fail: () => toast('拨号未成功，可手动拨打：' + (c.phone || '')) })
    }
  }
}
</script>

<style scoped>
.or__task{display:flex;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid var(--border-light)}
.or__task:last-child{border-bottom:0}.or__task-title,.or__task-state,.or__task-reason{display:block;line-height:1.6}.or__task-title{font-weight:600}.or__task-state{color:var(--text-secondary);font-size:13px}.or__task-reason{color:var(--text-tertiary);font-size:12px;overflow-wrap:anywhere}
.or__task button{flex-shrink:0;margin:0;padding:7px 10px;min-height:42px;font-size:13px;color:var(--brand-primary);border:1px solid var(--border-light);border-radius:8px}

.or__housing-summary { display: flex; align-items: center; gap: 12px; padding: 14px 0; border-bottom: 1px solid var(--border-light); }
.or__housing-summary button { margin: 0; padding: 6px 12px; min-height: 40px; font-size: 14px; color: var(--brand-primary); border: 1px solid var(--border-light); border-radius: 6px; }
.or__hero { padding: 20px; border-radius: 20px; color: #fff; background: linear-gradient(135deg, #1859d8, #2f74ed); box-shadow: 0 12px 30px rgba(31, 95, 219, .18); }
.or__hero.is-done { background: linear-gradient(135deg, #087f5b, #13a477); box-shadow: 0 12px 30px rgba(8, 127, 91, .18); }
.or__hero-batch { font-size: var(--font-size-xs); opacity: .82; }
.or__hero-main { display: flex; align-items: center; gap: 13px; margin-top: 11px; }
.or__hero-icon { width: 44px; height: 44px; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0; background: rgba(255,255,255,.2); font-size: 20px; font-weight: 700; }
.or__hero-title { display: block; font-size: 22px; font-weight: 700; }
.or__hero-sub { display: block; margin-top: 4px; font-size: var(--font-size-sm); opacity: .88; }
.or__identity-line { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 15px; padding-top: 12px; border-top: 1px solid rgba(255,255,255,.2); font-size: var(--font-size-xs); opacity: .9; }
.or__result { border: 1px solid #b8ead8; background: #f2fbf7; }
.or__result-title { font-size: var(--font-size-lg); font-weight: 700; color: #086c4e; }
.or__done-tag { padding: 4px 10px; border-radius: 20px; color: #087456; background: #d7f4e8; font-size: var(--font-size-xs); }
.or__result-desc { display: block; margin-top: 9px; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.or__result-meta { margin-top: 11px; padding-top: 10px; border-top: 1px solid #d8eee5; color: #407164; font-size: var(--font-size-xs); }
.or__arrangement { display: flex; align-items: center; gap: 12px; padding: 9px 0; border-bottom: 1px solid var(--border-light); }
.or__arrangement:last-child { border-bottom: 0; }
.or__arrangement-icon { width: 34px; height: 34px; display: flex; align-items: center; justify-content: center; border-radius: 10px; background: var(--gray-50); }
.or__arrangement-label { display: block; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.or__arrangement-value { display: block; margin-top: 2px; color: var(--text-primary); font-size: var(--font-size-base); font-weight: 600; }
.or__after-list { display: flex; flex-direction: column; gap: 15px; }
.or__after-item { display: flex; align-items: flex-start; gap: 10px; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.55; }
.or__after-no { width: 22px; height: 22px; border-radius: 50%; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: #fff; background: var(--brand-primary); font-size: 11px; }
.or__next { border: 1px solid #cfe0ff; background: linear-gradient(145deg, #fff, #f4f8ff); }
.or__eyebrow { color: var(--brand-primary); font-size: var(--font-size-sm); font-weight: 600; }
.or__next-tag { padding: 4px 9px; border-radius: 20px; color: #1558c8; background: #e9f1ff; font-size: var(--font-size-xs); }
.or__next-tag.is-school { color: #667085; background: #f0f2f5; }
.or__next-title { display: block; margin-top: 13px; color: var(--text-primary); font-size: 21px; font-weight: 700; }
.or__next-desc { display: block; margin: 7px 0 15px; color: var(--text-secondary); font-size: var(--font-size-sm); line-height: 1.6; }
.or__fold { padding: 15px 17px; }
.or__fold-title { display: block; color: var(--text-primary); font-size: var(--font-size-base); font-weight: 600; }
.or__fold-sub { display: block; margin-top: 3px; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.or__fold-arrow { color: var(--brand-primary); font-size: var(--font-size-sm); }
.or__fold-content, .or__timeline, .or__tool-list { margin-top: 13px; padding-top: 12px; border-top: 1px solid var(--border-light); }
.or__school-item { display: flex; gap: 8px; margin-top: 7px; color: var(--text-secondary); font-size: var(--font-size-sm); }
.or__school-dot { color: var(--success-600); }
.or__tool-list { display: grid; grid-template-columns: 1fr 1fr; gap: 9px; }
.or__tool { padding: 12px 10px; border-radius: 10px; color: var(--text-secondary); background: var(--gray-50); text-align: center; font-size: var(--font-size-sm); }
.or__tool.is-help { grid-column: 1 / -1; color: #8a5b00; background: #fff7e5; }
.or__contact { display: flex; align-items: center; gap: var(--space-3); }
.or__contact-avatar { width: 38px; height: 38px; border-radius: 50%; background: var(--primary-50); color: var(--brand-primary); display: flex; align-items: center; justify-content: center; }
.or__contact-role { display: block; color: var(--text-tertiary); font-size: var(--font-size-xs); }
.or__contact-call { padding: 6px 13px; border: 1px solid var(--brand-primary); border-radius: 20px; color: var(--brand-primary); font-size: var(--font-size-sm); }
</style>
