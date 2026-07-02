<template>
  <SecurityErrorShell
    code="401"
    title="登录状态已失效"
    description="您尚未登录或登录状态已失效，请重新登录后继续操作。"
  />
</template>

<script>
import SecurityErrorShell from './SecurityErrorShell.vue'

export default {
  name: 'Error401View',
  components: { SecurityErrorShell }
}
</script>
