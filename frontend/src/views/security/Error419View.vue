<template>
  <SecurityErrorShell
    code="419"
    title="登录已超时"
    description="登录已超时或校验失效，请重新登录。"
  />
</template>

<script>
import SecurityErrorShell from './SecurityErrorShell.vue'

export default {
  name: 'Error419View',
  components: { SecurityErrorShell }
}
</script>
