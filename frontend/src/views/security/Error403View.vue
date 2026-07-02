<template>
  <SecurityErrorShell
    code="403"
    title="无权访问"
    description="当前账号没有访问该页面或资源的权限。如需开通，请联系学校管理员。"
  />
</template>

<script>
import SecurityErrorShell from './SecurityErrorShell.vue'

export default {
  name: 'Error403View',
  components: { SecurityErrorShell }
}
</script>
