<template>
  <view class="page-wrap">
    <MobileNavBar variant="brand" title="服务大厅" subtitle="按场景办事，不按部门找菜单" />
    <MobileGlobalState :state="state" @retry="load">
      <view class="page-pad" v-if="data">
        <!-- 搜索占位 -->
        <view class="sv__search">
          <text class="sv__search-icon">🔍</text>
          <text class="sv__search-ph">搜索服务，如「请假」「证明」</text>
        </view>

        <!-- 分类筛选 -->
        <view class="sv__cats">
          <view class="sv__cat" :class="{ 'is-active': cat === 'all' }" @click="cat = 'all'">全部</view>
          <view
            v-for="c in data.categories"
            :key="c.key"
            class="sv__cat"
            :class="{ 'is-active': cat === c.key }"
            @click="cat = c.key"
          >{{ c.icon }} {{ c.label }}</view>
        </view>

        <!-- 服务列表 -->
        <view class="stack">
          <MobileActionCard
            v-for="s in filtered"
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
        </view>

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
export default {
  data() { return { data: null, state: 'loading', cat: 'all' } },
  onLoad() { this.load() },
  computed: {
    filtered() {
      if (!this.data) return []
      return this.cat === 'all' ? this.data.items : this.data.items.filter((s) => s.cat === this.cat)
    }
  },
  methods: {
    load() {
      this.state = 'loading'
      studentApi.getServices().then((d) => { this.data = d; this.state = 'ready' }).catch(() => { this.state = 'error' })
    },
    catIcon(key) {
      const c = (this.data.categories || []).find((x) => x.key === key)
      return c ? c.icon : '▤'
    },
    apply(s) {
      if (!s.available) return toast('当前不可办理：' + s.desc)
      const q = 'name=' + encodeURIComponent(s.name) + '&dept=' + encodeURIComponent(s.dept) + '&approve=' + (s.needApprove ? '1' : '0')
      go('/pages/student/service-apply/index?' + q)
    }
  }
}
</script>

<style scoped>
.sv__search { display: flex; align-items: center; gap: var(--space-2); background: var(--bg-card); border-radius: var(--radius-full); padding: 10px var(--space-4); margin-bottom: var(--space-4); box-shadow: var(--shadow-card); }
.sv__search-ph { color: var(--text-tertiary); font-size: var(--font-size-base); }
.sv__cats { display: flex; flex-wrap: wrap; gap: var(--space-2); margin-bottom: var(--space-4); }
.sv__cat { padding: 6px 14px; border-radius: var(--radius-full); background: var(--bg-card); font-size: var(--font-size-sm); color: var(--text-secondary); border: 1px solid var(--border-base); }
.sv__cat.is-active { background: var(--brand-primary); color: #fff; border-color: var(--brand-primary); }
.sv__unavailable { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.sv__foot { text-align: center; margin-top: var(--space-5); }
</style>
