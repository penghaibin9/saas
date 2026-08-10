<template>
  <StudentIdentityView v-if="state === 'READY'" :ctx="ctx" />

  <ModulePageShell
    v-else
    title="身份核验记录"
    :subtitle="subtitle"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
    watermark-purpose="身份核验管理"
  >
    <div class="sic-state">
      <div v-if="state === 'LOADING'" class="sic-card">
        <div class="sic-spinner" aria-hidden="true"></div>
        <h3>正在确认身份核验能力</h3>
        <p>正在读取服务端能力状态，不使用空数组代替配置状态。</p>
      </div>

      <div v-else-if="state === 'NOT_CONFIGURED'" class="sic-card is-info">
        <span class="sic-badge">NOT_CONFIGURED</span>
        <h3>学校尚未配置第三方身份核验服务</h3>
        <p>{{ notice || '当前没有可读取的实名/人脸核验记录，这不是“暂无数据”。' }}</p>
        <div class="sic-actions">
          <AppButton variant="primary" @click="$router.push('/admin/orientation')">去数字迎新信息核验</AppButton>
          <AppButton variant="ghost" @click="load">重新检测</AppButton>
        </div>
      </div>

      <div v-else-if="state === 'EMPTY'" class="sic-card is-empty">
        <span class="sic-badge">EMPTY</span>
        <h3>核验服务已可用，当前暂无核验记录</h3>
        <p>服务能力正常，但当前筛选范围内没有记录。新产生的核验事实会在这里显示。</p>
        <AppButton variant="ghost" @click="load">刷新</AppButton>
      </div>

      <div v-else-if="state === 'FORBIDDEN'" class="sic-card is-danger">
        <span class="sic-badge">FORBIDDEN</span>
        <h3>当前账号无权查看身份核验记录</h3>
        <p>{{ notice || '请联系学校管理员核对学生主档与敏感核验数据权限。' }}</p>
        <AppButton variant="ghost" @click="$router.push('/workbench')">返回工作台</AppButton>
      </div>

      <div v-else class="sic-card is-danger">
        <span class="sic-badge">ERROR</span>
        <h3>身份核验服务读取失败</h3>
        <p>{{ notice || '服务端返回异常，未把故障伪装成“暂无记录”。' }}</p>
        <AppButton variant="primary" @click="load">重试</AppButton>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell } from '@/components/business'
import { AppButton } from '@/components/ui'
import { studentApi } from '@/modules/student/api/student.api'
import StudentIdentityView from './StudentIdentityView.vue'

const FORBIDDEN_CODES = new Set(['FORBIDDEN', 'NO_PERMISSION', 'PERMISSION_DENIED', '403', '403001'])

function normalizeCapability(result) {
  const code = Number(result?.code ?? 1)
  const bizCode = String(result?.bizCode || result?.errorCode || '').toUpperCase()
  const message = result?.message || ''
  const data = result?.data || {}

  if (code !== 0) {
    const forbidden = code === 403 || FORBIDDEN_CODES.has(bizCode) || /FORBIDDEN|NO_PERMISSION|PERMISSION/.test(bizCode)
    return { state: forbidden ? 'FORBIDDEN' : 'ERROR', notice: message }
  }

  const capability = String(data.capabilityStatus || '').toUpperCase()
  if (capability === 'NOT_CONFIGURED') return { state: 'NOT_CONFIGURED', notice: data.notice || message }
  if (capability === 'FORBIDDEN') return { state: 'FORBIDDEN', notice: data.notice || message }
  if (capability === 'ERROR') return { state: 'ERROR', notice: data.notice || message }
  if (Number(data.total || 0) === 0) return { state: 'EMPTY', notice: data.notice || '' }
  return { state: 'READY', notice: data.notice || '' }
}

export default {
  name: 'StudentIdentityCapabilityView',
  components: { ModulePageShell, AppButton, StudentIdentityView },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { state: 'LOADING', notice: '' }
  },
  computed: {
    subtitle() {
      return {
        LOADING: '正在读取服务端能力状态',
        NOT_CONFIGURED: '能力未配置，与“暂无记录”明确区分',
        EMPTY: '能力正常，当前没有核验事实',
        FORBIDDEN: '当前账号没有核验记录查看权限',
        ERROR: '服务异常，未降级为空数据'
      }[this.state] || '身份核验能力状态'
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.state = 'LOADING'
      this.notice = ''
      try {
        const result = await studentApi.getIdentityRecords({ page: 1, pageSize: 1 })
        const normalized = normalizeCapability(result)
        this.state = normalized.state
        this.notice = normalized.notice
      } catch (error) {
        const status = Number(error?.status || error?.response?.status || 0)
        this.state = status === 403 ? 'FORBIDDEN' : 'ERROR'
        this.notice = error?.message || '身份核验服务读取失败'
      }
    }
  }
}
</script>

<style scoped>
.sic-state { max-width: 760px; margin: 48px auto; padding: 0 20px; }
.sic-card { padding: 32px; border: 1px solid var(--border-color, #e2e8f0); border-radius: 16px; background: var(--bg-card, #fff); box-shadow: 0 10px 30px rgba(15, 23, 42, .06); }
.sic-card h3 { margin: 12px 0 8px; font-size: 20px; color: var(--text-primary, #0f172a); }
.sic-card p { margin: 0 0 20px; line-height: 1.7; color: var(--text-secondary, #475569); }
.sic-card.is-info { border-color: rgba(37, 99, 235, .28); }
.sic-card.is-empty { border-color: rgba(100, 116, 139, .28); }
.sic-card.is-danger { border-color: rgba(220, 38, 38, .26); }
.sic-badge { display: inline-flex; padding: 4px 9px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: .04em; background: #eff6ff; color: #1d4ed8; }
.is-danger .sic-badge { background: #fef2f2; color: #b91c1c; }
.sic-actions { display: flex; gap: 10px; flex-wrap: wrap; }
.sic-spinner { width: 28px; height: 28px; border: 3px solid #dbeafe; border-top-color: #2563eb; border-radius: 50%; animation: sic-spin .8s linear infinite; }
@keyframes sic-spin { to { transform: rotate(360deg); } }
</style>
