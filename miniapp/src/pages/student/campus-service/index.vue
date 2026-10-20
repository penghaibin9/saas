<template>
  <view class="student-shell">
    <MobileStudentHero title="服务大厅" subtitle="校园事务，一站办理">
      <view class="shell-search">
        <MobileShellIcon name="search" tone="gray" :size="22" />
        <input
          class="sv__search-input"
          v-model="keyword"
          placeholder="搜索服务"
          maxlength="40"
          placeholder-class="sv__search-ph"
          confirm-type="search"
        />
      </view>
    </MobileStudentHero>

    <MobileGlobalState :state="state" @retry="load">
      <view v-if="data">
        <view class="sv__domains">
          <button v-for="c in data.categories" :key="c.key" class="sv__domain"
            :class="{ 'is-active': selectedCategory === c.key }" @click="selectCategory(c.key)">
            <MobileShellIcon :name="domainIcon(c.key)" :tone="selectedCategory === c.key ? 'blue' : 'gray'" :size="28" />
            <text class="sv__domain-name">{{ c.label }}</text>
          </button>
        </view>
        <view class="shell-pad">
        <view class="shell-panel shell-row sv__records" @click="go('/pages/student/my-work/index')">
          <MobileShellIcon name="file-text" :size="26" round />
          <view class="shell-row__body"><text class="shell-row__title">我的办理</text><text class="shell-muted">查看进度与反馈</text></view>
          <view class="shell-link">查看<MobileShellIcon name="chevron-right" :size="18" /></view>
        </view>
        <template v-if="!keyword.trim() && category">
          <view class="shell-panel">
          <view class="shell-heading sv__heading">
            <text class="shell-title">{{ category.label.replace('中心', '') }}服务</text>
            <view v-if="!category.reason" class="shell-link" @click="apply(category)">查看{{ category.label.replace('中心', '') }}事项<MobileShellIcon name="chevron-right" :size="17" /></view>
          </view>
          <text class="shell-muted">{{ category.reason || '查看当前安排，办理校园事务' }}</text>
          <view v-for="group in groups" :key="group.label" class="sv__group">
            <view class="sv__group-heading"><text>{{ group.label }}</text><view class="sv__rule" /></view>
            <view class="sv__services">
              <button v-for="s in group.items" :key="s.id" class="sv__service shell-plain-button" @click="apply(s)">
                <MobileShellIcon :name="serviceVisual(s).icon" :tone="serviceVisual(s).tone" :size="24" round />
                <view class="sv__service-copy"><text>{{ s.name }}</text>
                <text v-if="!canOpen(s)" class="sv__hint">{{ s.action?.disabledReason || '暂不可办' }}</text></view>
              </button>
            </view>
          </view>
          </view>
        </template>

        <!-- 搜索结果：改用列表卡展示，带办理入口 -->
        <template v-else>
          <view class="stack">
            <MobileActionCard
              v-for="s in searchResult"
              :key="s.id"
              :title="s.name"
              :description="s.desc"
              :action-text="canOpen(s) ? '进入服务' : ''"
              :disabled="!canOpen(s)"
              @action="apply(s)"
              @click="apply(s)"
            >
              <template v-if="!canOpen(s)" #action>
                <text class="sv__unavailable">暂不可办</text>
              </template>
            </MobileActionCard>
            <view v-if="!searchResult.length" class="sv__empty"><text class="t-sm t-tertiary">没有找到相关服务</text></view>
          </view>
        </template>

        <view class="sv__foot">
          <text class="t-xs t-tertiary">目录不等于办理资格。开放时间、本人任务和申请条件以业务页面为准。</text>
        </view>
        </view>
      </view>
    </MobileGlobalState>

    <MobileTabBar side="student" active="service" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { canNavigate, runAction } from '@/services/actionRouter'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { getStatusBarHeight } from '@/utils/deviceInfo'
import { go } from '@/utils/nav'
import { serviceVisual } from '@/services/studentShellPresentation.mjs'

export default {
  data() { return { data: null, state: 'loading', keyword: '', selectedCategory: 'studentAffairs', statusBarHeight: 20, loadSeq: 0 } },
  onLoad() {
    this.statusBarHeight = getStatusBarHeight()
    this.load()
  },
  onUnload() { this.loadSeq++ },
  onShow() {
    if (this._session !== undefined && this._session !== currentSessionGeneration()) {
      this.keyword = ''; this.selectedCategory = 'studentAffairs'; this.load()
    }
  },
  computed: {
    category() { return this.data?.categories.find(c => c.key === this.selectedCategory) || null },
    groups() {
      const groups = []
      for (const item of this.data?.items || []) {
        if (item.cat !== this.selectedCategory) continue
        const label = item.group || '全部服务'
        let group = groups.find(g => g.label === label)
        if (!group) { group = { label, items: [] }; groups.push(group) }
        group.items.push(item)
      }
      return groups
    },
    searchResult() {
      if (!this.data || !this.keyword) return []
      const kw = this.keyword.trim().toLowerCase()
      if (!kw) return []
      // 固定、有界的导航目录，不是下载业务记录后本地搜索。
      return this.data.items.filter((s) => (s.name + s.desc).toLowerCase().includes(kw))
    }
  },
  methods: {
    go,
    serviceVisual(s) { return serviceVisual(s.name || s.label) },
    domainIcon(key) { return { studentAffairs: 'school', academicAffairs: 'book', internship: 'briefcase', graduation: 'file-text' }[key] || 'folder' },
    selectCategory(key) { this.selectedCategory = key; this.keyword = '' },
    load() {
      const session = currentSessionGeneration()
      this._session = session
      const seq = ++this.loadSeq
      const current = () => seq === this.loadSeq && session === currentSessionGeneration()
      this.state = 'loading'
      this.data = null
      return studentApi.getServices().then((d) => {
        if (!current()) return
        this.data = d; this.state = 'ready'
        if (!d.categories.some(c => c.key === this.selectedCategory)) this.selectedCategory = d.categories[0].key
      }).catch(() => { if (current()) this.state = 'error' })
    },
    canOpen(s) { return canNavigate(s.action, 'student') },
    apply(s) { return runAction(s.action, { side: 'student' }) }
  }
}
</script>

<style scoped lang="scss">
@import '@/styles/student-shell.scss';
.sv__hero { padding: 0 var(--page-padding-mobile) var(--space-3); }
.sv__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.sv__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.sv__search { display: flex; align-items: center; gap: var(--space-2); background: rgba(255,255,255,.94); border-radius: var(--radius-md); padding: 10px var(--space-4); margin-top: var(--space-1); }
.sv__search-input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); }
.sv__search-ph { color: var(--text-tertiary); }
.sv__group { margin-top: var(--card-gap-mobile); }
.sv__records { display:flex; align-items:center; justify-content:space-between; gap:12px; min-height:60px; }
.sv__hint { display:block; font-size:12px; line-height:1.6; color:var(--text-secondary); font-weight:400; }
.sv__domains { display:flex; background:#fff; padding:14px 8px 0; }
.sv__domain { flex:1; margin:0; padding:0 0 14px; line-height:1.5; background:transparent; border:0; border-bottom:3px solid transparent; border-radius:0; display:flex; flex-direction:column; align-items:center; gap:6px; }
.sv__domain::after { border:0; }
.sv__domain.is-active { border-bottom-color:#1671f8; }
.sv__domain-name { display:block; font-size:14px; font-weight:600; color:#5d6880; }
.sv__domain.is-active .sv__domain-name { color:#1671f8; }
.sv__group { margin-top:24px; }
.sv__group-heading { display:flex; align-items:center; gap:12px; font-size:17px; font-weight:600; }
.sv__rule { flex:1; height:1px; background:#e8edf4; }
.sv__services { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); column-gap:10px; row-gap:10px; margin-top:12px; }
.sv__service { display:flex; align-items:center; gap:9px; min-height:64px; font-size:14px; color:#142440; }
.sv__service-copy { flex:1; min-width:0; }
.sv__heading { margin-bottom:0; }
@media (max-width:375px) { .sv__service { gap:6px; font-size:13px; } .sv__heading .shell-link { font-size:12px; } }
.sv__unavailable { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.sv__empty { text-align: center; padding: var(--space-6) 0; }
.sv__foot { text-align: center; margin-top: var(--space-5); }
</style>
