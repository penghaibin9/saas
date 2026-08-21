<template>
  <AppCard class="pmfa">
    <AppSectionHeader title="平台主管 MFA 二次认证" />

    <div v-if="loading" class="pmfa__muted">正在读取 MFA 状态…</div>
    <template v-else>
      <div class="pmfa__status">
        <div>
          <div class="pmfa__status-title">高危操作保护</div>
          <div class="pmfa__muted">租户永久销毁等不可逆操作必须再次输入认证器 6 位动态码。</div>
        </div>
        <StatusTag
          :type="status.enabled ? 'success' : status.status === 'PENDING' ? 'warning' : 'default'"
          :label="status.enabled ? 'TOTP 已启用' : status.status === 'PENDING' ? '待完成绑定' : '未启用'"
        />
      </div>

      <div v-if="status.enabled" class="pmfa__ready">
        <b>已启用 TOTP</b>
        <span>高危操作页会单独要求动态码并签发 10 分钟 step-up Token；不会替换你的正常登录会话。</span>
      </div>

      <template v-else>
        <div class="pmfa__notice">
          <b>{{ status.status === 'PENDING' ? '上次绑定尚未确认' : '首次绑定需要主密码复核' }}</b>
          <span v-if="status.status === 'PENDING'">重新开始会生成新的未确认密钥并替换上一次 PENDING 密钥。</span>
          <span v-else>密钥只在本次开始绑定响应中展示，请立即加入 Microsoft Authenticator、Google Authenticator、1Password 等 TOTP 认证器。</span>
        </div>

        <div class="pmfa__form">
          <label class="pmfa__field">
            <span>当前平台主管密码</span>
            <input v-model="password" type="password" autocomplete="current-password" class="pmfa__input" placeholder="用于确认是本人操作" />
          </label>
          <AppButton variant="primary" :loading="starting" :disabled="!password" @click="startEnrollment">
            {{ status.status === 'PENDING' ? '重新开始绑定' : '开始绑定 TOTP' }}
          </AppButton>
        </div>
      </template>

      <div v-if="enrollment" class="pmfa__enrollment">
        <div class="pmfa__step">
          <span class="pmfa__step-no">1</span>
          <div>
            <b>把密钥加入认证器</b>
            <p>当前前端不伪造二维码。可在认证器中选择“输入设置密钥”，名称建议使用当前跃科平台主管账号。</p>
          </div>
        </div>

        <div class="pmfa__secret">
          <code>{{ enrollment.secret }}</code>
          <AppButton variant="ghost" @click="copyText(enrollment.secret, 'TOTP 密钥')">复制密钥</AppButton>
        </div>
        <div class="pmfa__meta">算法 {{ enrollment.algorithm }} · {{ enrollment.digits }} 位 · 每 {{ enrollment.periodSeconds }} 秒更新</div>

        <details class="pmfa__uri">
          <summary>高级：复制 otpauth:// 配置地址</summary>
          <div class="pmfa__uri-body">
            <code>{{ enrollment.provisioningUri }}</code>
            <AppButton variant="ghost" @click="copyText(enrollment.provisioningUri, '配置地址')">复制地址</AppButton>
          </div>
        </details>

        <div class="pmfa__step">
          <span class="pmfa__step-no">2</span>
          <div>
            <b>输入认证器当前 6 位动态码完成确认</b>
            <p>确认成功后密钥不会再次返回前端。</p>
          </div>
        </div>
        <div class="pmfa__confirm">
          <input v-model.trim="confirmCode" inputmode="numeric" maxlength="6" class="pmfa__input pmfa__input--code" placeholder="6 位动态码" @keyup.enter="confirmEnrollment" />
          <AppButton variant="primary" :loading="confirming" :disabled="confirmCode.length !== 6" @click="confirmEnrollment">确认并启用 MFA</AppButton>
        </div>
      </div>
    </template>
  </AppCard>
</template>

<script>
import { AppButton, AppCard, AppSectionHeader } from '@/components/ui'
import { StatusTag } from '@/components/business'
import { platformSecurityOpsApi } from '@/modules/platform/api/platformSecurityOps.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformMfaPanel',
  components: { AppButton, AppCard, AppSectionHeader, StatusTag },
  data() {
    return {
      loading: true,
      starting: false,
      confirming: false,
      status: { enabled: false, status: 'NONE', method: 'TOTP' },
      password: '',
      enrollment: null,
      confirmCode: ''
    }
  },
  created() {
    this.loadStatus()
  },
  methods: {
    async loadStatus() {
      this.loading = true
      try {
        this.status = await platformSecurityOpsApi.getMfaStatus()
      } catch (error) {
        toast.error(error.message || 'MFA 状态加载失败')
      } finally {
        this.loading = false
      }
    },
    async startEnrollment() {
      if (!this.password) return toast.error('请输入当前平台主管密码')
      this.starting = true
      try {
        this.enrollment = await platformSecurityOpsApi.startMfaEnrollment(this.password)
        this.password = ''
        this.confirmCode = ''
        this.status = { enabled: false, status: 'PENDING', method: 'TOTP' }
        toast.success('新的 TOTP 密钥已生成，请立即加入认证器并完成确认')
      } catch (error) {
        toast.error(error.message || 'MFA 绑定启动失败')
      } finally {
        this.starting = false
      }
    },
    async confirmEnrollment() {
      if (!/^\d{6}$/.test(this.confirmCode)) return toast.error('请输入 6 位动态码')
      this.confirming = true
      try {
        await platformSecurityOpsApi.confirmMfaEnrollment(this.confirmCode)
        this.enrollment = null
        this.confirmCode = ''
        await this.loadStatus()
        toast.success('平台主管 MFA 已启用')
      } catch (error) {
        toast.error(error.message || 'MFA 确认失败')
      } finally {
        this.confirming = false
      }
    },
    async copyText(value, label) {
      try {
        await navigator.clipboard.writeText(String(value || ''))
        toast.success(`${label}已复制`)
      } catch {
        toast.info(`无法自动复制，请手动选择${label}`)
      }
    }
  }
}
</script>

<style scoped>
.pmfa { padding: var(--space-4); margin-bottom: var(--space-3); }
.pmfa__status { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--space-3); margin-top: var(--space-2); }
.pmfa__status-title { color: var(--t1); font-weight: var(--font-weight-semibold); }
.pmfa__muted, .pmfa__meta { color: var(--text-tertiary); font-size: 12px; line-height: 1.6; }
.pmfa__ready, .pmfa__notice { display: flex; flex-direction: column; gap: 4px; margin-top: var(--space-3); padding: var(--space-3); border-radius: 10px; background: var(--bg-soft, rgba(37, 99, 235, 0.06)); color: var(--text-secondary); font-size: 13px; }
.pmfa__ready b, .pmfa__notice b { color: var(--t1); }
.pmfa__form, .pmfa__confirm { display: flex; align-items: flex-end; gap: var(--space-2); flex-wrap: wrap; margin-top: var(--space-3); }
.pmfa__field { display: flex; flex-direction: column; gap: var(--space-1); min-width: 280px; font-size: 13px; color: var(--text-secondary); }
.pmfa__input { height: 36px; padding: 0 10px; border: 1px solid var(--card-b); border-radius: 9px; background: rgba(255,255,255,.88); color: var(--t1); font: inherit; }
.pmfa__input:focus { outline: none; border-color: var(--glow); }
.pmfa__input--code { width: 150px; letter-spacing: .18em; font-variant-numeric: tabular-nums; }
.pmfa__enrollment { margin-top: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--card-b); }
.pmfa__step { display: flex; gap: var(--space-2); align-items: flex-start; margin: var(--space-3) 0 var(--space-2); }
.pmfa__step p { margin: 3px 0 0; color: var(--text-tertiary); font-size: 12px; line-height: 1.55; }
.pmfa__step-no { width: 22px; height: 22px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; flex: none; background: var(--btn-p-bg); color: white; font-size: 12px; font-weight: 700; }
.pmfa__secret, .pmfa__uri-body { display: flex; align-items: center; justify-content: space-between; gap: var(--space-2); padding: var(--space-2) var(--space-3); border: 1px solid var(--card-b); border-radius: 9px; background: rgba(255,255,255,.72); }
.pmfa__secret code { color: var(--t1); font-size: 14px; letter-spacing: .08em; word-break: break-all; }
.pmfa__uri { margin-top: var(--space-2); color: var(--text-secondary); font-size: 12px; }
.pmfa__uri summary { cursor: pointer; }
.pmfa__uri-body { margin-top: var(--space-2); }
.pmfa__uri-body code { min-width: 0; overflow-wrap: anywhere; color: var(--text-tertiary); }
@media (max-width: 720px) {
  .pmfa__status { flex-direction: column; }
  .pmfa__field { min-width: 100%; width: 100%; }
  .pmfa__secret, .pmfa__uri-body { align-items: stretch; flex-direction: column; }
}
</style>
