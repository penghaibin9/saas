<template>
  <div class="gd-root">
    <!-- 登录门 -->
    <div v-if="!loggedIn" class="gd-gate">
      <div class="gd-card">
        <div style="display:flex;flex-direction:column;align-items:center;margin-bottom:22px">
          <span class="gd-logo"><svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21c-4-3-8-6.5-8-11a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 4.5-4 8-8 11z" /></svg></span>
          <div style="text-align:center;font-size:16.5px;font-weight:600;color:#1D2129">{{ school }} · 家长端</div>
          <div style="text-align:center;margin-top:5px;font-size:12.5px;color:#98A0AE">手机号验证码登录 · 仅查看已授权学生信息</div>
        </div>
        <div style="display:flex;flex-direction:column;gap:12px">
          <input v-model.trim="phone" class="gd-inp" placeholder="家长手机号" @keyup.enter="doLogin" />
          <div style="display:flex;gap:8px">
            <input v-model.trim="code" class="gd-inp" style="flex:1" placeholder="验证码" @keyup.enter="doLogin" />
            <button class="gd-codebtn" :disabled="cooldown > 0 || sending" @click="sendCode">{{ cooldown > 0 ? cooldown + 's' : '获取验证码' }}</button>
          </div>
          <div v-if="devCode" class="gd-dev">演示验证码：<b>{{ devCode }}</b>（未开短信，联调直接用）</div>
          <div v-if="error" class="gd-err">{{ error }}</div>
          <button class="gd-btn" :disabled="loading" @click="doLogin">{{ loading ? '登录中…' : '登 录' }}</button>
        </div>
        <div style="margin-top:16px;font-size:11.5px;color:#C6CCD6;text-align:center">此端仅供已授权家长只读查看，无法进行任何提交操作</div>
      </div>
    </div>

    <!-- 看板 -->
    <div v-else>
      <header class="gd-header">
        <div style="display:flex;align-items:center;gap:12px">
          <span class="gd-logo gd-logo--sm"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21c-4-3-8-6.5-8-11a5 5 0 0 1 9-3 5 5 0 0 1 9 3c0 4.5-4 8-8 11z" /></svg></span>
          <div><div style="font-size:14.5px;font-weight:600;color:#1D2129">{{ school }} · 家长端</div><div style="font-size:11.5px;color:#98A0AE">查看学生：{{ stu.studentName }}（{{ stu.studentNo }}）</div></div>
        </div>
        <div style="display:flex;align-items:center;gap:14px">
          <span class="gd-ro"><svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z" /><circle cx="12" cy="12" r="3" /></svg>仅查看 · 只读</span>
          <a style="font-size:12.5px;color:#86909C;cursor:pointer" @click="logout">退出</a>
        </div>
      </header>

      <main class="gd-main">
        <div class="gd-note">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#1D4ED8" stroke-width="2" stroke-linecap="round" style="flex:none;margin-top:1px"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></svg>
          本页仅展示学生本人授权的四项范围；心理关注、家庭隐私材料明细、证件号等敏感信息不对家长开放。
        </div>

        <div class="gd-stu">
          <span class="gd-stu__av">{{ (stu.studentName || '学').slice(0,1) }}</span>
          <div>
            <div style="font-size:16px;font-weight:600;color:#1D2129">{{ stu.studentName }}</div>
            <div style="margin-top:4px;font-size:12.5px;color:#86909C">{{ stu.college }} · {{ stu.major }} · {{ stu.className }} · {{ stu.stage }}</div>
          </div>
        </div>

        <div class="gd-grid">
          <section v-for="c in cards" :key="c.scope" class="gd-scope">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
              <span style="font-size:15px;font-weight:600;color:#1D2129">{{ c.title }}</span>
              <span :class="c.on ? 'gd-tag gd-tag--on' : 'gd-tag'">{{ c.on ? '已授权' : '未授权' }}</span>
            </div>
            <div v-if="c.on" class="gd-scope__body" :class="{ 'gd-scope__body--alert': c.alert }">{{ c.desc }}</div>
            <div v-else class="gd-scope__off">该范围未授权，如需查看请联系学生在门户「我的档案 · 家长授权」中开通。</div>
          </section>
        </div>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

const API_BASE = (() => {
  const env = (typeof import.meta !== 'undefined' && import.meta.env) || {}
  if (env.VITE_API_BASE_URL) return String(env.VITE_API_BASE_URL).replace(/\/+$/, '')
  if (env.DEV) return 'http://localhost:8000'
  return ''
})()
const TOKEN_KEY = 'sp_guardian_v1'

const phone = ref('')
const code = ref('')
const devCode = ref('')
const error = ref('')
const loading = ref(false)
const sending = ref(false)
const cooldown = ref(0)
const token = ref(localStorage.getItem(TOKEN_KEY) || '')
const students = ref([])
const overview = ref({})

const loggedIn = computed(() => !!token.value)
const school = computed(() => '学生服务门户')
const stu = computed(() => students.value[0] || {})
const SCOPE_CARDS = [
  { scope: 'ACADEMIC_GRADE', title: '① 学业成绩与课表' },
  { scope: 'FEE_AID_STATUS', title: '② 缴费与资助办理状态' },
  { scope: 'CAMPUS_ALERT', title: '③ 在校异常与安全提醒' },
  { scope: 'CAREER_PROGRESS', title: '④ 毕业 / 实习 / 就业进度' }
]
function renderScope(scope, d) {
  d = d || {}
  if (scope === 'ACADEMIC_GRADE') return `平均绩点 GPA ${d.gpa ?? '—'} · 已获学分 ${d.earnedCredits ?? 0} / ${d.requiredCredits ?? '—'} · 已修 ${d.courseCount ?? 0} 门 · 平均分 ${d.avgScore ?? '—'}`
  if (scope === 'FEE_AID_STATUS') return d.note || '缴费与资助状态正常'
  if (scope === 'CAMPUS_ALERT') return d.safe ? '近期无异常提醒，在校状态正常。' : `${d.warningCount || 0} 项提醒：${d.latest || '请关注'}`
  if (scope === 'CAREER_PROGRESS') return `当前阶段：${d.stage || '在校'}\n实习：${d.internshipEnterprise || '—'}${d.internshipStatus ? '（' + d.internshipStatus + '）' : ''}\n就业：${d.employmentDestination || '待登记'}${d.employmentCompany ? '（' + d.employmentCompany + '）' : ''}`
  return ''
}
const cards = computed(() => {
  const scopes = stu.value.visibleScopes || []
  const s = overview.value.scopes || {}
  return SCOPE_CARDS.map((c) => {
    const on = scopes.includes(c.scope)
    return { ...c, on, alert: c.scope === 'CAMPUS_ALERT' && !(s[c.scope] || {}).safe && on, desc: on ? renderScope(c.scope, s[c.scope]) : '' }
  })
})

async function api(path, { method = 'GET', body, auth = false } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  if (auth && token.value) headers.Authorization = `Bearer ${token.value}`
  const res = await fetch(`${API_BASE}/api/v1${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined })
  const payload = await res.json().catch(() => null)
  if (!payload || payload.code !== 0) throw new Error(payload?.message || `请求失败(${res.status})`)
  return payload.data
}

async function sendCode() {
  if (!/^\d{11}$/.test(phone.value)) { error.value = '请输入 11 位手机号'; return }
  sending.value = true; error.value = ''
  try {
    const d = await api('/portal/guardian/otp', { method: 'POST', body: { phone: phone.value } })
    devCode.value = d?.devCode || ''
    cooldown.value = 60
    const t = setInterval(() => { cooldown.value -= 1; if (cooldown.value <= 0) clearInterval(t) }, 1000)
  } catch (e) { error.value = e?.message || '验证码发送失败' } finally { sending.value = false }
}
async function doLogin() {
  if (!phone.value || !code.value) { error.value = '请输入手机号与验证码'; return }
  loading.value = true; error.value = ''
  try {
    const d = await api('/portal/guardian/login', { method: 'POST', body: { phone: phone.value, code: code.value } })
    token.value = d?.accessToken || ''
    localStorage.setItem(TOKEN_KEY, token.value)
    await loadStudents()
  } catch (e) { error.value = e?.message || '登录失败' } finally { loading.value = false }
}
async function loadStudents() {
  try {
    const d = await api('/portal/guardian/students', { auth: true })
    students.value = d?.items || []
    const lid = students.value[0]?.linkId
    if (lid) overview.value = await api(`/portal/guardian/students/${lid}/overview`, { auth: true }).catch(() => ({}))
  } catch (e) { logout() }
}
function logout() { token.value = ''; localStorage.removeItem(TOKEN_KEY); students.value = []; overview.value = {} }

onMounted(() => { if (token.value) loadStudents() })
</script>

<style scoped>
.gd-root { min-height: 100vh; background: var(--bg); }
.gd-gate { min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 24px; }
.gd-card { width: 380px; max-width: 92vw; background: #fff; border: 1px solid var(--line); border-radius: 20px; box-shadow: 0 20px 60px -20px rgba(16,24,40,.18); padding: 34px 30px; }
.gd-logo { width: 48px; height: 48px; border-radius: 13px; background: linear-gradient(135deg, var(--g2), var(--g1)); display: flex; align-items: center; justify-content: center; margin-bottom: 12px; }
.gd-logo--sm { width: 34px; height: 34px; border-radius: 10px; margin-bottom: 0; }
.gd-inp { height: 42px; border: 1px solid #DDE1E8; border-radius: 10px; padding: 0 14px; font-size: 14px; box-sizing: border-box; width: 100%; }
.gd-inp:focus { outline: none; border-color: var(--pri); }
.gd-codebtn { flex: none; padding: 0 14px; border: 1px solid var(--pri-100); background: #fff; color: var(--pri); border-radius: 10px; font-size: 12.5px; cursor: pointer; }
.gd-codebtn:disabled { opacity: .55; cursor: not-allowed; }
.gd-dev { font-size: 12px; color: var(--warn-fg); background: var(--warn-bg); border-radius: 8px; padding: 7px 10px; }
.gd-err { font-size: 12.5px; color: var(--danger-fg); }
.gd-btn { height: 42px; border: none; border-radius: 10px; background: var(--pri); color: #fff; font-size: 14px; font-weight: 600; cursor: pointer; }
.gd-btn:hover { background: var(--pri-h); }
.gd-btn:disabled { opacity: .7; }

.gd-header { height: 60px; background: #fff; border-bottom: 1px solid var(--line); display: flex; align-items: center; justify-content: space-between; padding: 0 28px; }
.gd-ro { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 12px; background: #F2F3F5; color: var(--t2); border-radius: 14px; font-size: 12px; font-weight: 500; }
.gd-main { max-width: 1080px; margin: 0 auto; padding: 26px 32px 48px; }
.gd-note { display: flex; gap: 10px; padding: 12px 16px; background: #EFF6FF; border: 1px solid #DBEAFE; border-radius: 11px; margin-bottom: 20px; font-size: 13px; color: #1D4ED8; line-height: 1.5; }
.gd-stu { display: flex; align-items: center; gap: 16px; background: #fff; border: 1px solid var(--line); border-radius: 16px; padding: 20px 22px; margin-bottom: 18px; }
.gd-stu__av { width: 54px; height: 54px; flex: none; border-radius: 14px; background: linear-gradient(135deg, var(--g2), var(--g1)); color: #fff; font-size: 22px; font-weight: 600; display: flex; align-items: center; justify-content: center; }
.gd-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.gd-scope { background: #fff; border: 1px solid var(--line); border-radius: 16px; padding: 20px 22px; }
.gd-scope__body { font-size: 13px; color: var(--t2); line-height: 1.7; white-space: pre-line; }
.gd-scope__body--alert { color: var(--danger-fg); }
.gd-scope__off { font-size: 13px; color: var(--t4); line-height: 1.7; }
.gd-tag { display: inline-flex; height: 22px; align-items: center; padding: 0 9px; border-radius: 6px; font-size: 11.5px; background: var(--draft-bg); color: var(--draft-fg); }
.gd-tag--on { background: var(--ok-bg); color: var(--ok-fg); }
@media (max-width: 760px) { .gd-grid { grid-template-columns: 1fr; } }
</style>
