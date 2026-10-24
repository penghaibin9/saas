<template>
  <SecurityErrorShell
    code="404"
    title="页面不存在"
    description="您访问的地址不存在或已下线。请从左侧菜单重新进入，或返回首页。"
  />
</template>

<script>
import SecurityErrorShell from './SecurityErrorShell.vue'

export default {
  name: 'Error404View',
  components: { SecurityErrorShell }
}
</script>