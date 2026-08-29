<template>
  <AppDrawer v-model:visible="open" :title="`运行配置 · ${serviceName}`" mode="modal" size="medium">
    <div class="psc-config">
      <div class="psc-config__mode">
        <StatusTag type="info" :label="guide.mode" />
        <span>{{ serviceCode }}</span>
      </div>
      <p class="psc-config__summary">{{ guide.summary }}</p>

      <section class="psc-config__section">
        <h4>配置项</h4>
        <ul>
          <li v-for="item in guide.items" :key="item.key">
            <code>{{ item.key }}</code>
            <span>{{ item.label }}</span>
          </li>
        </ul>
      </section>

      <div class="psc-config__notice">
        <strong>为什么这里不直接保存？</strong>
        <p>{{ guide.notice }}</p>
      </div>
    </div>
  </AppDrawer>
</template>

<script>
import { StatusTag } from '@/components/business'
import AppDrawer from '@/components/ui/AppDrawer.vue'

const DEPLOY_NOTICE = '这类参数决定进程启动、网络连接或系统密钥。浏览器热改可能导致服务中断或密钥泄露，必须通过服务器环境变量和受控发布流程变更。'

const GUIDES = Object.freeze({
  API_GATEWAY: {
    mode: '部署环境管理',
    summary: '后端 API 的来源白名单、访问限流、令牌与进程参数由服务器部署配置统一管理。',
    items: [
      { key: 'CORS_ORIGINS', label: '允许访问 API 的前端来源' },
      { key: 'TENANT_API_RATE_LIMIT_PER_SECOND', label: '租户级接口限流' },
      { key: 'USER_API_RATE_LIMIT_PER_SECOND', label: '用户级接口限流' },
      { key: 'JWT_* / WEB_CONCURRENCY', label: '令牌与 API 进程参数' }
    ],
    notice: DEPLOY_NOTICE
  },
  MYSQL: {
    mode: '部署环境管理',
    summary: 'MySQL 是平台主数据源，连接地址、账号、密码和连接池必须随部署发布并经过迁移检查。',
    items: [
      { key: 'DB_HOST / DB_PORT / DB_NAME', label: '数据库地址与库名' },
      { key: 'DB_USER / DB_PASSWORD', label: '数据库凭证（禁止页面回显）' },
      { key: 'DB_POOL_*', label: '连接池容量、超时与回收参数' },
      { key: 'DATABASE_URL', label: '完整连接串（配置时优先）' }
    ],
    notice: DEPLOY_NOTICE
  },
  REDIS: {
    mode: '部署环境管理',
    summary: 'Redis 承载缓存、限流和分布式运行状态，连接信息由部署环境提供。',
    items: [
      { key: 'REDIS_URL', label: 'Redis 连接串' },
      { key: 'REDIS_KEY_PREFIX', label: '键空间前缀' },
      { key: 'REDIS_CONNECT_TIMEOUT', label: '连接超时' },
      { key: 'REDIS_SOCKET_TIMEOUT', label: '读写超时' }
    ],
    notice: DEPLOY_NOTICE
  },
  MINIAPP: {
    mode: '部署环境管理',
    summary: '小程序登录和订阅消息使用微信平台密钥与模板，密钥只允许从服务器安全环境注入。',
    items: [
      { key: 'WX_APPID', label: '微信小程序 AppID' },
      { key: 'WX_SECRET', label: '微信小程序 AppSecret（敏感）' },
      { key: 'WX_SUBSCRIBE_TEMPLATE_*', label: '退回、审批、考试和实习提醒模板' },
      { key: 'MINIAPP_API_BASE_URL', label: '小程序端 API 地址' }
    ],
    notice: DEPLOY_NOTICE
  },
  PC_ADMIN: {
    mode: '构建与部署管理',
    summary: 'PC 管理端的 API 地址、域名、静态资源和反向代理由前端构建与 Nginx 部署管理。',
    items: [
      { key: 'API_BASE_URL', label: '管理端访问的后端 API 地址' },
      { key: 'CORS_ORIGINS', label: '后端允许的管理端来源' },
      { key: 'Nginx / HTTPS', label: '域名、证书、缓存和反向代理' }
    ],
    notice: DEPLOY_NOTICE
  },
  STUDENT_PORTAL: {
    mode: '部署 + 租户配置',
    summary: '学生门户的域名与 API 地址属于部署配置；每所学校的门户功能和品牌在租户详情中配置。',
    items: [
      { key: 'PORTAL / API URL', label: '门户域名和后端地址' },
      { key: 'CORS_ORIGINS', label: '后端允许的门户来源' },
      { key: '租户详情 → 学生门户配置', label: '学校级模块开关、品牌与展示' }
    ],
    notice: '全平台运行地址必须走部署发布；学校级门户开关必须在对应租户详情中保存，不能用一份全局值覆盖所有学校。'
  },
  WORKER: {
    mode: '部署环境管理',
    summary: '后台 Worker 和调度器需要独立进程、队列与互斥配置，必须随服务部署管理。',
    items: [
      { key: 'SCHEDULER_MODE', label: '内嵌或独立调度器模式' },
      { key: 'WEB_CONCURRENCY / MULTI_INSTANCE', label: '进程与多实例模式' },
      { key: 'REDIS_URL', label: '任务协调和分布式状态依赖' }
    ],
    notice: DEPLOY_NOTICE
  },
  CLAMAV: {
    mode: '部署环境管理',
    summary: '病毒扫描由 ClamAV 守护进程和文件扫描 Worker 共同完成，连接与重试参数属于服务器配置。',
    items: [
      { key: 'CLAMAV_ENABLED / CLAMAV_HOST / CLAMAV_PORT', label: '扫描服务开关和地址' },
      { key: 'CLAMAV_CONNECT_TIMEOUT / CLAMAV_READ_TIMEOUT', label: '连接与扫描超时' },
      { key: 'FILE_SCAN_*', label: '扫描批次、重试和锁超时' }
    ],
    notice: DEPLOY_NOTICE
  },
  SMS_GATEWAY: {
    mode: '部署环境管理',
    summary: '短信发送已接腾讯云/阿里云 Provider，但访问密钥、签名和模板目前由服务器安全环境注入。',
    items: [
      { key: 'SMS_ENABLED / SMS_PROVIDER', label: '短信总开关和服务商' },
      { key: 'SMS_ACCESS_KEY_ID / SMS_ACCESS_KEY_SECRET', label: '服务商访问密钥（敏感）' },
      { key: 'SMS_SIGN_NAME / SMS_TENCENT_SDK_APP_ID', label: '短信签名和腾讯云应用 ID' },
      { key: 'SMS_TEMPLATE_*', label: '找回密码、待办、退回、预警等模板 ID' }
    ],
    notice: DEPLOY_NOTICE
  }
})

const FALLBACK = Object.freeze({
  mode: '尚未登记配置合同',
  summary: '该服务还没有对应的运行配置合同。',
  items: [{ key: 'Owner / runbook', label: '请先登记负责人和运维手册' }],
  notice: '在真实后端接入前不提供浏览器假保存。'
})

export default {
  name: 'PlatformServiceConfigDrawer',
  components: { AppDrawer, StatusTag },
  props: {
    visible: { type: Boolean, default: false },
    service: { type: Object, default: null }
  },
  emits: ['update:visible'],
  computed: {
    open: {
      get() { return this.visible },
      set(value) { this.$emit('update:visible', value) }
    },
    serviceCode() { return String(this.service?.serviceCode || '') },
    serviceName() { return this.service?.serviceName || '服务' },
    guide() { return GUIDES[this.serviceCode] || FALLBACK }
  }
}
</script>

<style scoped>
.psc-config { display: flex; flex-direction: column; gap: var(--space-4); }
.psc-config__mode { display: flex; align-items: center; gap: var(--space-2); color: var(--text-secondary); }
.psc-config__summary { margin: 0; color: var(--text-secondary); line-height: 1.7; }
.psc-config__section h4 { margin: 0 0 var(--space-2); color: var(--t1); }
.psc-config__section ul { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.psc-config__section li { display: grid; grid-template-columns: minmax(180px, 1fr) 1.4fr; gap: var(--space-3); padding: var(--space-2); border: 1px solid var(--border-light); border-radius: var(--radius-sm); }
.psc-config__section code { color: var(--primary-700); overflow-wrap: anywhere; }
.psc-config__section span { color: var(--text-secondary); }
.psc-config__notice { padding: var(--space-3); border-radius: var(--radius-md); background: var(--bg-section-blue, #eef2ff); }
.psc-config__notice p { margin: var(--space-1) 0 0; color: var(--text-secondary); line-height: 1.7; }
@media (max-width: 640px) { .psc-config__section li { grid-template-columns: 1fr; } }
</style>
