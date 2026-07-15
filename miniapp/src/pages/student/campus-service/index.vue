<template>
  <view class="page-wrap">
    <view class="sv__hero hero-band is-brand">
      <view class="mnav__status" :style="{ height: statusBarHeight + 'px' }" />
      <view class="sv__navbar"><text class="sv__navbar-title">服务大厅</text></view>
      <view class="sv__search" @click="focusSearch">
        <text class="sv__search-icon">🔍</text>
        <input
          class="sv__search-input"
          v-model="keyword"
          placeholder="搜索服务，如「请假」「证明」"
          placeholder-class="sv__search-ph"
          confirm-type="search"
        />
      </view>
    </view>

    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data" style="padding-top: var(--space-3);">
        <template v-if="!keyword">
          <view v-for="c in data.categories" :key="c.key" class="card sv__group">
            <view class="row-between"><text class="card-title">{{ c.label }}</text></view>
            <view class="icon-grid">
              <view
                v-for="s in itemsOf(c.key)"
                :key="s.id"
                class="icon-grid__item"
                :class="{ 'is-disabled': !s.available }"
                @click="apply(s)"
              >
                <view class="icon-grid__badge" :class="gradClass(s.id)">{{ c.icon }}</view>
                <text class="icon-grid__label">{{ s.name }}</text>
                <text v-if="!s.available" class="sv__soon">暂不可办</text>
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
              :description="s.desc + ' · ' + s.dept + (s.needApprove ? ' · 需审批' : '')"
              :icon="catIcon(s.cat)"
              :action-text="s.available ? '去办理' : ''"
              :disabled="!s.available"
              @action="apply(s)"
              @click="apply(s)"
            >
              <template v-if="!s.available" #action>
                <text class="sv__unavailable">暂不可办</text>
              </template>
            </MobileActionCard>
            <view v-if="!searchResult.length" class="sv__empty"><text class="t-sm t-tertiary">没有找到相关服务</text></view>
          </view>
        </template>

        <view class="sv__foot">
          <text class="t-xs t-tertiary">是否可办由「学生阶段 + 权限 + 模块开关」共同决定</text>
        </view>
      </view>
    </MobileGlobalState>

    <MobileTabBar side="student" active="service" />
  </view>
</template>

<script>
import { studentApi } from '@/services/studentApi'
import { toast, go } from '@/utils/nav'

const GRAD_CLASSES = ['g1', 'g3', 'g4', 'g5', 'g7', 'g6', 'g2', 'g8']

export default {
  data() { return { data: null, state: 'loading', keyword: '', statusBarHeight: 20 } },
  onLoad() {
    try { this.statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 20 } catch (e) {}
    this.load()
  },
  computed: {
    searchResult() {
      if (!this.data || !this.keyword) return []
      const kw = this.keyword.trim().toLowerCase()
      if (!kw) return []
      return this.data.items.filter((s) => (s.name + s.desc + s.dept).toLowerCase().includes(kw))
    }
  },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getServices().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    itemsOf(catKey) {
      return this.data.items.filter((s) => s.cat === catKey)
    },
    catIcon(key) {
      const c = (this.data.categories || []).find((x) => x.key === key)
      return c ? c.icon : '▤'
    },
    gradClass(id) {
      let h = 0
      for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) >>> 0
      return GRAD_CLASSES[h % GRAD_CLASSES.length]
    },
    focusSearch() {},
    apply(s) {
      if (!s.available) return toast('当前不可办理：' + s.desc)
      if (s.name === '心理健康问卷') return go('/pages/student/campus-service/mental-survey/index')
      const q = 'name=' + encodeURIComponent(s.name) + '&dept=' + encodeURIComponent(s.dept) + '&approve=' + (s.needApprove ? '1' : '0')
      go('/pages/student/service-apply/index?' + q)
    }
  }
}
</script>

<style scoped>
.sv__hero { padding: 0 var(--page-padding-mobile) var(--space-3); }
.sv__navbar { height: 40px; display: flex; align-items: center; justify-content: center; }
.sv__navbar-title { font-size: var(--font-size-lg); font-weight: var(--font-weight-semibold); color: #fff; }
.sv__search { display: flex; align-items: center; gap: var(--space-2); background: rgba(255,255,255,.94); border-radius: var(--radius-md); padding: 10px var(--space-4); margin-top: var(--space-1); }
.sv__search-input { flex: 1; font-size: var(--font-size-base); color: var(--text-primary); }
.sv__search-ph { color: var(--text-tertiary); }
.sv__group + .sv__group { margin-top: var(--card-gap-mobile); }
.icon-grid__item.is-disabled { opacity: 0.5; }
.sv__soon { position: absolute; top: -4px; font-size: 9px; color: var(--text-tertiary); }
.sv__unavailable { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.sv__empty { text-align: center; padding: var(--space-6) 0; }
.sv__foot { text-align: center; margin-top: var(--space-5); }
</style>
