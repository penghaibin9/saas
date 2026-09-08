<template>
  <MiniLoginAuthPanel entry="teacher" :dorm-rectification-id="dormRectificationId" />
</template>

<script>
import MiniLoginAuthPanel from '@/components/login/MiniLoginAuthPanel.vue'

export default {
  components: { MiniLoginAuthPanel },
  data() { return { dormRectificationId: '' } },
  onLoad(q) { this.dormRectificationId = String(q?.dormRectificationId || '') }
}
</script>
