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
        <StateBlock v-if="!shownList.length" type="empty" text="暂无消息" />
        <button v-for="(m, i) in shownList" :key="m.id || i" class="mrow" @click="go(m)">
          <span class="sp-tag" :class="'sp-tag--' + toneOf(m)" style="flex:none">{{ levelText(m) }}</span>
          <div style="flex:1;min-width:0">
            <div style="font-size:14px;color:var(--t1);line-height:1.5" :style="{ fontWeight: m.read ? 400 : 600 }">{{ m.title }}</div>
            <div style="margin-top:4px;font-size:12.5px;color:var(--t4)">
              {{ modName(m.module) }} · {{ fmt(m.time) }}
              <span v-if="m.deadline"> · 截止 {{ fmt(m.deadline) }}</span>
              <span v-if="m.receipt"> · 待确认</span>
            </div>
          </div>
          <span v-if="!m.read" style="flex:none;margin-top:6px;width:8px;height:8px;border-radius:50%;background:var(--pri)" />
        </button>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import StateBlock from '../../components/StateBlock.vue'
import { portalApi } from '../../services/portalApi'
import { request } from '../../services/request'
import { useUiStore } from '../../stores/ui'
import { MODULES } from '../../platform/moduleRegistry'

const ACTION_ROUTES = {
  STUDENT_AFFAIRS: '/campus-service',
  STUDENT_AFFAIRS_LEAVE: '/campus-service?tab=leave',
  STUDENT_AFFAIRS_AID: '/campus-service?tab=aid',
  STUDENT_AFFAIRS_FUNDING: '/campus-service?tab=funding',
  STUDENT_AFFAIRS_DISCIPLINE: '/campus-service?tab=discipline',
  STUDENT_AFFAIRS_DORM: '/campus-service?tab=dorm',
  STUDENT_AFFAIRS_ACTIVITY: '/campus-service?tab=activity',
  STUDENT_APPLICATIONS: '/campus-service?tab=applications',
  INTERNSHIP: '/internship',
  GRADUATION: '/graduation',
  ACADEMIC: '/academic',
  ORIENTATION: '/orientation',
  EMPLOYMENT: '/employment'
}

const MODULE_ROUTES = {
  'student-affairs': '/campus-service',
  campusService: '/campus-service',
  'campus-service': '/campus-service',
  internship: '/internship',
  graduation: '/graduation',
  'academic-affairs': '/academic',
  academic: '/academic',
  orientation: '/orientation',
  employment: '/employment'
}

const ui = useUiStore()
const router = useRouter()
const loading = ref(true)
const busy = ref(false)
const data = ref({})
const pref = ref({})
const tab = ref('all')

const allTabs = computed(() => {
  const t = [{ key: 'all', label: '全部' }]
  for (const x of (data.value.tabs || [])) t.push({ key: x.key, label: x.label, badge: x.badge })
  t.push({ key: 'settings', label: '消息设置' })
  return t
})
const shownList = computed(() => {
  if (tab.value === 'all') return data.value.list || []
  const g = data.value.groups || {}
  return g[tab.value] || (data.value.list || [])
})

function modName(key) { return MODULES.find((m) => m.key === key || m.domain === key)?.title || '系统' }
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
function messageTarget(m) {
  if (!m || m.withdrawn) return '/messages'
  const params = m.actionParams && typeof m.actionParams === 'object' ? m.actionParams : {}
  const materialRequirementId = params.materialRequirementId || params.requirementId || ''
  if (materialRequirementId) return `/materials?requirementId=${encodeURIComponent(String(materialRequirementId))}`
  const key = String(m.actionKey || '').trim().toUpperCase()
  let target = ACTION_ROUTES[key] || ''
  const biz = String(params.businessType || params.bizType || '').trim().toUpperCase()
  if (!target && biz) target = ACTION_ROUTES[`STUDENT_AFFAIRS_${biz}`] || ACTION_ROUTES[biz] || ''
  if (!target && m.status === 'RETURNED') target = ACTION_ROUTES.STUDENT_APPLICATIONS
  if (!target) target = MODULE_ROUTES[String(m.module || '').trim()] || ''
  if (!target) {
    const mod = MODULES.find((x) => x.key === m.link || x.path === m.link || x.domain === m.link)
    target = mod ? `/${mod.path}` : '/messages'
  }
  const recordId = params.recordId || params.bizId || params.applyId || params.applicationId || params.caseId || params.leaveId || ''
  if (recordId && target !== '/messages') target += `${target.includes('?') ? '&' : '?'}recordId=${encodeURIComponent(String(recordId))}`
  return target
}

async function load() {
  loading.value = true
  try {
    data.value = await portalApi.messagesInbox(1, 30)
    pref.value = await portalApi.messagePreferences().catch(() => ({}))
  } catch (e) { data.value = {} } finally { loading.value = false }
}
async function markAll() {
  try {
    const r = await portalApi.messagesReadAll()
    ui.notify(`已标已读 ${r?.affectedCount ?? ''}`.trim())
    await load()
  } catch (e) {
    ui.notify(e?.message || '全部已读失败')
  }
}
async function go(m) {
  const rawId = String(m.messageId || m.id || '')
  const isUnified = m.kind === 'UNIFIED_MESSAGE' || /^\d+$/.test(rawId) || /^msg-\d+$/.test(rawId)
  const mid = rawId.replace(/^msg-/, '')
  if (isUnified && !m.read && /^\d+$/.test(mid)) {
    try { await portalApi.messageRead(mid); m.read = true } catch (e) { /* ignore */ }
  }
  if (isUnified && m.receipt && /^\d+$/.test(mid)) {
    try {
      await portalApi.messageReceipt(mid)
      m.receipt = false
      m.acked = true
      ui.notify('已确认回执')
    } catch (e) { /* 非强制 */ }
  }
  let detail = m
  if (isUnified && /^\d+$/.test(mid)) {
    try { detail = await request(`/mobile/me/messages/${mid}`) } catch (e) { /* 列表数据安全降级 */ }
  }
  router.push(messageTarget(detail))
}
async function togglePref(p) {
  busy.value = true
  const next = !p.enabled
  try { await portalApi.messageSetPreference({ key: p.key, enabled: next }); p.enabled = next; ui.notify('偏好已更新') }
  catch (e) { ui.notify(e?.message || '设置失败') } finally { busy.value = false }
}
onMounted(load)
</script>

<style scoped>
.mhead { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; border-bottom: 1px solid var(--line2); }
.mtab { all: unset; box-sizing: border-box; cursor: pointer; display: inline-flex; align-items: center; height: 30px; padding: 0 13px; border-radius: 8px; font-size: 13px; font-weight: 500; color: var(--t2); }
.mtab.on { background: var(--pri-50); color: var(--pri); font-weight: 600; }
.mbadge { min-width: 16px; height: 16px; padding: 0 4px; margin-left: 5px; border-radius: 8px; background: var(--danger-fg); color: #fff; font-size: 11px; display: inline-flex; align-items: center; justify-content: center; }
.linkall { font-size: 13px; color: var(--pri); cursor: pointer; }
.mrow { all: unset; cursor: pointer; box-sizing: border-box; width: 100%; display: flex; align-items: flex-start; gap: 13px; padding: 15px 14px; border-radius: 10px; }
.mrow:hover { background: #FAFBFC; }
.prefrow { display: flex; align-items: center; justify-content: space-between; padding: 13px 4px; border-bottom: 1px solid #F4F5F7; }
.switch { all: unset; cursor: pointer; width: 40px; height: 22px; border-radius: 11px; background: #DDE1E8; position: relative; flex: none; transition: background .15s; }
.switch.on { background: var(--pri); }
.switch span { position: absolute; top: 2px; left: 2px; width: 18px; height: 18px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.2); transition: left .15s; }
.switch.on span { left: 20px; }
</style>
