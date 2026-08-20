<template>
  <view class="page-wrap">
    <MobileNavBar variant="teacher" title="学生360" subtitle="单学生移动工作台" :show-back="true" />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad stack" v-if="s">
        <view class="sd__head card">
          <view class="sd__avatar">{{ (s.base.name || '').slice(0, 1) }}</view>
          <view class="flex-1">
            <view class="row" style="gap:6px;">
              <text class="t-lg t-bold">{{ s.base.name }}</text>
              <MobileRiskTag v-if="s.risk && s.risk.level !== 'LOW'" :level="s.risk.level" />
            </view>
            <text class="sd__sub">{{ s.base.studentNo }} · {{ s.base.className || '未分班' }}</text>
            <text class="sd__sub">{{ stageText(s.base.stage) }} · {{ s.base.status || '—' }}</text>
          </view>
        </view>

        <MobileInlineAlert
          v-if="s.risk && s.risk.level !== 'LOW'"
          type="danger"
          :title="'当前风险：' + riskText(s.risk.level)"
          :description="riskDescription"
        />

        <view class="section-head"><text class="section-head__title">快捷处理</text></view>
        <view class="sd__actions card">
          <view
            v-for="action in s.actions"
            :key="action.key"
            class="sd__action"
            :class="{ 'is-disabled': !action.enabled }"
            @click="runAction(action)"
          >
            <text class="sd__action-icon">{{ actionIcon(action.key) }}</text>
            <text class="sd__action-label">{{ action.label }}</text>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">关键状态</text></view>
        <view class="stack-sm">
          <view v-for="section in s.sections" :key="section.key" class="card sd__section" @click="openSection(section)">
            <view class="row-between">
              <view class="flex-1">
                <view class="row" style="gap:6px;">
                  <text class="t-md t-bold">{{ section.title }}</text>
                  <text v-if="section.abnormal" class="sd__abnormal">需关注</text>
                </view>
                <text class="sd__section-summary">{{ section.summary }}</text>
              </view>
              <text v-if="section.actionKey" class="sd__link">去处理 ›</text>
            </view>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">敏感专区</text></view>
        <view class="card stack-sm">
          <view class="sd__sensitive" @click="openMental">
            <view class="flex-1">
              <text class="t-md">心理关注</text>
              <text class="sd__section-summary">{{ s.sensitive.mental.exists ? '存在关注标记' : '暂无关注标记' }} · 明细需专项授权与审计</text>
            </view>
            <text class="sd__link">专项入口 ›</text>
          </view>
          <view class="sd__divider" />
          <view class="sd__sensitive">
            <view class="flex-1">
              <text class="t-md">处分记录</text>
              <text class="sd__section-summary">{{ s.sensitive.discipline.exists ? statusText(s.sensitive.discipline.status) : '暂无生效处分投影' }} · 不展示事由与文书正文</text>
            </view>
          </view>
        </view>

        <view class="section-head"><text class="section-head__title">最近动态</text></view>
        <MobileGlobalState v-if="!s.timeline.length" state="empty" title="暂无最近动态" description="没有真实状态变化时不生成示例数据。" />
        <view class="card" v-else>
          <view v-for="event in s.timeline" :key="event.id" class="sd__timeline">
            <view class="sd__dot" />
            <view class="flex-1">
              <text class="sd__timeline-text">{{ stageText(event.stage) }}{{ event.reason ? ' · ' + event.reason : '' }}</text>
              <text class="sd__timeline-time">{{ formatTime(event.time) }}</text>
            </view>
          </view>
        </view>

        <text class="sd__freshness">数据时间 {{ formatTime(s.asOf) }} · 投影 {{ s.projectionVersion }}</text>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import { teacherStudent360V3Api } from '@/services/teacherStudent360V3Api'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

const RISK = { LOW: '低', MEDIUM: '中', HIGH: '高', CRITICAL: '严重', URGENT: '紧急' }
const STAGE = {
  ADMITTED: '录取', PRE_STUDENT_VERIFIED: '预备生', REGISTERED_PENDING_ENROLLMENT: '待注册',
  ENROLLED: '在校', INTERN: '实习', GRADUATING: '毕业年级', GRADUATED: '已毕业', ALUMNI: '校友'
}
const ACTION_ICON = { RECORD_CONTACT: '联', NEW_TALK: '谈', FAMILY_CONTACT: '家', EMPLOYMENT_FOLLOWUP: '就' }

function query(params) {
  return Object.entries(params)
    .filter(([, value]) => value !== undefined && value !== null && String(value) !== '')
    .map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
    .join('&')
}

export default {
  data() { return { s: null, state: 'loading', id: '' } },
  onLoad(q) { this.id = (q && q.id) || '' },
  onShow() { if (this.id) this.load() },
  computed: {
    riskDescription() {
      if (!this.s || !this.s.risk) return ''
      const parts = []
      if (Number(this.s.risk.warningCount || 0) > 0) parts.push(`${this.s.risk.warningCount} 条学业预警`)
      if (this.s.risk.internshipRisk && this.s.risk.internshipRisk !== 'NONE') parts.push(`实习 ${this.s.risk.internshipRisk}`)
      if (this.s.risk.affairsRisk && this.s.risk.affairsRisk !== 'LOW') parts.push(`学工 ${this.s.risk.affairsRisk}`)
      return parts.join(' · ') || '存在需要关注的业务状态'
    }
  },
  methods: {
    riskText(value) { return RISK[value] || value || '—' },
    stageText(value) { return STAGE[value] || value || '当前阶段' },
    statusText(value) { return value === 'EFFECTIVE' ? '存在生效处分' : (value || '存在记录') },
    actionIcon(key) { return ACTION_ICON[key] || '办' },
    formatTime(value) { return value ? String(value).slice(0, 16).replace('T', ' ') : '—' },
    load() {
      this.state = 'loading'
      teacherStudent360V3Api.get(this.id).then((data) => {
        this.s = data && data.hasData ? data : null
        this.state = this.s ? 'ready' : 'empty'
      }).catch((error) => {
        const normalized = normalizeError(error)
        if (normalized.kind === 'forbidden' || normalized.kind === 'notfound') {
          toast(normalized.kind === 'forbidden' ? '无权限查看该学生' : '未找到该学生')
          this.s = null
          this.state = 'empty'
        } else {
          this.state = 'error'
        }
      })
    },
    studentParams(extra = {}) {
      const base = this.s && this.s.base ? this.s.base : {}
      return query({
        source: 'student360',
        studentId: this.s && this.s.studentId,
        studentName: base.name,
        studentNo: base.studentNo,
        className: base.className,
        ...extra
      })
    },
    runAction(action) {
      if (!action || !action.enabled) return toast('当前学生暂无可执行的该项业务')
      if (action.key === 'RECORD_CONTACT') {
        return uni.navigateTo({ url: `/pages/teacher/family-contact/index?${this.studentParams({ mode: 'create', contactType: 'PHONE' })}` })
      }
      if (action.key === 'NEW_TALK') {
        return uni.navigateTo({ url: `/pages/teacher/affairs/talk/index?${this.studentParams({ mode: 'create' })}` })
      }
      if (action.key === 'FAMILY_CONTACT') {
        return uni.navigateTo({ url: `/pages/teacher/family-contact/index?${this.studentParams({ mode: 'create' })}` })
      }
      if (action.key === 'EMPLOYMENT_FOLLOWUP') {
        const employmentStudentId = this.s && this.s.context && this.s.context.employmentStudentId
        return uni.navigateTo({ url: `/pages/teacher/employment-follow/index?${this.studentParams({ mode: 'follow', employmentStudentId })}` })
      }
    },
    openSection(section) {
      if (!section || !section.actionKey) return
      if (section.actionKey === 'ACADEMIC_WARNING') return uni.navigateTo({ url: '/pages/teacher/academic-warning/index' })
      if (section.actionKey === 'INTERNSHIP_GUIDANCE') {
        return uni.navigateTo({ url: `/pages/teacher/internship-review/index?${this.studentParams({ internshipId: this.s.context && this.s.context.internshipId })}` })
      }
      if (section.actionKey === 'GRADUATION_GUIDANCE') return uni.navigateTo({ url: '/pages/teacher/graduation-guide/index' })
      if (section.actionKey === 'EMPLOYMENT_FOLLOWUP') {
        const action = (this.s.actions || []).find((item) => item.key === 'EMPLOYMENT_FOLLOWUP')
        return this.runAction(action)
      }
      if (section.actionKey === 'STUDENT_AFFAIRS') return uni.navigateTo({ url: '/pages/teacher/affairs/index' })
    },
    openMental() {
      uni.navigateTo({ url: `/pages/teacher/affairs/mental/index?${this.studentParams({ mode: 'create' })}` })
    }
  }
}
</script>

<style scoped>
.sd__head { display: flex; align-items: center; gap: var(--space-3); }
.sd__avatar { width: 50px; height: 50px; border-radius: var(--radius-full); background: var(--teacher-50); color: var(--teacher-700); display: flex; align-items: center; justify-content: center; font-size: var(--font-size-xl); flex-shrink: 0; }
.sd__sub { display: block; font-size: var(--font-size-sm); color: var(--text-secondary); margin-top: 3px; }
.sd__actions { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--space-2); }
.sd__action { min-width: 0; display: flex; flex-direction: column; align-items: center; gap: 6px; padding: var(--space-2) 2px; }
.sd__action.is-disabled { opacity: .4; }
.sd__action-icon { width: 34px; height: 34px; border-radius: var(--radius-lg); display: flex; align-items: center; justify-content: center; background: var(--teacher-50); color: var(--teacher-700); font-weight: var(--font-weight-semibold); }
.sd__action-label { font-size: var(--font-size-xs); color: var(--text-secondary); text-align: center; }
.sd__section { padding-top: var(--space-3); padding-bottom: var(--space-3); }
.sd__section-summary { display: block; margin-top: 4px; font-size: var(--font-size-sm); color: var(--text-tertiary); line-height: 1.45; }
.sd__abnormal { font-size: 10px; color: var(--danger-700); background: var(--danger-50); border-radius: var(--radius-full); padding: 2px 7px; }
.sd__link { flex-shrink: 0; margin-left: var(--space-2); font-size: var(--font-size-sm); color: var(--teacher-700); }
.sd__sensitive { display: flex; align-items: center; gap: var(--space-2); }
.sd__divider { height: 1px; background: var(--border-light); }
.sd__timeline { display: flex; gap: var(--space-3); padding: 8px 0; }
.sd__dot { width: 9px; height: 9px; margin-top: 5px; border-radius: var(--radius-full); background: var(--teacher-500); flex-shrink: 0; }
.sd__timeline-text { font-size: var(--font-size-base); color: var(--text-primary); }
.sd__timeline-time { display: block; margin-top: 2px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.sd__freshness { display: block; padding: 2px 0 var(--space-2); text-align: center; font-size: 10px; color: var(--text-tertiary); }
@media (max-width: 360px) { .sd__actions { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
