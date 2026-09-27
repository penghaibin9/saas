<template>
  <AppGlobalState state="forbidden" :title="title" :description="description" @back="$emit('back')" />
</template>

<script>
/** NoPermissionState — 无权限状态（模块局部语义化别名，底层复用 AppGlobalState）。 */
import { AppGlobalState } from '@/components/common'

export default {
  name: 'NoPermissionState',
  components: { AppGlobalState },
  props: {
    title: { type: String, default: '暂无访问权限' },
    description: { type: String, default: '当前角色的数据范围不包含本页面内容，如需访问请联系管理员调整权限。' }
  },
  emits: ['back']
}
</script>
