<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="工作台 · 领导驾驶舱"
    :menus="menus"
    :active-key="activeKey"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <ErrorState
      v-else-if="ctxError"
      :description="ctxError"
      @retry="loadContext"
      @back="$router.push('/admin')"
    />
    <LoadingState v-else text="正在加载数据中心真实身份与数据范围…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminDataCenterLayout — /admin/data-center 父布局。
 * 品牌名 / 角色 / 数据范围全部来自 dataCenterApi.getContext()。
 * 上下文服务异常时明确报错并允许重试，绝不构造默认角色/全校范围继续渲染驾驶舱。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { dataCenterApi } from '@/modules/dataCenter/api/dataCenter.api'

const MENUS = [
  { key: 'dc-dashboard', label: '数据驾驶舱', icon: '◫', path: '/admin/data-center' },
  { key: 'dc-lifecycle', label: '生命周期总览', icon: '↻', path: '/admin/data-center/lifecycle' },
  { key: 'dc-rankings', label: '排行分析', icon: '▤', path: '/admin/data-center/rankings' },
  { key: 'dc-risk', label: '风险预警', icon: '◐', path: '/admin/data-center/risk' },
  { key: 'dc-reports', label: '专题报表', icon: '▦', path: '/admin/data-center/reports' }
]

export default {
  name: 'AdminDataCenterLayout',
  components: { BasePortalLayout, LoadingState, ErrorState },
  data() {
    return { menus: MENUS, ctx: null, ctxError: '' }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return this.ctx.tenantBrandConfig.schoolName + ' · 管理端'
    },
    activeKey() {
      const path = this.$route.path
      const hit = [...this.menus]
        .sort((a, b) => b.path.length - a.path.length)
        .find((m) => path === m.path || path.startsWith(m.path + '/'))
      return hit ? hit.key : 'dc-dashboard'
    }
  },
  async created() {
    await this.loadContext()
  },
  methods: {
    async loadContext() {
      this.ctx = null
      this.ctxError = ''
      const res = await dataCenterApi.getContext()
      if (res.code === 0 && res.data) {
        this.ctx = res.data
      } else {
        this.ctxError = res.message || '数据中心身份与数据范围加载失败，请重试'
      }
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>

<style scoped>
.dcl-scope {
  font-size: var(--font-size-xs);
  color: var(--primary-700);
  background: var(--primary-50);
  border: 1px solid var(--primary-100);
  border-radius: var(--radius-full);
  padding: 0 var(--space-3);
  height: 24px;
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}
.dcl-user {
  padding-left: var(--space-4);
  border-left: 1px solid var(--border-base);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}
</style>
