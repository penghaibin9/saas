<template>
  <nav class="sa-v6-workspace-nav" aria-label="学工业务工作区">
    <header class="sa-v6-workspace-nav__header">
      <div class="sa-v6-workspace-nav__title-row">
        <div>
          <strong>学工工作区</strong>
          <span>二级组织工作区，三级进入真实页面</span>
        </div>
        <b :title="`${meta.formalPageCount} 个正式三级入口 / ${meta.allNodeCount} 个页面节点`">
          {{ meta.workspaceCount }}×{{ meta.allNodeCount }}
        </b>
      </div>
    </header>

    <div class="sa-v6-workspace-nav__list">
      <template v-for="workspace in workspaces" :key="workspace.id">
        <section
          class="sa-v6-workspace"
          :class="{
            'is-route-active': workspace.id === routeWorkspaceId,
            'is-expanded': workspace.id === expandedWorkspaceId,
            'is-locked': !firstAccessibleLeaf(workspace)
          }"
          :data-workspace="workspace.id"
        >
          <button
            type="button"
            class="sa-v6-workspace__head"
            :aria-expanded="workspace.id === expandedWorkspaceId"
            :aria-current="workspace.id === routeWorkspaceId ? 'page' : undefined"
            :disabled="!firstAccessibleLeaf(workspace)"
            :title="`${workspace.title}：${workspace.subtitle}`"
            @click="selectWorkspace(workspace)"
          >
            <span class="sa-v6-workspace__no">{{ workspace.no }}</span>
            <span class="sa-v6-workspace__name">{{ workspace.title }}</span>
            <span class="sa-v6-workspace__count">{{ formalCount(workspace) }}</span>
            <span class="sa-v6-workspace__caret" aria-hidden="true">›</span>
          </button>

          <div v-if="workspace.id === expandedWorkspaceId" class="sa-v6-workspace__detail">
            <p class="sa-v6-workspace__subtitle">{{ workspace.subtitle }}</p>

            <div
              v-if="workspace.groups.length > 1"
              class="sa-v6-workspace__groups"
              role="tablist"
              :aria-label="`${workspace.title}页面分组`"
            >
              <button
                v-for="item in workspace.groups"
                :key="item.id"
                type="button"
                role="tab"
                class="sa-v6-workspace__group"
                :class="{ 'is-on': item.id === selectedGroupId(workspace) }"
                :aria-selected="item.id === selectedGroupId(workspace)"
                @click.stop="selectGroup(workspace, item)"
              >{{ item.label }}</button>
            </div>

            <div class="sa-v6-workspace__leaves" role="tabpanel">
              <button
                v-for="leafItem in selectedGroup(workspace).leaves"
                :key="leafItem.id"
                type="button"
                class="sa-v6-workspace__leaf"
                :class="{
                  'is-on': isLeafActive(leafItem),
                  'is-locked': isLeafLocked(leafItem)
                }"
                :disabled="isLeafLocked(leafItem)"
                :aria-current="isLeafActive(leafItem) ? 'page' : undefined"
                :title="isLeafLocked(leafItem) ? `${leafItem.label}：当前身份无权限` : `${leafItem.label} · ${leafItem.kind}`"
                @click="navigateLeaf(leafItem)"
              >
                <span class="sa-v6-workspace__dot" aria-hidden="true" />
                <span class="sa-v6-workspace__leaf-label">{{ leafItem.label }}</span>
                <span v-if="isLeafLocked(leafItem)" class="sa-v6-workspace__lock" aria-hidden="true">锁</span>
                <span v-else class="sa-v6-workspace__leaf-type" aria-hidden="true">{{ typeLabel(leafItem) }}</span>
              </button>
            </div>

            <div
              v-if="workspace.id === routeWorkspaceId && !hasActiveFormalLeaf(workspace)"
              class="sa-v6-workspace__drill-current"
            >
              <small>当前对象下钻</small>
              <b :title="currentRouteTitle">{{ currentRouteTitle }}</b>
            </div>
          </div>
        </section>
      </template>
    </div>

    <footer class="sa-v6-workspace-nav__footer">
      <span>{{ meta.formalPageCount }} 个正式三级入口</span>
      <small>对象详情、兼容路由和专项下钻通过页面对象与顶部搜索进入</small>
    </footer>
  </nav>
</template>

<script>
import { matchPermission } from '@/config/navPlan'
import {
  STUDENT_AFFAIRS_WORKSPACE_META,
  STUDENT_AFFAIRS_WORKSPACES
} from '@/modules/studentAffairs/config/studentAffairsWorkspaceNavigation'

function parseTarget(rawPath) {
  const value = String(rawPath || '')
  const hashIndex = value.indexOf('#')
  const withoutHash = hashIndex >= 0 ? value.slice(0, hashIndex) : value
  const hash = hashIndex >= 0 ? value.slice(hashIndex) : ''
  const queryIndex = withoutHash.indexOf('?')
  const path = queryIndex >= 0 ? withoutHash.slice(0, queryIndex) : withoutHash
  const query = new URLSearchParams(queryIndex >= 0 ? withoutHash.slice(queryIndex + 1) : '')
  return { path, query, hash }
}

export default {
  name: 'StudentAffairsWorkspaceNav',
  props: {
    ctx: { type: Object, default: null }
  },
  data() {
    return {
      meta: STUDENT_AFFAIRS_WORKSPACE_META,
      workspaces: STUDENT_AFFAIRS_WORKSPACES,
      expandedWorkspaceId: 'today',
      selectedGroups: {}
    }
  },
  computed: {
    permissionPatterns() {
      return Array.isArray(this.ctx?.permissionPatterns) ? this.ctx.permissionPatterns : []
    },
    currentRouteTitle() {
      return String(this.$route?.meta?.title || '当前详情页')
    },
    routeWorkspaceId() {
      const scored = []
      for (const workspace of this.workspaces) {
        let score = -1
        for (const item of workspace.groups) {
          for (const leafItem of item.leaves) score = Math.max(score, this.leafMatchScore(leafItem))
        }
        const routePath = String(this.$route.path || '')
        for (const prefix of workspace.routePrefixes || []) {
          if (routePath === prefix || routePath.startsWith(`${prefix}/`)) score = Math.max(score, prefix.length)
        }
        if (score >= 0) scored.push({ id: workspace.id, score })
      }
      scored.sort((a, b) => b.score - a.score)
      return scored[0]?.id || 'today'
    }
  },
  watch: {
    '$route.fullPath': {
      immediate: true,
      handler() {
        this.syncFromRoute()
      }
    }
  },
  methods: {
    formalCount(workspace) {
      return workspace.groups.reduce((total, item) => total + item.leaves.length, 0)
    },
    hasPermission(leafItem) {
      if (!Array.isArray(leafItem.permissionAny) || !leafItem.permissionAny.length) return false
      return leafItem.permissionAny.some((code) => matchPermission(this.permissionPatterns, code))
    },
    typeLabel(leafItem) {
      const kind = String(leafItem.kind || '')
      if (/主工作台|角色首页|主列表|域首页/.test(kind)) return '主'
      if (/配置|闸门/.test(kind)) return '配'
      if (/台账/.test(kind)) return '台'
      if (/统计|驾驶舱/.test(kind)) return '统'
      if (/队列/.test(kind)) return '队'
      if (/归档/.test(kind)) return '档'
      if (/专项|管理专属/.test(kind)) return '专'
      return '页'
    },
    isLeafLocked(leafItem) {
      return !this.hasPermission(leafItem)
    },
    firstAccessibleLeaf(workspace) {
      for (const item of workspace.groups) {
        const found = item.leaves.find((leafItem) => this.hasPermission(leafItem))
        if (found) return found
      }
      return null
    },
    leafMatchScore(leafItem) {
      const target = parseTarget(leafItem.path)
      if (String(this.$route.path || '') !== target.path) return -1
      let score = target.path.length
      for (const [key, value] of target.query.entries()) {
        if (String(this.$route.query?.[key] ?? '') !== value) return -1
        score += 20
      }
      if (target.hash) {
        if (String(this.$route.hash || '') !== target.hash) return -1
        score += 10
      } else if (this.$route.hash) {
        score -= 2
      }
      return score
    },
    isLeafActive(leafItem) {
      if (this.leafMatchScore(leafItem) < 0) return false
      const workspace = this.workspaces.find((item) => item.id === this.routeWorkspaceId)
      if (!workspace) return true
      const candidates = workspace.groups.flatMap((item) => item.leaves)
      const best = Math.max(...candidates.map((item) => this.leafMatchScore(item)))
      return this.leafMatchScore(leafItem) === best
    },
    hasActiveFormalLeaf(workspace) {
      return workspace.groups.some((item) => item.leaves.some((leafItem) => this.isLeafActive(leafItem)))
    },
    activeGroup(workspace) {
      for (const item of workspace.groups) {
        if (item.leaves.some((leafItem) => this.isLeafActive(leafItem))) return item
      }
      return workspace.groups[0]
    },
    selectedGroupId(workspace) {
      return this.selectedGroups[workspace.id] || this.activeGroup(workspace)?.id || workspace.groups[0]?.id
    },
    selectedGroup(workspace) {
      return workspace.groups.find((item) => item.id === this.selectedGroupId(workspace)) || workspace.groups[0]
    },
    selectGroup(workspace, item) {
      this.selectedGroups = { ...this.selectedGroups, [workspace.id]: item.id }
      const target = item.leaves.find((leafItem) => this.hasPermission(leafItem))
      if (target) this.navigateLeaf(target)
    },
    syncFromRoute() {
      this.expandedWorkspaceId = this.routeWorkspaceId
      const workspace = this.workspaces.find((item) => item.id === this.routeWorkspaceId)
      if (workspace) {
        const item = this.activeGroup(workspace)
        if (item) this.selectedGroups = { ...this.selectedGroups, [workspace.id]: item.id }
      }
      this.$nextTick(() => this.scrollActiveWorkspaceIntoView())
    },
    scrollActiveWorkspaceIntoView() {
      const root = this.$el
      if (!root || typeof root.querySelector !== 'function') return
      const active = root.querySelector(`[data-workspace="${this.routeWorkspaceId}"]`)
      active?.scrollIntoView?.({ block: 'nearest' })
    },
    selectWorkspace(workspace) {
      this.expandedWorkspaceId = workspace.id
      const active = this.activeGroup(workspace) || workspace.groups[0]
      if (active) this.selectedGroups = { ...this.selectedGroups, [workspace.id]: active.id }
      if (workspace.id === this.routeWorkspaceId) return
      const target = this.firstAccessibleLeaf(workspace)
      if (target) this.navigateLeaf(target)
    },
    scrollToTargetHash(rawPath) {
      const { hash } = parseTarget(rawPath)
      if (!hash) {
        const main = document.querySelector('.bpl-main')
        main?.scrollTo?.({ top: 0, behavior: 'auto' })
        return
      }
      const id = decodeURIComponent(hash.slice(1))
      const fallbackSelectors = {
        'work-queue': '.sa-v6-queue-card',
        audit: '.sa-dashboard-panel--audit'
      }
      this.$nextTick(() => {
        const fallbackSelector = fallbackSelectors[id]
        const target = document.getElementById(id) || (fallbackSelector ? document.querySelector(fallbackSelector) : null)
        target?.scrollIntoView?.({ block: 'start', behavior: 'auto' })
      })
    },
    navigateLeaf(leafItem) {
      if (this.isLeafLocked(leafItem)) return
      if (leafItem.path === this.$route.fullPath) {
        this.scrollToTargetHash(leafItem.path)
        return
      }
      this.$router.push(leafItem.path)
        .then(() => this.scrollToTargetHash(leafItem.path))
        .catch(() => {})
    }
  }
}
</script>

<style scoped>
.sa-v6-workspace-nav {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  color: var(--text-primary);
}
.sa-v6-workspace-nav__header {
  padding: 2px 6px 9px;
  border-bottom: 1px solid var(--border-light);
}
.sa-v6-workspace-nav__title-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.sa-v6-workspace-nav__title-row > div {
  min-width: 0;
  flex: 1;
}
.sa-v6-workspace-nav__title-row strong,
.sa-v6-workspace-nav__title-row span {
  display: block;
}
.sa-v6-workspace-nav__title-row strong {
  font-size: 15px;
  line-height: 22px;
}
.sa-v6-workspace-nav__title-row span {
  margin-top: 2px;
  color: var(--text-tertiary);
  font-size: 12px;
  line-height: 17px;
}
.sa-v6-workspace-nav__title-row b {
  flex: none;
  padding: 3px 7px;
  border-radius: var(--radius-full);
  background: var(--primary-50);
  color: var(--primary-700);
  font-size: 11px;
  line-height: 17px;
}
.sa-v6-workspace-nav__list {
  min-height: 0;
  flex: 1;
  padding: 7px 0;
}
.sa-v6-workspace {
  margin: 2px 0 5px;
}
.sa-v6-workspace__head {
  display: grid;
  width: 100%;
  min-height: 40px;
  grid-template-columns: 30px minmax(0, 1fr) 24px 14px;
  align-items: center;
  gap: 6px;
  padding: 4px 6px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
}
.sa-v6-workspace__head:hover:not(:disabled) {
  background: var(--bg-section);
  color: var(--text-primary);
}
.sa-v6-workspace__head:disabled {
  cursor: not-allowed;
}
.sa-v6-workspace.is-route-active > .sa-v6-workspace__head {
  background: linear-gradient(90deg, var(--primary-50), color-mix(in srgb, var(--primary-50) 42%, transparent));
  color: var(--primary-700);
  box-shadow: inset 3px 0 0 var(--pri);
}
.sa-v6-workspace__head:focus-visible,
.sa-v6-workspace__group:focus-visible,
.sa-v6-workspace__leaf:focus-visible {
  outline: 2px solid var(--pri);
  outline-offset: 2px;
}
.sa-v6-workspace__no {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--bg-section);
  color: var(--text-tertiary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  font-weight: 800;
}
.sa-v6-workspace.is-route-active .sa-v6-workspace__no {
  background: var(--pri);
  color: var(--text-inverse);
}
.sa-v6-workspace__name {
  min-width: 0;
  overflow: hidden;
  font-size: 13px;
  font-weight: 700;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-workspace__count {
  color: var(--text-tertiary);
  font-size: 11px;
  text-align: right;
}
.sa-v6-workspace__caret {
  color: var(--text-tertiary);
  font-size: 18px;
  line-height: 1;
  transform: rotate(0deg);
  transition: transform 150ms ease;
}
.sa-v6-workspace.is-expanded .sa-v6-workspace__caret {
  transform: rotate(90deg);
}
.sa-v6-workspace.is-locked > .sa-v6-workspace__head {
  opacity: 0.66;
}
.sa-v6-workspace__detail {
  padding: 1px 3px 5px 36px;
}
.sa-v6-workspace__subtitle {
  margin: 1px 4px 5px;
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 16px;
}
.sa-v6-workspace__groups {
  display: flex;
  max-width: 100%;
  gap: 3px;
  margin: 0 0 4px;
  overflow-x: auto;
  scrollbar-width: none;
}
.sa-v6-workspace__groups::-webkit-scrollbar {
  display: none;
}
.sa-v6-workspace__group {
  min-height: 27px;
  flex: none;
  padding: 0 7px;
  border: 1px solid var(--border-light);
  border-radius: 7px;
  background: var(--bg-card);
  color: var(--text-tertiary);
  font-size: 11px;
  white-space: nowrap;
}
.sa-v6-workspace__group.is-on {
  border-color: var(--primary-100);
  background: var(--primary-50);
  color: var(--primary-700);
  font-weight: 700;
}
.sa-v6-workspace__leaves {
  display: grid;
  gap: 1px;
}
.sa-v6-workspace__leaf {
  display: grid;
  width: 100%;
  min-height: 32px;
  grid-template-columns: 7px minmax(0, 1fr) auto;
  align-items: center;
  gap: 7px;
  padding: 4px 7px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
}
.sa-v6-workspace__leaf:hover:not(:disabled) {
  background: var(--bg-section);
  color: var(--text-primary);
}
.sa-v6-workspace__leaf.is-on {
  background: var(--primary-50);
  color: var(--primary-700);
  font-weight: 700;
}
.sa-v6-workspace__leaf.is-locked {
  cursor: not-allowed;
  opacity: 0.5;
}
.sa-v6-workspace__dot {
  width: 5px;
  height: 5px;
  border-radius: var(--radius-full);
  background: var(--border-base);
}
.sa-v6-workspace__leaf.is-on .sa-v6-workspace__dot {
  background: var(--pri);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--pri) 16%, transparent);
}
.sa-v6-workspace__leaf-label {
  min-width: 0;
  overflow: hidden;
  font-size: 12px;
  line-height: 18px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-workspace__lock,
.sa-v6-workspace__leaf-type {
  flex: none;
  min-width: 20px;
  padding: 1px 4px;
  border: 1px solid var(--border-light);
  border-radius: var(--radius-full);
  color: var(--text-tertiary);
  font-size: 9px;
  line-height: 14px;
  text-align: center;
}
.sa-v6-workspace__leaf.is-on .sa-v6-workspace__leaf-type {
  border-color: var(--primary-100);
  color: var(--primary-700);
}
.sa-v6-workspace__drill-current {
  display: grid;
  gap: 1px;
  margin-top: 4px;
  padding: 7px 8px;
  border: 1px dashed var(--border-base);
  border-radius: 8px;
  background: var(--bg-section);
}
.sa-v6-workspace__drill-current small {
  color: var(--text-tertiary);
  font-size: 10px;
  line-height: 14px;
}
.sa-v6-workspace__drill-current b {
  overflow: hidden;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 17px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.sa-v6-workspace-nav__footer {
  display: grid;
  gap: 3px;
  margin-top: auto;
  padding: 9px 7px 2px;
  border-top: 1px solid var(--border-light);
}
.sa-v6-workspace-nav__footer span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
}
.sa-v6-workspace-nav__footer small {
  color: var(--text-tertiary);
  font-size: 11px;
  line-height: 16px;
}
/* V6 学工工作区仅收紧使用本投影的管理端；其他中心不受影响。 */
:global(.base-portal-layout:has(.sa-v6-workspace-nav) .bpl-rail) {
  width: 64px;
}
:global(.base-portal-layout:has(.sa-v6-workspace-nav) .bpl-rail__item) {
  width: 54px;
  padding-block: 8px 6px;
  border-radius: 11px;
}
:global(.base-portal-layout:has(.sa-v6-workspace-nav) .bpl-aside--subnav) {
  width: 214px;
  padding: 12px 8px 10px;
}
@media (max-width: 1280px) {
  :global(.base-portal-layout:has(.sa-v6-workspace-nav) .bpl-aside--subnav) {
    width: 206px;
  }
}
@media (prefers-reduced-motion: reduce) {
  .sa-v6-workspace__caret {
    transition: none;
  }
}
</style>
