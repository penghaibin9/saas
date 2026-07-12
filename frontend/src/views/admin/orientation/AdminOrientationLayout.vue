<template>
  <BasePortalLayout
    :title="portalTitle"
    subtitle="学工中心 · 数字迎新"
    :ctx="
      brand
        ? {
            tenantBrandConfig: brand,
            currentRole: roles.find((r) => r.roleId === currentRoleId) || {},
            dataScope: { name: dataScopeName }
          }
        : null
    "
    @menu-select="onMenuSelect"
  >
    <template #header-right>
      <label class="ol-role">
        <span class="ol-role__label">当前角色</span>
        <select class="ol-role__select" :value="currentRoleId" @change="onRoleChange($event.target.value)">
          <option v-for="r in roles" :key="r.roleId" :value="r.roleId">{{ r.roleName }}</option>
        </select>
      </label>
    </template>
    <router-view :key="viewKey" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminOrientationLayout — /admin/orientation 模块内布局（不改全局 Layout / 全局菜单）。
 * 门户标题与角色/数据范围来自 orientation.api 的 tenantBrandConfig / currentRole，禁止硬编码。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { getOrientationContext, switchOrientationRole } from '@/modules/orientation/api/orientation.api'

export default {
  name: 'AdminOrientationLayout',
  components: { BasePortalLayout },
  data() {
    return { brand: null, roles: [], currentRoleId: '', dataScopeName: '' }
  },
  computed: {
    portalTitle() {
      if (!this.brand) return '加载中…'
      return `${this.brand.schoolName} · ${this.brand.platformDisplayName}`
    },
    viewKey() {
      return `${this.$route.fullPath}::${this.currentRoleId}`
    }
  },
  async created() {
    await this.loadContext()
  },
  methods: {
    async loadContext() {
      const res = await getOrientationContext()
      if (res.code === 0) this.applyContext(res.data)
    },
    applyContext(ctx) {
      this.brand = ctx.tenantBrandConfig
      this.roles = ctx.roles
      this.currentRoleId = ctx.currentRole.roleId
      this.dataScopeName = ctx.dataScope.name
    },
    async onRoleChange(roleId) {
      const res = await switchOrientationRole(roleId)
      if (res.code === 0) this.applyContext(res.data)
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>

<style scoped>
.ol-role {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}
.ol-role__label {
  font-size: var(--font-size-xs);
  color: var(--text-tertiary);
  white-space: nowrap;
}
.ol-role__select {
  height: 28px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  font-size: var(--font-size-xs);
  padding: 0 var(--space-1);
  outline: none;
}
</style>
