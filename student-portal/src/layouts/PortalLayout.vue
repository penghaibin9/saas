<template>
  <PortalLayoutV5 />
  <button
    v-if="activeModulePath === 'graduation'"
    class="graduation-material-link"
    type="button"
    @click="toggleGraduationView"
  >
    {{ route.name === 'graduation-material-library' ? '返回毕业设计工作台' : '我的材料库' }}
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PortalLayoutV5 from './PortalLayoutV5.vue'

const route = useRoute()
const router = useRouter()
const activeModulePath = computed(() => route.meta?.modulePath || route.path.replace(/^\//, '').split('/')[0])

function toggleGraduationView() {
  router.push(route.name === 'graduation-material-library' ? '/graduation' : '/graduation/materials')
}
</script>

<style scoped>
.graduation-material-link {
  position: fixed;
  z-index: 60;
  top: 18px;
  right: 390px;
  min-height: 34px;
  padding: 0 14px;
  border: 1px solid color-mix(in srgb, var(--pri, #2f6bff) 28%, #fff);
  border-radius: 10px;
  background: color-mix(in srgb, var(--pri, #2f6bff) 8%, #fff);
  color: var(--pri, #2f6bff);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}
.graduation-material-link:hover {
  background: color-mix(in srgb, var(--pri, #2f6bff) 14%, #fff);
}
@media (max-width: 1180px) {
  .graduation-material-link { right: 330px; }
}
</style>
