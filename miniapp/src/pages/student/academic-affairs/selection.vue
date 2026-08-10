<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="网上选课" back />

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="loaded">
        <view class="sl__hero">
          <view class="sl__hero-main">
            <text class="sl__eyebrow">教务学业 · 网上选课</text>
            <text class="sl__hero-title">{{ groups.length ? '当前有开放选课批次' : '当前暂无开放选课批次' }}</text>
            <text class="sl__hero-desc">余量用于快速判断，提交时仍会重新校验容量、冲突、选课窗口和培养方案。</text>
            <view class="sl__trust">
              <text>实时余量</text><text>规则校验</text><text>办理后回读</text>
            </view>
          </view>
          <view class="sl__hero-count">
            <text>可查看课程</text><text class="sl__hero-number">{{ courseCount }}</text><text>门</text>
          </view>
        </view>

        <view class="sl__metrics">
          <view class="sl__metric"><text>开放批次</text><text class="sl__metric-value">{{ groups.length }}</text></view>
          <view class="sl__metric"><text>本人已选</text><text class="sl__metric-value">{{ mySelected.length }}</text></view>
          <view class="sl__metric"><text>已选学分</text><text class="sl__metric-value">{{ selectedCredits }}</text></view>
        </view>

        <MobileAcademicDecisionCard
          v-if="decisionError"
          class="sl__decision"
          :trace="decisionError.decisionTrace"
          :message="decisionError.message"
          audience="student"
        />

        <view class="sl__tabs">
          <view class="sl__tab" :class="{ 'is-active': tab === 'courses' }" @click="tab = 'courses'">
            <text>可选课程</text><text class="sl__tab-count">{{ courseCount }}</text>
          </view>
          <view class="sl__tab" :class="{ 'is-active': tab === 'mine' }" @click="tab = 'mine'">
            <text>我的选课</text><text class="sl__tab-count">{{ mySelected.length }}</text>
          </view>
        </view>

        <template v-if="tab === 'courses'">
          <MobileGlobalState v-if="!groups.length" state="empty" title="暂无开放中的选课批次" description="教务处开放新的选课窗口后会显示在这里。" />
          <view v-for="g in groups" :key="g.batch.batchId" class="sl__group">
            <view class="sl__group-head">
              <view>
                <text class="sl__group-kicker">开放批次</text>
                <text class="sl__group-title">{{ g.batch.batchName || '选课批次' }}</text>
              </view>
              <view class="sl__group-stats"><text>{{ g.courses.length }}门</text><text>{{ batchOpenCount(g) }}门可选</text></view>
            </view>

            <view v-if="g.courses.length" class="sl__course-list">
              <view v-for="c in g.courses" :key="c.selectionCourseId" class="sl__course" :class="{ 'is-selected': isSelected(c) }">
                <view class="sl__course-main">
                  <view class="sl__course-title-line">
                    <text class="sl__course-title">{{ c.courseName || '课程名称待补充' }}</text>
                    <text v-if="isSelected(c)" class="sl__selected-chip">已选</text>
                  </view>
                  <text class="sl__course-meta">{{ c.teacherName || '教师待定' }} · {{ c.credit ?? '—' }}学分</text>
                  <view class="sl__remain">
                    <text>余量 {{ remainText(c) }}</text>
                    <view class="sl__remain-bar"><view :style="{ width: availabilityPct(c) + '%' }" /></view>
                  </view>
                </view>
                <button
                  class="btn sl__btn"
                  :class="isSelected(c) ? 'btn-ghost' : 'btn-primary'"
                  :disabled="acting === c.selectionCourseId || (!isSelected(c) && !canEnroll(c))"
                  @click="isSelected(c) ? drop(c) : enroll(c)"
                >
                  {{ acting === c.selectionCourseId ? '处理中…' : isSelected(c) ? '退课' : canEnroll(c) ? '选课' : '不可选' }}
                </button>
              </view>
            </view>
            <view v-else class="sl__group-empty"><text>本批次暂无可选课程</text></view>
          </view>
        </template>

        <template v-else>
          <MobileGlobalState v-if="!mySelected.length" state="empty" title="暂无有效选课记录" description="在「可选课程」中选课后会显示在这里。" />
          <view v-else class="sl__mine-list">
            <view v-for="r in mySelected" :key="r.recordId || r.selectionCourseId" class="sl__mine-card">
              <view class="sl__mine-icon"><text>课</text></view>
              <view class="flex-1">
                <text class="sl__course-title">{{ r.courseName || '课程名称待补充' }}</text>
                <text class="sl__course-meta">{{ r.credit ?? '—' }}学分 · {{ (r.enrolledAt || '').slice(0, 10) || '时间待确认' }}</text>
              </view>
              <MobileStatusTag :status="r.status" />
            </view>
          </view>
        </template>

        <view class="sl__rule-note">
          <view class="sl__rule-icon"><text>i</text></view>
          <view class="flex-1">
            <text class="sl__rule-title">办理以服务器最终校验为准</text>
            <text class="sl__rule-text">如果选课未通过，页面会显示真实规则原因和学校业务代码给出的下一步，不在前端自行编造补救方式。</text>
          </view>
        </view>
      </view>
    </MobileGlobalState>
  </view>
</template>

<script>
import MobileAcademicDecisionCard from '@/components/MobileAcademicDecisionCard.vue'
import { studentApi } from '@/services/studentApi'
import { normalizeError } from '@/services/request'
import { toast } from '@/utils/nav'

export default {
  components: { MobileAcademicDecisionCard },
  data() {
    return {
      groups: [], selections: [], state: 'loading', loaded: false,
      tab: 'courses', acting: null, decisionError: null
    }
  },
  computed: {
    mySelected() { return this.selections.filter((r) => r.status === 'SELECTED') },
    courseCount() { return this.groups.reduce((sum, group) => sum + ((group && group.courses && group.courses.length) || 0), 0) },
    selectedCredits() { return this.mySelected.reduce((sum, item) => sum + Number(item.credit || 0), 0) }
  },
  onLoad() { this.load() },
  methods: {
    isSelected(c) {
      return this.selections.some((r) => r.selectionCourseId === c.selectionCourseId && r.status === 'SELECTED')
    },
    remain(c) {
      const explicit = Number(c && c.remain)
      if (Number.isFinite(explicit)) return explicit
      const capacity = Number(c && c.capacity)
      const selected = Number((c && (c.selectedCount || c.enrolledCount)) || 0)
      return Number.isFinite(capacity) ? Math.max(0, capacity - selected) : null
    },
    remainText(c) {
      const value = this.remain(c)
      const capacity = Number(c && c.capacity)
      if (value == null) return '待确认'
      return Number.isFinite(capacity) ? `${value}/${capacity}` : String(value)
    },
    availabilityPct(c) {
      const value = this.remain(c)
      const capacity = Number(c && c.capacity)
      if (value == null || !Number.isFinite(capacity) || capacity <= 0) return 0
      return Math.max(0, Math.min(100, Math.round(value / capacity * 100)))
    },
    canEnroll(c) {
      if (this.isSelected(c)) return false
      const value = this.remain(c)
      if (value != null && value <= 0) return false
      const status = String((c && (c.status || c.courseStatus)) || 'OPEN').toUpperCase()
      return !['CLOSED', 'DISABLED', 'FULL'].includes(status)
    },
    batchOpenCount(group) {
      return ((group && group.courses) || []).filter((course) => this.canEnroll(course)).length
    },
    load() {
      this.state = 'loading'
      this.decisionError = null
      Promise.all([studentApi.getSelectionCourses(), studentApi.getMySelections()]).then(([groups, selections]) => {
        this.groups = groups || []
        this.selections = selections || []
        this.loaded = true
        this.state = 'ready'
      }).catch(() => { this.state = 'error' })
    },
    enroll(c) {
      if (this.acting) return
      this.acting = c.selectionCourseId
      this.decisionError = null
      studentApi.enrollSelection(c.selectionCourseId).then(() => {
        uni.showToast({ title: '选课成功', icon: 'success' })
        this.load()
      }).catch((e) => {
        if (e && e.decisionTrace) this.decisionError = e
        toast(e && e.biz ? normalizeError(e).text : '选课失败，请稍后重试')
      }).finally(() => { this.acting = null })
    },
    drop(c) {
      if (this.acting) return
      this.acting = c.selectionCourseId
      this.decisionError = null
      studentApi.dropSelection(c.selectionCourseId).then(() => {
        uni.showToast({ title: '已退课', icon: 'success' })
        this.load()
      }).catch((e) => toast(e && e.biz ? normalizeError(e).text : '退课失败，请稍后重试'))
        .finally(() => { this.acting = null })
    }
  }
}
</script>

<style scoped>
.sl__hero { display: flex; align-items: stretch; justify-content: space-between; gap: var(--space-3); padding: var(--space-4); border: 1px solid rgba(59,130,246,.13); border-radius: 18px; background: linear-gradient(135deg, rgba(255,255,255,.98), rgba(239,246,255,.92)); box-shadow: var(--shadow-card); }
.sl__hero-main { flex: 1; min-width: 0; }
.sl__eyebrow { display: block; font-size: 10px; font-weight: 700; letter-spacing: 1px; color: var(--brand-primary); }
.sl__hero-title { display: block; margin-top: 5px; font-size: 18px; font-weight: 700; line-height: 1.4; color: var(--text-primary); }
.sl__hero-desc { display: block; margin-top: 5px; font-size: var(--font-size-xs); line-height: 1.65; color: var(--text-secondary); }
.sl__trust { display: flex; flex-wrap: wrap; gap: 6px; margin-top: var(--space-3); }
.sl__trust text { font-size: 10px; line-height: 22px; padding: 0 8px; border-radius: var(--radius-full); background: rgba(255,255,255,.84); color: var(--text-secondary); }
.sl__hero-count { flex-shrink: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; width: 78px; border-left: 1px solid rgba(59,130,246,.10); color: var(--text-tertiary); font-size: 10px; }
.sl__hero-number { margin: 4px 0 2px; font-size: 28px; line-height: 1; font-weight: 800; color: var(--brand-primary); }
.sl__metrics { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-2); margin-top: var(--space-3); }
.sl__metric { padding: var(--space-3); border: 1px solid var(--border-light); border-radius: 14px; background: var(--bg-card); box-shadow: var(--shadow-card); }
.sl__metric > text:first-child { display: block; font-size: 10px; color: var(--text-tertiary); }
.sl__metric-value { display: block; margin-top: 4px; font-size: 20px; font-weight: 800; color: var(--text-primary); }
.sl__decision { margin-top: var(--space-3); }
.sl__tabs { display: flex; gap: 5px; margin-top: var(--space-4); padding: 5px; border: 1px solid var(--border-light); border-radius: 13px; background: var(--bg-card); }
.sl__tab { flex: 1; display: flex; align-items: center; justify-content: center; gap: 6px; min-height: 38px; border-radius: 9px; font-size: var(--font-size-sm); color: var(--text-secondary); }
.sl__tab.is-active { color: var(--brand-primary); font-weight: var(--font-weight-semibold); background: rgba(59,130,246,.08); }
.sl__tab-count { min-width: 20px; line-height: 18px; padding: 0 5px; border-radius: var(--radius-full); text-align: center; background: rgba(15,23,42,.05); color: var(--text-tertiary); font-size: 10px; }
.sl__tab.is-active .sl__tab-count { background: rgba(255,255,255,.9); color: var(--brand-primary); }
.sl__group { margin-top: var(--space-3); overflow: hidden; border: 1px solid var(--border-light); border-radius: 16px; background: var(--bg-card); box-shadow: var(--shadow-card); }
.sl__group + .sl__group { margin-top: var(--space-3); }
.sl__group-head { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); padding: var(--space-3) var(--space-4); border-bottom: 1px solid var(--border-light); }
.sl__group-kicker { display: block; font-size: 9px; font-weight: 700; letter-spacing: 1px; color: var(--brand-primary); }
.sl__group-title { display: block; margin-top: 3px; font-size: var(--font-size-base); font-weight: 700; color: var(--text-primary); }
.sl__group-stats { display: flex; flex-direction: column; align-items: flex-end; gap: 2px; font-size: 10px; color: var(--text-tertiary); }
.sl__course-list { padding: 0 var(--space-4); }
.sl__course { display: flex; align-items: center; gap: var(--space-3); padding: var(--space-4) 0; border-bottom: 1px solid var(--border-light); }
.sl__course:last-child { border-bottom: 0; }
.sl__course.is-selected { background: linear-gradient(90deg, rgba(22,163,74,.035), transparent); }
.sl__course-main { flex: 1; min-width: 0; }
.sl__course-title-line { display: flex; align-items: center; gap: 6px; }
.sl__course-title { font-size: var(--font-size-base); font-weight: 600; line-height: 1.45; color: var(--text-primary); }
.sl__selected-chip { flex-shrink: 0; font-size: 9px; line-height: 18px; padding: 0 6px; border-radius: var(--radius-full); color: #15803d; background: rgba(22,163,74,.10); }
.sl__course-meta { display: block; margin-top: 3px; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.sl__remain { display: flex; align-items: center; gap: var(--space-2); margin-top: 7px; }
.sl__remain > text { flex-shrink: 0; font-size: 10px; color: var(--text-secondary); }
.sl__remain-bar { width: 62px; height: 5px; overflow: hidden; border-radius: var(--radius-full); background: rgba(15,23,42,.06); }
.sl__remain-bar view { height: 100%; border-radius: inherit; background: var(--brand-primary); }
.sl__btn { flex-shrink: 0; min-height: 34px; padding: 0 var(--space-3); font-size: var(--font-size-sm); margin-left: var(--space-1); }
.sl__group-empty { padding: var(--space-5); text-align: center; font-size: var(--font-size-xs); color: var(--text-tertiary); }
.sl__mine-list { margin-top: var(--space-3); }
.sl__mine-card { display: flex; align-items: center; gap: var(--space-3); margin-bottom: var(--space-2); padding: var(--space-3) var(--space-4); border: 1px solid var(--border-light); border-radius: 14px; background: var(--bg-card); box-shadow: var(--shadow-card); }
.sl__mine-icon { flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; border-radius: 11px; background: rgba(59,130,246,.08); color: var(--brand-primary); font-size: 11px; font-weight: 700; }
.sl__rule-note { display: flex; align-items: flex-start; gap: var(--space-3); margin-top: var(--space-4); padding: var(--space-3) var(--space-4); border: 1px solid rgba(59,130,246,.10); border-radius: 14px; background: rgba(255,255,255,.75); }
.sl__rule-icon { flex-shrink: 0; display: flex; align-items: center; justify-content: center; width: 30px; height: 30px; border-radius: 9px; background: rgba(59,130,246,.08); color: var(--brand-primary); font-family: serif; font-weight: 700; }
.sl__rule-title { display: block; font-size: var(--font-size-sm); font-weight: 600; color: var(--text-primary); }
.sl__rule-text { display: block; margin-top: 3px; font-size: 10px; line-height: 1.65; color: var(--text-tertiary); }
</style>
