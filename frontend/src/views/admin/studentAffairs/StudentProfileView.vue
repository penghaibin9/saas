<template>
  <ModulePageShell
    title="学生画像 360"
    subtitle="各域沉淀汇总 · 成长时间线（进 360 事件）"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="学生画像查阅"
  >
    <div class="pf-picker">
      <span class="pf-picker__label">选择学生</span>
      <div class="pf-picker__control">
        <AppStudentPicker v-model="studentId" :remote-search="searchStudents" placeholder="按姓名 / 学号搜索学生查看 360 画像" @change="onPick" />
      </div>
    </div>

    <EmptyState v-if="!studentId" title="请选择一名学生" description="查看该生在学工各业务域的沉淀与成长时间线" />
    <LoadingState v-else-if="loading" text="正在加载学生画像…" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <template v-else-if="profile">
      <!-- 基础信息 -->
      <section class="pf-base">
        <div class="pf-base__main">
          <span class="pf-base__name">{{ profile.baseInfo.realName }}</span>
          <span class="pf-base__no">{{ profile.baseInfo.studentNo }}</span>
        </div>
        <div class="pf-base__meta">
          <span>阶段：{{ stageLabel(profile.baseInfo.currentStage) }}</span>
          <span>学籍：{{ profile.baseInfo.studentStatus || '—' }}</span>
          <span v-if="profile.psyFlag === '需关注'" class="pf-psy">🔒 心理需关注</span>
        </div>
      </section>

      <!-- 各域摘要卡 -->
      <section class="pf-cards">
        <div class="pf-card">
          <span class="pf-card__label">请假记录</span>
          <span class="pf-card__value">{{ profile.leaveSummary.total }}<i>次</i></span>
        </div>
        <div class="pf-card">
          <span class="pf-card__label">困难认定</span>
          <span class="pf-card__value pf-card__value--sm">{{ profile.aidSummary.inLibrary ? levelLabel(profile.aidSummary.difficultLevel) : '未认定' }}</span>
        </div>
        <div class="pf-card">
          <span class="pf-card__label">获得资助</span>
          <span class="pf-card__value">{{ profile.fundingSummary.grantedCount }}<i>项</i></span>
        </div>
        <div class="pf-card">
          <span class="pf-card__label">在效处分</span>
          <span v-if="profile.disciplineSummary.restricted" class="pf-card__value pf-card__value--sm pf-restricted">明细受限</span>
          <span v-else class="pf-card__value" :class="{ 'pf-alert': profile.disciplineSummary.activeCount > 0 }">{{ profile.disciplineSummary.activeCount }}<i>项</i></span>
        </div>
        <div class="pf-card">
          <span class="pf-card__label">在办风险</span>
          <span class="pf-card__value" :class="{ 'pf-alert': profile.riskSummary.openCount > 0 }">
            {{ profile.riskSummary.openCount }}<i>条</i>
          </span>
          <RiskTag v-if="profile.riskSummary.topLevel && profile.riskSummary.topLevel !== 'NONE'" :level="profile.riskSummary.topLevel" />
        </div>
        <div class="pf-card">
          <span class="pf-card__label">谈心谈话</span>
          <span class="pf-card__value">{{ profile.talkSummary.total }}<i>次</i></span>
          <span v-if="profile.talkSummary.lastTalkAt" class="pf-card__sub">最近 {{ fmt(profile.talkSummary.lastTalkAt) }}</span>
        </div>
        <div class="pf-card">
          <span class="pf-card__label">心理关注</span>
          <span class="pf-card__value pf-card__value--sm" :class="{ 'pf-alert': profile.psyFlag === '需关注' }">{{ profile.psyFlag }}</span>
        </div>
      </section>

      <!-- 成长时间线 -->
      <section class="pf-timeline">
        <div class="pf-timeline__head">
          <h3 class="pf-timeline__title">成长时间线（360）</h3>
          <div class="pf-timeline__filters">
            <button
              v-for="f in moduleFilters"
              :key="f.key"
              type="button"
              class="pf-chip"
              :class="{ 'is-on': moduleFilter === f.key }"
              @click="setModuleFilter(f.key)"
            >{{ f.label }}</button>
          </div>
        </div>
        <LoadingState v-if="timelineLoading" text="正在加载时间线…" />
        <EmptyState v-else-if="!timeline.length" title="暂无进 360 事件" description="该生在各业务域尚无已闭环（进 360）的事件" />
        <ul v-else class="pf-events">
          <li v-for="e in timeline" :key="e.eventId" class="pf-event">
            <span class="pf-event__dot" :class="'pf-event__dot--' + e.module" />
            <div class="pf-event__body">
              <div class="pf-event__title">{{ e.title }}<span class="pf-event__mod">{{ moduleLabel(e.module) }}</span></div>
              <div class="pf-event__detail">{{ e.detail }}</div>
              <div class="pf-event__time">{{ fmt(e.occurredAt) }}</div>
            </div>
          </li>
        </ul>
      </section>
    </template>
  </ModulePageShell>
</template>

<script>
/**
 * 学生画像 360（/admin/student-affairs/profile）—— 13A P6 集中兑现「进入 360」。
 * 真实对接 /api/v1/student-affairs/students/{id}/profile + /timeline：各域沉淀汇总 + 成长时间线。
 * 处分明细/心理来源按角色权限（无权限出计数或「需关注」标记，不出明细）。
 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppRiskTag, AppStudentPicker } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'

const LEVEL = { SPECIAL: '特别困难', DIFFICULT: '困难', GENERAL: '一般困难' }
const STAGE = { ORIENTATION: '迎新', ON_CAMPUS: '在校', INTERNSHIP: '实习', GRADUATION_DESIGN: '毕业设计', EMPLOYMENT: '就业' }
const MODULE_LABEL = { leave: '请假', aid: '困难认定', funding: '奖助', discipline: '处分', risk: '风险', talk: '谈话', system: '其他' }

export default {
  name: 'StudentProfileView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState, RiskTag: AppRiskTag, AppStudentPicker },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      studentId: '', loading: false, error: '', profile: null,
      timeline: [], timelineLoading: false, moduleFilter: ''
    }
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    dataScopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    moduleFilters() {
      return [
        { key: '', label: '全部' },
        { key: 'leave', label: '请假' },
        { key: 'aid', label: '困难认定' },
        { key: 'discipline', label: '处分' },
        { key: 'risk', label: '风险' },
        { key: 'talk', label: '谈话' }
      ]
    }
  },
  methods: {
    fmt(t) {
      return t ? String(t).replace('T', ' ').slice(0, 16) : ''
    },
    levelLabel(l) {
      return LEVEL[l] || l || '—'
    },
    stageLabel(s) {
      return STAGE[s] || s || '—'
    },
    moduleLabel(m) {
      return MODULE_LABEL[m] || m
    },
    searchStudents(keyword) {
      return studentAffairsApi.searchStudents(keyword)
    },
    onPick() {
      if (this.studentId) this.load()
    },
    async load() {
      if (!this.studentId) return
      this.loading = true
      this.error = ''
      this.moduleFilter = ''
      const res = await studentAffairsApi.getStudentProfile(this.studentId)
      this.loading = false
      if (res.code === 0 && res.data) {
        this.profile = res.data
        this.loadTimeline()
      } else {
        this.profile = null
        this.error = res.message || '画像加载失败'
      }
    },
    setModuleFilter(key) {
      this.moduleFilter = key
      this.loadTimeline()
    },
    async loadTimeline() {
      if (!this.studentId) return
      this.timelineLoading = true
      const res = await studentAffairsApi.getStudentTimeline(this.studentId, { eventType: this.moduleFilter, page: 1, pageSize: 100 })
      this.timelineLoading = false
      this.timeline = res.code === 0 && res.data ? (res.data.items || []) : []
    }
  }
}
</script>

<style scoped>
.pf-picker {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}
.pf-picker__label {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
.pf-picker__control {
  min-width: 320px;
}
.pf-base {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-lg);
}
.pf-base__main {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}
.pf-base__name {
  font-size: var(--font-size-xl);
  font-weight: 700;
  color: var(--text-primary);
}
.pf-base__no {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pf-base__meta {
  display: flex;
  gap: var(--space-4);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  flex-wrap: wrap;
}
.pf-psy {
  color: var(--danger-600, #dc2626);
}
.pf-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-5);
}
.pf-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  padding: var(--space-4);
  background: var(--bg-card);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-lg);
}
.pf-card__label {
  font-size: var(--font-size-sm);
  color: var(--text-tertiary);
}
.pf-card__value {
  font-size: var(--font-size-2xl);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.1;
}
.pf-card__value--sm {
  font-size: var(--font-size-lg);
}
.pf-card__value i {
  font-size: var(--font-size-xs);
  font-weight: 500;
  color: var(--text-tertiary);
  font-style: normal;
  margin-left: 2px;
}
.pf-alert {
  color: var(--danger-600, #dc2626);
}
.pf-restricted {
  color: var(--text-tertiary);
  font-style: italic;
}
.pf-card__sub {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
}
.pf-timeline__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-3);
}
.pf-timeline__title {
  margin: 0;
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--text-primary);
}
.pf-timeline__filters {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}
.pf-chip {
  height: 26px;
  padding: 0 var(--space-2);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-secondary);
  font-size: var(--font-size-xs);
  cursor: pointer;
}
.pf-chip.is-on {
  border-color: var(--primary-400);
  color: var(--primary-700);
  background: var(--primary-50);
}
.pf-events {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.pf-event {
  display: flex;
  gap: var(--space-3);
}
.pf-event__dot {
  flex: none;
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: 50%;
  background: var(--primary-500);
}
.pf-event__dot--risk {
  background: var(--danger-500, #ef4444);
}
.pf-event__dot--discipline {
  background: var(--warning-500, #f59e0b);
}
.pf-event__dot--aid,
.pf-event__dot--funding {
  background: var(--success-500, #22c55e);
}
.pf-event__body {
  border-left: 1px solid var(--border-base);
  padding-left: var(--space-3);
  padding-bottom: var(--space-2);
}
.pf-event__title {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-primary);
}
.pf-event__mod {
  font-size: var(--font-size-xs);
  font-weight: 400;
  color: var(--text-tertiary);
  margin-left: var(--space-2);
  padding: 0 var(--space-1);
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
}
.pf-event__detail {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  margin-top: 2px;
}
.pf-event__time {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}
</style>
