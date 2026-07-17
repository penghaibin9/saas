<template>
  <div class="sp-page">
    <section class="sp-hero">
      <div>
        <p class="sp-eyebrow">我的档案</p>
        <h1>{{ info.name || '我的学籍信息' }}</h1>
        <p class="sp-hero__sub">学籍信息只读，敏感字段默认脱敏；查看明文需填写原因并留痕。</p>
      </div>
      <button class="sp-btn sp-btn--ghost" :disabled="loading" @click="load">刷新</button>
    </section>

    <StateBlock v-if="loading" type="loading" text="正在加载学籍信息…" />
    <StateBlock v-else-if="error" type="error" :text="error" />
    <template v-else>
      <section v-if="!info.hasData" class="sp-notice">
        <strong>暂无学籍档案</strong>
        <p>{{ info.message || '尚未建立你的学籍档案，请联系学院教务。' }}</p>
      </section>

      <section class="sp-panel">
        <div class="sp-panel__head">学籍信息</div>
        <dl class="sp-desc">
          <div><dt>姓名</dt><dd>{{ info.name || '—' }}</dd></div>
          <div><dt>学号</dt><dd>{{ info.studentNo || '—' }}</dd></div>
          <div><dt>性别</dt><dd>{{ info.gender || '—' }}</dd></div>
          <div><dt>年级</dt><dd>{{ info.grade || '—' }}</dd></div>
          <div><dt>学院</dt><dd>{{ info.collegeName || '—' }}</dd></div>
          <div><dt>专业</dt><dd>{{ info.majorName || '—' }}</dd></div>
          <div><dt>班级</dt><dd>{{ info.className || '—' }}</dd></div>
          <div><dt>入学日期</dt><dd>{{ info.enrollDate || '—' }}</dd></div>
          <div>
            <dt>当前阶段</dt>
            <dd><StatusTag :text="info.stageLabel || info.stage || '—'" tone="default" /></dd>
          </div>
          <div>
            <dt>学籍状态</dt>
            <dd><StatusTag :text="statusText(info.studentStatus)" :tone="info.studentStatus === 'NORMAL' ? 'success' : 'warn'" /></dd>
          </div>
          <div class="sp-desc__wide">
            <dt>手机号</dt>
            <dd>
              <span>{{ reveal.phone || info.phoneMasked || '—' }}</span>
              <button v-if="canReveal('phone') && !reveal.phone && revealingField !== 'phone'" class="sp-link" :disabled="busy" @click="startReveal('phone')">查看明文</button>
              <template v-if="revealingField === 'phone'">
                <input v-model.trim="revealReason" class="sp-inline-input" placeholder="填写查看原因（留痕）" @keyup.enter="confirmReveal('phone')" />
                <button class="sp-link" :disabled="busy || !revealReason" @click="confirmReveal('phone')">确认</button>
                <button class="sp-link sp-link--danger" :disabled="busy" @click="cancelReveal">取消</button>
              </template>
            </dd>
          </div>
          <div class="sp-desc__wide">
            <dt>身份证号</dt>
            <dd>
              <span>{{ reveal.idCard || info.idCardMasked || '—' }}</span>
              <button v-if="canReveal('idCard') && !reveal.idCard && revealingField !== 'idCard'" class="sp-link" :disabled="busy" @click="startReveal('idCard')">查看明文</button>
              <template v-if="revealingField === 'idCard'">
                <input v-model.trim="revealReason" class="sp-inline-input" placeholder="填写查看原因（留痕）" @keyup.enter="confirmReveal('idCard')" />
                <button class="sp-link" :disabled="busy || !revealReason" @click="confirmReveal('idCard')">确认</button>
                <button class="sp-link sp-link--danger" :disabled="busy" @click="cancelReveal">取消</button>
              </template>
            </dd>
          </div>
        </dl>
      </section>

      <section class="sp-panel">
        <div class="sp-panel__head">
          家长授权代理
          <button class="sp-btn sp-btn--sm" :disabled="busy" @click="showBind = !showBind">授权家长查看</button>
        </div>
        <div v-if="showBind" class="sp-form">
          <label>家长姓名<input v-model.trim="bindForm.name" placeholder="家长姓名" /></label>
          <label>手机号<input v-model.trim="bindForm.phone" placeholder="家长手机号" /></label>
          <label>关系<input v-model.trim="bindForm.relation" placeholder="如：父亲 / 母亲 / 监护人" /></label>
          <button class="sp-btn" :disabled="busy || !bindForm.phone" @click="bind">提交授权</button>
        </div>
        <StateBlock v-if="guardianError" type="error" :text="guardianError" />
        <StateBlock v-else-if="!guardians.length" type="empty" text="尚未授权任何家长查看" />
        <div v-else class="sp-table-wrap">
          <table class="sp-table">
            <thead><tr><th>家长</th><th>手机号</th><th>关系</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="g in guardians" :key="g.id || g.linkId">
                <td>{{ g.name || g.guardianName || '—' }}</td>
                <td>{{ g.phoneMasked || g.phone || '—' }}</td>
                <td>{{ g.relation || '—' }}</td>
                <td><StatusTag :text="g.status || '已授权'" :tone="(g.status === 'REVOKED') ? 'danger' : 'success'" /></td>
                <td>
                  <template v-if="confirmRevoke === (g.id || g.linkId)">
                    <button class="sp-link sp-link--danger" :disabled="busy" @click="doRevoke(g.id || g.linkId)">确认撤销</button>
                    <button class="sp-link" :disabled="busy" @click="confirmRevoke = ''">取消</button>
                  </template>
                  <button v-else-if="g.status !== 'REVOKED'" class="sp-link sp-link--danger" :disabled="busy" @click="confirmRevoke = (g.id || g.linkId)">撤销</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import StateBlock from '../../components/StateBlock.vue'
import StatusTag from '../../components/StatusTag.vue'
import { portalApi } from '../../services/portalApi'
import { useUiStore } from '../../stores/ui'

const ui = useUiStore()
const loading = ref(true)
const busy = ref(false)
const error = ref('')
const info = ref({})
const guardians = ref([])
const guardianError = ref('')
const reveal = reactive({ phone: '', idCard: '' })
const revealingField = ref('')
const revealReason = ref('')
const showBind = ref(false)
const bindForm = reactive({ name: '', phone: '', relation: '' })
const confirmRevoke = ref('')

const STATUS_MAP = { NORMAL: '正常', SUSPENDED: '休学', TRANSFERRED: '转学', WITHDRAWN: '退学', GRADUATED: '毕业' }
function statusText(s) { return STATUS_MAP[s] || s || '—' }
function canReveal(field) { return (info.value.sensitiveViewable || []).includes(field) }

async function load() {
  loading.value = true
  error.value = ''
  try {
    info.value = await portalApi.profileEnrollment()
  } catch (e) {
    error.value = e?.message || '学籍信息加载失败'
  } finally {
    loading.value = false
  }
  loadGuardians()
}

async function loadGuardians() {
  guardianError.value = ''
  try {
    const data = await portalApi.listGuardians()
    guardians.value = Array.isArray(data) ? data : (data?.items || data?.guardians || [])
  } catch (e) {
    // 家长授权列表读取失败不阻断学籍主视图
    guardianError.value = '家长授权信息暂时读取失败，可稍后重试。'
    guardians.value = []
  }
}

function startReveal(field) { revealingField.value = field; revealReason.value = '' }
function cancelReveal() { revealingField.value = ''; revealReason.value = '' }
async function confirmReveal(field) {
  if (!revealReason.value) return
  busy.value = true
  try {
    const data = await portalApi.profileSensitive(field, revealReason.value)
    reveal[field] = data?.value || data?.plain || data?.[field] || '（已授权，但未返回明文）'
    ui.notify('已按你的授权展示明文并留痕')
    revealingField.value = ''
    revealReason.value = ''
  } catch (e) {
    ui.notify(e?.message || '查看明文失败')
  } finally { busy.value = false }
}

async function bind() {
  busy.value = true
  try {
    await portalApi.bindGuardian({ name: bindForm.name, phone: bindForm.phone, relation: bindForm.relation })
    ui.notify('已提交家长授权')
    showBind.value = false
    bindForm.name = ''; bindForm.phone = ''; bindForm.relation = ''
    loadGuardians()
  } catch (e) { ui.notify(e?.message || '授权提交失败') } finally { busy.value = false }
}

async function doRevoke(linkId) {
  busy.value = true
  try {
    await portalApi.revokeGuardian(linkId)
    ui.notify('已撤销授权')
    confirmRevoke.value = ''
    loadGuardians()
  } catch (e) { ui.notify(e?.message || '撤销失败') } finally { busy.value = false }
}

onMounted(load)
</script>

<style scoped>
.sp-desc__wide { grid-column: 1 / -1; }
.sp-inline-input { width: 220px; max-width: 60%; padding: 5px 9px; font: inherit; border: 1px solid #dcdfe6; border-radius: 6px; }
@media (max-width: 760px) { .sp-inline-input { max-width: 100%; } }
</style>
