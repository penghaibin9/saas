<template>
  <AppLifecycleBanner v-bind="$attrs" />
</template>

<script>
import AppLifecycleBanner from './AppLifecycleBanner.vue'

export default {
  name: 'LifecycleTimeline',
  components: { AppLifecycleBanner },
  inheritAttrs: false
}
</script>
