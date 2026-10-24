<template>
  <SecurityErrorShell
    code="500"
    title="服务暂时不可用"
    description="请稍后重试；仍无法使用时，请联系管理员。"
  />
</template>

<script>
import SecurityErrorShell from './SecurityErrorShell.vue'

export default {
  name: 'Error500View',
  components: { SecurityErrorShell }
}
</script>
