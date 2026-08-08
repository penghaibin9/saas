<template>
  <BasePortalLayout :title="brandTitle" subtitle="帮助中心" :ctx="ctx" @menu-select="onMenu">
    <template #menu>
      <nav class="help-nav" aria-label="帮助目录">
        <button
          type="button"
          class="help-nav__home"
          :class="{ 'is-active': !currentEntry }"
          @click="showOverview"
        >
          <span>自助服务首页</span>
          <small>{{ overview.total }} 项</small>
        </button>

        <details
          v-for="section in visibleSections"
          :key="section.key"
          class="help-nav__section"
          :open="isSectionOpen(section)"
        >
          <summary>
            <span>{{ section.label }}</span>
            <small>{{ section.items.length }}</small>
          </summary>
          <button
            v-for="entry in section.items"
            :key="entry.id"
            type="button"
            class="help-nav__item"
            :class="{ 'is-active': entry.id === currentId }"
            @click="selectTopic(entry.id)"
          >
            {{ entry.title }}
          </button>
        </details>

        <div v-if="!visibleSections.length" class="help-nav__empty">
          当前筛选下没有目录项。
        </div>
      </nav>
    </template>

    <div class="help-shell">
      <header class="help-hero">
        <div>
          <p class="help-eyebrow">跃科 SaaS · 免培训自助服务</p>
          <h1>自助办理与问题解决中心</h1>
          <p>不用先读说明书。直接告诉系统“我要办什么”或“哪里做不了”，也可以沿核心业务流程看现在在哪一步、下一步谁处理。</p>
        </div>
        <dl class="help-metrics" aria-label="帮助内容统计">
          <div><dt>已核验任务</dt><dd>{{ overview.taskCards }}</dd></div>
          <div><dt>业务流程</dt><dd>{{ overview.flowGuides }}</dd></div>
          <div><dt>可视指南</dt><dd>{{ overview.visualGuides }}</dd></div>
        </dl>
      </header>

      <section v-if="qualityMetrics" class="help-quality" aria-label="帮助中心近30天质量指标">
        <div class="help-quality__heading">
          <div>
            <p class="help-eyebrow">V3-08 · 近 {{ qualityMetrics.windowDays }} 天</p>
            <h2>帮助中心质量</h2>
          </div>
          <small>只统计真实搜索和用户明确反馈；未打通人工工单前，不伪造“真实自助解决率”。</small>
        </div>
        <dl class="help-quality__metrics">
          <div>
            <dt>搜索命中率</dt>
            <dd>{{ formatRate(qualityMetrics.searchHitRate) }}</dd>
            <small>{{ qualityMetrics.searches }} 次搜索 · {{ metricStatusLabel(qualityMetrics.quality?.search) }}</small>
          </div>
          <div>
            <dt>明确反馈解决率</dt>
            <dd>{{ formatRate(qualityMetrics.explicitResolutionRate) }}</dd>
            <small>{{ qualityMetrics.feedbackVotes }} 次反馈 · {{ metricStatusLabel(qualityMetrics.quality?.resolution) }}</small>
          </div>
          <div>
            <dt>真正自助解决率</dt>
            <dd>—</dd>
            <small>等待人工升级/工单闭环后计算</small>
          </div>
        </dl>
      </section>

      <section class="help-controls" aria-label="帮助筛选">
        <label class="help-control help-control--search">
          <span>直接描述你要办的事或遇到的问题</span>
          <input
            v-model.trim="queryText"
            type="search"
            placeholder="例如：成绩为什么提交不了？怎么发布选课？为什么看不到学生？"
            autocomplete="off"
            @keyup.enter="syncFiltersToUrl"
          />
        </label>
        <label class="help-control">
          <span>我的角色</span>
          <select v-model="selectedRole" @change="onFilterChange">
            <option v-for="role in roleOptions" :key="role.value" :value="role.value">
              {{ role.label }}
            </option>
          </select>
        </label>
        <label class="help-control">
          <span>业务分类</span>
          <select v-model="selectedCategory" @change="onFilterChange">
            <option value="all">全部分类</option>
            <option v-for="category in categoryOptions" :key="category.value" :value="category.value">
              {{ category.label }}（{{ category.count }}）
            </option>
          </select>
        </label>
        <button v-if="hasFilters" type="button" class="help-clear" @click="clearFilters">
          清除筛选
        </button>
      </section>

      <div v-if="invalidTopic" class="help-notice" role="alert">
        原链接指向的帮助条目不存在或已调整。已返回自助服务首页，请重新搜索。
      </div>

      <article v-if="currentEntry" class="help-article">
        <button type="button" class="help-back" @click="showOverview">← 返回自助服务首页</button>

        <header class="help-article__header">
          <div class="help-badges">
            <span>{{ currentEntry.typeLabel }}</span>
            <span>{{ currentEntry.category }}</span>
            <span v-if="displayRoles.length">{{ displayRoles.join('、') }}</span>
          </div>
          <h2>{{ currentEntry.title }}</h2>
          <p>{{ currentEntry.summary }}</p>
          <div v-if="currentItem.entry || currentItem.route" class="help-entry">
            <div>
              <strong>从哪里进入</strong>
              <span>{{ currentItem.entry || '从对应业务模块进入' }}</span>
            </div>
            <button v-if="currentItem.route" type="button" @click="goRoute(currentItem.route)">
              前往办理页面
            </button>
          </div>
        </header>

        <section v-if="currentItem.prerequisites?.length" class="help-section">
          <h3>操作前准备</h3>
          <ul><li v-for="(item, index) in currentItem.prerequisites" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentEntry.type === 'card' && currentItem.steps?.length" class="help-section">
          <h3>照着做</h3>
          <ol class="help-task-steps">
            <li v-for="(step, index) in currentItem.steps" :key="index">
              <span>{{ index + 1 }}</span>
              <div>{{ stringify(step) }}</div>
            </li>
          </ol>
        </section>

        <section v-else-if="currentEntry.type === 'flow' && currentItem.steps?.length" class="help-section">
          <h3>业务流转</h3>
          <ol class="help-flow">
            <li v-for="(step, index) in currentItem.steps" :key="index">
              <span class="help-flow__number">{{ index + 1 }}</span>
              <div>
                <strong>{{ step.name || stringify(step) }}</strong>
                <small v-if="step.who">{{ step.who }}</small>
                <p v-if="step.detail">{{ step.detail }}</p>
              </div>
            </li>
          </ol>
        </section>

        <section v-if="currentEntry.type === 'doc' && currentItem.points?.length" class="help-section">
          <h3>关键要点</h3>
          <ul><li v-for="(point, index) in currentItem.points" :key="index">{{ stringify(point) }}</li></ul>
        </section>

        <section v-if="currentItem.fields?.length" class="help-section">
          <h3>需要填写或确认</h3>
          <ul><li v-for="(field, index) in currentItem.fields" :key="index">{{ stringify(field) }}</li></ul>
        </section>

        <section v-for="(section, index) in currentItem.sections || []" :key="index" class="help-section">
          <h3>{{ section.title || section.heading || `补充说明 ${index + 1}` }}</h3>
          <p v-if="section.body">{{ section.body }}</p>
          <ul v-if="section.items || section.list">
            <li v-for="(line, lineIndex) in section.items || section.list" :key="lineIndex">{{ stringify(line) }}</li>
          </ul>
        </section>

        <section v-if="currentItem.successCriteria?.length" class="help-section help-section--success">
          <h3>怎样才算办成功</h3>
          <ul><li v-for="(item, index) in currentItem.successCriteria" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentItem.nextSteps?.length" class="help-section help-section--next">
          <h3>办完以后下一步</h3>
          <ul><li v-for="(item, index) in currentItem.nextSteps" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentItem.tips?.length" class="help-section help-section--tip">
          <h3>操作提示</h3>
          <ul><li v-for="(tip, index) in currentItem.tips" :key="index">{{ stringify(tip) }}</li></ul>
        </section>

        <section v-if="currentItem.warnings?.length" class="help-section help-section--warning">
          <h3>重要提醒</h3>
          <ul><li v-for="(warning, index) in currentItem.warnings" :key="index">{{ stringify(warning) }}</li></ul>
        </section>

        <section v-if="currentItem.faq?.length" class="help-section">
          <h3>常见问题</h3>
          <details v-for="(qa, index) in currentItem.faq" :key="index" class="help-faq">
            <summary>{{ qa.q || qa.question || stringify(qa) }}</summary>
            <p v-if="qa.a || qa.answer">{{ qa.a || qa.answer }}</p>
          </details>
        </section>

        <section v-if="currentItem.troubleshooting?.length" class="help-section">
          <h3>做不了时怎么自己排查</h3>
          <ol><li v-for="(item, index) in currentItem.troubleshooting" :key="index">{{ stringify(item) }}</li></ol>
        </section>

        <section v-if="currentItem.contactAdminWhen?.length" class="help-section help-section--admin">
          <h3>什么情况才需要找管理员</h3>
          <ul><li v-for="(item, index) in currentItem.contactAdminWhen" :key="index">{{ stringify(item) }}</li></ul>
        </section>

        <section v-if="currentItem.related?.length" class="help-section">
          <h3>相关入口</h3>
          <div class="help-related">
            <button
              v-for="(related, index) in currentItem.related"
              :key="index"
              type="button"
              @click="goRoute(related.route)"
            >
              {{ related.label || stringify(related) }} ↗
            </button>
          </div>
        </section>

        <section v-if="currentItem.embed" class="help-section help-section--embed">
          <h3>可视化说明</h3>
          <iframe
            :src="currentItem.embed"
            sandbox="allow-scripts"
            referrerpolicy="no-referrer"
            :title="currentItem.title"
          ></iframe>
        </section>

        <section class="help-feedback" aria-label="帮助是否解决问题">
          <div>
            <strong>这篇帮助解决你的问题了吗？</strong>
            <small>你的选择只用于改进帮助质量。</small>
          </div>
          <div v-if="!currentFeedback" class="help-feedback__actions">
            <button type="button" @click="submitArticleFeedback('HELPFUL')">已解决</button>
            <button type="button" class="is-secondary" @click="submitArticleFeedback('NOT_HELPFUL')">没解决</button>
          </div>
          <span v-else class="help-feedback__done">已记录，谢谢反馈。</span>
        </section>

        <footer class="help-article__footer">
          <span>文章编号：{{ currentEntry.id }}</span>
          <span v-if="!currentEntry.quality.isComplete">该条目仍有元数据待治理，不影响当前阅读。</span>
        </footer>
      </article>

      <template v-else>
        <section v-if="queryText || selectedCategory !== 'all'" class="help-results">
          <div class="help-section-heading">
            <div>
              <p class="help-eyebrow">自助搜索结果</p>
              <h2>找到 {{ filteredEntries.length }} 项可执行帮助</h2>
            </div>
          </div>
          <div v-if="filteredEntries.length" class="help-card-grid">
            <button
              v-for="entry in filteredEntries"
              :key="entry.id"
              type="button"
              class="help-card"
              @click="selectTopic(entry.id)"
            >
              <span>{{ entry.typeLabel }} · {{ entry.category }}</span>
              <strong>{{ entry.title }}</strong>
              <p>{{ entry.summary }}</p>
            </button>
          </div>
          <div v-else class="help-empty-state">
            <h3>没有找到已经核验的答案</h3>
            <p>可以换成更具体的业务动作或错误现象，例如“成绩提交”“退回”“数据范围”“409”。没有通过 verified-only 发布门的旧知识不会为了凑答案重新展示。</p>
            <button type="button" @click="clearFilters">返回自助服务首页</button>
          </div>
        </section>

        <template v-else>
          <section class="help-intents" aria-label="自助服务入口">
            <button
              v-for="intent in v3Home.intents"
              :key="intent.key"
              type="button"
              class="help-intent"
              :class="{ 'is-active': homeMode === intent.key }"
              @click="selectHomeMode(intent.key)"
            >
              <span>{{ intent.title }}</span>
              <strong>{{ intent.description }}</strong>
              <small>{{ intent.hint }}</small>
            </button>
          </section>

          <section v-if="homeMode === 'tasks'" class="help-section-block">
            <div class="help-section-heading">
              <div>
                <p class="help-eyebrow">我要办一件事</p>
                <h2>按当前角色推荐高频办理</h2>
              </div>
              <p>当前按“{{ activeRoleLabel }}”推荐；每一项都来自已核验正式知识。</p>
            </div>
            <div class="help-card-grid">
              <button
                v-for="entry in priorityEntries"
                :key="entry.id"
                type="button"
                class="help-card"
                @click="selectTopic(entry.id)"
              >
                <span>{{ entry.typeLabel }} · {{ entry.category }}</span>
                <strong>{{ entry.title }}</strong>
                <p>{{ entry.summary }}</p>
              </button>
            </div>
          </section>

          <template v-else-if="homeMode === 'problems'">
            <section class="help-section-block">
              <div class="help-section-heading">
                <div>
                  <p class="help-eyebrow">我遇到问题</p>
                  <h2>先选最像你当前情况的问题</h2>
                </div>
                <p>点击后直接搜索相关已核验答案，不要求你先知道问题属于哪个模块。</p>
              </div>
              <div class="help-question-grid">
                <button
                  v-for="question in v3Home.quickQuestions"
                  :key="question.label"
                  type="button"
                  class="help-question"
                  @click="applyQuickQuestion(question)"
                >
                  {{ question.label }}
                </button>
              </div>
            </section>

            <section class="help-section-block help-diagnosis">
              <div>
                <p class="help-eyebrow">通用自查顺序</p>
                <h2>先自己排查，再决定是否需要找管理员</h2>
              </div>
              <ol>
                <li>确认当前学期、批次、学生或业务范围是否正确。</li>
                <li>确认账号当前角色、数据范围和记录归属。</li>
                <li>确认业务状态是否允许当前操作，是否已经提交、发布或归档。</li>
                <li>确认前置数据、必填字段和材料是否齐全。</li>
                <li>遇到 403 / 409 / 明确业务提示时，先按帮助中的对应原因处理，不反复连续点击。</li>
                <li>只有组织、账号、权限、数据范围配置明显错误，或按帮助排查仍无法恢复时，再联系学校管理员。</li>
              </ol>
            </section>
          </template>

          <section v-else-if="homeMode === 'journeys'" class="help-section-block">
            <div class="help-section-heading">
              <div>
                <p class="help-eyebrow">核心业务流程</p>
                <h2>看现在在哪一步，下一步该做什么</h2>
              </div>
              <p>当前只展示已经通过 verified-only 发布门的流程节点；尚未重新验真的历史节点不会混进来。</p>
            </div>
            <div class="help-journey-grid">
              <article v-for="journey in v3Home.journeys" :key="journey.key" class="help-journey">
                <header>
                  <div>
                    <strong>{{ journey.title }}</strong>
                    <span>已核验 {{ journey.verifiedCount }} 个节点</span>
                  </div>
                  <p>{{ journey.description }}</p>
                </header>
                <ol class="help-journey-steps">
                  <li v-for="(entry, index) in journey.entries" :key="entry.id">
                    <span>{{ index + 1 }}</span>
                    <button type="button" @click="selectTopic(entry.id)">
                      {{ entry.title }}
                    </button>
                  </li>
                </ol>
              </article>
            </div>
          </section>
        </template>
      </template>
    </div>
  </BasePortalLayout>
</template>

<script>
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import {
  HELP_ROLE_OPTIONS,
  getHelpCategories,
  getHelpEntry,
  getHelpOverview,
  getHelpSections,
  getV3HomeModel,
  resolveHelpRole,
  searchHelpCenter
} from '@/config/helpCenterModel'
import {
  formatHelpRate,
  helpMetricStatusLabel,
  loadHelpMetricsSummary,
  recordHelpMetric
} from '@/config/help/helpMetrics'
import { getAuthContext } from '@/security/auth/auth.context'

export default {
  name: 'AdminHelpView',
  components: { BasePortalLayout },
  data() {
    const auth = getAuthContext()
    const requestedTopic = String(this.$route.query.topic || '')
    const defaultRole = resolveHelpRole(
      auth.currentRole || auth.primaryRole || (auth.roles && auth.roles[0]),
      auth.label
    )
    const requestedRole = String(this.$route.query.role || defaultRole || 'all')
    const selectedRole = HELP_ROLE_OPTIONS.some((role) => role.value === requestedRole) ? requestedRole : defaultRole
    return {
      auth,
      roleOptions: HELP_ROLE_OPTIONS,
      currentId: getHelpEntry(requestedTopic) ? requestedTopic : '',
      invalidTopic: Boolean(requestedTopic && !getHelpEntry(requestedTopic)),
      queryText: String(this.$route.query.q || ''),
      selectedRole,
      selectedCategory: String(this.$route.query.category || 'all'),
      homeMode: 'tasks',
      qualityMetrics: null,
      articleFeedback: {}
    }
  },
  computed: {
    brandTitle() {
      return `${this.auth.schoolName || '管理端'} · 管理端`
    },
    ctx() {
      return {
        tenantBrandConfig: { schoolName: this.auth.schoolName },
        currentRole: {
          roleType: this.auth.currentRole || this.auth.primaryRole || (this.auth.roles && this.auth.roles[0]) || 'SCHOOL_ADMIN',
          userName: this.auth.displayName
        }
      }
    },
    currentEntry() {
      return getHelpEntry(this.currentId)
    },
    currentItem() {
      return this.currentEntry?.item || {}
    },
    currentFeedback() {
      return this.articleFeedback[this.currentId] || ''
    },
    displayRoles() {
      const roles = this.currentItem.roles || this.currentItem.role || []
      return Array.isArray(roles) ? roles : [roles].filter(Boolean)
    },
    overview() {
      return getHelpOverview(this.selectedRole)
    },
    categoryOptions() {
      return getHelpCategories(this.selectedRole)
    },
    visibleSections() {
      return getHelpSections(this.selectedRole, this.queryText, this.selectedCategory)
    },
    filteredEntries() {
      return searchHelpCenter(this.queryText, {
        role: this.selectedRole,
        category: this.selectedCategory,
        limit: 100
      })
    },
    v3Home() {
      return getV3HomeModel(this.selectedRole)
    },
    priorityEntries() {
      return this.v3Home.priorityTasks
    },
    hasFilters() {
      return Boolean(this.queryText || this.selectedCategory !== 'all' || this.selectedRole !== 'all')
    },
    activeRoleLabel() {
      return this.roleOptions.find((role) => role.value === this.selectedRole)?.label || '全部角色'
    }
  },
  watch: {
    '$route.query.topic'(value) {
      const id = String(value || '')
      this.currentId = getHelpEntry(id) ? id : ''
      this.invalidTopic = Boolean(id && !getHelpEntry(id))
    }
  },
  mounted() {
    this.refreshQualityMetrics()
    if (this.currentEntry) this.trackArticleView(this.currentEntry, 'direct_link')
  },
  methods: {
    formatRate(value) {
      return formatHelpRate(value)
    },
    metricStatusLabel(value) {
      return helpMetricStatusLabel(value)
    },
    async refreshQualityMetrics() {
      this.qualityMetrics = await loadHelpMetricsSummary(30)
    },
    trackArticleView(entry, source = 'directory') {
      if (!entry) return
      void recordHelpMetric({
        eventType: 'ARTICLE_VIEW',
        articleId: entry.id,
        source,
        category: entry.category,
        roleGroup: this.selectedRole
      })
    },
    onMenu(item) {
      if (item?.path && item.path !== this.$route.path) this.$router.push(item.path)
    },
    selectTopic(id) {
      const entry = getHelpEntry(id)
      if (!entry) return
      this.currentId = id
      this.invalidTopic = false
      this.replaceQuery({ topic: id })
      this.trackArticleView(entry)
      window.scrollTo({ top: 0, behavior: 'smooth' })
    },
    showOverview() {
      this.currentId = ''
      this.invalidTopic = false
      this.replaceQuery({ topic: undefined })
    },
    selectHomeMode(mode) {
      this.homeMode = mode
      this.currentId = ''
      this.invalidTopic = false
    },
    applyQuickQuestion(question) {
      this.queryText = String(question?.query || question?.label || '').trim()
      this.selectedCategory = 'all'
      this.syncFiltersToUrl({ source: 'quick_question' })
    },
    onFilterChange() {
      if (this.selectedCategory !== 'all' && !this.categoryOptions.some((item) => item.value === this.selectedCategory)) {
        this.selectedCategory = 'all'
      }
      this.showOverview()
      this.syncFiltersToUrl({ trackSearch: false })
    },
    clearFilters() {
      this.queryText = ''
      this.selectedRole = 'all'
      this.selectedCategory = 'all'
      this.currentId = ''
      this.invalidTopic = false
      this.homeMode = 'tasks'
      this.replaceQuery({ topic: undefined, q: undefined, role: undefined, category: undefined })
    },
    syncFiltersToUrl(options = {}) {
      this.currentId = ''
      this.invalidTopic = false
      this.replaceQuery({
        topic: undefined,
        q: this.queryText || undefined,
        role: this.selectedRole !== 'all' ? this.selectedRole : undefined,
        category: this.selectedCategory !== 'all' ? this.selectedCategory : undefined
      })
      if (options?.trackSearch !== false && this.queryText) {
        void recordHelpMetric({
          eventType: 'SEARCH',
          query: this.queryText,
          resultCount: this.filteredEntries.length,
          source: options?.source || 'search',
          category: this.selectedCategory,
          roleGroup: this.selectedRole
        })
      }
    },
    async submitArticleFeedback(eventType) {
      if (!this.currentEntry || this.currentFeedback) return
      const id = this.currentEntry.id
      const result = await recordHelpMetric({
        eventType,
        articleId: id,
        source: 'article',
        category: this.currentEntry.category,
        roleGroup: this.selectedRole
      })
      if (!result) return
      this.articleFeedback = { ...this.articleFeedback, [id]: eventType }
      void this.refreshQualityMetrics()
    },
    replaceQuery(patch) {
      const query = { ...this.$route.query, ...patch }
      Object.keys(query).forEach((key) => {
        if (query[key] === undefined || query[key] === null || query[key] === '') delete query[key]
      })
      this.$router.replace({ query }).catch(() => {})
    },
    goRoute(target) {
      if (typeof target === 'string' && target.startsWith('/')) this.$router.push(target)
    },
    isSectionOpen(section) {
      return section.items.some((entry) => entry.id === this.currentId) || section.key.endsWith('overview')
    },
    stringify(value) {
      if (typeof value === 'string') return value
      if (!value || typeof value !== 'object') return String(value || '')
      return value.label || value.name || value.title || value.detail || value.text || JSON.stringify(value)
    }
  }
}
</script>

<style scoped>
.help-nav { display: flex; flex-direction: column; gap: 8px; }
.help-nav button { font: inherit; }
.help-nav__home,
.help-nav__item { width: 100%; border: 0; text-align: left; cursor: pointer; color: var(--t2); background: transparent; }
.help-nav__home { display: flex; justify-content: space-between; align-items: center; padding: 10px 11px; border-radius: 10px; font-weight: 700; }
.help-nav__home small,
.help-nav__section summary small { color: var(--t3); font-weight: 600; }
.help-nav__home:hover,
.help-nav__home.is-active,
.help-nav__item:hover,
.help-nav__item.is-active { color: var(--brand); background: color-mix(in srgb, var(--brand) 9%, transparent); }
.help-nav__section { border-top: 1px solid var(--dv); padding-top: 7px; }
.help-nav__section summary { display: flex; justify-content: space-between; gap: 8px; padding: 7px 9px; cursor: pointer; color: var(--t1); font-size: 12px; font-weight: 800; }
.help-nav__item { padding: 8px 10px 8px 18px; border-radius: 9px; font-size: 12.5px; line-height: 1.45; }
.help-nav__empty { padding: 12px 10px; color: var(--t3); font-size: 12px; }
.help-shell { display: grid; gap: 18px; max-width: 1180px; margin: 0 auto; }
.help-hero { display: flex; justify-content: space-between; gap: 24px; padding: 26px; border: 1px solid var(--dv); border-radius: 20px; background: linear-gradient(135deg, color-mix(in srgb, var(--brand) 12%, white), white 62%); }
.help-hero h1 { margin: 3px 0 8px; font-size: 28px; color: var(--t1); }
.help-hero p { margin: 0; max-width: 680px; color: var(--t2); line-height: 1.7; }
.help-eyebrow { margin: 0; color: var(--brand); font-size: 12px; font-weight: 800; letter-spacing: .08em; }
.help-metrics { display: grid; grid-template-columns: repeat(3, minmax(76px, 1fr)); gap: 10px; margin: 0; min-width: 270px; }
.help-metrics div { padding: 13px; border-radius: 14px; background: rgba(255,255,255,.82); border: 1px solid rgba(255,255,255,.9); }
.help-metrics dt { color: var(--t3); font-size: 11px; }
.help-metrics dd { margin: 5px 0 0; color: var(--t1); font-size: 22px; font-weight: 800; }
.help-quality { padding: 18px; border: 1px solid var(--dv); border-radius: 16px; background: linear-gradient(135deg, #f7faff, white); }
.help-quality__heading { display: flex; justify-content: space-between; gap: 18px; align-items: end; margin-bottom: 14px; }
.help-quality__heading h2 { margin: 4px 0 0; color: var(--t1); font-size: 18px; }
.help-quality__heading > small { max-width: 520px; color: var(--t3); line-height: 1.55; }
.help-quality__metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 0; }
.help-quality__metrics div { padding: 14px; border: 1px solid var(--dv); border-radius: 12px; background: white; }
.help-quality__metrics dt { color: var(--t3); font-size: 11px; }
.help-quality__metrics dd { margin: 5px 0; color: var(--t1); font-size: 22px; font-weight: 850; }
.help-quality__metrics small { color: var(--t3); line-height: 1.45; }
.help-controls { display: grid; grid-template-columns: minmax(300px, 1fr) minmax(160px, .35fr) minmax(180px, .4fr) auto; gap: 12px; align-items: end; padding: 16px; border: 1px solid var(--dv); border-radius: 16px; background: var(--c0); }
.help-control { display: grid; gap: 6px; color: var(--t2); font-size: 12px; font-weight: 700; }
.help-control input,
.help-control select { width: 100%; min-height: 40px; padding: 0 12px; border: 1px solid var(--dv); border-radius: 10px; color: var(--t1); background: white; font: inherit; outline: none; }
.help-control input:focus,
.help-control select:focus { border-color: var(--brand); box-shadow: 0 0 0 3px color-mix(in srgb, var(--brand) 14%, transparent); }
.help-clear { min-height: 40px; padding: 0 15px; border: 1px solid var(--dv); border-radius: 10px; background: white; color: var(--t2); cursor: pointer; }
.help-notice { padding: 12px 14px; border-radius: 12px; border: 1px solid #f4c66f; background: #fff8e6; color: #7a4d00; }
.help-article,
.help-section-block,
.help-results { padding: 26px; border: 1px solid var(--dv); border-radius: 18px; background: white; }
.help-intents { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 13px; }
.help-intent { display: grid; gap: 8px; min-height: 128px; padding: 18px; border: 1px solid var(--dv); border-radius: 16px; background: white; text-align: left; cursor: pointer; }
.help-intent:hover,
.help-intent.is-active { border-color: color-mix(in srgb, var(--brand) 52%, var(--dv)); background: color-mix(in srgb, var(--brand) 6%, white); box-shadow: 0 10px 24px rgba(20,53,90,.07); }
.help-intent span { color: var(--brand); font-size: 17px; font-weight: 850; }
.help-intent strong { color: var(--t1); font-size: 13px; line-height: 1.6; }
.help-intent small { color: var(--t3); line-height: 1.5; }
.help-back { border: 0; padding: 0; background: transparent; color: var(--brand); font-weight: 700; cursor: pointer; }
.help-article__header { padding: 18px 0 22px; border-bottom: 1px solid var(--dv); }
.help-article__header h2 { margin: 12px 0 10px; color: var(--t1); font-size: 27px; line-height: 1.3; }
.help-article__header > p { margin: 0; max-width: 820px; color: var(--t2); line-height: 1.75; }
.help-badges { display: flex; flex-wrap: wrap; gap: 7px; }
.help-badges span { padding: 5px 9px; border-radius: 999px; background: color-mix(in srgb, var(--brand) 9%, white); color: var(--brand); font-size: 11px; font-weight: 700; }
.help-entry { display: flex; justify-content: space-between; gap: 16px; align-items: center; margin-top: 18px; padding: 14px; border-radius: 12px; background: var(--c1); }
.help-entry div { display: grid; gap: 4px; }
.help-entry strong { color: var(--t1); }
.help-entry span { color: var(--t2); font-size: 13px; }
.help-entry button,
.help-related button,
.help-empty-state button { border: 0; border-radius: 9px; padding: 9px 13px; background: var(--brand); color: white; font-weight: 700; cursor: pointer; }
.help-section { padding: 22px 0; border-bottom: 1px solid var(--dv); }
.help-section h3 { margin: 0 0 12px; color: var(--t1); font-size: 17px; }
.help-section p,
.help-section li { color: var(--t2); line-height: 1.75; }
.help-section ul,
.help-section ol { margin: 0; padding-left: 22px; }
.help-section--tip { margin-top: 18px; padding: 18px; border: 1px solid #b9ddff; border-radius: 13px; background: #f2f8ff; }
.help-section--warning { margin-top: 18px; padding: 18px; border: 1px solid #f6cf7d; border-radius: 13px; background: #fff9eb; }
.help-section--success { margin-top: 18px; padding: 18px; border: 1px solid #b7e4c7; border-radius: 13px; background: #f1fbf5; }
.help-section--next { margin-top: 18px; padding: 18px; border: 1px solid #c9d7ff; border-radius: 13px; background: #f5f7ff; }
.help-section--admin { margin-top: 18px; padding: 18px; border: 1px solid #e3d5f5; border-radius: 13px; background: #fbf8ff; }
.help-task-steps { display: grid; gap: 12px; padding: 0 !important; list-style: none; }
.help-task-steps li { display: grid; grid-template-columns: 30px 1fr; gap: 12px; align-items: start; }
.help-task-steps li > span,
.help-flow__number { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--brand); color: white; font-size: 12px; font-weight: 800; }
.help-flow { display: grid; gap: 10px; padding: 0 !important; list-style: none; }
.help-flow li { display: grid; grid-template-columns: 32px 1fr; gap: 12px; padding: 14px; border: 1px solid var(--dv); border-radius: 12px; }
.help-flow strong { color: var(--t1); }
.help-flow small { margin-left: 8px; color: var(--brand); }
.help-flow p { margin: 5px 0 0; }
.help-faq { padding: 12px 0; border-top: 1px solid var(--dv); }
.help-faq summary { cursor: pointer; color: var(--t1); font-weight: 700; }
.help-faq p { margin-bottom: 0; }
.help-related { display: flex; flex-wrap: wrap; gap: 9px; }
.help-section--embed iframe { width: 100%; min-height: 680px; border: 1px solid var(--dv); border-radius: 13px; background: white; }
.help-feedback { display: flex; justify-content: space-between; gap: 18px; align-items: center; margin-top: 20px; padding: 16px; border: 1px solid var(--dv); border-radius: 13px; background: var(--c1); }
.help-feedback > div:first-child { display: grid; gap: 4px; }
.help-feedback strong { color: var(--t1); }
.help-feedback small { color: var(--t3); }
.help-feedback__actions { display: flex; gap: 8px; }
.help-feedback__actions button { border: 0; border-radius: 9px; padding: 9px 14px; background: var(--brand); color: white; font-weight: 750; cursor: pointer; }
.help-feedback__actions button.is-secondary { border: 1px solid var(--dv); background: white; color: var(--t2); }
.help-feedback__done { color: var(--brand); font-size: 12px; font-weight: 800; }
.help-article__footer { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px; padding-top: 18px; color: var(--t3); font-size: 11px; }
.help-section-heading { display: flex; justify-content: space-between; gap: 18px; align-items: end; margin-bottom: 18px; }
.help-section-heading h2 { margin: 5px 0 0; color: var(--t1); }
.help-section-heading > p { max-width: 430px; margin: 0; color: var(--t3); line-height: 1.6; }
.help-card-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 13px; }
.help-card { display: grid; gap: 9px; min-height: 150px; padding: 18px; border: 1px solid var(--dv); border-radius: 14px; background: white; text-align: left; cursor: pointer; transition: transform .18s ease, border-color .18s ease, box-shadow .18s ease; }
.help-card:hover { transform: translateY(-2px); border-color: color-mix(in srgb, var(--brand) 45%, var(--dv)); box-shadow: 0 10px 24px rgba(20,53,90,.08); }
.help-card span { color: var(--brand); font-size: 11px; font-weight: 800; }
.help-card strong { color: var(--t1); font-size: 16px; }
.help-card p { margin: 0; color: var(--t2); font-size: 13px; line-height: 1.65; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.help-question-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.help-question { min-height: 48px; padding: 11px 14px; border: 1px solid var(--dv); border-radius: 12px; background: var(--c1); color: var(--t1); text-align: left; font-weight: 750; cursor: pointer; }
.help-question:hover { border-color: var(--brand); color: var(--brand); background: color-mix(in srgb, var(--brand) 6%, white); }
.help-journey-grid { display: grid; gap: 14px; }
.help-journey { padding: 18px; border: 1px solid var(--dv); border-radius: 15px; background: linear-gradient(180deg, #fff, #fbfcff); }
.help-journey header { display: grid; gap: 7px; margin-bottom: 14px; }
.help-journey header > div { display: flex; justify-content: space-between; gap: 12px; align-items: center; }
.help-journey header strong { color: var(--t1); font-size: 17px; }
.help-journey header span { color: var(--brand); font-size: 11px; font-weight: 800; }
.help-journey header p { margin: 0; color: var(--t2); line-height: 1.65; }
.help-journey-steps { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; list-style: none; }
.help-journey-steps li { display: flex; align-items: center; gap: 7px; }
.help-journey-steps li > span { display: grid; place-items: center; width: 22px; height: 22px; border-radius: 50%; background: color-mix(in srgb, var(--brand) 12%, white); color: var(--brand); font-size: 10px; font-weight: 800; }
.help-journey-steps button { border: 1px solid var(--dv); border-radius: 999px; padding: 7px 10px; background: white; color: var(--t2); cursor: pointer; font: inherit; font-size: 12px; }
.help-journey-steps button:hover { border-color: var(--brand); color: var(--brand); }
.help-diagnosis { display: grid; grid-template-columns: .7fr 1fr; gap: 24px; background: linear-gradient(135deg, #f7faff, white); }
.help-diagnosis h2 { margin: 5px 0 0; color: var(--t1); }
.help-diagnosis ol { margin: 0; padding-left: 20px; }
.help-diagnosis li { padding: 5px 0; color: var(--t2); line-height: 1.6; }
.help-empty-state { padding: 50px 24px; text-align: center; color: var(--t2); }
.help-empty-state h3 { color: var(--t1); }
.help-empty-state p { max-width: 620px; margin: 0 auto 18px; line-height: 1.7; }
@media (max-width: 900px) {
  .help-hero { flex-direction: column; }
  .help-metrics { min-width: 0; }
  .help-quality__heading { align-items: flex-start; flex-direction: column; }
  .help-quality__metrics { grid-template-columns: 1fr; }
  .help-controls { grid-template-columns: 1fr 1fr; }
  .help-control--search { grid-column: 1 / -1; }
  .help-intents { grid-template-columns: 1fr; }
  .help-card-grid,
  .help-question-grid { grid-template-columns: 1fr; }
  .help-diagnosis { grid-template-columns: 1fr; }
}
@media (max-width: 620px) {
  .help-hero,
  .help-article,
  .help-section-block,
  .help-results { padding: 18px; border-radius: 14px; }
  .help-controls { grid-template-columns: 1fr; }
  .help-control--search { grid-column: auto; }
  .help-metrics { grid-template-columns: 1fr; }
  .help-entry,
  .help-feedback,
  .help-section-heading,
  .help-journey header > div { align-items: flex-start; flex-direction: column; }
  .help-section--embed iframe { min-height: 520px; }
}
</style>