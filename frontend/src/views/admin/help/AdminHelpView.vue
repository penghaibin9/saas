<template>
  <BasePortalLayout :title="brandTitle" subtitle="帮助中心" :ctx="ctx" @menu-select="onMenu">
    <!-- 左侧：帮助目录（功能帮助 / 业务流程图） -->
    <template #menu>
      <nav class="help-nav">
        <div class="help-nav__head">帮助中心</div>
        <template v-for="sec in sections" :key="sec.key">
          <div class="help-nav__label">{{ sec.label }}</div>
          <a
            v-for="it in sec.items"
            :key="it.id"
            class="help-nav__item"
            :class="{ 'is-active': it.id === currentId }"
            href="javascript:void(0)"
            @click="currentId = it.id"
          >{{ it.title }}</a>
        </template>
      </nav>
    </template>

    <!-- 右侧：选中条目内容 -->
    <div class="help-body">
      <template v-if="current">
        <span class="help-kind">{{ current.type === 'flow' ? '业务流程图' : '功能帮助' }}</span>
        <h1 class="help-title">{{ current.item.title }}</h1>
        <p class="help-summary">{{ current.item.summary }}</p>

        <!-- 功能帮助：要点列表 -->
        <ul v-if="current.type === 'doc'" class="help-points">
          <li v-for="(p, i) in current.item.points" :key="i">{{ p }}</li>
        </ul>

        <!-- 业务流程图：分步流程 -->
        <div v-else class="help-flow">
          <div v-for="(s, i) in current.item.steps" :key="i" class="help-flow__row">
            <div class="help-flow__step">
              <span class="help-flow__no">{{ i + 1 }}</span>
              <div class="help-flow__info">
                <div class="help-flow__name">
                  {{ s.name }}<span class="help-flow__who">{{ s.who }}</span>
                </div>
                <div class="help-flow__detail">{{ s.detail }}</div>
              </div>
            </div>
            <div v-if="i < current.item.steps.length - 1" class="help-flow__arrow">↓</div>
          </div>
        </div>
      </template>
      <div v-else class="help-empty">请选择左侧帮助条目</div>
    </div>
  </BasePortalLayout>
</template>

<script>
/**
 * AdminHelpView — 帮助中心（/admin/help）。
 * 内容源：config/helpContent.js（功能帮助 + 业务流程图，均对应真实模块/流程）。
 * 顶部「功能/帮助」搜索命中帮助条目后，以 ?topic=<id> 跳入并定位。
 */
import BasePortalLayout from '@/layouts/BasePortalLayout.vue'
import { HELP_SECTIONS, HELP_DOCS, getHelpById } from '@/config/helpContent'
import { getAuthContext } from '@/security/auth/auth.context'

export default {
  name: 'AdminHelpView',
  components: { BasePortalLayout },
  data() {
    const auth = getAuthContext()
    return {
      auth,
      sections: HELP_SECTIONS,
      currentId: this.$route.query.topic || (HELP_DOCS[0] && HELP_DOCS[0].id) || ''
    }
  },
  computed: {
    brandTitle() {
      return (this.auth.schoolName || '管理端') + ' · 管理端'
    },
    ctx() {
      return {
        tenantBrandConfig: { schoolName: this.auth.schoolName },
        currentRole: {
          roleType: (this.auth.roles && this.auth.roles[0]) || 'SCHOOL_ADMIN',
          userName: this.auth.displayName
        }
      }
    },
    current() {
      return getHelpById(this.currentId)
    }
  },
  watch: {
    '$route.query.topic'(v) {
      if (v) this.currentId = v
    }
  },
  methods: {
    onMenu(item) {
      if (item && item.path && item.path !== this.$route.path) this.$router.push(item.path)
    }
  }
}
</script>

<style scoped>
/* 左侧帮助目录 */
.help-nav {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
.help-nav__head {
  font-size: 15px;
  font-weight: var(--font-weight-bold);
  padding: 2px 8px 12px;
  border-bottom: 1px solid var(--dv);
  margin-bottom: 8px;
}
.help-nav__label {
  font-size: 10.5px;
  font-weight: var(--font-weight-bold);
  letter-spacing: 0.08em;
  color: var(--t3);
  padding: 12px 8px 5px;
}
.help-nav__item {
  display: block;
  padding: 8px 10px;
  border-radius: 9px;
  font-size: 13px;
  color: var(--t2);
  font-weight: var(--font-weight-medium);
  text-decoration: none;
  transition:
    background 0.15s ease,
    color 0.15s ease;
}
.help-nav__item:hover {
  background: var(--pri-bg);
  color: var(--t1);
}
.help-nav__item.is-active {
  background: var(--pri-bg);
  color: var(--pri);
  font-weight: var(--font-weight-semibold);
}

/* 右侧内容 */
.help-body {
  max-width: 780px;
}
.help-kind {
  display: inline-block;
  font-size: 11px;
  font-weight: var(--font-weight-semibold);
  color: var(--pri);
  background: var(--pri-bg);
  border: 1px solid var(--pri-100);
  border-radius: 20px;
  padding: 3px 12px;
}
.help-title {
  margin: 12px 0 6px;
  font-size: 22px;
  font-weight: var(--font-weight-bold);
  letter-spacing: -0.01em;
}
.help-summary {
  margin: 0 0 20px;
  font-size: 14px;
  color: var(--t2);
  line-height: 1.7;
}
.help-points {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.help-points li {
  position: relative;
  padding: 12px 16px 12px 40px;
  background: var(--card);
  border: 1px solid var(--card-b);
  border-radius: 12px;
  font-size: 13.5px;
  color: var(--t1);
  line-height: 1.6;
}
.help-points li::before {
  content: '✓';
  position: absolute;
  left: 14px;
  top: 12px;
  color: var(--pri);
  font-weight: var(--font-weight-bold);
}

/* 业务流程图 */
.help-flow {
  display: flex;
  flex-direction: column;
  align-items: stretch;
}
.help-flow__row {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.help-flow__step {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  width: 100%;
  padding: 14px 18px;
  background: var(--card);
  border: 1px solid var(--card-b);
  border-radius: 14px;
  box-shadow: var(--s1);
}
.help-flow__no {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--btn-p-bg);
  color: #fff;
  font-size: 13px;
  font-weight: var(--font-weight-bold);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px -4px var(--glow);
}
.help-flow__name {
  font-size: 14.5px;
  font-weight: var(--font-weight-semibold);
  color: var(--t1);
}
.help-flow__who {
  margin-left: 10px;
  font-size: 11.5px;
  font-weight: var(--font-weight-medium);
  color: var(--pri);
  background: var(--pri-bg);
  border-radius: 12px;
  padding: 2px 9px;
}
.help-flow__detail {
  margin-top: 4px;
  font-size: 13px;
  color: var(--t2);
  line-height: 1.6;
}
.help-flow__arrow {
  color: var(--t3);
  font-size: 18px;
  line-height: 1;
  padding: 6px 0;
}
.help-empty {
  padding: 40px;
  text-align: center;
  color: var(--t3);
  font-size: 14px;
}
</style>
