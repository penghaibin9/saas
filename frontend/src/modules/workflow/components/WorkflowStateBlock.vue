<template>
  <div class="wf-state-block">
    <!-- noLicense：不展示业务数据 -->
    <AppGlobalState
      v-if="viewState === 'NO_LICENSE'"
      state="noLicense"
      title="权限与流程模块未授权"
      description="当前学校尚未开通该模块，如需使用请联系学校管理员或服务商"
    />
    <template v-else>
      <!-- readonly：可看，写操作由页面按钮 disabled 承担，此处只给轻提示 -->
      <AppInlineAlert
        v-if="viewState === 'READONLY'"
        type="warning"
        title="模块已到期，当前为只读模式"
        description="历史数据可查看，启停/审批等写操作已禁用；续费请联系管理员。"
        class="wf-state-block__readonly"
      />
      <AppGlobalState :state="dataState" :description="errorMessage" @retry="$emit('retry')">
        <slot />
      </AppGlobalState>
    </template>
  </div>
</template>

<script>
/**
 * WorkflowStateBlock —— workflow 模块统一页面状态入口。
 * 五态：loading / empty / error / readonly / noLicense（readonly 叠加在数据态之上）。
 * 兼容 licenseContext 冻结优先级：NO_LICENSE > READONLY > 数据态。
 */
import AppGlobalState from '@/components/common/AppGlobalState.vue'
import AppInlineAlert from '@/components/common/AppInlineAlert.vue'

export default {
  name: 'WorkflowStateBlock',
  components: { AppGlobalState, AppInlineAlert },
  props: {
    loading: { type: Boolean, default: false },
    error: { type: String, default: '' },
    empty: { type: Boolean, default: false },
    /** NORMAL | READONLY | NO_LICENSE */
    viewState: { type: String, default: 'NORMAL' }
  },
  emits: ['retry'],
  computed: {
    dataState() {
      if (this.loading) return 'loading'
      if (this.error) return 'error'
      if (this.empty) return 'empty'
      return 'ready'
    },
    errorMessage() {
      return this.error || ''
    }
  }
}
</script>

<style scoped>
.wf-state-block__readonly {
  margin-bottom: var(--space-4);
}
</style>
