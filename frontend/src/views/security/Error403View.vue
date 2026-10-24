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
          || '权限信息加载失败，请刷新重试；仍失败请联系管理员。'
      }
      return '当前账号无权访问，如需开通请联系学校管理员。'
    }
  }
}
</script>
