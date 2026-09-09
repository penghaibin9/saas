<template>
  <div class="ix-workspace-bar">
    <nav class="ix-tabs" aria-label="已打开的实习页面">
      <div
        v-for="tab in visibleTabs"
        :key="tab.path"
        class="ix-tab"
        :class="{ 'is-active': tab.path === route.fullPath }"
      >
        <RouterLink :to="tab.path" :aria-current="tab.path === route.fullPath ? 'page' : undefined"
          ><AppIcon name="records" :size="14" />{{ tab.label }}</RouterLink
        >
        <button type="button" :aria-label="'关闭' + tab.label" @click="close(tab)">×</button>
      </div>
    </nav>
    <button
      class="ix-star"
      type="button"
      :disabled="!currentLeaf"
      :aria-pressed="isFavorite"
      :aria-label="isFavorite ? '从快捷栏移除当前页' : '将当前页加入快捷栏'"
      @click="toggleFavorite"
    >
      {{ isFavorite ? '★' : '☆' }}
    </button>
    <div class="ix-dock" :class="{ 'is-collapsed': dockCollapsed }">
      <button
        v-if="dockCollapsed"
        type="button"
        class="ix-dock-trigger"
        @click="dockCollapsed = false"
      >
        ☆ 快捷栏
      </button>
      <template v-else>
        <span class="ix-dock-label">我的<br />常用</span>
        <RouterLink
          v-for="item in favorites"
          :key="item.path"
          :to="withInternshipBatch(item.path, batchId)"
          :title="item.label"
          ><AppIcon :name="item.icon" :size="20" /><span>{{ item.label }}</span></RouterLink
        >
        <span v-if="!favorites.length" class="ix-dock-empty">点页签右侧星标，添加常用页面</span>
        <button
          type="button"
          class="ix-dock-trigger"
          aria-label="收起快捷栏"
          @click="dockCollapsed = true"
        >
          ⌄
        </button>
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter, isNavigationFailure } from 'vue-router'
import { AppIcon } from '@/components/ui'
import { internshipLocation, withInternshipBatch } from '../../navigation.js'

const props = defineProps({
  workspaces: { type: Array, default: () => [] },
  batchId: { type: String, default: '' },
  preferenceKey: { type: String, default: '' }
})
const route = useRoute()
const router = useRouter()
const tabs = ref([])
const dockCollapsed = ref(true)
const favoritePaths = ref([])
watch(
  () => props.preferenceKey,
  (key) => {
    try {
      const saved = key
        ? JSON.parse(localStorage.getItem('internship.shortcuts.' + key) || '[]')
        : []
      favoritePaths.value = Array.isArray(saved)
        ? saved.filter((path) => typeof path === 'string').slice(-6)
        : []
    } catch {
      favoritePaths.value = []
    }
  },
  { immediate: true }
)
watch(favoritePaths, (paths) => {
  if (!props.preferenceKey) return
  try {
    localStorage.setItem('internship.shortcuts.' + props.preferenceKey, JSON.stringify(paths))
  } catch {
    /* Session shortcuts still work when storage is unavailable. */
  }
})
const leaves = computed(() =>
  props.workspaces.flatMap((workspace) =>
    workspace.children.map((leaf) => ({ ...leaf, icon: workspace.icon }))
  )
)
const currentLeaf = computed(() => {
  const active = internshipLocation(route.fullPath, props.workspaces)
  return leaves.value.find((leaf) => leaf.path === active.path)
})
const favorites = computed(() =>
  favoritePaths.value.map((path) => leaves.value.find((leaf) => leaf.path === path)).filter(Boolean)
)
const isFavorite = computed(() => favoritePaths.value.includes(currentLeaf.value?.path))
const visibleTabs = computed(() =>
  tabs.value.filter((tab) => leaves.value.some((leaf) => leaf.path === tab.owner))
)
watch(
  [() => route.fullPath, leaves],
  () => {
    if (!currentLeaf.value) return
    const active = internshipLocation(route.fullPath, props.workspaces)
    const isDetail = route.path !== new URL(active.path, 'https://local.invalid').pathname
    const label = isDetail ? route.meta.title || active.label : active.label
    const key = isDetail ? route.path : active.path
    const previous = tabs.value.findIndex((tab) => tab.key === key)
    const tab = { key, path: route.fullPath, label, owner: active.path }
    if (previous >= 0) tabs.value.splice(previous, 1, tab)
    else tabs.value = [...tabs.value.slice(-9), tab]
  },
  { immediate: true }
)
watch(
  () => props.batchId,
  () => {
    tabs.value = tabs.value.filter((tab) => tab.path === route.fullPath)
  }
)
async function close(tab) {
  if (tab.path === route.fullPath) {
    const next = visibleTabs.value.find((item) => item.path !== tab.path)
    const fallback = leaves.value[0]?.path
    if (!next && !fallback) return
    const target = next?.path || withInternshipBatch(fallback, props.batchId)
    if (await router.push(target).then(isNavigationFailure)) return
  }
  tabs.value = tabs.value.filter((item) => item.path !== tab.path)
}
function toggleFavorite() {
  if (!currentLeaf.value) return
  const path = currentLeaf.value.path
  favoritePaths.value = isFavorite.value
    ? favoritePaths.value.filter((item) => item !== path)
    : [...favoritePaths.value.slice(-5), path]
  dockCollapsed.value = false
}
</script>

<style scoped>
.ix-workspace-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 42px;
  padding: 4px 12px;
  background: var(--card);
  border-bottom: 1px solid var(--card-b);
}
.ix-tabs {
  display: flex;
  gap: 5px;
  min-width: 0;
  overflow: auto;
  flex: 1;
}
.ix-tab {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  max-width: 240px;
  border-radius: 5px;
  color: var(--t3);
  border-bottom: 2px solid transparent;
  font-size: 12px;
}
.ix-tab.is-active {
  background: var(--pri-bg);
  color: var(--pri);
  border-bottom-color: var(--pri);
}
.ix-tab a {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 6px 0 6px 9px;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: inherit;
  text-decoration: none;
}
.ix-tab button,
.ix-star,
.ix-dock-trigger {
  border: 0;
  background: transparent;
  color: var(--t3);
  cursor: pointer;
  font: inherit;
  min-width: 28px;
  min-height: 28px;
}
.ix-star {
  font-size: 21px;
}
.ix-star[aria-pressed='true'] {
  color: var(--pri);
}
.ix-star:disabled {
  opacity: 0.4;
  cursor: default;
}
.ix-dock {
  position: fixed;
  bottom: 15px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 18px;
  max-width: calc(100vw - 32px);
  overflow-x: auto;
  padding: 12px 16px;
  border: 1px solid var(--card-b);
  border-radius: 18px;
  background: var(--card);
  box-shadow: 0 8px 24px #233f6b18;
  z-index: 30;
}
.ix-dock.is-collapsed {
  padding: 5px 13px;
  border-radius: 24px;
}
.ix-dock-label,
.ix-dock-empty {
  font-size: 11px;
  color: var(--t3);
  white-space: nowrap;
}
.ix-dock a {
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 7px;
  color: var(--t2);
  text-decoration: none;
  font-size: 11px;
  white-space: nowrap;
}
.ix-dock a :deep(svg) {
  box-sizing: content-box;
  padding: 8px;
  color: var(--pri);
  background: var(--pri-bg);
  border-radius: 10px;
}
button:focus-visible,
a:focus-visible {
  outline: 2px solid var(--pri);
  outline-offset: 2px;
}
</style>
