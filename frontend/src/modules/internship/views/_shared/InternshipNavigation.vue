<template>
  <div class="ix-navigation">
    <nav class="ix-modules" :class="{ 'is-expanded': expanded }" aria-label="岗位实习二级菜单">
      <button
        class="ix-nav-toggle"
        type="button"
        :aria-expanded="expanded"
        :aria-label="expanded ? '收起二级菜单' : '展开二级菜单完整名称'"
        @click="expanded = !expanded"
      >
        {{ expanded ? '«' : '»' }}
      </button>
      <button
        v-for="item in workspaces"
        :key="item.key"
        type="button"
        class="ix-module"
        :class="{ 'is-active': selectedKey === item.key }"
        :title="item.label"
        :aria-label="item.label"
        :aria-expanded="selectedKey === item.key"
        @click="selectedKey = item.key"
      >
        <AppIcon :name="item.icon" :size="17" />
        <span>{{ expanded ? item.label : item.short }}</span>
      </button>
    </nav>
    <nav
      v-if="selected"
      class="ix-pages"
      :class="{ 'is-compact': compact }"
      :aria-label="selected.label + '三级菜单'"
    >
      <button
        class="ix-nav-toggle"
        type="button"
        :aria-expanded="!compact"
        :aria-label="compact ? '展开三级菜单完整名称' : '收起三级菜单'"
        @click="compact = !compact"
      >
        {{ compact ? '»' : '«' }}<span v-if="!compact">{{ selected.label }}</span>
      </button>
      <RouterLink
        v-for="page in selected.children"
        :key="page.path"
        :to="withInternshipBatch(page.path, batchId)"
        class="ix-page"
        :class="{ 'is-active': active.path === page.path && active.workspaceKey === selected.key }"
        :aria-current="
          active.path === page.path && active.workspaceKey === selected.key ? 'page' : undefined
        "
        :title="page.label"
        :aria-label="page.label"
        >{{ compact ? page.label.slice(0, 2) : page.label }}</RouterLink
      >
      <p v-if="!compact" class="ix-nav-hint">{{ selected.hint }}</p>
    </nav>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { AppIcon } from '@/components/ui'
import { internshipLocation, withInternshipBatch } from '../../navigation.js'

const props = defineProps({
  workspaces: { type: Array, default: () => [] },
  batchId: { type: String, default: '' }
})
const route = useRoute()
const expanded = ref(false)
const compact = ref(false)
const selectedKey = ref('')
const active = computed(() => internshipLocation(route.fullPath, props.workspaces))
const selected = computed(() => props.workspaces.find((item) => item.key === selectedKey.value))
watch(
  [() => route.fullPath, () => props.workspaces],
  () => {
    const owner = internshipLocation(route.fullPath).workspaceKey
    selectedKey.value =
      active.value.workspaceKey ||
      props.workspaces.find((item) => item.key === owner)?.key ||
      props.workspaces[0]?.key ||
      ''
  },
  { immediate: true }
)
</script>

<style scoped>
.ix-navigation {
  display: flex;
  height: 100%;
  color: var(--t2);
  font-size: 12px;
}
.ix-modules {
  width: 74px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 6px;
  border-right: 1px solid var(--card-b);
  background: var(--bg);
  overflow-y: auto;
}
.ix-modules.is-expanded {
  width: 154px;
}
.ix-nav-toggle {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 38px;
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--t3);
  font: inherit;
  cursor: pointer;
  text-align: left;
  padding: 0 12px;
}
.ix-module {
  display: flex;
  align-items: center;
  gap: 7px;
  min-height: 39px;
  width: 100%;
  padding: 8px;
  border: 0;
  border-radius: 5px;
  background: transparent;
  color: var(--t2);
  font: inherit;
  text-align: left;
  cursor: pointer;
  white-space: nowrap;
}
.ix-module.is-active,
.ix-page.is-active {
  background: var(--pri-bg);
  color: var(--pri);
  box-shadow: inset 2px 0 var(--pri);
  font-weight: 600;
}
.ix-pages {
  width: 164px;
  flex-shrink: 0;
  overflow-y: auto;
  padding: 8px 6px;
  background: var(--card);
}
.ix-pages.is-compact {
  width: 66px;
}
.ix-page {
  display: block;
  margin: 4px 0;
  padding: 11px 10px;
  border-radius: 5px;
  color: var(--t2);
  text-decoration: none;
  line-height: 1.5;
}
.ix-module:hover,
.ix-page:hover {
  background: var(--fill-2, var(--pri-bg));
  color: var(--pri);
}
.ix-nav-hint {
  margin: 24px 10px;
  color: var(--t3);
  font-size: 11px;
  line-height: 1.8;
}
button:focus-visible,
a:focus-visible {
  outline: 2px solid var(--pri);
  outline-offset: -2px;
}
@media (max-width: 760px) {
  .ix-navigation {
    height: auto;
    flex-direction: column;
  }
  .ix-modules,
  .ix-modules.is-expanded {
    width: 100%;
    flex-direction: row;
    overflow-x: auto;
    border-right: 0;
    border-bottom: 1px solid var(--card-b);
  }
  .ix-modules .ix-nav-toggle {
    display: none;
  }
  .ix-module {
    width: auto;
    flex-shrink: 0;
  }
  .ix-pages,
  .ix-pages.is-compact {
    display: flex;
    align-items: center;
    width: 100%;
    overflow-x: auto;
    gap: 5px;
    padding: 4px 8px;
  }
  .ix-pages .ix-nav-toggle,
  .ix-nav-hint {
    display: none;
  }
  .ix-page {
    white-space: nowrap;
    flex-shrink: 0;
    padding: 7px 10px;
  }
}
</style>
