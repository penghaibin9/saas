<template>
  <div class="sp-app" :style="{ '--sp-primary': primary }">
    <router-view />
    <div v-if="ui.toast" class="sp-toast">{{ ui.toast }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { usePortalConfigStore } from './stores/portalConfig'
import { useUiStore } from './stores/ui'

const cfg = usePortalConfigStore()
const ui = useUiStore()
// 品牌主色来自 portal-config（不写死）；未加载时用安全默认。
const primary = computed(() => cfg.brand?.primaryColor || '#1677ff')
</script>
