<template>
  <div class="sp-page message-page">
    <section class="sp-card">
      <h1>消息通知</h1>
      <p>学校和指导教师发给本人的岗位实习消息。阅读消息后，请明确标记已读；已读不代表业务办结。</p>
      <form class="message-tools" @submit.prevent="applyFilter">
        <label>阅读状态<select v-model="filter"><option value="">全部</option><option value="UNREAD">未读</option><option value="READ">已读</option></select></label>
        <button class="sp-btn" type="submit">查询</button><button class="sp-btn sp-btn--ghost" type="button" @click="loadList">重新读取</button>
      </form>
      <StateBlock v-if="loading" type="loading" text="正在读取本人消息…" />
      <StateBlock v-else-if="error" type="error" :text="error" />
      <StateBlock v-else-if="!items.length" type="empty" text="当前筛选下暂无消息" />
      <ul v-else class="message-list">
        <li v-for="item in items" :key="item.messageId">
          <button type="button" class="message-item" @click="openMessage(item.messageId)">
            <span><strong>{{ item.title || '学校消息' }}</strong><span class="message-summary">{{ item.summary }}</span></span>
            <span>{{ item.readStatus === 'READ' ? '已读' : '未读' }}</span>
          </button>
        </li>
      </ul>
      <div v-if="!loading && !error" class="message-tools"><span>共{{ total }}条，第{{ page }}页</span><button class="sp-btn sp-btn--ghost" type="button" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button><button class="sp-btn sp-btn--ghost" type="button" :disabled="!hasMore" @click="changePage(page + 1)">下一页</button></div>
    </section>
    <section v-if="detailLoading || detail || detailError" ref="detailPanel" tabindex="-1" class="sp-card">
      <StateBlock v-if="detailLoading" type="loading" text="正在读取消息正文…" />
      <StateBlock v-else-if="detailError" type="error" :text="detailError" />
      <template v-else-if="detail">
        <h2>{{ detail.title || '学校消息' }}</h2>
        <p class="message-content">{{ detail.contentPlain || detail.content || detail.summary || '暂无正文' }}</p>
        <p v-if="detail.withdrawn">该消息已撤回，请以学校最新通知为准。</p><p v-if="detail.expired">该消息已过期。</p>
        <p v-if="detail.requireAck">本条消息还有确认要求，标记已读不等于确认或办结，请按学校正式业务入口办理。</p>
        <p v-if="employmentMessageVersion">第{{ employmentMessageVersion }}版核验结果，当前状态请查看就业登记。</p>
        <p v-if="messageAction"><button type="button" class="sp-btn sp-btn--ghost" @click="openBusiness">{{ messageAction.label }}</button><span class="sp-muted">原单显示最新办理状态；历史消息不代表当前仍需补正。</span></p>
        <p v-else-if="detail.actionKey==='student.internship.employment-registration' && !detail.withdrawn && !detail.expired" class="sp-muted">请在学生移动端“就业上报”查看原单。</p>
        <p v-else-if="detail.actionKey && !detail.withdrawn && !detail.expired" class="sp-muted">此消息暂无电脑端原单入口，请从对应业务页核对办理进度。</p>
        <p v-if="readError" role="alert">{{ readError }}</p><p v-if="receipt" role="status">{{ receipt }}</p>
        <button v-if="detail.readStatus !== 'READ'" class="sp-btn" type="button" :disabled="readBusy" @click="markRead">{{ readBusy ? '正在保存已读…' : '标记这条消息已读' }}</button><span v-else>这条消息已读</span>
      </template>
    </section>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import StateBlock from '../components/StateBlock.vue'
import { portalApi } from '../services/portalApi'
import { currentSessionGeneration } from '../services/request'
import { useSessionStore } from '../stores/session'

const route = useRoute(), router = useRouter(), session = useSessionStore()
const items = ref([]), total = ref(0), hasMore = ref(false), page = ref(1), filter = ref('')
const loading = ref(false), error = ref(''), detail = ref(null), detailLoading = ref(false), detailError = ref('')
const detailPanel = ref(null)
const readBusy = ref(false), readError = ref(''), receipt = ref('')
const employmentMessageVersion=computed(()=>{
  const row=detail.value,revision=row?.actionParams?.revisionNo
  return row?.actionKey==='student.internship.employment-registration' && !row.withdrawn && !row.expired && Number.isSafeInteger(revision) && revision>0 ? revision : null
})
const messageAction=computed(()=>{
  const row=detail.value,p=row?.actionParams
  if(!row || row.withdrawn || row.expired || !p)return null
  if(row.actionKey==='student.internship.volunteer-result') {
    if(!/^[1-9]\d*$/.test(String(p.groupId || '')) || !/^(0|[1-9]\d*)$/.test(String(p.groupVersion ?? '')))return null
    return {path:'/internship/volunteer-result',query:{groupId:String(p.groupId),groupVersion:String(p.groupVersion)},label:'查看志愿原单'}
  }
  if(row.actionKey!=='student.internship.weekly-report')return null
  if(['reportId','batchId','internshipId'].some(key=>!/^[1-9]\d*$/.test(String(p[key] || ''))))return null
  return {path:'/internship',query:{view:'report',reportType:'WEEKLY',reportId:String(p.reportId),batchId:String(p.batchId)},label:'查看周报原单'}
})
function openBusiness(){if(messageAction.value)router.push(messageAction.value)}
let alive = true, listSequence = 0, detailSequence = 0
const identity = computed(() => JSON.stringify([String(session.user?.tenantId || ''), String(session.user?.userId || ''), session.user?.roleCode || '']))
function capture() { return { identity: identity.value, generation: currentSessionGeneration() } }
function current(t) { return alive && t.identity === identity.value && t.generation === currentSessionGeneration() }
function clearDetail() { detailSequence++; detail.value = null; detailLoading.value = false; detailError.value = ''; readBusy.value = false; readError.value = ''; receipt.value = '' }
async function loadList() {
  const t = capture(), sequence = ++listSequence
  loading.value = true; error.value = ''; items.value = []; total.value = 0; hasMore.value = false
  if (!session.user?.userId) { loading.value = false; return }
  try {
    const result = await portalApi.messages({ page: page.value, pageSize: 20, readStatus: filter.value || undefined })
    if (!current(t) || sequence !== listSequence) return
    if (!Array.isArray(result?.items) || !Number.isInteger(result.total) || result.total < 0 || result.page !== page.value) throw new Error('消息列表返回异常，请重新读取')
    items.value = result.items; total.value = result.total; hasMore.value = result.hasMore === true
  } catch (e) { if (current(t) && sequence === listSequence) error.value = e?.message || '消息读取失败，请重试' }
  finally { if (current(t) && sequence === listSequence) loading.value = false }
}
function routeQuery(nextPage) { return { ...(filter.value ? { readStatus: filter.value } : {}), ...(nextPage > 1 ? { page: String(nextPage) } : {}) } }
function applyFilter() {
  if (page.value === 1 && (route.query.readStatus || '') === filter.value) return loadList()
  return router.replace({ path: '/messages', query: routeQuery(1) })
}
function changePage(value) { return router.replace({ path: '/messages', query: routeQuery(value) }) }
async function openMessage(id) {
  clearDetail()
  const t = capture(), sequence = detailSequence, messageId = String(id)
  detailLoading.value = true
  await nextTick()
  if (!current(t) || sequence !== detailSequence) return
  detailPanel.value?.focus()
  detailPanel.value?.scrollIntoView({ block: 'start' })
  try {
    const result = await portalApi.messageDetail(messageId)
    if (!current(t) || sequence !== detailSequence) return
    if (String(result?.messageId) !== messageId) throw new Error('消息编号不一致，请重新打开')
    detail.value = result
  } catch (e) { if (current(t) && sequence === detailSequence) detailError.value = e?.message || '消息正文读取失败，请重试' }
  finally { if (current(t) && sequence === detailSequence) detailLoading.value = false }
}
async function markRead() {
  if (readBusy.value || !detail.value || detail.value.readStatus === 'READ') return
  const t = capture(), sequence = detailSequence, id = String(detail.value.messageId)
  readBusy.value = true; readError.value = ''; receipt.value = ''
  try {
    const result = await portalApi.readMessage(id)
    if (!current(t) || sequence !== detailSequence) return
    if (String(result?.messageId) !== id || result.readStatus !== 'READ') throw new Error('已读结果返回异常，请重新读取核对')
    detail.value = { ...detail.value, ...result }; receipt.value = '已标记为已读。'
    if (typeof window !== 'undefined') window.dispatchEvent(new Event('internship-message-read'))
    await loadList()
  } catch (e) { if (current(t) && sequence === detailSequence) readError.value = e?.message || '已读保存失败，请重试' }
  finally { if (current(t) && sequence === detailSequence) readBusy.value = false }
}
watch(() => [identity.value, route.query.page, route.query.readStatus], () => {
  clearDetail(); listSequence++
  const raw = Number(route.query.page || 1)
  page.value = Number.isInteger(raw) && raw > 0 ? raw : 1
  filter.value = ['UNREAD', 'READ'].includes(route.query.readStatus) ? route.query.readStatus : ''
  loadList()
}, { immediate: true, flush: 'sync' })
onBeforeUnmount(() => { alive = false; listSequence++; clearDetail() })
</script>

<style scoped>
.message-page{display:grid;gap:18px}.message-page h1{font-size:23px}.message-page p{line-height:1.7;color:var(--t3)}.message-tools{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:16px 0}.message-tools label{display:flex;align-items:center;gap:8px}.message-tools select{font:inherit;padding:8px;border:1px solid var(--line);border-radius:8px;background:var(--surface)}.message-list{list-style:none;padding:0;margin:0}.message-list li{border-bottom:1px solid var(--line)}.message-item{display:flex;justify-content:space-between;gap:18px;text-align:left;background:none;border:0;width:100%;padding:16px 0;color:var(--t1);font:inherit;cursor:pointer}.message-item>span:first-child{min-width:0}.message-item>span:last-child{flex:none;font-size:13px}.message-item strong,.message-summary{display:block;overflow-wrap:anywhere}.message-summary{font-size:14px;line-height:1.6;color:var(--t3);margin-top:6px}.message-content{white-space:pre-wrap;overflow-wrap:anywhere}@media(max-width:430px){.message-tools{gap:8px}.message-item{gap:8px}}
</style>
