<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="学工待办" subtitle="逐条待办、权限、数据范围与 PC 同源" back />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <view class="ta__total">
          <text class="ta__total-n">{{ data.total }}</text>
          <text class="ta__total-l">项学工待办</text>
        </view>

        <view class="section-head"><text class="section-head__title">待我处理</text></view>
        <view class="ta__empty" v-if="!todoItems.length"><text>暂无待办</text></view>
        <view class="stack" v-else>
          <view v-for="item in todoItems" :key="item.todoId" class="ta__todo" @click="openTodo(item)">
            <view class="flex-1">
              <view class="ta__todo-head">
                <text class="ta__label">{{ item.label || item.todoType }}</text>
                <text v-if="item.overdue" class="ta__overdue">已逾期</text>
              </view>
              <text class="ta__title">{{ item.title || '学工待办' }}</text>
              <text v-if="item.studentName || item.studentNo" class="ta__sub">
                {{ item.studentName || '学生' }}{{ item.studentNo ? ` · ${item.studentNo}` : '' }}{{ item.className ? ` · ${item.className}` : '' }}
              </text>
              <text v-if="item.dueAt" class="ta__due">截止 {{ formatTime(item.dueAt) }}</text>
            </view>
            <text class="ta__go">›</text>
          </view>
        </view>

        <view class="section-head ta__section"><text class="section-head__title">按业务分类</text></view>
        <view class="stack">
          <view v-for="c in data.cards" :key="c.todoType" class="ta__card" @click="openCard(c)">
            <text class="ta__label">{{ c.label }}</text>
            <view class="ta__right"><text class="ta__count">{{ c.count }}</text><text class="ta__go">›</text></view>
          </view>
        </view>

        <template v-if="activityVisible">
          <view class="section-head ta__section"><text class="section-head__title">现场活动签到</text></view>
          <MobileInlineAlert v-if="activityError" type="warning" title="活动签到暂不可用" :description="activityError" />
          <MobileGlobalState v-else-if="!activities.length" state="empty" title="暂无进行中活动" description="活动开始后可在此生成5分钟动态签到码。" />
          <view v-else class="stack">
            <view v-for="a in activities" :key="a.activityId" class="ta__card ta__activity">
              <view class="flex-1">
                <text class="ta__label">{{ a.activityName }}</text>
                <text class="ta__sub">{{ a.location || '未填写地点' }} · 已报名 {{ a.signupCount || 0 }} 人</text>
              </view>
              <button class="btn btn-primary ta__code-btn" :disabled="codeLoading === a.activityId" @click="showCode(a)">
                {{ codeLoading === a.activityId ? '生成中…' : '生成签到码' }}
              </button>
            </view>
          </view>
        </template>
      </view>
    </MobileGlobalState>

    <view v-if="codeData" class="ta__mask" @click.self="codeData = null">
      <view class="card ta__code-card">
        <text class="card-title">{{ codeData.activityName }}</text>
        <text class="ta__code">{{ codeData.checkinCode }}</text>
        <text class="ta__code-tip">请学生在活动页输入此码。动态码最多5分钟有效，过期后重新生成。</text>
        <button class="btn btn-primary" @click="codeData = null">完成</button>
      </view>
    </view>
  </view>
</template>

<script>
import { teacherApi } from '@/services/teacherApi'
import { affairsContractApi } from '@/services/affairsContractApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const ROUTES = {
  LEAVE_APPROVAL: '/pages/teacher/affairs-leave/index', LEAVE_CANCEL: '/pages/teacher/affairs-leave/index',
  LEAVE_OVERDUE: '/pages/teacher/affairs-leave/index', LEAVE_EXTENSION: '/pages/teacher/affairs-leave/index',
  AID_APPROVAL: '/pages/teacher/affairs-review/index?type=AID_APPROVAL',
  AID_ADJUST: '/pages/teacher/affairs-review/index?type=AID_ADJUST',
  FUNDING_APPROVAL: '/pages/teacher/affairs-review/index?type=FUNDING_APPROVAL',
  DISCIPLINE_APPROVAL: '/pages/teacher/affairs-review/index?type=DISCIPLINE_APPROVAL',
  DISCIPLINE_REMOVE: '/pages/teacher/affairs-review/index?type=DISCIPLINE_REMOVE',
  RISK_HANDLE: '/pages/teacher/affairs-review/index?type=RISK_HANDLE',
  DORM_TRANSFER: '/pages/teacher/dorm-review/index?tab=transfer',
  DORM_EXCEPTION: '/pages/teacher/dorm-review/index?tab=exception',
  AID_OBJECTION_REVIEW: '/pages/teacher/affairs-review/index?type=AID_OBJECTION_REVIEW',
  FUNDING_APPEAL_REVIEW: '/pages/teacher/affairs-review/index?type=FUNDING_APPEAL_REVIEW',
  DISCIPLINE_APPEAL_REVIEW: '/pages/teacher/affairs-review/index?type=DISCIPLINE_APPEAL_REVIEW',
  SECOND_CLASS_APPEAL_REVIEW: '/pages/teacher/affairs-review/index?type=SECOND_CLASS_APPEAL_REVIEW'
}

export default {
  data() { return { data: null, state: 'loading', activities: [], activityVisible: true, activityError: '', codeData: null, codeLoading: '' } },
  computed: { todoItems() { return (this.data && Array.isArray(this.data.items)) ? this.data.items : [] } },
  onLoad() { this.load() },
  onShow() { if (this.state === 'ready') this.load() },
  methods: {
    formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '' },
    load() {
      this.state = 'loading'; this.activityError = ''
      teacherApi.getAffairs().then((d) => { this.data = d; this.state = 'ready' })
        .catch((e) => { this.state = 'error'; toast(normalizeError(e).text || '学工待办加载失败') })
      affairsContractApi.getOngoingActivities().then((d) => { this.activities = (d && d.items) || []; this.activityVisible = true })
        .catch((e) => {
          const n = normalizeError(e)
          if (n.kind === 'forbidden') { this.activityVisible = false; this.activities = [] }
          else { this.activityVisible = true; this.activityError = n.text || '活动数据加载失败，请稍后重试' }
        })
    },
    routeFor(todoType, params = {}) {
      const base = ROUTES[todoType]
      if (!base) return ''
      const query = []
      if (params.recordId) query.push(`recordId=${encodeURIComponent(params.recordId)}`)
      if (params.todoId) query.push(`todoId=${encodeURIComponent(params.todoId)}`)
      if (!query.length) return base
      return base + (base.includes('?') ? '&' : '?') + query.join('&')
    },
    openTodo(item) {
      const params = {
        ...(item.actionParams || {}),
        recordId: item.recordId || (item.actionParams && item.actionParams.recordId) || '',
        todoId: item.todoId || (item.actionParams && item.actionParams.todoId) || ''
      }
      const url = this.routeFor(item.todoType, params)
      if (!url) { toast('该待办类型尚未配置移动端处理入口'); return }
      uni.navigateTo({ url })
    },
    openCard(c) {
      const url = this.routeFor(c.todoType)
      if (!url) { toast('该待办类型尚未配置移动端处理入口'); return }
      uni.navigateTo({ url })
    },
    showCode(a) {
      if (this.codeLoading) return
      this.codeLoading = a.activityId
      affairsContractApi.getActivityCheckinToken(a.activityId).then((d) => { this.codeData = d })
        .catch((e) => toast(normalizeError(e).text || '签到码生成失败'))
        .finally(() => { this.codeLoading = '' })
    }
  }
}
</script>

<style scoped>
.ta__total { background: var(--brand-primary); color: #fff; border-radius: var(--radius-lg); padding: var(--space-4); margin-bottom: var(--space-4); display: flex; align-items: baseline; gap: var(--space-2); }
.ta__total-n { font-size: 28px; font-weight: 700; }
.ta__empty { text-align: center; color: var(--text-tertiary); padding: var(--space-5); }
.ta__card,.ta__todo { display: flex; justify-content: space-between; align-items: center; background: var(--bg-card); border-radius: var(--radius-lg); padding: var(--space-4); box-shadow: var(--shadow-card); }
.ta__todo { align-items: flex-start; gap: 12px; }
.ta__todo-head { display: flex; align-items: center; gap: 8px; }
.ta__overdue { font-size: 11px; color: var(--danger-600); background: var(--danger-50, #fef2f2); padding: 2px 6px; border-radius: 6px; }
.ta__title { display: block; margin-top: 5px; color: var(--text-primary); font-size: 14px; line-height: 1.5; }
.ta__label { display: block; font-weight: 600; color: var(--text-primary); }
.ta__sub,.ta__due { display: block; margin-top: 4px; font-size: 12px; color: var(--text-tertiary); }
.ta__due { color: var(--warning-700); }
.ta__right { display: flex; align-items: center; gap: 8px; }
.ta__count { font-size: 20px; font-weight: 700; color: var(--brand-primary); }
.ta__go { color: var(--text-tertiary); font-size: 20px; }
.ta__section { margin-top: 22px; }
.ta__activity { gap: 10px; }
.ta__code-btn { flex-shrink: 0; font-size: 12px; padding: 0 10px; }
.ta__mask { position: fixed; inset: 0; z-index: 1000; background: rgba(15,23,42,.5); display: flex; align-items: center; justify-content: center; padding: 24px; }
.ta__code-card { width: 100%; text-align: center; padding: 24px; }
.ta__code { display: block; font-size: 44px; letter-spacing: 10px; font-weight: 800; color: var(--brand-primary); margin: 22px 0 12px; }
.ta__code-tip { display: block; font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin-bottom: 18px; }
</style>
