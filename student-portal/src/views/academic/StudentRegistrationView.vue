<template>
  <div class="sp-page registration-page">
    <section class="registration-hero">
      <div>
        <div class="registration-hero__eyebrow">教务学业 · 学期注册</div>
        <h1>完成本学期注册</h1>
        <p>只展示本人当前可办理批次。资格不满足时显示真实阻断原因，不把按钮隐藏成“没有业务”。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" type="button" :disabled="loading || !!actingId" @click="load">
        {{ loading ? '加载中…' : '刷新状态' }}
      </button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在读取本人注册批次…" />
    <section v-else-if="error" class="sp-card registration-error">
      <StateBlock type="error" :text="error" />
      <button class="sp-btn sp-btn--ghost" type="button" @click="load">重新加载</button>
    </section>
    <template v-else>
      <section class="sp-card student-card">
        <div>
          <strong>{{ data.realName || '本人' }}</strong>
          <span>{{ data.studentNo || '学号待绑定' }} · 学籍状态 {{ data.studentStatus || '待确认' }}</span>
        </div>
        <StatusTag :text="summaryText" :tone="pendingCount ? 'warn' : 'success'" />
      </section>

      <StateBlock
        v-if="!batches.length"
        type="empty"
        :text="data.note || '暂无开放中的注册批次'"
      />
      <section v-else class="registration-list">
        <article v-for="batch in batches" :key="batch.batchId" class="sp-card batch-card">
          <header class="batch-card__head">
            <div>
              <strong>{{ batch.batchName || '注册批次' }}</strong>
              <span>{{ batch.registerTypeLabel || '学期注册' }} · {{ dateText(batch.windowStart) }} 至 {{ dateText(batch.windowEnd) }}</span>
            </div>
            <StatusTag :text="registrationStatusText(batch.registrationStatus)" :tone="registrationTone(batch.registrationStatus)" />
          </header>

          <dl class="batch-card__facts">
            <div><dt>注册资格</dt><dd>{{ eligibilityText(batch.eligibilityStatus) }}</dd></div>
            <div><dt>办理状态</dt><dd>{{ registrationStatusText(batch.registrationStatus) }}</dd></div>
            <div><dt>办理窗口</dt><dd>{{ windowText(batch) }}</dd></div>
          </dl>

          <div v-if="batch.blockReason" class="batch-card__block" role="status">
            <strong>当前无法注册</strong>
            <span>{{ batch.blockReason }}</span>
          </div>
          <div v-if="batch.deferral" class="batch-card__deferral">
            <strong>暂缓申请</strong>
            <span>{{ deferralText(batch.deferral) }}</span>
          </div>

          <div v-if="batch.canDefer" class="batch-card__defer-form">
            <label :for="`reason-${batch.batchId}`">暂缓原因（至少 2 字）</label>
            <textarea
              :id="`reason-${batch.batchId}`"
              v-model.trim="deferReasons[batch.batchId]"
              class="sp-inp"
              maxlength="300"
              placeholder="说明暂时无法完成注册的原因"
            />
          </div>

          <footer class="batch-card__actions">
            <button
              class="sp-btn sp-btn--ghost"
              type="button"
              :disabled="!batch.canDefer || !!actingId || !canDefer(batch)"
              @click="submitDefer(batch)"
            >
              {{ actingId === `defer:${batch.batchId}` ? '提交中…' : '申请暂缓' }}
            </button>
            <button
              class="sp-btn"
              type="button"
              :disabled="!batch.canRegister || !!actingId"
              @click="register(batch)"
            >
              {{ actingId === `register:${batch.batchId}` ? '注册中…' : '确认完成注册' }}
            </button>
          </footer>
        </article>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const error = ref('')
const actingId = ref('')
const data = ref({ batches: [] })
const deferReasons = reactive({})

const batches = computed(() => Array.isArray(data.value.batches) ? data.value.batches : [])
const pendingCount = computed(() => batches.value.filter((batch) => batch.canRegister || batch.canDefer).length)
const summaryText = computed(() => pendingCount.value ? `${pendingCount.value} 个批次可办理` : '当前无待办理')

function dateText(value) {
  return String(value || '').slice(0, 10) || '待定'
}
function registrationStatusText(status) {
  const map = {
    PENDING: '待注册', REGISTERED: '已注册', DEFERRED: '已暂缓',
    EXEMPTED: '免注册', CLOSED: '已关闭', BLOCKED: '暂不可办'
  }
  return map[String(status || '').toUpperCase()] || status || '待确认'
}
function registrationTone(status) {
  const value = String(status || '').toUpperCase()
  if (['REGISTERED', 'EXEMPTED'].includes(value)) return 'success'
  if (['BLOCKED', 'CLOSED'].includes(value)) return 'danger'
  return 'warn'
}
function eligibilityText(status) {
  const map = { ELIGIBLE: '符合', INELIGIBLE: '不符合', PENDING: '待核验' }
  return map[String(status || '').toUpperCase()] || status || '待核验'
}
function windowText(batch) {
  if (batch.canRegister || batch.canDefer) return '窗口开放中'
  return `${dateText(batch.windowStart)} 至 ${dateText(batch.windowEnd)}`
}
function deferralText(deferral) {
  const status = String(deferral.status || '').toUpperCase()
  const map = { PENDING: '审核中', APPROVED: '已批准', RETURNED: '已退回', REJECTED: '未通过' }
  return `${map[status] || deferral.status || '待处理'}${deferral.reason ? ` · ${deferral.reason}` : ''}`
}
function canDefer(batch) {
  return String(deferReasons[batch.batchId] || '').trim().length >= 2
}
async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await portalApi.academicRegistration() || { batches: [] }
    for (const batch of batches.value) {
      if (deferReasons[batch.batchId] == null) deferReasons[batch.batchId] = ''
    }
  } catch (e) {
    error.value = e?.message || '注册批次读取失败，请稍后重试'
  } finally {
    loading.value = false
  }
}
async function register(batch) {
  if (!batch?.canRegister || actingId.value) return
  const confirmed = window.confirm(`确认完成“${batch.batchName || '当前批次'}”注册？`)
  if (!confirmed) return
  actingId.value = `register:${batch.batchId}`
  try {
    await portalApi.academicRegistrationRegister(batch.batchId)
    ui.notify('注册成功')
    await load()
  } catch (e) {
    ui.notify(e?.message || '注册失败')
  } finally {
    actingId.value = ''
  }
}
async function submitDefer(batch) {
  if (!batch?.canDefer || !canDefer(batch) || actingId.value) return
  actingId.value = `defer:${batch.batchId}`
  try {
    await portalApi.academicRegistrationDefer(batch.batchId, {
      reason: String(deferReasons[batch.batchId] || '').trim()
    })
    deferReasons[batch.batchId] = ''
    ui.notify('暂缓申请已提交')
    await load()
  } catch (e) {
    ui.notify(e?.message || '暂缓申请提交失败')
  } finally {
    actingId.value = ''
  }
}

onMounted(load)
</script>

<style scoped>
.registration-page { max-width: 1080px; margin: 0 auto; }
.registration-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; margin-bottom: 16px; padding: 24px 26px; border: 1px solid var(--line); border-radius: 16px; background: linear-gradient(135deg, #fff, var(--pri-50)); }
.registration-hero__eyebrow { color: var(--pri); font-size: 12px; font-weight: 700; letter-spacing: .08em; }
.registration-hero h1 { margin: 8px 0 6px; color: var(--t1); font-size: 24px; }
.registration-hero p { margin: 0; color: var(--t3); font-size: 13px; line-height: 1.65; }
.registration-error { display: flex; flex-direction: column; align-items: center; gap: 12px; }
.student-card { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 14px; }
.student-card strong, .student-card span { display: block; }
.student-card strong { color: var(--t1); font-size: 15px; }
.student-card span { margin-top: 4px; color: var(--t3); font-size: 12px; }
.registration-list { display: grid; gap: 12px; }
.batch-card { padding: 18px 20px; }
.batch-card__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.batch-card__head strong, .batch-card__head span { display: block; }
.batch-card__head strong { color: var(--t1); font-size: 15px; }
.batch-card__head span { margin-top: 5px; color: var(--t3); font-size: 12px; }
.batch-card__facts { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 16px 0 0; }
.batch-card__facts div { padding: 11px 12px; border-radius: 10px; background: var(--bg2); }
.batch-card__facts dt { color: var(--t4); font-size: 11px; }
.batch-card__facts dd { margin: 5px 0 0; color: var(--t1); font-size: 13px; font-weight: 600; }
.batch-card__block, .batch-card__deferral { display: grid; gap: 4px; margin-top: 12px; padding: 11px 13px; border-radius: 10px; font-size: 12px; }
.batch-card__block { background: var(--bad-bg); color: var(--bad-fg); }
.batch-card__deferral { background: var(--warn-bg); color: var(--warn-fg); }
.batch-card__defer-form { display: grid; gap: 6px; margin-top: 14px; }
.batch-card__defer-form label { color: var(--t2); font-size: 12px; font-weight: 600; }
.batch-card__defer-form textarea { min-height: 76px; resize: vertical; }
.batch-card__actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 16px; padding-top: 14px; border-top: 1px solid var(--line2); }
@media (max-width: 720px) {
  .registration-hero, .student-card, .batch-card__head { align-items: stretch; flex-direction: column; }
  .batch-card__facts { grid-template-columns: 1fr; }
  .batch-card__actions { flex-direction: column-reverse; }
  .batch-card__actions .sp-btn { width: 100%; }
}
</style>
