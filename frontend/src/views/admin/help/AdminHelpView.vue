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
            @click="selectTopic(it.id)"
          >{{ it.title }}</a>
        </template>
      </nav>
    </template>

    <!-- 右侧：选中条目内容 -->
    <div
      class="help-body"
      :class="{ 'help-body--wide': current && current.type === 'doc' && current.item.embed }"
    >
      <template v-if="current">
        <span class="help-kind">{{ kindLabel }}</span>
        <h1 class="help-title">{{ current.item.title }}</h1>

        <!-- 任务卡：适用角色 + 入口路径 -->
        <template v-if="current.type === 'card'">
          <div class="help-card-meta">
            <div class="help-card-meta__row">
              <span class="help-card-meta__k">适用角色</span>
              <span class="help-card-meta__roles">
                <span v-for="(r, i) in current.item.roles" :key="i" class="help-role">{{ r }}</span>
              </span>
            </div>
            <div class="help-card-meta__row">
              <span class="help-card-meta__k">入口路径</span>
              <a class="help-card-meta__entry" href="javascript:void(0)" @click="goRoute(current.item.route)">{{ current.item.entry }}</a>
            </div>
          </div>
          <p class="help-summary">{{ current.item.summary }}</p>

          <h2 class="help-h2">操作步骤</h2>
          <ol class="help-steps">
            <li v-for="(s, i) in current.item.steps" :key="i">{{ s }}</li>
          </ol>

          <template v-if="current.item.fields && current.item.fields.length">
            <h2 class="help-h2">需要填写</h2>
            <ul class="help-fields">
              <li v-for="(f, i) in current.item.fields" :key="i">{{ f }}</li>
            </ul>
          </template>

          <template v-if="current.item.faq && current.item.faq.length">
            <h2 class="help-h2">常见问题</h2>
            <div class="help-faq">
              <div v-for="(qa, i) in current.item.faq" :key="i" class="help-faq__item">
                <div class="help-faq__q">Q：{{ qa.q }}</div>
                <div class="help-faq__a">A：{{ qa.a }}</div>
              </div>
            </div>
          </template>

          <template v-if="current.item.related && current.item.related.length">
            <h2 class="help-h2">相关入口</h2>
            <div class="help-related">
              <a
                v-for="(rel, i) in current.item.related"
                :key="i"
                class="help-related__link"
                href="javascript:void(0)"
                @click="goRoute(rel.route)"
              >{{ rel.label }} ↗</a>
            </div>
          </template>
        </template>

        <template v-else-if="current.type === 'doc' && current.item.embed">
          <p class="help-summary">{{ current.item.summary }}</p>
          <iframe
            class="help-embed"
            :src="current.item.embed"
            sandbox="allow-scripts"
            referrerpolicy="no-referrer"
            :title="current.item.title"
          ></iframe>
        </template>

        <template v-else>
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
    },
    kindLabel() {
      if (!this.current) return ''
      if (this.current.type === 'card') return '帮助任务卡'
      if (this.current.type === 'flow') return '业务流程图'
      return '功能帮助'
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
    },
    /** 选中左侧帮助条目：同步 ?topic=<id> 到地址栏，使当前条目可被深链分享/刷新保留。 */
    selectTopic(id) {
      this.currentId = id
      if (this.$route.query.topic !== id) {
        this.$router.replace({ query: { ...this.$route.query, topic: id } }).catch(() => {})
      }
    },
    /** 跳到任务卡指向的真实功能页（含 ?panel= 深链） */
    goRoute(route) {
      if (route) this.$router.push(route)
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
.help-body--wide {
  width: 100%;
  max-width: none;
}
.help-body--wide .help-title {
  font-size: 28px;
}
.help-body--wide .help-summary {
  max-width: 1120px;
  font-size: 17px;
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

/* 任务卡：适用角色 + 入口路径 */
.help-card-meta {
  margin: 12px 0 16px;
  padding: 12px 16px;
  background: var(--card);
  border: 1px solid var(--card-b);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.help-card-meta__row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  font-size: 13px;
}
.help-card-meta__k {
  flex-shrink: 0;
  width: 60px;
  color: var(--t3);
  font-weight: var(--font-weight-semibold);
}
.help-card-meta__roles {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.help-role {
  font-size: 11.5px;
  color: var(--pri);
  background: var(--pri-bg);
  border: 1px solid var(--pri-100);
  border-radius: 12px;
  padding: 2px 10px;
}
.help-card-meta__entry {
  color: var(--pri);
  text-decoration: none;
  font-weight: var(--font-weight-medium);
  line-height: 1.6;
}
.help-card-meta__entry:hover {
  text-decoration: underline;
}

/* 任务卡：小节标题 */
.help-h2 {
  margin: 22px 0 10px;
  font-size: 15px;
  font-weight: var(--font-weight-bold);
  color: var(--t1);
}

/* 任务卡：操作步骤 */
.help-steps {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.help-steps li {
  font-size: 13.5px;
  color: var(--t1);
  line-height: 1.6;
  padding-left: 4px;
}

/* 任务卡：需要填写 */
.help-fields {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.help-fields li {
  position: relative;
  padding: 8px 14px 8px 30px;
  background: var(--card);
  border: 1px solid var(--card-b);
  border-radius: 10px;
  font-size: 13px;
  color: var(--t1);
  line-height: 1.55;
}
.help-fields li::before {
  content: '•';
  position: absolute;
  left: 13px;
  top: 8px;
  color: var(--pri);
  font-weight: var(--font-weight-bold);
}

/* 任务卡：常见问题 */
.help-faq {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.help-faq__item {
  padding: 10px 14px;
  background: var(--card);
  border: 1px solid var(--card-b);
  border-radius: 10px;
}
.help-faq__q {
  font-size: 13px;
  font-weight: var(--font-weight-semibold);
  color: var(--t1);
  line-height: 1.5;
}
.help-faq__a {
  margin-top: 4px;
  font-size: 12.5px;
  color: var(--t2);
  line-height: 1.6;
}

/* 任务卡：相关入口 */
.help-related {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.help-related__link {
  font-size: 12.5px;
  color: var(--pri);
  background: var(--pri-bg);
  border: 1px solid var(--pri-100);
  border-radius: 20px;
  padding: 5px 14px;
  text-decoration: none;
}
.help-related__link:hover {
  background: var(--pri-100);
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
.help-embed {
  display: block;
  width: 100%;
  min-height: 760px;
  height: calc(100vh - 190px);
  border: 1px solid var(--card-b);
  border-radius: 14px;
  background: var(--card);
}
</style>
