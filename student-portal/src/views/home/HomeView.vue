<template>
  <div class="sp-page">
    <section class="sp-hero">
      <div>
        <p class="sp-eyebrow">首页概览</p>
        <h1>欢迎，{{ studentName }}</h1>
        <p class="sp-hero__sub">
          <StatusTag v-if="stageLabel" :text="stageLabel" tone="default" />
          重任务（材料上传、证明下载、长表单、大表格）在左侧对应模块办理；日常提醒两端同一账号、同一数据。
        </p>
      </div>
      <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新</button>
    </section>

    <StateBlock v-if="loading" type="loading" text="加载中…" />
    <template v-else>
      <section class="sp-kpis">
        <div class="sp-kpi"><div class="sp-kpi__label">待办</div><div class="sp-kpi__value">{{ todos.length }}</div></div>
        <div class="sp-kpi"><div class="sp-kpi__label">预警</div><div class="sp-kpi__value">{{ alerts.length }}</div></div>
        <div class="sp-kpi"><div class="sp-kpi__label">未读消息</div><div class="sp-kpi__value">{{ home.unreadCount ?? 0 }}</div></div>
        <div class="sp-kpi"><div class="sp-kpi__label">已开通模块</div><div class="sp-kpi__value">{{ cards.length }}</div></div>
      </section>

      <div class="sp-cols">
        <div class="sp-col">
          <section class="sp-panel">
            <div class="sp-panel__head">我的待办</div>
            <StateBlock v-if="!todos.length" type="empty" text="暂无待办" />
            <ul v-else class="sp-todo">
              <li v-for="t in todos" :key="t.id">
                <span>{{ t.title }}</span>
                <button class="sp-link" @click="goModule(t.module)">前往</button>
              </li>
            </ul>
          </section>

          <section v-if="alerts.length" class="sp-panel">
            <div class="sp-panel__head">预警提醒</div>
            <ul class="sp-todo">
              <li v-for="(a, i) in alerts" :key="i">
                <span><StatusTag :text="a.level === 'HIGH' ? '高' : a.level === 'MID' ? '中' : '低'" :tone="a.level === 'HIGH' ? 'danger' : 'warn'" /> {{ a.title }}</span>
                <button class="sp-link" @click="goModule(a.domain)">查看</button>
              </li>
            </ul>
          </section>
        </div>

        <div class="sp-col">
          <section v-if="domains.length" class="sp-panel">
            <div class="sp-panel__head">各环节状态</div>
            <ul class="sp-todo">
              <li v-for="d in domains" :key="d.key">
                <span>{{ d.label }}</span>
                <StatusTag :text="d.hasData ? (statusLabel(d.status)) : '未开始'" :tone="d.hasData ? 'success' : 'default'" />
              </li>
            </ul>
          </section>
        </div>
      </div>

      <section class="sp-panel">
        <div class="sp-panel__head">快捷入口</div>
        <StateBlock v-if="!cards.length" type="empty" text="暂无已开通模块，请联系学校管理员" />
        <div v-else class="sp-grid">
          <ModuleCard v-for="m in cards" :key="m.key" :title="m.title" :icon="m.icon" :to="m.to" />
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { usePortalConfigStore } from '../../stores/portalConfig'
import { useSessionStore } from '../../stores/session'
import { portalApi } from '../../services/portalApi'
import { buildMenu } from '../../platform/menuRegistry'
import { MODULES } from '../../platform/moduleRegistry'
import ModuleCard from '../../components/ModuleCard.vue'
import StatusTag from '../../components/StatusTag.vue'
import StateBlock from '../../components/StateBlock.vue'

const cfg = usePortalConfigStore()
const session = useSessionStore()
const router = useRouter()

const loading = ref(true)
const home = ref({})

const studentName = computed(() => home.value.student?.name || session.user?.realName || '同学')
const stageLabel = computed(() => home.value.stage?.label || '')
const todos = computed(() => home.value.todos || [])
const alerts = computed(() => home.value.alerts || [])
const domains = computed(() => home.value.domains || [])
const cards = computed(() => buildMenu(cfg.config).filter((m) => m.key !== 'dashboard'))

const STATUS_LABELS = {
  CHECKED_IN: '已报到', ONBOARD: '进行中', DONE: '已完成', NORMAL: '正常', SIGNED: '已签约',
  WARNING: '预警', PENDING: '待处理', PROCESSING: '进行中', APPROVED: '已通过', VERIFIED: '已核验'
}
function statusLabel(s) { return STATUS_LABELS[s] || s || '进行中' }
function goModule(key) {
  const mod = MODULES.find((m) => m.key === key || m.path === key)
  router.push('/' + (mod ? mod.path : (key || 'home')))
}

async function load() {
  loading.value = true
  try {
    home.value = await portalApi.homeOverview()
  } catch (e) {
    home.value = {}
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.sp-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.sp-col { min-width: 0; }
@media (max-width: 860px) { .sp-cols { grid-template-columns: 1fr; } }
</style>
