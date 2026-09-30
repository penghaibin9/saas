<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="消息中心"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <router-view v-if="ctx" :ctx="ctx" />
    <LoadingState v-else text="正在加载消息中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * MessageCenterLayout — /admin/messages 父布局。
 * 复用工作台壳上下文；侧栏由 navPlan「消息中心」叶子驱动。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import LoadingState from '@/components/business/LoadingState.vue'
import { fetchLayoutContext } from '@/modules/workbench/api/workbench.api'
import { messageCenterPickerAdapters } from '@/modules/messageCenter/pickerAdapters'
import router from '@/router'

export default {
  name: 'MessageCenterLayout',
  components: { BasePortalLayout, LoadingState },
  provide() {
    return { appPickerAdapters: messageCenterPickerAdapters, affairsWorkspace: true, conciseBusinessHeader: true }
  },
  data() {
    return { ctx: null }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      const school =
        (this.ctx.tenantBrandConfig && this.ctx.tenantBrandConfig.schoolName) || '管理端'
      return school + ' · 管理端'
    }
  },
  async created() {
    try {
      this.ctx = await fetchLayoutContext()
    } catch {
      this.ctx = {
        tenantBrandConfig: { schoolName: '管理端' },
        currentRole: { roleCode: '', roleName: '', userName: '' },
        dataScope: { scopeName: '' },
        permissionPatterns: null,
        messageUnreadCount: 0,
        ctxKey: ''
      }
    }
  },
  methods: {
    onMenuSelect(item) {
      if (item?.path && item.path !== this.$route.fullPath.split('#')[0]) {
        router.push(item.path).catch(() => {})
      }
    }
  }
}
</script>
