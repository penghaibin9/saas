<template>
  <BasePortalLayout :title="brandTitle" :subtitle="subtitle" :menus="[]" :ctx="ctx" @menu-select="onMenu">
    <div class="pp-body">
      <template v-if="mod">
        <!-- 面包屑 + 状态 -->
        <div class="pp-crumb">
          {{ group.label }} / {{ mod.label }}<template v-if="leaf"> / {{ leaf.label }}</template>
        </div>
        <div class="pp-hero">
          <span class="pp-badge">规划中 · 待施工</span>
          <h1 class="pp-title">{{ leaf ? leaf.label : mod.label }}</h1>
          <p class="pp-desc">
            该功能已列入总施工图，尚未开始施工。本页为规划占位页，仅展示规划信息，不含任何业务数据。
          </p>
          <p v-if="info && info.why" class="pp-why">{{ info.why }}</p>
        </div>

        <!-- 本模块三级清单（真实状态；已实现项可直接进入） -->
        <div class="pp-card">
          <div class="pp-card__head">「{{ mod.label }}」三级页面清单</div>
          <ul class="pp-leaves">
            <li
              v-for="(lf, i) in mod.children"
              :key="i"
              class="pp-leaf"
              :class="{ 'is-current': leafIdx === i, 'is-done': lf.status === 'implemented' || lf.status === 'partial' }"
            >
              <span class="pp-leaf__dot" :class="'st-' + lf.status"></span>
              <a
                v-if="lf.path"
                href="javascript:void(0)"
                class="pp-leaf__link"
                @click="go(lf.path)"
              >{{ lf.label }}</a>
              <span v-else class="pp-leaf__link">{{ lf.label }}</span>
              <span class="pp-leaf__st" :class="'st-' + lf.status">{{ statusText(lf.status) }}</span>
            </li>
          </ul>
          <div v-if="!mod.children.length" class="pp-empty">该模块为单页模块，无三级子项</div>
        </div>

        <!-- 施工卡（仅 DEV / 学校管理员 / 平台角色可见，与侧栏施工地图开关同一口径） -->
        <div v-if="canSeeConstruction && info" class="pp-card pp-card--dev">
          <div class="pp-card__head">
            施工卡
            <span v-if="info.ord" class="pp-chip">顺序 {{ info.ord }}</span>
            <span v-if="info.pkg" class="pp-chip">{{ info.pkg }}</span>
          </div>
          <div v-if="info.instruction" class="pp-instr">
            <pre class="pp-instr__pre">{{ info.instruction }}</pre>
            <button type="button" class="pp-copy" @click="copyInstruction">
              {{ copied ? '已复制 ✓' : '复制推进指令发给 Claude' }}
            </button>
          </div>
          <div v-else class="pp-empty">暂无推进指令</div>
        </div>

        <div class="pp-actions">
          <button type="button" class="pp-back" @click="goBack">← 返回上一页</button>
        </div>
      </template>

      <template v-else>
        <div class="pp-hero">
          <h1 class="pp-title">未找到该规划模块</h1>
          <p class="pp-desc">链接可能已过期，请从左侧菜单重新进入。</p>
          <div class="pp-actions">
            <button type="button" class="pp-back" @click="goBack">← 返回上一页</button>
          </div>
        </div>
      </template>
    </div>
  </BasePortalLayout>
</template>

<script>
/**
 * PlannedPlaceholderView — 规划占位页（CLAUDE.md §42，2026-07-11 甲方拍板）。
 * 路由：/admin/planned/:groupKey/:modKey/:leafIdx?
 * 定位：全系统 planned 菜单项的唯一公共落地页——按 navPlan + constructionMap
 * 展示该模块的规划信息（所属中心、三级清单与真实状态、施工顺序、推进指令）。
 * 红线：不调用任何业务 API；无假按钮、假数据、假写操作；planned 状态不因本页存在而改变。
 * 施工卡区域（施工包/推进指令）仅 DEV 构建或 SCHOOL_ADMIN / PLATFORM / PLATFORM_SUPER_ADMIN
 * 可见——与 BasePortalLayout.canTogglePlannerMap 同一口径，正式角色只见中性说明。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { NAV_PLAN } from '@/config/navPlan'
import { getConstructionInfo } from '@/config/constructionMap'
import { getAuthContext } from '@/security/auth/auth.context'

const STATUS_TEXT = {
  implemented: '已实现',
  partial: '待补强',
  planned: '待施工',
  unauthorized: '未开通'
}

export default {
  name: 'PlannedPlaceholderView',
  components: { BasePortalLayout },
  data() {
    return { auth: getAuthContext(), copied: false, copyTimer: null }
  },
  computed: {
    group() {
      return NAV_PLAN.find((g) => g.key === this.$route.params.groupKey) || null
    },
    mod() {
      if (!this.group) return null
      return this.group.children.find((m) => m.key === this.$route.params.modKey) || null
    },
    leafIdx() {
      const raw = this.$route.params.leafIdx
      if (raw === undefined || raw === '') return -1
      const n = Number(raw)
      return Number.isInteger(n) && n >= 0 && this.mod && n < this.mod.children.length ? n : -1
    },
    leaf() {
      return this.leafIdx >= 0 ? this.mod.children[this.leafIdx] : null
    },
    info() {
      if (!this.group || !this.mod) return null
      return getConstructionInfo(this.group.key, this.mod.label)
    },
    roleType() {
      return (this.auth.roles && this.auth.roles[0]) || ''
    },
    canSeeConstruction() {
      if (import.meta.env && import.meta.env.DEV) return true
      return this.roleType === 'SCHOOL_ADMIN' || this.roleType === 'PLATFORM' || this.roleType === 'PLATFORM_SUPER_ADMIN'
    },
    ctx() {
      return {
        tenantBrandConfig: { schoolName: this.auth.schoolName },
        currentRole: { roleType: this.roleType || 'SCHOOL_ADMIN', userName: this.auth.displayName }
      }
    },
    brandTitle() {
      return (this.auth.schoolName || '管理端') + ' · 管理端'
    },
    subtitle() {
      return this.group && this.mod ? `${this.group.label} · ${this.mod.label}` : '规划模块'
    }
  },
  watch: {
    '$route.params'() {
      this.copied = false
    }
  },
  beforeUnmount() {
    clearTimeout(this.copyTimer)
  },
  methods: {
    statusText(s) {
      return STATUS_TEXT[s] || s
    },
    go(path) {
      if (path && path !== this.$route.fullPath) this.$router.push(path)
    },
    goBack() {
      const back = this.$router.options.history.state.back
      if (back && String(back).startsWith('/admin')) this.$router.back()
      else this.$router.push('/workbench')
    },
    onMenu(item) {
      if (item && item.path && item.path !== this.$route.path) this.$router.push(item.path)
    },
    async copyInstruction() {
      if (!this.info || !this.info.instruction) return
      try {
        await navigator.clipboard.writeText(this.info.instruction)
        this.copied = true
        clearTimeout(this.copyTimer)
        this.copyTimer = setTimeout(() => {
          this.copied = false
        }, 1500)
      } catch {
        /* 剪贴板不可用（非 https 等）时静默降级：用户可手动选中复制 */
      }
    }
  }
}
</script>

<style scoped>
.pp-body {
  max-width: 860px;
}
.pp-crumb {
  font-size: 12.5px;
  color: var(--t3);
  margin-bottom: 10px;
}
.pp-hero {
  margin-bottom: 18px;
}
.pp-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  color: #92400e;
  background: #fef3c7;
  border: 1px solid #fde68a;
  border-radius: 20px;
  padding: 3px 12px;
}
.pp-title {
  margin: 10px 0 6px;
  font-size: 22px;
  font-weight: var(--font-weight-bold);
  letter-spacing: -0.01em;
}
.pp-desc {
  margin: 0;
  font-size: 13.5px;
  color: var(--t2);
  line-height: 1.7;
}
.pp-why {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--t2);
  line-height: 1.7;
  background: var(--pri-bg);
  border: 1px solid var(--pri-100);
  border-radius: 10px;
  padding: 10px 14px;
}
.pp-card {
  background: var(--card);
  border: 1px solid var(--card-b);
  border-radius: 14px;
  padding: 16px 18px;
  margin-bottom: 14px;
}
.pp-card--dev {
  border-style: dashed;
}
.pp-card__head {
  font-size: 14px;
  font-weight: var(--font-weight-semibold);
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.pp-chip {
  font-size: 11px;
  font-weight: var(--font-weight-medium);
  color: var(--pri);
  background: var(--pri-bg);
  border: 1px solid var(--pri-100);
  border-radius: 12px;
  padding: 2px 10px;
}
.pp-leaves {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.pp-leaf {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  border-radius: 9px;
  font-size: 13px;
}
.pp-leaf.is-current {
  background: var(--pri-bg);
}
.pp-leaf__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #cbd5e1;
}
.pp-leaf__dot.st-implemented {
  background: #10b981;
}
.pp-leaf__dot.st-partial {
  background: #f59e0b;
}
.pp-leaf__link {
  color: var(--t1);
  text-decoration: none;
  cursor: pointer;
}
.pp-leaf:not(.is-done) .pp-leaf__link {
  color: var(--t2);
}
.pp-leaf__st {
  margin-left: auto;
  font-size: 11px;
  color: var(--t3);
}
.pp-leaf__st.st-implemented {
  color: #059669;
}
.pp-leaf__st.st-partial {
  color: #b45309;
}
.pp-empty {
  font-size: 12.5px;
  color: var(--t3);
  padding: 6px 2px;
}
.pp-instr__pre {
  margin: 0 0 10px;
  padding: 12px 14px;
  background: var(--pri-bg, #f8fafc);
  border: 1px solid var(--card-b);
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 260px;
  overflow: auto;
}
.pp-copy,
.pp-back {
  font-size: 12.5px;
  font-weight: var(--font-weight-medium);
  padding: 7px 14px;
  border-radius: 9px;
  border: 1px solid var(--card-b);
  background: var(--card);
  color: var(--t1);
  cursor: pointer;
}
.pp-copy:hover,
.pp-back:hover {
  background: var(--pri-bg);
}
.pp-actions {
  margin-top: 4px;
}
</style>
