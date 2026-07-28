<template>
  <div class="login">
    <!-- 左：视觉区 -->
    <div class="visual">
      <div class="visual__photo">
        <div class="visual__grid" />
        <div class="visual__scan" />
        <div class="visual__fade" />
      </div>
      <div class="visual__top">
        <div style="display:flex;align-items:center;gap:11px">
          <span class="vlogo"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 8.5 12 4.5l9.5 4-9.5 4z" /><path d="M6.5 11v4.2c0 1.3 2.5 2.3 5.5 2.3s5.5-1 5.5-2.3V11M21.5 8.5V13" /></svg></span>
          <span style="color:#fff;font-size:15px;font-weight:600;text-shadow:0 1px 6px rgba(0,0,0,.2)">{{ schoolName }}</span>
        </div>
        <div class="vstatus"><span class="vstatus__dot" />系统运行正常</div>
      </div>
      <div class="vtags">
        <span class="vtag">🔒 数据加密传输</span><span class="vtag">👁 仅本人可见</span>
      </div>
      <div class="visual__bottom">
        <div style="color:#fff;font-size:32px;font-weight:700;line-height:1.35;max-width:460px;text-shadow:0 2px 12px rgba(0,0,0,.18)">你好呀，欢迎回来<br>继续你的校园时光</div>
        <div style="color:rgba(255,255,255,.82);font-size:14px;margin-top:12px;max-width:420px;line-height:1.7">重任务、传材料、下证明、填长表单——学生 PC 门户陪你办完在校的每一件事。</div>
        <div class="idcard">
          <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:14px"><span style="font-size:10.5px;letter-spacing:1.5px;color:rgba(255,255,255,.75);font-weight:600">STUDENT ID</span><span style="font-size:10px;padding:2px 8px;border-radius:5px;background:rgba(255,255,255,.22);color:#fff">在校学生</span></div>
          <div style="display:flex;align-items:center;gap:12px">
            <span class="idav">{{ (demoName).slice(0,1) }}</span>
            <div><div style="color:#fff;font-size:15px;font-weight:600">{{ demoName }}</div><div style="color:rgba(255,255,255,.75);font-size:11.5px;margin-top:2px">数字媒体技术 · 学生门户</div></div>
          </div>
          <div class="idbar" />
        </div>
      </div>
    </div>

    <!-- 右：表单 -->
    <div class="form">
      <div style="width:100%;max-width:320px">
        <div style="font-size:11px;font-weight:700;letter-spacing:1.6px;color:#8A94A6">STUDENT PORTAL</div>
        <div style="display:flex;align-items:baseline;justify-content:space-between;margin-top:9px">
          <span style="font-size:27px;font-weight:700;color:#11151A;letter-spacing:-.3px">登录</span>
          <div style="display:flex;align-items:center;gap:9px">
            <a class="modet" :class="{ on: mode==='account' }" @click="mode='account'">账号密码</a>
            <span style="color:#DFE3E8;font-size:12px">/</span>
            <a class="modet" :class="{ on: mode==='qr' }" @click="mode='qr'">微信扫码</a>
          </div>
        </div>
        <div style="margin-top:7px;font-size:13.5px;color:#8A94A6;line-height:1.6">{{ mode==='qr' ? '打开微信扫一扫，快速登录学生服务门户' : ('使用学号和密码访问' + schoolName + '学生服务门户') }}</div>

        <div v-if="mode==='account'" style="display:flex;flex-direction:column;gap:16px;margin-top:26px">
          <div>
            <div class="flabel">学校编码（多校账号时必填）</div>
            <input v-model.trim="tenantCode" class="finput" placeholder="如 sandbox-school / demo-school" @keyup.enter="doLogin" />
          </div>
          <div>
            <div class="flabel">账号</div>
            <input v-model.trim="loginName" class="finput" placeholder="学号 / 账号" @keyup.enter="doLogin" />
          </div>
          <div>
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:7px"><span class="flabel" style="margin:0">密码</span><button class="showpwd" @click="showPwd=!showPwd">{{ showPwd ? '隐藏' : '显示' }}</button></div>
            <input v-model="password" :type="showPwd ? 'text' : 'password'" class="finput" placeholder="密码" @keyup.enter="doLogin" />
          </div>
          <div style="display:flex;align-items:center;justify-content:space-between;margin-top:-4px">
            <label style="display:flex;align-items:center;gap:6px;font-size:12.5px;color:#4E5969;cursor:pointer"><input type="checkbox" checked style="accent-color:var(--pri)">记住我</label>
            <a style="font-size:12.5px;cursor:pointer;color:#8A94A6">忘记密码?</a>
          </div>
          <div v-if="error" class="ferror"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#D92D20" stroke-width="2" stroke-linecap="round" style="flex:none;margin-top:1px"><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16h.01" /></svg>{{ error }}</div>
          <button class="fbtn" :disabled="loading" @click="doLogin"><span v-if="loading" class="spin" />{{ loading ? '登录中…' : '登 录' }}</button>
          <div style="display:flex;align-items:center;gap:12px;margin-top:2px"><span style="flex:1;height:1px;background:#EAECF0" /><span style="font-size:12px;color:#98A2B3">或</span><span style="flex:1;height:1px;background:#EAECF0" /></div>
          <button class="fbtn2" @click="ui.notify('统一身份认证登录对接学校 CAS 后启用')">统一身份认证登录</button>
        </div>

        <div v-else style="display:flex;flex-direction:column;align-items:center;margin-top:26px">
          <div class="qr"><div v-for="n in 40" :key="n" class="qrd" :style="qrStyle(n)" /></div>
          <div style="margin-top:16px;font-size:13.5px;color:#384250;font-weight:600">请使用微信扫一扫</div>
          <div style="margin-top:4px;font-size:12px;color:#98A2B3">对接微信开放平台后为真实二维码</div>
          <button class="fbtn2" style="margin-top:16px" @click="mode='account'">使用账号密码登录</button>
        </div>

        <div v-if="demoAccounts.length" class="demo">
          <div style="font-size:12px;color:#8A94A6;margin-bottom:8px">演示体验账号（仅开发环境展示，不自动填充密码）</div>
          <div style="display:flex;flex-wrap:wrap;gap:8px">
            <button v-for="a in demoAccounts" :key="a.loginName" class="demobtn" @click="fill(a)">{{ a.label }}：{{ a.loginName }}</button>
          </div>
        </div>
        <div style="margin-top:20px;text-align:center;font-size:11.5px;color:#C6CCD6">连接已加密 · 与学生小程序为同一套账号 · 数据范围仅本人</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from '../../stores/session'
import { usePortalConfigStore } from '../../stores/portalConfig'
import { useUiStore } from '../../stores/ui'

const router = useRouter()
const route = useRoute()
const session = useSessionStore()
const cfg = usePortalConfigStore()
const ui = useUiStore()

const loginName = ref('')
const password = ref('')
const tenantCode = ref('')
const error = ref('')
const loading = ref(false)
const showPwd = ref(false)
const mode = ref('account')

const schoolName = computed(() => cfg.brand?.schoolName || '学生服务门户')
const demoName = computed(() => '张同学')
const demoAccounts = computed(() => {
  if (import.meta.env.PROD) return []
  const raw = String(import.meta.env.VITE_DEMO_STUDENT_ACCOUNTS || '').trim()
  if (!raw) return []
  return raw.split(',').map((entry) => {
    const [label, account, schoolCode] = entry.split('|').map((part) => String(part || '').trim())
    return { label: label || '演示账号', loginName: account, tenantCode: schoolCode }
  }).filter((account) => account.loginName)
})
function fill(a) {
  loginName.value = a.loginName
  password.value = ''
  tenantCode.value = a.tenantCode || ''
  error.value = ''
}
function qrStyle(n) {
  const cols = 8
  const x = (n % cols) * 18 + 14, y = Math.floor(n / cols) * 18 + 14
  const on = (n * 7 + 3) % 3 !== 0
  return { left: x + 'px', top: y + 'px', opacity: on ? 1 : 0 }
}

async function doLogin() {
  if (!loginName.value || !password.value) { error.value = '请输入账号与密码'; return }
  loading.value = true
  error.value = ''
  try {
    await session.login(loginName.value, password.value, tenantCode.value || undefined)
    cfg.reset()
    await cfg.load()
    const redirect = route.query.redirect
    router.replace(typeof redirect === 'string' ? redirect : '/home')
  } catch (e) {
    error.value = e?.notStudent ? '请使用学生账号登录学生门户' : (e?.message || '登录失败')
  } finally { loading.value = false }
}
</script>

<style scoped>
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes scanline { 0%,100% { top: 0%; opacity: 0; } 8% { opacity: 1; } 50% { top: 98%; opacity: 1; } 92% { opacity: 0; } }
@keyframes pulseDot { 0%,100% { opacity: 1; } 50% { opacity: .3; } }
@keyframes floatCard { 0%,100% { transform: rotate(-3deg) translateY(0); } 50% { transform: rotate(-3deg) translateY(-8px); } }
@keyframes fadeUp { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }

.login { min-height: 100vh; width: 100%; display: flex; }
.visual { flex: 1.25; position: relative; overflow: hidden; background: linear-gradient(135deg, var(--g2), var(--g1)); min-width: 0; }
.visual__photo { position: absolute; top: 0; left: 0; right: 0; height: 58%; overflow: hidden; }
.visual__grid { position: absolute; inset: 0; background-image: linear-gradient(rgba(255,255,255,.07) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.07) 1px, transparent 1px); background-size: 32px 32px; }
.visual__scan { position: absolute; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, transparent, rgba(255,255,255,.95), transparent); box-shadow: 0 0 14px 2px rgba(255,255,255,.7); animation: scanline 4s ease-in-out infinite; }
.visual__fade { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(10,20,50,.12) 0%, rgba(8,16,42,.05) 55%, var(--g2) 100%); }
.visual__top { position: relative; display: flex; align-items: center; justify-content: space-between; gap: 11px; padding: 34px 40px 0; z-index: 1; }
.vlogo { width: 38px; height: 38px; flex: none; border-radius: 11px; background: rgba(255,255,255,.16); backdrop-filter: blur(6px); display: flex; align-items: center; justify-content: center; border: 1px solid rgba(255,255,255,.28); }
.vstatus { display: flex; align-items: center; gap: 6px; padding: 6px 12px; background: rgba(255,255,255,.14); backdrop-filter: blur(8px); border: 1px solid rgba(255,255,255,.25); border-radius: 20px; font-size: 11px; color: #fff; white-space: nowrap; }
.vstatus__dot { width: 7px; height: 7px; border-radius: 50%; background: #4ADE80; box-shadow: 0 0 6px 1px #4ADE80; animation: pulseDot 2s ease-in-out infinite; }
.vtags { position: absolute; left: 40px; top: calc(58% - 40px); display: flex; gap: 8px; z-index: 1; }
.vtag { display: inline-flex; align-items: center; gap: 5px; padding: 6px 12px; background: rgba(255,255,255,.14); backdrop-filter: blur(8px); border: 1px solid rgba(255,255,255,.25); border-radius: 20px; font-size: 11px; color: #fff; white-space: nowrap; }
.visual__bottom { position: absolute; top: 58%; left: 0; right: 0; bottom: 0; display: flex; flex-direction: column; justify-content: flex-end; padding: 0 44px 46px; }
.idcard { position: relative; margin-top: 34px; width: 250px; background: rgba(255,255,255,.14); backdrop-filter: blur(14px); border: 1px solid rgba(255,255,255,.32); border-radius: 16px; padding: 18px 20px; box-shadow: 0 20px 46px -14px rgba(0,0,0,.45); animation: floatCard 5s ease-in-out infinite; }
.idav { width: 42px; height: 42px; flex: none; border-radius: 11px; background: rgba(255,255,255,.9); color: var(--pri); font-size: 17px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.idbar { margin-top: 14px; height: 14px; border-radius: 3px; background: repeating-linear-gradient(90deg, rgba(255,255,255,.9) 0 2px, transparent 2px 4px, rgba(255,255,255,.5) 4px 5px, transparent 5px 8px); }

.form { width: 452px; flex: none; display: flex; align-items: center; justify-content: center; padding: 40px; background: #fff; }
.form > div { animation: fadeUp .4s ease; }
.modet { cursor: pointer; font-size: 12.5px; font-weight: 700; color: #8A94A6; }
.modet.on { color: #11151A; }
.flabel { font-size: 12.5px; font-weight: 600; color: #384250; margin-bottom: 7px; }
.finput { width: 100%; height: 44px; border: 1.5px solid #DFE3E8; border-radius: 8px; padding: 0 13px; font-size: 14.5px; box-sizing: border-box; color: #11151A; transition: border-color .12s, box-shadow .12s; }
.finput:focus { outline: none; border-color: var(--pri); box-shadow: 0 0 0 3.5px var(--pri-50); }
.showpwd { all: unset; cursor: pointer; font-size: 12px; font-weight: 600; color: var(--pri); }
.ferror { display: flex; gap: 8px; padding: 10px 12px; background: #FDECEC; border: 1px solid #F7C9C1; border-radius: 9px; color: #B42318; font-size: 12.5px; }
.fbtn { all: unset; cursor: pointer; box-sizing: border-box; width: 100%; height: 44px; border-radius: 8px; background: var(--pri); color: #fff; font-size: 14px; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 8px; box-shadow: 0 1px 2px rgba(16,24,40,.06); }
.fbtn:hover { background: var(--pri-h); }
.fbtn:disabled { opacity: .7; cursor: not-allowed; }
.spin { width: 14px; height: 14px; border-radius: 50%; border: 2px solid rgba(255,255,255,.4); border-top-color: #fff; animation: spin .7s linear infinite; }
.fbtn2 { all: unset; cursor: pointer; box-sizing: border-box; width: 100%; height: 44px; border: 1.5px solid #DFE3E8; border-radius: 8px; display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 13.5px; font-weight: 600; color: #384250; }
.fbtn2:hover { background: #F9FAFB; border-color: #C9CED6; }
.qr { position: relative; width: 168px; height: 168px; border: 1.5px solid #E5E8EE; border-radius: 14px; background: #fff; overflow: hidden; }
.qrd { position: absolute; width: 8px; height: 8px; background: #11151A; border-radius: 1px; }
.demo { margin-top: 22px; padding-top: 16px; border-top: 1px dashed #E5E6EB; }
.demobtn { all: unset; cursor: pointer; font-size: 12px; border: 1px solid #DFE3E8; background: #fff; border-radius: 6px; padding: 6px 10px; }
.demobtn:hover { border-color: var(--pri); color: var(--pri); }
@media (max-width: 860px) { .visual { display: none; } .form { width: 100%; } }
</style>
