<template>
  <view class="page-wrap activity-page">
    <MobileNavBar variant="teacher" title="活动现场" subtitle="推进活动、签到与名单确认" show-back />
    <MobileGlobalState :state="state" :description="loadError" @retry="load">
      <view v-if="state === 'ready'" class="page-pad activity-body">
        <scroll-view class="activity-filters" scroll-x>
          <button v-for="item in filters" :key="item.value" class="activity-filter" :class="{ active: status === item.value }" @click="changeStatus(item.value)">
            {{ item.label }}<text v-if="item.value"> {{ count(item.value) }}</text>
          </button>
        </scroll-view>

        <view v-if="activities.length" class="activity-list">
          <view v-for="item in activities" :key="item.activityId" class="activity-row" :class="{ focused: String(item.activityId) === focusId }" @click="openActivity(item)">
            <view class="activity-main">
              <view class="activity-title-line">
                <text class="activity-title">{{ item.activityName }}</text>
                <MobileStatusTag :status="item.status" :label="item.statusLabel" />
              </view>
              <text class="activity-meta">{{ timeText(item) }}</text>
              <text class="activity-meta">{{ item.location || '地点待定' }} · 已报名 {{ item.signupCount || 0 }}</text>
            </view>
            <text class="activity-next">›</text>
          </view>
          <button v-if="activities.length < total" class="btn btn-secondary activity-more" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多' }}</button>
        </view>
        <MobileGlobalState v-else state="empty" title="当前没有匹配活动" description="切换状态查看其他活动。" />
      </view>
    </MobileGlobalState>

    <view v-if="selected" class="activity-mask" @click.self="closeDetail">
      <view class="activity-sheet">
        <view class="activity-sheet-head">
          <view class="activity-main"><text class="activity-title">{{ selected.activityName }}</text><text class="activity-meta">{{ selected.location || '地点待定' }} · {{ selected.statusLabel }}</text></view>
          <button size="mini" :disabled="!!busy" @click="closeDetail">关闭</button>
        </view>
        <scroll-view scroll-y class="activity-sheet-body">
          <view class="activity-progress">
            <text v-for="step in steps" :key="step.status" class="activity-step" :class="{ done: stepDone(step.status), current: selected.status === step.status }">{{ step.label }}</text>
          </view>
          <view class="activity-facts">
            <text>{{ timeText(selected) }}</text>
            <text>报名 {{ participantSummary.total }} · 已签到 {{ participantSummary.checkedIn }}</text>
            <text v-if="selected.creditValue != null">确认后每人计 {{ selected.creditValue }} {{ creditUnit(selected.creditType) }}</text>
          </view>
          <MobileInlineAlert v-if="detailError" type="warning" title="名单暂不可用" :description="detailError" />
          <view v-else class="activity-participants">
            <view class="activity-section-head"><text>参与名单</text><text>{{ participantSummary.checkedIn }}/{{ participantSummary.total }} 已签到</text></view>
            <text v-if="!participants.length" class="activity-empty">尚无报名学生</text>
            <view v-for="person in participants" :key="person.signupId" class="participant-row">
              <view><text class="participant-name">{{ person.realName || '学生' }}</text><text class="activity-meta">{{ person.studentNo || '学号未同步' }}</text></view>
              <MobileStatusTag :status="person.signupStatus" :label="participantLabel(person.signupStatus)" />
            </view>
          </view>
        </scroll-view>
        <view v-if="actionable" class="activity-actions">
          <button v-if="allows('ENROLL_CLOSE')" class="btn btn-primary" :disabled="!!busy" @click="confirmTransition('ENROLL_CLOSE')">截止报名</button>
          <button v-if="allows('START')" class="btn btn-primary" :disabled="!!busy" @click="confirmTransition('START')">开始活动</button>
          <button v-if="selected.status === 'ONGOING'" class="btn btn-secondary" :disabled="!!busy" @click="showCode">生成签到码</button>
          <button v-if="allows('FINISH')" class="btn btn-primary" :disabled="!!busy" @click="confirmTransition('FINISH')">结束活动</button>
          <button v-if="allows('CONFIRM')" class="btn btn-primary" :disabled="!!busy || participantSummary.checkedIn === 0" @click="confirmRoster">确认名单并生成积分</button>
        </view>
      </view>
    </view>

    <view v-if="codeData" class="activity-code-mask" @click.self="codeData = null">
      <view class="card activity-code-card">
        <text class="activity-title">{{ codeData.activityName }}</text>
        <text class="activity-code">{{ codeData.checkinCode }}</text>
        <text class="activity-meta">动态码 5 分钟有效，学生在“活动与第二课堂”输入。</text>
        <button class="btn btn-primary" @click="codeData = null">完成</button>
      </view>
    </view>
  </view>
</template>

<script>
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const STATUS_ORDER = ['PUBLISHED', 'ENROLL_CLOSED', 'ONGOING', 'FINISHED', 'CONFIRMED', 'ARCHIVED']

export default {
  data() {
    return {
      state: 'loading', loadError: '', status: 'PUBLISHED,ENROLL_CLOSED,ONGOING,FINISHED', activities: [], total: 0,
      page: 1, loadingMore: false, selected: null, participants: [], detailError: '', busy: '', codeData: null,
      focusId: '',
      filters: [
        { value: 'PUBLISHED,ENROLL_CLOSED,ONGOING,FINISHED', label: '待处理' },
        { value: 'ONGOING', label: '进行中' },
        { value: 'CONFIRMED,ARCHIVED', label: '已完成' },
        { value: '', label: '全部' }
      ],
      steps: [
        { status: 'PUBLISHED', label: '报名' }, { status: 'ENROLL_CLOSED', label: '截止' },
        { status: 'ONGOING', label: '进行' }, { status: 'FINISHED', label: '结束' },
        { status: 'CONFIRMED', label: '确认' }
      ],
      statusCounts: {}
    }
  },
  computed: {
    participantSummary() {
      return {
        total: this.participants.filter(x => x.signupStatus !== 'CANCELLED').length,
        checkedIn: this.participants.filter(x => ['CHECKED_IN', 'CONFIRMED'].includes(x.signupStatus)).length
      }
    },
    actionable() { return this.selected && (this.selected.allowedActions || []).some(x => ['ENROLL_CLOSE', 'START', 'FINISH', 'CONFIRM'].includes(x)) }
  },
  onLoad(query = {}) { this.focusId = String(query.activityId || query.recordId || ''); this.load() },
  onShow() { if (this.state === 'ready' && !this.selected) this.load(false) },
  onPullDownRefresh() { this.load(false).finally(() => uni.stopPullDownRefresh()) },
  onBackPress() { if (this.codeData) { this.codeData = null; return true } if (this.selected) { this.closeDetail(); return true } return false },
  methods: {
    count(value) { return String(value).split(',').reduce((sum, key) => sum + Number(this.statusCounts[key] || 0), 0) },
    allows(action) { return Array.isArray(this.selected?.allowedActions) && this.selected.allowedActions.includes(action) },
    timeText(item) { const start = item.startAt ? new Date(item.startAt).toLocaleString('zh-CN', { hour12: false }) : '时间待定'; const end = item.endAt ? new Date(item.endAt).toLocaleString('zh-CN', { hour12: false }) : ''; return end ? `${start} 至 ${end}` : start },
    participantLabel(value) { return ({ ENROLLED: '已报名', WAITLIST: '候补', CHECKED_IN: '已签到', CONFIRMED: '已确认', CANCELLED: '已取消' })[value] || '状态待确认' },
    creditUnit(value) { return value === 'VOLUNTEER_HOUR' ? '志愿小时' : '第二课堂积分' },
    stepDone(value) { return STATUS_ORDER.indexOf(this.selected?.status) >= STATUS_ORDER.indexOf(value) },
    changeStatus(value) { if (this.status === value) return; this.status = value; this.focusId = ''; this.load() },
    async load(more = false) {
      if (more && (this.loadingMore || this.activities.length >= this.total)) return
      const page = more ? this.page + 1 : 1
      if (!more) { this.state = 'loading'; this.loadError = '' } else this.loadingMore = true
      try {
        const data = await affairsContractApi.getTeacherActivities({ status: this.status, page, pageSize: 20 })
        if (!Array.isArray(data?.items)) throw new Error('活动列表暂不可用')
        this.activities = more ? [...this.activities, ...data.items] : data.items
        this.total = Number(data.total || 0); this.statusCounts = data.statusCounts || {}; this.page = page; this.state = 'ready'
        if (!more && this.focusId) {
          const row = this.activities.find(x => String(x.activityId) === this.focusId)
          if (row) await this.openActivity(row)
          else { this.loadError = '该活动不存在、已变更，或不在当前权限范围内'; this.state = 'error' }
        }
      } catch (e) {
        if (!more) { this.loadError = normalizeError(e).text || e.message || '活动列表加载失败'; this.state = normalizeError(e).pageState || 'error' }
        else toast(normalizeError(e).text || '加载更多失败')
      } finally { this.loadingMore = false }
    },
    loadMore() { return this.load(true) },
    async openActivity(item) {
      this.selected = item; this.participants = []; this.detailError = ''
      try {
        const data = await affairsContractApi.getTeacherActivityParticipants(item.activityId)
        if (!Array.isArray(data?.items)) throw new Error('活动名单暂不可用')
        this.participants = data.items
      } catch (e) { this.detailError = normalizeError(e).text || e.message || '活动名单加载失败' }
    },
    closeDetail() { if (!this.busy) { this.selected = null; this.participants = []; this.detailError = ''; this.focusId = '' } },
    confirmTransition(action) {
      const label = { ENROLL_CLOSE: '截止报名', START: '开始活动', FINISH: '结束活动' }[action]
      const note = action === 'FINISH' ? '结束后将进入名单确认，确认名单才会生成积分。' : `确认${label}“${this.selected.activityName}”？`
      uni.showModal({ title: label, content: note, success: res => { if (res.confirm) this.runTransition(action) } })
    },
    async runTransition(action) {
      if (this.busy || !this.selected) return
      this.busy = action
      try {
        const updated = await affairsContractApi.transitionTeacherActivity(this.selected.activityId, action, this.selected.version)
        toast(updated.statusLabel || '活动状态已更新'); this.replaceSelected(updated); await this.openActivity(updated)
      } catch (e) { toast(normalizeError(e).text || '状态更新失败，请刷新后重试') } finally { this.busy = '' }
    },
    confirmRoster() {
      if (!this.selected || this.participantSummary.checkedIn === 0) return
      uni.showModal({ title: '确认参与名单', content: `将为 ${this.participantSummary.checkedIn} 名已签到学生生成正式积分。确认后如需撤销，请在教师 PC 办理。`, success: res => { if (res.confirm) this.runConfirm() } })
    },
    async runConfirm() {
      if (this.busy || !this.selected) return
      this.busy = 'CONFIRM'
      try {
        const updated = await affairsContractApi.confirmTeacherActivity(this.selected.activityId, this.selected.version)
        toast(`名单已确认，已生成 ${updated.creditsGranted || 0} 人积分`); this.replaceSelected(updated); await this.openActivity(updated)
      } catch (e) { toast(normalizeError(e).text || '名单确认失败，请刷新后重试') } finally { this.busy = '' }
    },
    replaceSelected(updated) {
      this.selected = updated
      this.activities = this.activities.map(x => String(x.activityId) === String(updated.activityId) ? updated : x)
    },
    async showCode() {
      if (this.busy || !this.selected) return
      this.busy = 'CODE'
      try { this.codeData = { ...(await affairsContractApi.getActivityCheckinToken(this.selected.activityId)), activityName: this.selected.activityName } }
      catch (e) { toast(normalizeError(e).text || '签到码生成失败') } finally { this.busy = '' }
    }
  }
}
</script>

<style scoped>
.activity-page{min-height:100vh;background:var(--bg-page)}.activity-body{display:flex;flex-direction:column;gap:12px}.activity-filters{white-space:nowrap}.activity-filter{display:inline-flex;margin-right:8px;padding:8px 13px;border:1px solid var(--border-light);border-radius:18px;background:var(--bg-card);color:var(--text-secondary);font-size:12px}.activity-filter.active{border-color:var(--brand-primary);background:var(--brand-primary);color:#fff}.activity-list{border-top:1px solid var(--border-light)}.activity-row{display:flex;align-items:center;gap:10px;padding:15px 2px;border-bottom:1px solid var(--border-light)}.activity-row.focused{background:var(--brand-light)}.activity-main{min-width:0;flex:1}.activity-title-line,.activity-sheet-head,.activity-section-head{display:flex;align-items:center;justify-content:space-between;gap:10px}.activity-title{display:block;color:var(--text-primary);font-size:16px;font-weight:700;overflow-wrap:anywhere}.activity-meta{display:block;margin-top:5px;color:var(--text-secondary);font-size:12px;line-height:1.5}.activity-next{color:var(--text-tertiary);font-size:24px}.activity-more{width:100%;margin-top:14px}.activity-mask,.activity-code-mask{position:fixed;z-index:1000;inset:0;display:flex;align-items:flex-end;background:rgba(15,23,42,.52)}.activity-sheet{width:100%;max-height:88vh;border-radius:18px 18px 0 0;background:var(--bg-card);box-shadow:0 -12px 32px rgba(15,23,42,.12)}.activity-sheet-head{padding:18px;border-bottom:1px solid var(--border-light)}.activity-sheet-body{max-height:62vh;padding:0 18px;box-sizing:border-box}.activity-progress{display:flex;padding:16px 0 12px}.activity-step{position:relative;flex:1;padding-top:17px;color:var(--text-tertiary);font-size:10px;text-align:center}.activity-step::before{position:absolute;z-index:1;top:3px;left:50%;width:8px;height:8px;border:2px solid var(--border-default);border-radius:50%;background:var(--bg-card);content:'';transform:translateX(-50%)}.activity-step::after{position:absolute;top:8px;right:50%;width:100%;height:1px;background:var(--border-default);content:''}.activity-step:first-child::after{display:none}.activity-step.done{color:var(--brand-primary);font-weight:700}.activity-step.done::before,.activity-step.done::after{border-color:var(--brand-primary);background:var(--brand-primary)}.activity-facts{display:flex;flex-direction:column;gap:5px;padding:12px 0;border-bottom:1px solid var(--border-light);color:var(--text-secondary);font-size:12px}.activity-participants{padding:14px 0}.activity-section-head{color:var(--text-primary);font-size:13px;font-weight:700}.activity-section-head text:last-child{color:var(--text-secondary);font-size:11px;font-weight:400}.participant-row{display:flex;align-items:center;justify-content:space-between;padding:11px 0;border-bottom:1px solid var(--border-light)}.participant-name{display:block;color:var(--text-primary);font-size:13px;font-weight:600}.activity-empty{display:block;padding:24px 0;color:var(--text-secondary);font-size:13px;text-align:center}.activity-actions{display:flex;gap:8px;padding:12px 18px calc(12px + env(safe-area-inset-bottom));border-top:1px solid var(--border-light)}.activity-actions .btn{min-width:0;flex:1;margin:0;font-size:12px}.activity-code-mask{align-items:center;padding:24px;box-sizing:border-box}.activity-code-card{width:100%;padding:24px;text-align:center}.activity-code{display:block;margin:22px 0 12px;color:var(--brand-primary);font-size:44px;font-weight:800;letter-spacing:10px}
</style>
