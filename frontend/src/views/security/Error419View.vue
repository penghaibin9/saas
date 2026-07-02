<template>
  <SecurityErrorShell
    code="419"
    title="会话已超时"
    description="您长时间未操作或请求校验已失效，为保护数据安全已中断本次会话，请重新登录。"
  />
</template>

<script>
import SecurityErrorShell from './SecurityErrorShell.vue'

export default {
  name: 'Error419View',
  components: { SecurityErrorShell }
}
</script>
