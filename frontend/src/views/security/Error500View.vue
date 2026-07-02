<template>
  <SecurityErrorShell
    code="500"
    title="服务暂时不可用"
    description="系统开小差了，请稍后重试；若持续出现，请携带下方请求编号联系管理员。"
  />
</template>

<script>
import SecurityErrorShell from './SecurityErrorShell.vue'

export default {
  name: 'Error500View',
  components: { SecurityErrorShell }
}
</script>
