<template>
  <AppStepGuide v-if="steps.length" v-model="open" :steps="steps" @finish="open = false" @skip="open = false" />
</template>

<script>
import AppStepGuide from './AppStepGuide.vue'

export default {
  name: 'AppPageGuide',
  components: { AppStepGuide },
  props: {
    guideKey: { type: String, required: true },
    autoOpen: { type: Boolean, default: true },
    steps: { type: Array, default: () => [] }
  },
  data() { return { open: false } },
  mounted() {
    if (this.autoOpen && this.steps.length) this.open = true
  }
}
</script>
