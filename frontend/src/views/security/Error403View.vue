<template>
  <SecurityErrorShell
    :code="isServiceError ? '503' : '403'"
    :title="isServiceError ? '权限服务加载失败' : '无权访问'"
    :description="description"
  />
</template>

<script>
import SecurityErrorShell from './SecurityErrorShell.vue'

export default {
  name: 'Error403View',
  components: { SecurityErrorShell },
  computed: {
    isServiceError() {
      return this.$route.query.reason === 'permission-service'
    },
    description() {
      if (this.isServiceError) {
        return this.$route.query.message
          || '无法加载当前账号的权限上下文。请刷新页面重试；若持续失败请联系管理员，勿将此情况当作「未开通权限」。'
      }
      return '当前账号没有访问该页面或资源的权限。如需开通，请联系学校管理员。'
    }
  }
}
</script>
