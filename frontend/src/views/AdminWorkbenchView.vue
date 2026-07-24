<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="工作台"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <WorkbenchView
      v-if="ctx"
      :display-name="displayName"
    />
    <LoadingState v-else text="正在加载工作台…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminWorkbenchView — PC 管理端默认首页（`/`）。
 *
 * P2 角色化工作台：内容区改为 WorkbenchView（真实待办），不再做「菜单桥接卡片墙」。
 * 布局壳复用 BasePortalLayout + navPlan（与学工/实习等中心一致），不破坏一级轨与权限投影。
 *
 * 已移除：演示用「视角」下拉（假切换，会切出无权限死菜单）。
 * 切身份：顶栏 AppUserChip → POST /auth/switch-role（真实令牌轮换后整页刷新）。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import WorkbenchView from '@/modules/workbench/views/WorkbenchView.vue'
import { fetchLayoutContext } from '@/modules/workbench/api/workbench.api'
import { getAuthContext } from '@/security/auth/auth.context'
import router from '@/router'

export default {
  name: 'AdminWorkbenchView',
  components: { BasePortalLayout, LoadingState, WorkbenchView },
  data() {
    return {
      ctx: null,
      auth: getAuthContext()
    }
  },
  computed: {
    brandTitle() {
      const school =
        (this.ctx && this.ctx.tenantBrandConfig && this.ctx.tenantBrandConfig.schoolName) ||
        this.auth.schoolName ||
        '管理端'
      return school + ' · 管理端'
    },
    displayName() {
      const fromCtx =
        this.ctx &&
        this.ctx.currentRole &&
        (this.ctx.currentRole.userName || this.ctx.currentRole.roleName)
      return fromCtx || this.auth.displayName || '老师'
    }
  },
  created() {
    this.loadCtx()
  },
  methods: {
    async loadCtx() {
      try {
        this.ctx = await fetchLayoutContext()
      } catch {
        // fetchLayoutContext 内部已吞掉子请求失败；此处兜底保证壳可开
        this.ctx = {
          tenantBrandConfig: { schoolName: this.auth.schoolName || '管理端' },
          currentRole: {
            roleCode: (this.auth.roles && this.auth.roles[0]) || '',
            roleType: (this.auth.roles && this.auth.roles[0]) || '',
            roleName: '',
            userName: this.auth.displayName || ''
          },
          dataScope: { scopeName: '' },
          permissionPatterns: null,
          ctxKey: ''
        }
      }
    },
    onMenuSelect(item) {
      if (item?.path && item.path !== this.$route.fullPath.split('#')[0]) {
        router.push(item.path).catch(() => {})
      }
    }
  }
}
</script>
