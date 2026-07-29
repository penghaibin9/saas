<template>
  <div class="sp-page textbook-page">
    <section class="textbook-hero">
      <div>
        <div class="textbook-hero__eyebrow">教务学业 · 教材领用</div>
        <h1>核对本人教材、费用并完成签收</h1>
        <p>只展示本人教材发放记录。签收用于确认实际领到教材，不允许代替他人操作，也不在接口失败时显示成功。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading || !!actingId" @click="load">
        {{ loading ? '加载中…' : '刷新记录' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取本人教材领用记录…" />
    <section v-else-if="error" class="sp-card textbook-error">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>

    <template v-else>
      <section class="textbook-summary">
        <article class="summary-card"><span>教材记录</span><b>{{ records.length }}</b></article>
        <article class="summary-card" :class="{ 'is-action': pendingRecords.length }"><span>待签收</span><b>{{ pendingRecords.length }}</b></article>
        <article class="summary-card"><span>费用合计</span><b>{{ amountText(totalAmount) }}</b></article>
      </section>

      <section class="sp-card list-card">
        <header class="section-head">
          <div><strong>本人教材发放记录</strong><span>按学期、课程和发放批次核对</span></div>
          <StatusTag :text="pendingRecords.length ? `${pendingRecords.length} 本待签收` : '暂无待签收'" :tone="pendingRecords.length ? 'warn' : 'success'" />
        </header>
        <StateBlock v-if="!records.length" type="empty" text="暂无本人教材发放记录" />
        <div v-else class="textbook-list">
          <article v-for="record in records" :key="recordKey(record)" class="textbook-item">
            <div class="textbook-item__cover">书</div>
            <div class="textbook-item__main">
              <header>
                <div>
                  <strong>{{ record.textbookName || record.bookName || record.name || '教材名称待补充' }}</strong>
                  <span>{{ record.isbn ? `ISBN ${record.isbn}` : 'ISBN 待确认' }}{{ record.edition ? ` · ${record.edition}` : '' }}</span>
                </div>
                <StatusTag :text="statusText(record)" :tone="statusTone(record)" />
              </header>
              <dl>
                <div><dt>对应课程</dt><dd>{{ record.courseName || record.courseCode || '—' }}</dd></div>
                <div><dt>发放批次</dt><dd>{{ record.batchName || record.termCode || '—' }}</dd></div>
                <div><dt>数量</dt><dd>{{ record.quantity || 1 }}</dd></div>
                <div><dt>费用</dt><dd>{{ amountText(record.amount ?? record.feeAmount ?? record.price) }}</dd></div>
                <div v-if="record.distributedAt"><dt>发放时间</dt><dd>{{ dateTime(record.distributedAt) }}</dd></div>
                <div v-if="record.signedAt"><dt>签收时间</dt><dd>{{ dateTime(record.signedAt) }}</dd></div>
              </dl>
              <footer v-if="canSign(record)">
                <span>请在实际领到并核对教材后签收，提交后不可由学生端撤回。</span>
                <button
                  class="sp-btn"
                  type="button"
                  :disabled="!!actingId"
                  @click="sign(record)"
                >{{ actingId === recordKey(record) ? '签收中…' : '确认本人已领用' }}</button>
              </footer>
            </div>
          </article>
        </div>
      </section>

      <section class="sp-card textbook-note">
        <strong>签收说明</strong>
        <span>签收仅确认教材实物已交付本人，不代表费用已经缴清或课程成绩认定。费用与退换规则以学校教材管理制度为准。</span>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const actingId = ref('')
const records = ref([])

const pendingRecords = computed(() => records.value.filter(canSign))
const totalAmount = computed(() => records.value.reduce((sum, record) => {
  const value = Number(record.amount ?? record.feeAmount ?? record.price ?? 0)
  return sum + (Number.isFinite(value) ? value : 0)
}, 0))

function rowsOf(data) {
  if (Array.isArray(data)) return data
  return (data && (data.items || data.list || data.records || data.distributions)) || []
}
function recordKey(record) { return String(record.recordId || record.distributionRecordId || record.id || `${record.isbn || record.textbookName}:${record.batchId || ''}`) }
function rawStatus(record) { return String(record.status || record.signStatus || record.distributionStatus || '').toUpperCase() }
function canSign(record) {
  const id = record.recordId || record.distributionRecordId || record.id
  const status = rawStatus(record)
  return !!id && !record.signedAt && !['SIGNED', 'RECEIVED', 'CANCELLED', 'RETURNED'].includes(status)
}
function statusText(record) {
  const status = rawStatus(record)
  const map = { PENDING: '待发放', DISTRIBUTED: '待签收', ISSUED: '待签收', SIGNED: '已签收', RECEIVED: '已签收', RETURNED: '已退回', CANCELLED: '已取消' }
  if (!status && record.signedAt) return '已签收'
  return map[status] || status || (canSign(record) ? '待签收' : '待确认')
}
function statusTone(record) {
  const status = rawStatus(record)
  if (record.signedAt || ['SIGNED', 'RECEIVED'].includes(status)) return 'success'
  if (['RETURNED', 'CANCELLED'].includes(status)) return 'default'
  return canSign(record) ? 'warn' : 'default'
}
function dateTime(value) { return String(value || '').slice(0, 16).replace('T', ' ') || '—' }
function amountText(value) {
  const amount = Number(value)
  return Number.isFinite(amount) ? `¥${amount.toFixed(2)}` : '待确认'
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    records.value = rowsOf(await portalApi.academicTextbook())
  } catch (e) {
    error.value = e?.message || '教材记录读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
async function sign(record) {
  const id = record.recordId || record.distributionRecordId || record.id
  if (!id || actingId.value || !canSign(record)) return
  const confirmed = window.confirm(`确认本人已实际领到“${record.textbookName || record.bookName || '该教材'}”？提交后不可由学生端撤回。`)
  if (!confirmed) return
  actingId.value = recordKey(record)
  try {
    await portalApi.academicTextbookSign(id)
    ui.notify('教材签收成功')
    await load()
  } catch (e) {
    ui.notify(e?.message || '教材签收失败')
  } finally {
    actingId.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.textbook-page { max-width: 1080px; margin: 0 auto; }
.textbook-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.textbook-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.textbook-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.textbook-hero p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.textbook-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.textbook-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-bottom: 14px; }
.summary-card { padding: 16px 18px; border: 1px solid var(--line); border-radius: 13px; background: #fff; }
.summary-card span { display: block; color: var(--t3); font-size: 12px; }
.summary-card b { display: block; margin-top: 7px; color: var(--t1); font-size: 22px; }
.summary-card.is-action b { color: var(--pri); }
.list-card { padding: 18px 20px; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.section-head strong, .section-head span { display: block; }
.section-head strong { color: var(--t1); font-size: 15px; }
.section-head span { margin-top: 4px; color: var(--t3); font-size: 12px; }
.textbook-list { display: grid; gap: 10px; }
.textbook-item { display: grid; grid-template-columns: 54px minmax(0, 1fr); gap: 14px; padding: 14px; border: 1px solid var(--line2); border-radius: 11px; }
.textbook-item__cover { display: grid; place-items: center; width: 54px; height: 70px; border-radius: 8px; background: var(--pri-50); color: var(--pri); font-size: 18px; font-weight: 700; }
.textbook-item__main > header { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.textbook-item__main > header strong, .textbook-item__main > header span { display: block; }
.textbook-item__main > header strong { color: var(--t1); font-size: 14px; }
.textbook-item__main > header span { margin-top: 4px; color: var(--t4); font-size: 11.5px; }
.textbook-item dl { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px 16px; margin: 12px 0 0; padding-top: 11px; border-top: 1px solid var(--line2); }
.textbook-item dl div { display: grid; grid-template-columns: 78px minmax(0, 1fr); gap: 8px; }
.textbook-item dt { color: var(--t4); font-size: 12px; }
.textbook-item dd { margin: 0; color: var(--t2); font-size: 12.5px; overflow-wrap: anywhere; }
.textbook-item footer { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 12px; }
.textbook-item footer span { color: var(--t4); font-size: 12px; }
.textbook-note { display: flex; gap: 12px; margin-top: 14px; color: var(--t3); font-size: 12.5px; }
.textbook-note strong { color: var(--t1); white-space: nowrap; }
@media (max-width: 720px) {
  .textbook-hero, .section-head, .textbook-item__main > header, .textbook-item footer { align-items: stretch; flex-direction: column; }
  .textbook-summary { grid-template-columns: 1fr; }
  .textbook-item { grid-template-columns: 1fr; }
  .textbook-item dl { grid-template-columns: 1fr; }
  .textbook-item dl div { grid-template-columns: 1fr; gap: 3px; }
  .textbook-item footer .sp-btn { width: 100%; }
}
</style>
