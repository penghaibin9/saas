<template>
  <div class="sp-page">
    <section class="sp-hero">
      <div>
        <p class="sp-eyebrow">消息中心</p>
        <h1>我的消息</h1>
        <p class="sp-hero__sub">待办、通知与进度提醒集中查看；未读 {{ data.unreadCount ?? 0 }} 条。</p>
      </div>
      <div style="display:flex;gap:10px">
        <button class="sp-btn sp-btn--ghost" :disabled="busy" @click="showPref = !showPref">通知偏好</button>
        <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新</button>
      </div>
    </section>

    <section v-if="showPref" class="sp-panel">
      <div class="sp-panel__head">通知偏好</div>
      <StateBlock v-if="!(pref.items || []).length" type="empty" text="暂无可配置项" />
      <ul v-else class="sp-pref">
        <li v-for="p in pref.items" :key="p.key">
          <span>{{ p.label }}</span>
          <label class="sp-switch">
            <input type="checkbox" :checked="p.enabled" :disabled="busy" @change="togglePref(p, $event)" />
            <span>{{ p.enabled ? '已开启' : '已关闭' }}</span>
          </label>
        </li>
      </ul>
    </section>

    <nav v-if="(data.tabs || []).length" class="sp-tabs">
      <button v-for="t in data.tabs" :key="t.key" class="sp-tab" :class="{ 'is-active': tab === t.key }" @click="tab = t.key">
        {{ t.label }}<span v-if="t.badge" class="sp-badge">{{ t.badge }}</span>
      </button>
    </nav>

    <StateBlock v-if="loading" type="loading" text="加载中…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <section v-else class="sp-panel">
      <StateBlock v-if="!shownList.length" type="empty" text="暂无消息" />
      <ul v-else class="sp-msglist">
        <li v-for="m in shownList" :key="m.id" :class="{ 'is-unread': !m.read }">
          <div class="sp-msg__main">
            <div class="sp-msg__title">
              <span v-if="!m.read" class="sp-msg__dot" />
              {{ m.title }}
              <StatusTag v-if="m.level === 'high'" text="重要" tone="danger" />
            </div>
            <div class="sp-msg__meta">{{ moduleLabel(m.module) }} · {{ fmtTime(m.time) }}<span v-if="m.deadline"> · 截止 {{ fmtTime(m.deadline) }}</span></div>
          </div>
          <div class="sp-msg__ops">
            <button v-if="m.link" class="sp-link" @click="go(m.link)">前往</button>
            <button v-if="!m.read" class="sp-link" :disabled="busy" @click="markRead(m)">标记已读</button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'
import { MODULES } from '../../platform/moduleRegistry'

const ui = useUiStore()
const router = useRouter()
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const data = ref({})
const pref = ref({})
const tab = ref('')
const showPref = ref(false)

const shownList = computed(() => {
  const groups = data.value.groups || {}
  if (tab.value && groups[tab.value]) return groups[tab.value]
  return data.value.list || []
})

function moduleLabel(key) { return MODULES.find((m) => m.key === key)?.title || key || '系统' }
function fmtTime(t) { return t ? String(t).replace('T', ' ').slice(0, 16) : '' }

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await portalApi.messagesInbox()
    if (!tab.value && (data.value.tabs || []).length) tab.value = data.value.tabs[0].key
    pref.value = await portalApi.messagePreferences()
  } catch (e) { error.value = e?.message || '消息加载失败' }
  finally { loading.value = false }
}
async function markRead(m) {
  busy.value = true
  try { await portalApi.messageRead(m.id); m.read = true; if (data.value.unreadCount) data.value.unreadCount -= 1; ui.notify('已标记已读') }
  catch (e) { ui.notify(e?.message || '操作失败') } finally { busy.value = false }
}
async function togglePref(p, ev) {
  busy.value = true
  const enabled = ev.target.checked
  try { await portalApi.messageSetPreference({ key: p.key, enabled }); p.enabled = enabled; ui.notify('偏好已更新') }
  catch (e) { ev.target.checked = p.enabled; ui.notify(e?.message || '设置失败（演示租户为只读）') } finally { busy.value = false }
}
function go(link) {
  const mod = MODULES.find((m) => m.key === link || m.path === link)
  router.push('/' + (mod ? mod.path : link))
}

onMounted(load)
</script>

<style scoped>
.sp-msglist { list-style: none; margin: 0; padding: 0; }
.sp-msglist li { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid #f4f5f7; }
.sp-msglist li:last-child { border-bottom: 0; }
.sp-msg__title { font-size: 14px; color: #1d2129; display: flex; align-items: center; gap: 8px; }
.sp-msg__dot { width: 8px; height: 8px; border-radius: 50%; background: #f53f3f; display: inline-block; }
.sp-msg__meta { color: #86909c; font-size: 12px; margin-top: 5px; }
.sp-msg__ops { display: flex; gap: 12px; flex-shrink: 0; }
.sp-pref { list-style: none; margin: 0; padding: 0; }
.sp-pref li { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid #f4f5f7; font-size: 14px; }
.sp-switch { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #86909c; cursor: pointer; }
</style>
