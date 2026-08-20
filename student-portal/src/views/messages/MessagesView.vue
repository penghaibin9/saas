<template>
  <div class="sp-page">
    <section class="sp-card" style="padding:8px 10px">
      <div class="mhead">
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          <button v-for="t in allTabs" :key="t.key" class="mtab" :class="{ on: tab === t.key }" @click="tab = t.key">
            {{ t.label }}<span v-if="t.badge" class="mbadge">{{ t.badge }}</span>
          </button>
        </div>
        <a v-if="tab !== 'settings'" class="linkall" @click="markAll">全部标为已读</a>
      </div>

      <StateBlock v-if="loading" type="loading" text="加载中…" />
      <!-- SP-H02 同理：分区加载失败必须诚实报错，不能显示"暂无消息"。 -->
      <StateBlock v-else-if="tabError" type="error" :text="tabError" />
      <template v-else-if="tab === 'settings'">
        <div style="padding:16px 14px">
          <div class="sp-muted" style="margin-bottom:14px">设置各类消息的接收开关，退回 / 驳回等高优先级提醒建议保持开启。</div>
          <StateBlock v-if="!(pref.items||[]).length" type="empty" text="暂无可配置项" />
          <div v-for="p in (pref.items || [])" :key="p.key" class="prefrow">
            <div><div style="font-size:13.5px;color:var(--t1)">{{ p.label }}</div></div>
            <button class="switch" :class="{ on: p.enabled }" :disabled="busy" @click="togglePref(p)"><span /></button>
          </div>
        </div>
      </template>
      <template v-else>
        <StateBlock v-if="!items.length" type="empty" text="暂无消息" />
        <template v-else>
          <!-- SP-M01/M04：不再消费本地 ACTION_ROUTES/MODULE_ROUTES 猜路由；
               每条只消费服务端下发的 typed action，UNIFIED_MESSAGE 点击前还会
               重验详情，撤回/越权/失效一律原地报错，不导航（fail-closed）。 -->
          <button v-for="(m, i) in items" :key="m.id || i" class="mrow"
                  :disabled="itemDisabled(m)" :title="itemDisabled(m) ? (m.withdrawn ? '该消息已撤回' : actionReason(m.action)) : ''"
                  @click="openItem(m)">
            <span class="sp-tag" :class="'sp-tag--' + toneOf(m)" style="flex:none">{{ levelText(m) }}</span>
            <div style="flex:1;min-width:0">
              <div style="font-size:14px;color:var(--t1);line-height:1.5" :style="{ fontWeight: m.read ? 400 : 600 }">{{ displayMessageText(m.title) }}</div>
              <div style="margin-top:4px;font-size:12.5px;color:var(--t4)">
                {{ m.module }} · {{ fmt(m.time) }}
                <span v-if="m.deadline"> · 截止 {{ fmt(m.deadline) }}</span>
                <span v-if="m.receipt"> · 待确认</span>
                <span v-if="m.withdrawn"> · 已撤回</span>
              </div>
            </div>
            <span v-if="!m.read" style="flex:none;margin-top:6px;width:8px;height:8px;border-radius:50%;background:var(--pri)" />
          </button>
          <div v-if="hasMore" class="mmore">
            <button class="sp-btn sp-btn--ghost" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多' }}</button>
          </div>
        </template>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const router = useRouter()

const loading = ref(true)
const loadingMore = ref(false)
const busy = ref(false)
const tabError = ref('')

// SP-M05/M07：待办/通知/服务进度是三个独立 Authority，各自真实数据库分页，
// 不再合并成一份"消息列表"后在前端切片/过滤。
const tab = ref('todo')
const tabsMeta = ref([])
const items = ref([])
const page = ref(1)
const PAGE_SIZE = 20
const hasMore = ref(false)
const pref = ref({})

const allTabs = computed(() => {
  const t = tabsMeta.value.map((x) => ({ key: x.key, label: x.label, badge: x.badge }))
  t.push({ key: 'settings', label: '消息设置' })
  return t
})

const MESSAGE_STATUS_TEXT = { PENDING_REVIEW: '待审核', SUBMITTED: '已提交', RETURNED: '已退回', REJECTED: '未通过', APPROVED: '已通过', PROCESSING: '处理中', COMPLETED: '已完成', CLASS_REVIEW: '班级审核中', COLLEGE_REVIEW: '学院审核中', SCHOOL_REVIEW: '学校审核中' }
function displayMessageText(value) {
  let text = String(value || '')
  for (const [key, label] of Object.entries(MESSAGE_STATUS_TEXT)) text = text.replaceAll(key, label)
  return text || '系统通知'
}
function toneOf(m) {
  if (m && (m.emergency || m.level === 'high')) return 'danger'
  if (m && m.level === 'mid') return 'warn'
  return 'primary'
}
function levelText(m) {
  if (m && m.emergency) return '紧急'
  if (m && m.level === 'high') return '重要'
  if (m && m.level === 'mid') return '提醒'
  return '通知'
}
function fmt(t) { return t ? String(t).replace('T', ' ').slice(0, 16) : '' }

function canOpen(action) { return !!(action && action.target && action.target.path) }
function actionReason(action) { return (action && action.disabledReason) || '该事项暂无可直接办理的入口' }
function itemDisabled(m) {
  if (m.kind === 'UNIFIED_MESSAGE') return !!m.withdrawn
  return !canOpen(m.action)
}

async function loadTab(key, { page: p = 1, append = false } = {}) {
  if (key === 'settings') {
    loading.value = true
    tabError.value = ''
    try {
      pref.value = await portalApi.messagePreferences()
    } catch (e) {
      pref.value = {}
      tabError.value = e?.message || '通知偏好加载失败'
    } finally {
      loading.value = false
    }
    return
  }
  if (append) loadingMore.value = true
  else { loading.value = true; tabError.value = '' }
  try {
    const data = await portalApi.messagesInbox(key, p, PAGE_SIZE)
    tabsMeta.value = data.tabs || tabsMeta.value
    items.value = append ? [...items.value, ...(data.list || [])] : (data.list || [])
    page.value = data.page || p
    hasMore.value = !!data.hasMore
  } catch (e) {
    if (append) {
      ui.notify(e?.message || '加载更多失败')
    } else {
      items.value = []
      tabError.value = e?.message || '消息加载失败，请稍后重试'
    }
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

watch(tab, (key) => { loadTab(key, { page: 1 }) })

function loadMore() {
  if (!hasMore.value || loadingMore.value) return
  loadTab(tab.value, { page: page.value + 1, append: true })
}

async function markAll() {
  busy.value = true
  try {
    const r = await portalApi.messagesReadAll()
    ui.notify(r?.partial
      ? `已标记 ${r.affectedCount ?? 0} 条已读，部分历史消息处理失败`
      : `已标记 ${r?.affectedCount ?? 0} 条已读`)
    await loadTab(tab.value, { page: 1 })
  } catch (e) {
    // SP-M06：主 Authority 失败必须真报错，不能假装"全部已读成功"。
    ui.notify(e?.message || '全部已读失败')
  } finally {
    busy.value = false
  }
}

async function openItem(m) {
  if (m.kind === 'UNIFIED_MESSAGE') {
    if (m.withdrawn) { ui.notify('该消息已撤回'); return }
    const mid = String(m.messageId || m.id || '').replace(/^msg-/, '')
    if (/^\d+$/.test(mid)) {
      if (!m.read) {
        try { await portalApi.messageRead(mid); m.read = true } catch (e) { /* 非阻断 */ }
      }
      if (m.receipt) {
        try {
          await portalApi.messageReceipt(mid)
          m.receipt = false; m.acked = true
          ui.notify('已确认回执')
        } catch (e) { /* 非强制 */ }
      }
      // SP-M04：详情重验失败/撤回/越权，一律原地报错，不导航（fail-closed）。
      let detail
      try {
        detail = await portalApi.messageDetail(mid)
      } catch (e) {
        ui.notify(e?.message || '消息已失效，无法打开')
        return
      }
      if (detail?.withdrawn) { m.withdrawn = true; ui.notify('该消息已撤回'); return }
    }
  }
  if (!canOpen(m.action)) { ui.notify(actionReason(m.action)); return }
  const { path, query } = m.action.target
  router.push({ path, query: query && Object.keys(query).length ? { ...query } : undefined })
}

async function togglePref(p) {
  busy.value = true
  const next = !p.enabled
  try { await portalApi.messageSetPreference({ key: p.key, enabled: next }); p.enabled = next; ui.notify('偏好已更新') }
  catch (e) { ui.notify(e?.message || '设置失败') } finally { busy.value = false }
}

onMounted(() => loadTab(tab.value, { page: 1 }))
</script>

<style scoped>
.mhead { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid var(--line2); }
.mtab { all: unset; box-sizing: border-box; cursor: pointer; display: inline-flex; align-items: center; height: 30px; padding: 0 13px; border-radius: 8px; font-size: 13px; font-weight: 500; color: var(--t2); }
.mtab.on { background: var(--pri-50); color: var(--pri-text, var(--pri)); font-weight: 600; }
.mbadge { min-width: 16px; height: 16px; padding: 0 4px; margin-left: 5px; border-radius: 8px; background: var(--danger-fg); color: #fff; font-size: 11px; display: inline-flex; align-items: center; justify-content: center; }
.linkall { font-size: 13px; color: var(--pri-text, var(--pri)); cursor: pointer; }
.mrow { all: unset; cursor: pointer; box-sizing: border-box; width: 100%; display: flex; align-items: flex-start; gap: 13px; padding: 15px 14px; border-radius: 10px; }
.mrow:hover { background: var(--surface-2, #FAFBFC); }
.mrow:disabled { cursor: not-allowed; opacity: .55; }
.mmore { display: flex; justify-content: center; padding: 14px 0 6px; }
.prefrow { display: flex; align-items: center; justify-content: space-between; padding: 13px 4px; border-bottom: 1px solid var(--line2); }
.switch { all: unset; cursor: pointer; width: 40px; height: 22px; border-radius: 11px; background: #DDE1E8; position: relative; flex: none; transition: background .15s; }
.switch.on { background: var(--pri); }
.switch span { position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.2); transition: left .15s; }
.switch.on span { left: 20px; }
</style>
