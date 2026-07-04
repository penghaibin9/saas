<template>
  <AppGlobalState state="loading" :loading-text="text" />
</template>

<script>
/** LoadingState — 加载骨架状态（AppGlobalState 的语义化别名）。 */
import { AppGlobalState } from '@/components/common'

export default {
  name: 'LoadingState',
  components: { AppGlobalState },
  props: {
    text: { type: String, default: '正在加载数据…' }
  }
}
</script>
