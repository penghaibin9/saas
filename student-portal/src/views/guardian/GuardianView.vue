<template>
  <div class="gd-root">
    <div v-if="!loggedIn" class="gd-gate">
      <div class="gd-card gd-login-card">
        <div class="gd-login-head">
          <span class="gd-logo">家</span>
          <div class="gd-title">{{ school }} · 家长端</div>
          <div class="gd-sub">手机号验证码登录 · 授权信息只读 · 实习知情确认可办理</div>
        </div>
        <div v-if="hasLinkedTask" class="gd-link-hint">
          已从学校短信进入岗位实习知情确认，请使用收到短信的监护人手机号登录后继续。
        </div>
        <label class="gd-label" for="guardian-phone">监护人手机号</label>
        <input id="guardian-phone" v-model.trim="phone" class="gd-inp" type="tel" inputmode="numeric"
               autocomplete="tel" maxlength="11" placeholder="请输入11位手机号" @keyup.enter="doLogin" />
        <label class="gd-label" for="guardian-code">短信验证码</label>
        <div class="gd-code-row">
          <input id="guardian-code" v-model.trim="code" class="gd-inp" type="text" inputmode="numeric"
                 autocomplete="one-time-code" maxlength="6" placeholder="6位验证码" @keyup.enter="doLogin" />
          <button type="button" class="gd-codebtn" :disabled="cooldown > 0 || sending" @click="sendCode">
            {{ cooldown > 0 ? cooldown + 's' : sending ? '发送中…' : '获取验证码' }}
          </button>
        </div>
        <div v-if="devCode" class="gd-dev">联调验证码：<b>{{ devCode }}</b>（正式短信开启后不会显示）</div>
        <div v-if="error" class="gd-err" role="alert">{{ error }}</div>
        <button type="button" class="gd-btn" :disabled="loading || phone.length !== 11 || code.length !== 6" @click="doLogin">
          {{ loading ? '登录中…' : '登录并继续' }}
        </button>
        <div class="gd-foot-note">除岗位实习知情确认外，家长端不提供修改、审批或代学生提交功能。</div>
      </div>
    </div>

    <div v-else>
      <header class="gd-header">
        <div class="gd-header-brand">
          <span class="gd-logo gd-logo--sm">家</span>
          <div>
            <div class="gd-header-title">{{ school }} · 家长端</div>
            <div class="gd-header-sub">当前学生：{{ student.studentName || '未选择' }}（{{ student.studentNo || '—' }}）</div>
          </div>
        </div>
        <div class="gd-header-actions">
          <span class="gd-ro">授权信息只读 · 知情确认可办理</span>
          <button type="button" class="gd-link-btn" :disabled="loading" @click="loadAll">刷新</button>
          <button type="button" class="gd-link-btn" @click="logout">退出</button>
        </div>
      </header>

      <main class="gd-main">
        <div v-if="error" class="gd-alert gd-alert--error" role="alert">{{ error }}</div>
        <div class="gd-note">
          本页仅展示学生本人授权的范围；心理关注、家庭隐私材料、证件号和联系方式明文不向家长开放。
        </div>

        <section class="gd-section">
          <div class="gd-section-head">
            <div>
              <h2>岗位实习知情确认</h2>
              <p>必须从学校发送的一次性短信链接进入，并完成手机号验证码登录。打开正文不等于确认。</p>
            </div>
            <span class="gd-count">{{ pendingConsentCount }} 项待确认</span>
          </div>

          <div v-if="consentLoading" class="gd-empty">正在加载知情确认任务…</div>
          <div v-else-if="consentError" class="gd-alert gd-alert--error">{{ consentError }}</div>

          <article v-if="consentDetail" class="gd-consent-detail">
            <div class="gd-consent-meta">
              <div>
                <strong>岗位实习知情书</strong>
                <span class="gd-version">正文版本 {{ consentDetail.contentVersion || '—' }}</span>
              </div>
              <span :class="['gd-status', `is-${String(consentDetail.status || '').toLowerCase()}`]">
                {{ consentStatusText(consentDetail.status) }}
              </span>
            </div>
            <div class="gd-consent-party">
              确认人：{{ consentDetail.participantName || '监护人' }}
              <span v-if="consentDetail.participantRelation">（{{ relationText(consentDetail.participantRelation) }}）</span>
              <span v-if="consentDetail.contactMasked"> · {{ consentDetail.contactMasked }}</span>
            </div>
            <div class="gd-document" tabindex="0">{{ consentDetail.contentSnapshot || '正文暂不可用，请联系学校重新下发。' }}</div>

            <template v-if="consentDetail.status === 'PENDING'">
              <label class="gd-check">
                <input v-model="readAccepted" type="checkbox" />
                <span>我已阅读完整正文，确认本次操作由监护人本人完成，并知悉确认后将形成审计留痕。</span>
              </label>
              <button type="button" class="gd-btn gd-btn--inline" :disabled="confirming || !readAccepted" @click="confirmLinkedConsent">
                {{ confirming ? '确认中…' : '本人确认知情' }}
              </button>
            </template>
            <div v-else-if="consentDetail.status === 'VALID'" class="gd-alert gd-alert--success">
              已于 {{ formatTime(consentDetail.confirmedAt) }} 完成监护人本人确认。
            </div>
            <div v-else class="gd-alert">当前任务不可继续办理，请联系学校重新下发。</div>
          </article>

          <div v-if="!consentLoading && !consentDetail" class="gd-empty">
            {{ hasLinkedTask ? '请先完成登录，系统将自动打开短信对应任务。' : '当前没有通过本次短信链接打开的待确认正文。' }}
          </div>

          <div v-if="consents.length" class="gd-task-list">
            <div v-for="item in consents" :key="item.id" class="gd-task-row">
              <div>
                <div class="gd-task-title">岗位实习知情确认 · {{ item.participantName || '监护人' }}</div>
                <div class="gd-task-sub">版本 {{ item.contentVersion || '—' }} · 下发 {{ formatTime(item.deliveredAt) }}</div>
              </div>
              <div class="gd-task-actions">
                <span :class="['gd-status', `is-${String(item.status || '').toLowerCase()}`]">{{ consentStatusText(item.status) }}</span>
                <button v-if="canOpenLinked(item)" type="button" class="gd-link-btn" @click="loadLinkedConsent">打开正文</button>
                <span v-else-if="item.status === 'PENDING'" class="gd-task-tip">请使用最新短信链接</span>
              </div>
            </div>
          </div>
        </section>

        <section class="gd-section">
          <div class="gd-section-head">
            <div>
              <h2>学生授权信息</h2>
              <p>以下内容只读，授权范围由学生本人管理。</p>
            </div>
            <select v-if="students.length > 1" v-model="activeLinkId" class="gd-select" @change="loadOverview">
              <option v-for="item in students" :key="item.linkId" :value="item.linkId">
                {{ item.studentName }}（{{ item.studentNo }}）
              </option>
            </select>
          </div>

          <div v-if="student.studentName" class="gd-stu">
            <span class="gd-stu__av">{{ student.studentName.slice(0, 1) }}</span>
            <div>
              <div class="gd-stu-name">{{ student.studentName }}</div>
              <div class="gd-stu-meta">{{ student.college || '—' }} · {{ student.major || '—' }} · {{ student.className || '—' }} · {{ student.stage || '—' }}</div>
            </div>
          </div>
          <div v-else class="gd-empty">暂无有效学生授权，请联系学生核对家长授权关系。</div>

          <div class="gd-grid">
            <section v-for="card in cards" :key="card.scope" class="gd-scope">
              <div class="gd-scope-head">
                <span>{{ card.title }}</span>
                <span :class="card.on ? 'gd-tag gd-tag--on' : 'gd-tag'">{{ card.on ? '已授权' : '未授权' }}</span>
              </div>
              <div v-if="card.on" class="gd-scope__body" :class="{ 'gd-scope__body--alert': card.alert }">{{ card.desc }}</div>
              <div v-else class="gd-scope__off">该范围未授权，如需查看请联系学生在门户“我的档案 · 家长授权”中开通。</div>
            </section>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import guardianApi from '../../services/guardianApi'

const LINK_SESSION_KEY = 'guardian_consent_link_v1'
const phone = ref('')
const code = ref('')
const devCode = ref('')
const error = ref('')
const consentError = ref('')
const loading = ref(false)
const sending = ref(false)
const confirming = ref(false)
const consentLoading = ref(false)
const cooldown = ref(0)
const sessionToken = ref(guardianApi.getToken())
const students = ref([])
const activeLinkId = ref('')
const overview = ref({})
const consents = ref([])
const consentDetail = ref(null)
const linkedConsentId = ref('')
const linkedToken = ref('')
const readAccepted = ref(false)

const loggedIn = computed(() => !!sessionToken.value)
const school = computed(() => '学生服务门户')
const student = computed(() => students.value.find((item) => String(item.linkId) === String(activeLinkId.value)) || students.value[0] || {})
const hasLinkedTask = computed(() => !!linkedConsentId.value && !!linkedToken.value)
const pendingConsentCount = computed(() => consents.value.filter((item) => item.status === 'PENDING').length)

const SCOPE_CARDS = [
  { scope: 'ACADEMIC_GRADE', title: '学业成绩与课表' },
  { scope: 'FEE_AID_STATUS', title: '缴费与资助办理状态' },
  { scope: 'CAMPUS_ALERT', title: '在校异常与安全提醒' },
  { scope: 'CAREER_PROGRESS', title: '毕业 / 实习 / 就业进度' }
]

function renderScope(scope, data = {}) {
  if (scope === 'ACADEMIC_GRADE') return `平均绩点 GPA ${data.gpa ?? '—'} · 已获学分 ${data.earnedCredits ?? 0} / ${data.requiredCredits ?? '—'} · 已修 ${data.courseCount ?? 0} 门 · 平均分 ${data.avgScore ?? '—'}`
  if (scope === 'FEE_AID_STATUS') return data.note || '仅展示办理状态，不展示家庭隐私材料和金额明细。'
  if (scope === 'CAMPUS_ALERT') return data.safe ? '近期无对家长开放的异常提醒。' : `${data.warningCount || 0} 项提醒：${data.latest || '请关注'}`
  if (scope === 'CAREER_PROGRESS') return `当前阶段：${data.stage || '在校'}\n实习：${data.internshipEnterprise || '—'}${data.internshipStatus ? `（${data.internshipStatus}）` : ''}\n就业：${data.employmentDestination || '待登记'}${data.employmentCompany ? `（${data.employmentCompany}）` : ''}`
  return ''
}

const cards = computed(() => {
  const scopes = student.value.visibleScopes || []
  const scopeData = overview.value.scopes || {}
  return SCOPE_CARDS.map((card) => {
    const on = scopes.includes(card.scope)
    const data = scopeData[card.scope] || {}
    return {
      ...card,
      on,
      alert: card.scope === 'CAMPUS_ALERT' && on && !data.safe,
      desc: on ? renderScope(card.scope, data) : ''
    }
  })
})

const CONSENT_STATUS = {
  PENDING: '待本人确认', VALID: '已确认', REJECTED: '已拒绝', EXPIRED: '已过期',
  SUPERSEDED: '已被新版本替代', REVOKED: '已作废', NOT_APPLICABLE: '无需确认'
}
const RELATION = { FATHER: '父亲', MOTHER: '母亲', GUARDIAN: '监护人', PARENT: '家长', OTHER: '其他' }
function consentStatusText(status) { return CONSENT_STATUS[status] || status || '未知状态' }
function relationText(value) { return RELATION[value] || value || '监护人' }
function formatTime(value) { return value ? String(value).replace('T', ' ').slice(0, 16) : '—' }
function canOpenLinked(item) { return hasLinkedTask.value && String(item.id) === String(linkedConsentId.value) && item.status === 'PENDING' }

function persistLink() {
  try {
    if (hasLinkedTask.value) sessionStorage.setItem(LINK_SESSION_KEY, JSON.stringify({ consentId: linkedConsentId.value, token: linkedToken.value }))
    else sessionStorage.removeItem(LINK_SESSION_KEY)
  } catch { /* session storage unavailable */ }
}

function restoreLink() {
  const params = new URLSearchParams(window.location.search)
  const fromUrl = { consentId: params.get('consentId') || '', token: params.get('token') || '' }
  let saved = null
  try { saved = JSON.parse(sessionStorage.getItem(LINK_SESSION_KEY) || 'null') } catch { saved = null }
  linkedConsentId.value = fromUrl.consentId || saved?.consentId || ''
  linkedToken.value = fromUrl.token || saved?.token || ''
  persistLink()
  if (fromUrl.consentId || fromUrl.token) {
    window.history.replaceState({}, document.title, window.location.pathname)
  }
}

async function sendCode() {
  if (!/^\d{11}$/.test(phone.value)) { error.value = '请输入11位监护人手机号'; return }
  sending.value = true
  error.value = ''
  try {
    const data = await guardianApi.requestOtp(phone.value)
    devCode.value = data?.devCode || ''
    cooldown.value = 60
    const timer = window.setInterval(() => {
      cooldown.value -= 1
      if (cooldown.value <= 0) window.clearInterval(timer)
    }, 1000)
  } catch (err) {
    error.value = err?.message || '验证码发送失败'
  } finally {
    sending.value = false
  }
}

async function doLogin() {
  if (!/^\d{11}$/.test(phone.value)) { error.value = '请输入11位监护人手机号'; return }
  if (!/^\d{6}$/.test(code.value)) { error.value = '请输入6位短信验证码'; return }
  loading.value = true
  error.value = ''
  try {
    await guardianApi.login(phone.value, code.value)
    sessionToken.value = guardianApi.getToken()
    await loadAll()
  } catch (err) {
    error.value = err?.message || '登录失败'
  } finally {
    loading.value = false
  }
}

async function loadOverview() {
  overview.value = {}
  if (!activeLinkId.value) return
  try {
    overview.value = await guardianApi.studentOverview(activeLinkId.value) || {}
  } catch (err) {
    error.value = err?.message || '学生授权信息加载失败'
  }
}

async function loadConsents() {
  consentError.value = ''
  try {
    const data = await guardianApi.consents()
    consents.value = Array.isArray(data) ? data : (data?.items || [])
  } catch (err) {
    consents.value = []
    consentError.value = err?.message || '知情确认任务加载失败'
  }
}

async function loadLinkedConsent() {
  if (!hasLinkedTask.value) return
  consentLoading.value = true
  consentError.value = ''
  readAccepted.value = false
  try {
    consentDetail.value = await guardianApi.consentDetail(linkedConsentId.value, linkedToken.value)
  } catch (err) {
    consentDetail.value = null
    consentError.value = err?.message || '确认链接无效、已过期或已使用，请联系学校重新发送'
  } finally {
    consentLoading.value = false
  }
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const data = await guardianApi.students()
    students.value = data?.items || []
    if (!students.value.some((item) => String(item.linkId) === String(activeLinkId.value))) {
      activeLinkId.value = students.value[0]?.linkId || ''
    }
    await Promise.all([loadOverview(), loadConsents()])
    if (hasLinkedTask.value) await loadLinkedConsent()
  } catch (err) {
    if (err?.status === 401) logout(false)
    error.value = err?.message || '家长端数据加载失败'
  } finally {
    loading.value = false
  }
}

function deviceDigestSeed() {
  const key = 'guardian_device_session_v1'
  try {
    let value = sessionStorage.getItem(key)
    if (!value) {
      value = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`
      sessionStorage.setItem(key, value)
    }
    return value
  } catch { return `${Date.now()}-${Math.random()}` }
}

async function confirmLinkedConsent() {
  if (!consentDetail.value || !hasLinkedTask.value || !readAccepted.value) return
  confirming.value = true
  consentError.value = ''
  try {
    consentDetail.value = await guardianApi.confirmConsent(linkedConsentId.value, {
      token: linkedToken.value,
      expectedVersion: consentDetail.value.version,
      contentVersion: consentDetail.value.contentVersion,
      contentHash: consentDetail.value.contentHash,
      deviceDigest: deviceDigestSeed()
    })
    linkedToken.value = ''
    persistLink()
    await loadConsents()
  } catch (err) {
    consentError.value = err?.message || '确认失败，请刷新后重试'
    await loadConsents()
    const latest = consents.value.find((item) => String(item.id) === String(linkedConsentId.value))
    if (latest?.status === 'VALID') {
      consentDetail.value = { ...consentDetail.value, ...latest }
      linkedToken.value = ''
      persistLink()
    } else if (hasLinkedTask.value) {
      await loadLinkedConsent()
    }
  } finally {
    confirming.value = false
  }
}

function logout(clearLink = false) {
  guardianApi.clearSession()
  sessionToken.value = ''
  students.value = []
  overview.value = {}
  consents.value = []
  consentDetail.value = null
  error.value = ''
  if (clearLink) {
    linkedConsentId.value = ''
    linkedToken.value = ''
    persistLink()
  }
}

onMounted(async () => {
  restoreLink()
  if (loggedIn.value) await loadAll()
})
</script>

<style scoped>
.gd-root{min-height:100vh;background:var(--bg,#f5f7fa);color:var(--t1,#1d2129)}
.gd-gate{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:24px}
.gd-card,.gd-section{background:#fff;border:1px solid var(--line,#e5e7eb);border-radius:16px;box-shadow:0 12px 36px rgba(16,24,40,.06)}
.gd-login-card{width:400px;max-width:92vw;padding:32px}
.gd-login-head{display:flex;flex-direction:column;align-items:center;margin-bottom:22px}
.gd-logo{width:48px;height:48px;border-radius:14px;background:var(--pri,#2563eb);color:#fff;display:inline-flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;margin-bottom:12px}
.gd-logo--sm{width:34px;height:34px;border-radius:10px;font-size:15px;margin:0}
.gd-title{font-size:17px;font-weight:700}.gd-sub,.gd-header-sub{font-size:12px;color:var(--t3,#86909c);margin-top:5px}
.gd-label{display:block;font-size:12.5px;font-weight:600;margin:12px 0 6px}
.gd-inp,.gd-select{height:42px;border:1px solid #d9dde5;border-radius:9px;padding:0 12px;font-size:14px;box-sizing:border-box;width:100%;background:#fff}
.gd-inp:focus,.gd-select:focus{outline:none;border-color:var(--pri,#2563eb);box-shadow:0 0 0 3px rgba(37,99,235,.08)}
.gd-code-row{display:flex;gap:8px}.gd-code-row .gd-inp{flex:1}
.gd-codebtn,.gd-link-btn{border:1px solid #bfd2ff;background:#fff;color:var(--pri,#2563eb);border-radius:9px;padding:0 14px;cursor:pointer;white-space:nowrap}
.gd-link-btn{height:32px}.gd-codebtn:disabled,.gd-link-btn:disabled,.gd-btn:disabled{opacity:.55;cursor:not-allowed}
.gd-btn{width:100%;height:42px;border:0;border-radius:9px;background:var(--pri,#2563eb);color:#fff;font-weight:700;cursor:pointer;margin-top:14px}
.gd-btn--inline{width:auto;padding:0 22px;margin-top:14px}
.gd-link-hint,.gd-dev,.gd-alert,.gd-note{padding:10px 12px;border-radius:9px;font-size:12.5px;line-height:1.6;margin-bottom:12px}
.gd-link-hint,.gd-note{background:#eef4ff;color:#1d4ed8}.gd-dev{background:#fff7e6;color:#8b5c00;margin-top:10px}.gd-err,.gd-alert--error{color:#b42318;background:#fff1f0}.gd-err{font-size:12.5px;margin-top:10px}.gd-alert--success{color:#067647;background:#ecfdf3}
.gd-foot-note{margin-top:16px;font-size:11.5px;color:#98a0ae;text-align:center;line-height:1.6}
.gd-header{height:62px;background:#fff;border-bottom:1px solid var(--line,#e5e7eb);display:flex;align-items:center;justify-content:space-between;padding:0 28px;gap:16px}
.gd-header-brand,.gd-header-actions{display:flex;align-items:center;gap:12px}.gd-header-title{font-size:15px;font-weight:700}.gd-ro{font-size:12px;color:#475467;background:#f2f4f7;border-radius:16px;padding:6px 10px}
.gd-main{max-width:1120px;margin:0 auto;padding:24px 28px 48px}.gd-section{padding:20px;margin-top:16px}
.gd-section-head,.gd-consent-meta,.gd-scope-head,.gd-task-row,.gd-task-actions{display:flex;align-items:center;justify-content:space-between;gap:12px}.gd-section-head{align-items:flex-start;margin-bottom:16px}.gd-section-head h2{font-size:17px;margin:0}.gd-section-head p{font-size:12.5px;color:#86909c;margin:5px 0 0}.gd-count{font-size:12px;background:#fff7e6;color:#8b5c00;border-radius:14px;padding:5px 10px;white-space:nowrap}
.gd-consent-detail{border:1px solid #dbe7ff;background:#fbfdff;border-radius:12px;padding:18px}.gd-consent-meta strong{font-size:16px}.gd-version{font-size:12px;color:#86909c;margin-left:10px}.gd-consent-party{font-size:12.5px;color:#667085;margin-top:8px}.gd-document{white-space:pre-wrap;line-height:1.9;max-height:420px;overflow:auto;background:#fff;border:1px solid #e4e7ec;border-radius:10px;padding:18px;margin-top:14px;font-size:14px}.gd-check{display:flex;align-items:flex-start;gap:8px;font-size:13px;line-height:1.6;margin-top:14px}.gd-check input{margin-top:4px}
.gd-status{font-size:12px;border-radius:14px;padding:5px 9px;background:#f2f4f7;color:#475467;white-space:nowrap}.gd-status.is-pending{background:#fff7e6;color:#8b5c00}.gd-status.is-valid{background:#ecfdf3;color:#067647}.gd-status.is-rejected,.gd-status.is-revoked,.gd-status.is-expired{background:#fff1f0;color:#b42318}
.gd-task-list{margin-top:14px;border-top:1px solid #eef0f3}.gd-task-row{padding:12px 0;border-bottom:1px solid #eef0f3}.gd-task-title{font-size:13.5px;font-weight:600}.gd-task-sub,.gd-task-tip{font-size:12px;color:#98a0ae;margin-top:3px}.gd-task-actions{justify-content:flex-end}
.gd-empty{text-align:center;color:#98a0ae;font-size:13px;padding:22px}.gd-stu{display:flex;align-items:center;gap:12px;padding:14px;background:#f8fafc;border-radius:10px;margin-bottom:14px}.gd-stu__av{width:40px;height:40px;border-radius:50%;background:#e8f0ff;color:#1d4ed8;display:flex;align-items:center;justify-content:center;font-weight:700}.gd-stu-name{font-size:15px;font-weight:700}.gd-stu-meta{font-size:12.5px;color:#86909c;margin-top:4px}
.gd-select{width:auto;min-width:220px}.gd-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.gd-scope{border:1px solid #e6e8ec;border-radius:11px;padding:14px}.gd-scope-head{font-size:14px;font-weight:600;margin-bottom:10px}.gd-tag{font-size:11px;border-radius:12px;padding:4px 8px;background:#f2f4f7;color:#98a0ae}.gd-tag--on{background:#ecfdf3;color:#067647}.gd-scope__body,.gd-scope__off{white-space:pre-line;font-size:12.5px;line-height:1.7;color:#475467}.gd-scope__body--alert{color:#b42318}.gd-scope__off{color:#98a0ae}
@media(max-width:760px){.gd-header{height:auto;padding:12px 16px;align-items:flex-start}.gd-header-actions{flex-wrap:wrap;justify-content:flex-end}.gd-ro{display:none}.gd-main{padding:16px}.gd-grid{grid-template-columns:1fr}.gd-section-head,.gd-task-row{flex-direction:column;align-items:stretch}.gd-task-actions{justify-content:flex-start}.gd-select{width:100%}.gd-document{max-height:none}}
</style>
