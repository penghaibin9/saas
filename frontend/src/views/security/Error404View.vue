<template>
  <SecurityErrorShell
    code="404"
    title="页面不存在"
    :description="description"
  />
</template>

<script>
/**
 * Error404View — 未匹配任何路由时的兜底页（全局 catch-all）。
 * 复用 SecurityErrorShell，提供「返回首页」出口，避免旧书签 / 误输入 URL / 已下线深链接白屏。
 */
import SecurityErrorShell from './SecurityErrorShell.vue'

export default {
  name: 'Error404View',
  components: { SecurityErrorShell },
  computed: {
    description() {
      const from = this.$route.query.from || this.$route.fullPath
      return `未找到「${from}」对应的页面，可能链接已变更或页面已下线。请通过左侧菜单或返回首页继续操作。`
    }
  }
}
</script>
