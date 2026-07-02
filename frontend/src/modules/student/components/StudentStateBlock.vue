<template>
  <div class="stu-state-block">
    <AppGlobalState
      v-if="viewState === 'NO_LICENSE'"
      state="noLicense"
      title="学生主档模块未授权"
      description="当前学校尚未开通学生主档模块，如需使用请联系服务商"
    />
    <AppGlobalState
      v-else-if="noPermission"
      state="forbidden"
      title="当前身份无权查看"
      :description="noPermissionText"
    />
    <template v-else>
      <AppInlineAlert
        v-if="viewState === 'READONLY'"
        type="warning"
        title="模块已到期，当前为只读模式"
        description="历史数据可查看，核验/变更/导出等写操作已禁用。"
        class="stu-state-block__readonly"
      />
      <AppGlobalState :state="dataState" :description="error" @retry="$emit('retry')">
        <slot />
      </AppGlobalState>
    </template>
  </div>
</template>

<script>
/**
 * StudentStateBlock — 学生模块统一状态入口
 * 六态：loading / empty / error / noPermission / readonly / noLicense
 */
import AppGlobalState from '@/components/common/AppGlobalState.vue'
import AppInlineAlert from '@/components/common/AppInlineAlert.vue'

export default {
  name: 'StudentStateBlock',
  components: { AppGlobalState, AppInlineAlert },
  props: {
    loading: { type: Boolean, default: false },
    error: { type: String, default: '' },
    empty: { type: Boolean, default: false },
    noPermission: { type: Boolean, default: false },
    noPermissionText: { type: String, default: '原因：缺少学生主档查看权限。建议：联系管理员开通' },
    /** NORMAL | READONLY | NO_LICENSE（licenseContext 预留） */
    viewState: { type: String, default: 'NORMAL' }
  },
  emits: ['retry'],
  computed: {
    dataState() {
      if (this.loading) return 'loading'
      if (this.error) return 'error'
      if (this.empty) return 'empty'
      return 'ready'
    }
  }
}
</script>

<style scoped>
.stu-state-block__readonly {
  margin-bottom: var(--space-4);
}
</style>
