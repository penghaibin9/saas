<template>
  <ModulePageShell
    title="教务工作台"
    subtitle="先判断本学期当前阶段能否继续，再进入责任页面处理"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <div class="adb-actions">
        <AppTermEntityPicker
          v-model="selectedTermId"
          class="adb-term-picker"
          placeholder="切换查看学期"
          @change="reloadReadiness"
        />
        <input
          v-model.trim="exportPurpose"
          class="adb-purpose"
          type="text"
          maxlength="80"
          placeholder="导出用途（不少于5字）"
        />
        <AppButton variant="ghost" :loading="exporting" @click="exportChecklist">导出准备清单</AppButton>
        <AppButton variant="primary" @click="showAllItems = !showAllItems">
          {{ showAllItems ? '收起全部问题' : '查看全部阻断与风险' }}
        </AppButton>
      </div>
    </template>

    <LoadingState v-if="loading" text="正在判断本学期运行状态…" />
    <ErrorState v-else-if="error" :description="error" @retry="reloadAll" />
    <template v-else>
      <section class="adb-readiness" :class="`is-${readinessStatus.toLowerCase()}`">
        <div class="adb-readiness-main">
          <div class="adb-eyebrow">
            <span>{{ readiness.term?.termLabel || '未设置当前学期' }}</span>
            <span v-if="readiness.currentWeek != null">第 {{ readiness.currentWeek }} 教学周</span>
          </div>
          <div class="adb-title-line">
            <span class="adb-state-dot" />
            <h2>{{ readiness.conclusion || '尚未形成学期运行结论' }}</h2>
          </div>
          <p>
            当前阶段：<strong>{{ readiness.stageLabel || '待判断' }}</strong>
            <template v-if="readiness.term?.startDate || readiness.term?.endDate">
              · {{ readiness.term?.startDate || '未设置开始日期' }} 至 {{ readiness.term?.endDate || '未设置结束日期' }}
            </template>
          </p>
          <div class="adb-hero-actions">
            <AppButton
              v-if="topItems.length"
              variant="primary"
              @click="goTarget(topItems[0].route)"
            >
              处理首要问题
            </AppButton>
            <AppButton variant="ghost" @click="goTarget('/admin/academic-affairs/archive/precheck')">归档语义预检</AppButton>
          </div>
        </div>

        <div class="adb-readiness-metrics">
          <article>
            <b>{{ readiness.blockerCount || 0 }}</b>
            <span>阻断项</span>
          </article>
          <article>
            <b>{{ readiness.riskCount || 0 }}</b>
            <span>风险项</span>
          </article>
          <article>
            <b>{{ readiness.itemCount || 0 }}</b>
            <span>待关注规则</span>
          </article>
        </div>
      </section>

      <AppSectionCard
        id="adb-severe-items"
        title="当前最需要处理"
        subtitle="按阻断级别和业务截止时间排序，最多展示前三项"
      >
        <EmptyState
          v-if="!topItems.length"
          title="当前阶段无阻断或风险"
          description="可以继续推进本学期教务工作"
        />
        <div v-else class="adb-issue-list">
          <article v-for="item in topItems" :key="item.key" class="adb-issue" :class="severityClass(item)">
            <div class="adb-issue-rank">{{ item.severity === 'BLOCKER' ? '阻断' : '风险' }}</div>
            <div class="adb-issue-body">
              <div class="adb-issue-head">
                <div>
                  <h3>{{ item.title }}</h3>
                  <code>{{ item.ruleCode }}</code>
                </div>
                <strong>{{ item.count || 0 }} 项</strong>
              </div>
              <p>{{ item.summary }}</p>
              <div class="adb-responsibility">
                <span>责任角色：{{ item.ownerRole || '待明确' }}</span>
                <span>截止时间：{{ item.deadlineLabel || '未配置明确截止时间' }}</span>
              </div>
              <div class="adb-issue-actions">
                <AppButton size="small" variant="ghost" @click="goTarget(item.assignRoute)">分派责任人</AppButton>
                <AppButton size="small" variant="primary" @click="goTarget(item.route)">去处理</AppButton>
              </div>
            </div>
          </article>
        </div>
      </AppSectionCard>

      <AppSectionCard
        v-if="showAllItems"
        id="adb-all-readiness-items"
        title="全部阻断与风险"
        :subtitle="`共 ${allItems.length} 条规则结果，均回链现有业务页面`"
      >
        <EmptyState v-if="!allItems.length" title="没有待处理项" description="当前阶段运行正常" />
        <div v-else class="adb-all-grid">
          <article v-for="item in allItems" :key="item.key" class="adb-all-card" :class="severityClass(item)">
            <header>
              <span>{{ item.severity === 'BLOCKER' ? '阻断' : '风险' }}</span>
              <code>{{ item.ruleCode }}</code>
            </header>
            <h3>{{ item.title }}</h3>
            <p>{{ item.summary }}</p>
            <dl>
              <div><dt>数量</dt><dd>{{ item.count || 0 }}</dd></div>
              <div><dt>责任</dt><dd>{{ item.ownerRole || '待明确' }}</dd></div>
              <div><dt>截止</dt><dd>{{ item.deadlineLabel || '未配置' }}</dd></div>
            </dl>
            <footer>
              <button class="mp-link" @click="goTarget(item.assignRoute)">分派责任人</button>
              <button class="mp-link" @click="goTarget(item.route)">进入责任页面 →</button>
            </footer>
          </article>
        </div>
      </AppSectionCard>

      <div class="adb-two-columns">
        <AppSectionCard id="adb-todos" title="我的教务待办" subtitle="点击直达处理页面">
          <ErrorState v-if="remindersError" :description="remindersError" @retry="loadReminders" />
          <LoadingState v-else-if="remindersLoading" />
          <EmptyState v-else-if="!activeTodos.length" title="暂无待办" description="当前角色没有需要立即处理的教务事项" />
          <div v-else class="adb-todo-list">
            <button v-for="todo in activeTodos" :key="todo.key" class="adb-todo" @click="goTarget(todo.drillRoute)">
              <span>{{ todo.label }}</span>
              <b>{{ todo.count }}</b>
            </button>
          </div>
        </AppSectionCard>

        <AppSectionCard id="adb-today-teaching" title="今日教学运行" :subtitle="todayTeachingSubtitle">
          <ErrorState v-if="remindersError" :description="remindersError" @retry="loadReminders" />
          <LoadingState v-else-if="remindersLoading" />
          <div v-else class="adb-today-grid">
            <article><b>{{ todayTeaching.totalToday || 0 }}</b><span>今日课次</span></article>
            <article><b>{{ todayTeaching.inProgress || 0 }}</b><span>正在进行</span></article>
            <article><b>{{ todayTeaching.adjustedCount || 0 }}</b><span>调停课</span></article>
            <article><b>{{ todayTeaching.examCount || 0 }}</b><span>今日考试</span></article>
            <p v-if="todayTeaching.note">{{ todayTeaching.note }}</p>
            <button class="mp-link" @click="goTarget(todayTeaching.drillRoute || 'aa-schedule')">查看今日课表 →</button>
          </div>
        </AppSectionCard>
      </div>

      <AppSectionCard id="adb-expiring" title="即将到期" subtitle="未来14天需要完成的阶段责任和考试安排">
        <EmptyState v-if="!expiringSoon.length" title="未来14天暂无明确到期事项" description="未配置截止时间的事项仍会保留在上方阻断与风险中" />
        <div v-else class="adb-expiring-list">
          <button v-for="item in expiringSoon" :key="item.key" @click="goTarget(item.route)">
            <div>
              <strong>{{ item.title }}</strong>
              <span>{{ item.ownerRole || item.courseName || '' }}</span>
            </div>
            <time>{{ item.deadline || item.examDate }}</time>
          </button>
        </div>
      </AppSectionCard>

      <details class="adb-details" open>
        <summary>成绩、考务和预警运行明细</summary>
        <div class="adb-detail-grid">
          <AppSectionCard title="成绩提交进度" :subtitle="`已提交/审核/发布 ${gradeSubmittedCount} 个任务`">
            <div class="adb-mini-metrics">
              <span>总任务 <b>{{ gradeProgress.totalTasks || 0 }}</b></span>
              <span>提交率 <b>{{ gradeProgress.submittedRate || 0 }}%</b></span>
              <span>滞后 <b>{{ (gradeProgress.pendingTasks || []).length }}</b></span>
            </div>
            <button class="mp-link" @click="goTarget(gradeProgress.drillRoute || 'aa-grade-overview')">进入成绩工作台 →</button>
          </AppSectionCard>

          <AppSectionCard title="近期考试" :subtitle="`未来 ${examReminders.windowDays || 14} 天 ${examReminders.count || 0} 场`">
            <ul class="adb-compact-list">
              <li v-for="row in (examReminders.items || []).slice(0, 5)" :key="row.examCourseId">
                <span>{{ row.examDate }} {{ row.startTime }}</span>
                <strong>{{ row.courseName }}</strong>
              </li>
            </ul>
            <button class="mp-link" @click="goTarget(examReminders.drillRoute || 'aa-exam')">进入考务管理 →</button>
          </AppSectionCard>

          <AppSectionCard title="学业预警" :subtitle="`待处置 ${warningReminders.count || 0} 条`">
            <ul class="adb-compact-list">
              <li v-for="row in (warningReminders.items || []).slice(0, 5)" :key="row.warningId">
                <span>{{ row.level }}</span>
                <strong>{{ row.studentName }} · {{ row.reason }}</strong>
              </li>
            </ul>
            <button class="mp-link" @click="goTarget(warningReminders.drillRoute || 'aa-warnings')">进入预警工作台 →</button>
          </AppSectionCard>
        </div>
      </details>

      <details class="adb-details">
        <summary>近14天教务业务趋势</summary>
        <AppSectionCard title="教务数据趋势" subtitle="只展示真实业务发生量，不做预测或插值">
          <EmptyState v-if="!trendHasData" title="近期暂无相关业务发生" :description="dataTrends.note || ''" />
          <AppG2Chart v-else :spec="trendChartSpec" :height="280" />
        </AppSectionCard>
      </details>
    </template>
  </ModulePageShell>
</template>

<script>
/** AA-DASHBOARD-01：当前学期阶段 readiness + 责任入口。 */
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppSectionCard, AppTermEntityPicker, AppG2Chart } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { academicAffairsDashboardReadinessApi as readinessApi } from '@/modules/academicAffairs/api/academic-affairs-dashboard-readiness.api'

export default {
  name: 'AaDashboardView',
  components: {
    ModulePageShell, LoadingState, ErrorState, EmptyState,
    AppButton, AppSectionCard, AppTermEntityPicker, AppG2Chart
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      remindersLoading: true,
      remindersError: '',
      selectedTermId: '',
      exportPurpose: '',
      exporting: false,
      showAllItems: false,
      readiness: {},
      todos: [],
      todayTeaching: {},
      gradeProgress: {},
      examReminders: {},
      warningReminders: {},
      dataTrends: {}
    }
  },
  computed: {
    readinessStatus() { return this.readiness.status || 'BLOCKED' },
    topItems() { return Array.isArray(this.readiness.topItems) ? this.readiness.topItems : [] },
    allItems() { return Array.isArray(this.readiness.items) ? this.readiness.items : [] },
    activeTodos() { return (this.todos || []).filter((row) => Number(row.count || 0) > 0) },
    todayTeachingSubtitle() {
      const row = this.todayTeaching || {}
      return [row.dateLabel, row.termLabel, row.weekNo ? `第 ${row.weekNo} 教学周` : ''].filter(Boolean).join(' · ')
    },
    gradeSubmittedCount() {
      const counts = this.gradeProgress.counts || {}
      return Number(counts.SUBMITTED || 0) + Number(counts.ACADEMIC_REVIEW || 0) + Number(counts.PUBLISHED || 0)
    },
    expiringSoon() {
      const today = new Date()
      const end = new Date(today)
      end.setDate(end.getDate() + 14)
      const readinessItems = this.allItems
        .filter((row) => row.deadline)
        .map((row) => ({ ...row, key: `rule-${row.key}` }))
        .filter((row) => {
          const date = new Date(`${row.deadline}T00:00:00`)
          return !Number.isNaN(date.getTime()) && date >= today && date <= end
        })
      const exams = (this.examReminders.items || []).map((row) => ({
        ...row,
        key: `exam-${row.examCourseId}`,
        title: `${row.courseName} · ${row.className || '未分班'}`,
        ownerRole: row.teacherName ? `任课教师：${row.teacherName}` : '考务管理员',
        route: this.examReminders.drillRoute || 'aa-exam'
      })).filter((row) => {
        const date = new Date(`${row.examDate}T00:00:00`)
        return !Number.isNaN(date.getTime()) && date >= today && date <= end
      })
      return [...readinessItems, ...exams].sort((a, b) => String(a.deadline || a.examDate).localeCompare(String(b.deadline || b.examDate))).slice(0, 12)
    },
    trendRows() {
      return (this.dataTrends.series || []).flatMap((series) => (series.points || []).map((point) => ({
        date: point.date,
        series: series.label,
        value: point.value
      })))
    },
    trendHasData() {
      return (this.dataTrends.series || []).some((series) => (series.points || []).some((point) => Number(point.value || 0) > 0))
    },
    trendChartSpec() {
      return {
        type: 'line',
        data: this.trendRows,
        encode: { x: 'date', y: 'value', color: 'series' },
        shape: 'smooth',
        style: { lineWidth: 2.5, point: true },
        legend: { color: { position: 'bottom' } }
      }
    }
  },
  created() { this.reloadAll() },
  methods: {
    severityClass(item) { return item.severity === 'BLOCKER' ? 'is-blocker' : 'is-risk' },
    notify(message, type = 'info') {
      const channel = this.$message && this.$message[type]
      if (typeof channel === 'function') channel(message)
      else if (this.$message && typeof this.$message === 'function') this.$message(message)
      else window.alert(message)
    },
    async reloadAll() {
      this.loading = true
      this.error = ''
      try {
        await Promise.all([this.loadReadiness(), this.loadReminders()])
      } catch (error) {
        this.error = error?.message || '教务工作台加载失败'
      } finally {
        this.loading = false
      }
    },
    async reloadReadiness() {
      this.loading = true
      this.error = ''
      try {
        await this.loadReadiness()
      } catch (error) {
        this.error = error?.message || '学期运行状态读取失败'
      } finally {
        this.loading = false
      }
    },
    async loadReadiness() {
      const data = await readinessApi.get(this.selectedTermId || undefined)
      this.readiness = data || {}
      if (!this.selectedTermId && data?.term?.termId) this.selectedTermId = data.term.termId
    },
    async loadReminders() {
      this.remindersLoading = true
      this.remindersError = ''
      try {
        const response = await academicAffairsApi.getDashboardReminders()
        if (response.code !== 0) throw new Error(response.message || '教务提醒读取失败')
        const data = response.data || {}
        this.todos = data.todos || []
        this.todayTeaching = data.todayTeaching || {}
        this.gradeProgress = data.gradeProgress || {}
        this.examReminders = data.examReminders || {}
        this.warningReminders = data.warningReminders || {}
        this.dataTrends = data.dataTrends || {}
      } catch (error) {
        this.remindersError = error?.message || '教务提醒读取失败'
      } finally {
        this.remindersLoading = false
      }
    },
    goTarget(target) {
      if (!target) return
      if (String(target).startsWith('/')) this.$router.push(target).catch(() => {})
      else this.$router.push({ name: target }).catch(() => {})
    },
    async exportChecklist() {
      if (this.exportPurpose.length < 5) {
        this.notify('请填写不少于5个字的导出用途', 'warning')
        return
      }
      this.exporting = true
      try {
        const blob = await readinessApi.exportXlsx(this.selectedTermId || undefined, this.exportPurpose)
        const url = URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `${this.readiness.term?.termCode || '当前学期'}-教务运行准备清单.xlsx`
        link.click()
        URL.revokeObjectURL(url)
        this.notify('准备清单已导出', 'success')
      } catch (error) {
        this.notify(error?.message || '准备清单导出失败', 'error')
      } finally {
        this.exporting = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.adb-actions { display: flex; align-items: center; justify-content: flex-end; gap: 8px; flex-wrap: wrap; }
.adb-term-picker { width: 210px; }
.adb-purpose { width: 230px; height: 34px; padding: 0 10px; border: 1px solid var(--border-200, #d9dde5); border-radius: 8px; background: #fff; color: var(--text-900, #1f2329); }
.adb-readiness { display: flex; justify-content: space-between; gap: 28px; padding: 24px 26px; margin-bottom: 16px; border: 1px solid; border-radius: 16px; background: #fff; }
.adb-readiness.is-normal { border-color: #9bd5ad; background: #f4fbf6; }
.adb-readiness.is-risk { border-color: #f1c56f; background: #fffaf0; }
.adb-readiness.is-blocked { border-color: #efaaaa; background: #fff6f6; }
.adb-readiness-main { min-width: 0; }
.adb-eyebrow { display: flex; gap: 12px; color: #64748b; font-size: 12px; }
.adb-title-line { display: flex; align-items: flex-start; gap: 10px; margin: 8px 0; }
.adb-title-line h2 { margin: 0; color: #172033; font-size: 23px; line-height: 1.35; }
.adb-state-dot { width: 10px; height: 10px; margin-top: 10px; border-radius: 50%; background: #16a34a; flex: 0 0 auto; }
.is-risk .adb-state-dot { background: #d97706; }
.is-blocked .adb-state-dot { background: #dc2626; }
.adb-readiness-main p { margin: 0; color: #586174; font-size: 13px; }
.adb-hero-actions { display: flex; gap: 8px; margin-top: 16px; }
.adb-readiness-metrics { display: grid; grid-template-columns: repeat(3, minmax(88px, 1fr)); gap: 10px; align-self: center; }
.adb-readiness-metrics article { padding: 12px 14px; border: 1px solid rgba(148,163,184,.35); border-radius: 11px; background: rgba(255,255,255,.86); text-align: center; }
.adb-readiness-metrics b, .adb-readiness-metrics span { display: block; }
.adb-readiness-metrics b { color: #172033; font-size: 24px; }
.adb-readiness-metrics span { margin-top: 3px; color: #64748b; font-size: 11px; }
.adb-issue-list { display: flex; flex-direction: column; gap: 12px; }
.adb-issue { display: grid; grid-template-columns: 68px minmax(0,1fr); border: 1px solid #e2e8f0; border-radius: 12px; overflow: hidden; }
.adb-issue.is-blocker { border-color: #efb0b0; }
.adb-issue.is-risk { border-color: #f1cf86; }
.adb-issue-rank { display: flex; align-items: center; justify-content: center; background: #fff1f1; color: #b42318; font-weight: 700; font-size: 13px; }
.is-risk .adb-issue-rank { background: #fff8e8; color: #9a6700; }
.adb-issue-body { padding: 15px 17px; }
.adb-issue-head { display: flex; justify-content: space-between; gap: 12px; }
.adb-issue-head h3 { margin: 0; font-size: 15px; }
.adb-issue-head code { display: block; margin-top: 4px; color: #64748b; font-size: 10px; }
.adb-issue-head strong { white-space: nowrap; color: #b42318; }
.adb-issue-body p { margin: 9px 0; color: #475569; font-size: 13px; line-height: 1.6; }
.adb-responsibility { display: flex; gap: 20px; flex-wrap: wrap; color: #64748b; font-size: 12px; }
.adb-issue-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 11px; }
.adb-all-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.adb-all-card { padding: 14px; border: 1px solid #e2e8f0; border-radius: 11px; background: #fff; }
.adb-all-card.is-blocker { border-color: #efb0b0; }
.adb-all-card.is-risk { border-color: #f1cf86; }
.adb-all-card header, .adb-all-card footer { display: flex; justify-content: space-between; gap: 10px; }
.adb-all-card header span { font-weight: 700; font-size: 12px; }
.adb-all-card header code { color: #64748b; font-size: 9px; }
.adb-all-card h3 { margin: 10px 0 6px; font-size: 14px; }
.adb-all-card p { min-height: 42px; margin: 0; color: #64748b; font-size: 12px; line-height: 1.55; }
.adb-all-card dl { display: grid; gap: 5px; margin: 12px 0; }
.adb-all-card dl div { display: grid; grid-template-columns: 46px minmax(0,1fr); font-size: 11px; }
.adb-all-card dt { color: #94a3b8; }
.adb-all-card dd { margin: 0; color: #475569; }
.adb-two-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.adb-todo-list { display: grid; gap: 8px; }
.adb-todo { display: flex; justify-content: space-between; padding: 11px 12px; border: 1px solid #e5e7eb; border-radius: 9px; background: #fff; color: #334155; cursor: pointer; text-align: left; }
.adb-todo:hover { border-color: #8fb5ff; background: #f7faff; }
.adb-todo b { color: #245bd6; }
.adb-today-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 9px; }
.adb-today-grid article { padding: 11px; border-radius: 9px; background: #f8fafc; text-align: center; }
.adb-today-grid b, .adb-today-grid span { display: block; }
.adb-today-grid b { font-size: 20px; }
.adb-today-grid span { color: #64748b; font-size: 11px; }
.adb-today-grid p, .adb-today-grid button { grid-column: 1 / -1; }
.adb-expiring-list { display: grid; gap: 8px; }
.adb-expiring-list button { display: flex; align-items: center; justify-content: space-between; gap: 18px; width: 100%; padding: 11px 13px; border: 1px solid #e2e8f0; border-radius: 9px; background: #fff; cursor: pointer; text-align: left; }
.adb-expiring-list button:hover { border-color: #8fb5ff; }
.adb-expiring-list strong, .adb-expiring-list span { display: block; }
.adb-expiring-list strong { font-size: 13px; }
.adb-expiring-list span { margin-top: 3px; color: #64748b; font-size: 11px; }
.adb-expiring-list time { color: #b45309; font-size: 12px; white-space: nowrap; }
.adb-details { margin-top: 14px; border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; }
.adb-details > summary { padding: 14px 16px; cursor: pointer; color: #334155; font-weight: 650; }
.adb-details[open] > summary { border-bottom: 1px solid #eef2f7; }
.adb-detail-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; padding: 12px; }
.adb-mini-metrics { display: flex; gap: 12px; flex-wrap: wrap; margin-bottom: 12px; color: #64748b; font-size: 12px; }
.adb-mini-metrics b { color: #172033; }
.adb-compact-list { display: grid; gap: 7px; min-height: 72px; margin: 0 0 12px; padding: 0; list-style: none; }
.adb-compact-list li { display: grid; grid-template-columns: 90px minmax(0,1fr); gap: 8px; font-size: 11px; }
.adb-compact-list span { color: #64748b; }
.adb-compact-list strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
@media (max-width: 1100px) { .adb-readiness { flex-direction: column; } .adb-readiness-metrics { align-self: stretch; } .adb-two-columns, .adb-detail-grid { grid-template-columns: 1fr; } }
@media (max-width: 720px) { .adb-actions { justify-content: stretch; } .adb-term-picker, .adb-purpose { width: 100%; } .adb-readiness-metrics, .adb-today-grid { grid-template-columns: repeat(2,1fr); } .adb-issue { grid-template-columns: 1fr; } .adb-issue-rank { padding: 7px; } }
</style>
