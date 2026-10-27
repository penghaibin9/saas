<template>
  <BasePortalLayout
    :title="brandTitle"
    subtitle="学工中心 · 学生画像"
    :ctx="ctx"
    @menu-select="onMenuSelect"
  >
    <div v-if="ctx?.dictionaryUnavailable" class="dictionary-read-warning" role="status">学校字典读取不完整，当前暂用业务内置名称；不代表本校配置已生效。<button type="button" @click="loadContext">重新读取</button></div>
    <router-view v-if="ctx" :key="ctxVersion" :ctx="ctx" />
    <LoadingState v-else text="正在加载学生中心…" />
  </BasePortalLayout>
</template>

<script>
/**
 * AdminStudentLayout — /admin/student 父布局。
 * P6：已移除「演示角色」假切换；切身份须走真实 /auth/switch-role。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { LoadingState } from '@/components/business'
import { studentApi } from '@/modules/student/api/student.api'
import { registerStudentRoutes } from '@/modules/student/student.routes'

export default {
  name: 'AdminStudentLayout',
  components: { BasePortalLayout, LoadingState },
  provide() { return { affairsWorkspace: true, conciseBusinessHeader: true } },
  data() {
    return { ctx: null, ctxVersion: 0 }
  },
  computed: {
    brandTitle() {
      if (!this.ctx) return '管理端'
      return this.ctx.tenantBrandConfig.schoolName + ' · 管理端'
    }
  },
  async created() {
    registerStudentRoutes(this.$router)
    await this.loadContext()
  },
  methods: {
    async loadContext() {
      const res = await studentApi.getContext()
      if (res.code === 0) {
        this.ctx = res.data
        this.ctxVersion++
      }
    },
    onMenuSelect(item) {
      if (item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>
<style scoped>
.dictionary-read-warning { margin: 12px; padding: 12px; border: 1px solid var(--warning-500, #d97706); border-radius: 8px; }
.dictionary-read-warning button { margin-left: 12px; }
</style>
