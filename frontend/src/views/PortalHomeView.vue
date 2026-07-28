<template>
  <div class="pt">
    <!-- ── 第一层：统一品牌头部 ── -->
    <header class="pt-topbar">
      <div class="pt-shell pt-nav">
        <a class="pt-brand" href="#pt-hero">
          <span class="pt-brand-mark" aria-hidden="true">校</span>
          <span class="pt-brand-copy">
            <span class="pt-brand-title">{{ platformName }}</span>
            <span class="pt-brand-sub">{{ platformSubtitle }}</span>
          </span>
        </a>

        <nav class="pt-nav-actions" aria-label="门户导航">
          <a class="pt-nav-link" href="#pt-modules">业务系统</a>
          <a class="pt-nav-link" href="#pt-mobile">移动端</a>
          <a v-if="statusPageUrl" class="pt-nav-link" :href="statusPageUrl"
             target="_blank" rel="noopener noreferrer">系统运行状态</a>
          <span v-if="supportContact" class="pt-nav-support">服务支持 {{ supportContact }}</span>
          <a class="pt-nav-login" href="#pt-login">登录</a>
        </nav>

        <button class="pt-menu-toggle" type="button" :aria-expanded="String(menuOpen)"
                aria-controls="pt-mobile-menu" @click="menuOpen = !menuOpen">
          <span class="pt-sr">{{ menuOpen ? '收起菜单' : '展开菜单' }}</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path v-if="!menuOpen" d="M4 7h16M4 12h16M4 17h16" />
            <path v-else d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>

      <div v-show="menuOpen" id="pt-mobile-menu" class="pt-shell pt-mobile-menu">
        <a href="#pt-modules" @click="menuOpen = false">业务系统</a>
        <a href="#pt-mobile" @click="menuOpen = false">移动端</a>
        <a v-if="statusPageUrl" :href="statusPageUrl" target="_blank"
           rel="noopener noreferrer" @click="menuOpen = false">系统运行状态</a>
        <a href="#pt-login" @click="menuOpen = false">登录</a>
      </div>
    </header>

    <main>
      <!-- ── 第二层：主视觉 + 登录入口 ── -->
      <section id="pt-hero" class="pt-hero">
        <div class="pt-shell pt-hero-grid">
          <div class="pt-hero-main">
            <p class="pt-eyebrow">高校学生全生命周期管理平台</p>
            <h1 class="pt-hero-title">一个入口，贯通学生培养全过程</h1>
            <p class="pt-hero-lead">
              覆盖毕业设计、岗位实习、学工管理与教务运行，为教师和学生提供统一、清晰、可信的数字化工作入口。
            </p>
            <ul class="pt-hero-points">
              <li v-for="point in heroPoints" :key="point" class="pt-hero-point">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                  <path d="M20 7 10 17l-5-5" />
                </svg>
                {{ point }}
              </li>
            </ul>
          </div>

          <aside id="pt-login" class="pt-login-card" aria-labelledby="pt-login-title">
            <p class="pt-login-kicker">统一登录入口</p>
            <h2 id="pt-login-title" class="pt-login-title">请选择您的身份</h2>
            <p class="pt-login-desc">登录后直接进入与岗位匹配的工作台，无需再次选择业务系统。</p>

            <div class="pt-role-list">
              <a v-if="teacherLoginUrl" class="pt-role pt-role-primary" :href="teacherLoginUrl">
                <span class="pt-role-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M4 5h16v11H4z" /><path d="M8 20h8M12 16v4" />
                  </svg>
                </span>
                <span class="pt-role-text">
                  <span class="pt-role-title">教师 / 管理人员登录</span>
                  <span class="pt-role-sub">教务处、学工处、院系、辅导员、指导教师等</span>
                </span>
                <span class="pt-role-arrow" aria-hidden="true">→</span>
              </a>
              <div v-else class="pt-role pt-role-disabled" aria-disabled="true">
                <span class="pt-role-text">
                  <span class="pt-role-title">教师 / 管理人员登录</span>
                  <span class="pt-role-sub">入口暂未配置，请联系学校管理员</span>
                </span>
              </div>

              <a v-if="studentLoginUrl" class="pt-role pt-role-second" :href="studentLoginUrl">
                <span class="pt-role-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="m3 9 9-5 9 5-9 5-9-5Z" /><path d="M7 12v5c3 2 7 2 10 0v-5" />
                  </svg>
                </span>
                <span class="pt-role-text">
                  <span class="pt-role-title">学生登录</span>
                  <span class="pt-role-sub">事项办理、进度查询、材料提交与消息提醒</span>
                </span>
                <span class="pt-role-arrow" aria-hidden="true">→</span>
              </a>
              <div v-else class="pt-role pt-role-disabled" aria-disabled="true">
                <span class="pt-role-text">
                  <span class="pt-role-title">学生登录</span>
                  <span class="pt-role-sub">入口暂未配置，请联系学校管理员</span>
                </span>
              </div>
            </div>

            <p class="pt-login-tip">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8h.01" />
              </svg>
              <span>请使用学校下发的账号登录；账号或权限异常请联系本校管理员。</span>
            </p>
          </aside>
        </div>
      </section>

      <!-- ── 第三层：业务系统 ── -->
      <section id="pt-modules" class="pt-section">
        <div class="pt-shell">
          <div class="pt-section-head">
            <h2 class="pt-section-title">本平台包含的业务系统</h2>
            <p class="pt-section-desc">按真实业务闭环组织。可查看各系统的完整流转路径与模块关系图。</p>
          </div>

          <div class="pt-module-grid">
            <article v-for="mod in modules" :key="mod.key" class="pt-module-card"
                     :style="{ '--mod-color': mod.color, '--mod-soft': mod.soft }">
              <div class="pt-module-mark" aria-hidden="true">{{ mod.mark }}</div>
              <h3 class="pt-module-name">{{ mod.name }}</h3>
              <p class="pt-module-desc">{{ mod.desc }}</p>
              <ul class="pt-module-stages">
                <li v-for="stage in mod.stages" :key="stage">{{ stage }}</li>
              </ul>
              <div class="pt-module-actions">
                <button v-if="flowOf(mod.flowId)" class="pt-module-btn" type="button"
                        @click="openFlow(mod)">
                  查看业务流程
                </button>
                <a v-if="mod.relationshipMap" class="pt-module-btn pt-module-btn-ghost"
                   :href="mod.relationshipMap" target="_blank" rel="noopener noreferrer">
                  模块关系图
                </a>
              </div>
            </article>
          </div>
        </div>
      </section>

      <!-- ── 第四层：移动端入口 ── -->
      <section id="pt-mobile" class="pt-section">
        <div class="pt-shell pt-access-grid">
          <div class="pt-mobile-card">
            <h2 class="pt-card-title">微信小程序</h2>
            <p class="pt-card-desc">移动端承载高频办理、现场处置、进度查询与消息提醒。</p>
            <div class="pt-mobile-list">
              <div v-for="mp in miniPrograms" :key="mp.key" class="pt-mobile-entry">
                <span class="pt-mobile-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="7" y="2" width="10" height="20" rx="2" /><path d="M11 18h2" />
                  </svg>
                </span>
                <span class="pt-mobile-copy">
                  <span class="pt-mobile-title">{{ mp.name }}</span>
                  <span class="pt-mobile-sub">{{ mp.desc }}</span>
                </span>
                <button v-if="mp.qr" class="pt-mobile-btn" type="button" @click="openQr(mp)">
                  查看二维码
                </button>
                <span v-else class="pt-mobile-pending">即将接入</span>
              </div>
            </div>
            <p v-if="!hasAnyQr" class="pt-mobile-note">
              小程序发布后将在此展示正式二维码；当前请联系学校管理员获取入口。
            </p>
          </div>

          <!-- ── 第五层：平台价值 ── -->
          <aside class="pt-value-card">
            <h2 class="pt-card-title">平台特点</h2>
            <ul class="pt-value-list">
              <li v-for="value in values" :key="value">
                <span class="pt-value-check" aria-hidden="true">✓</span>{{ value }}
              </li>
            </ul>
          </aside>
        </div>
      </section>
    </main>

    <!-- ── 第六层：页脚 ── -->
    <footer class="pt-footer">
      <div class="pt-shell pt-footer-inner">
        <div class="pt-footer-brand">
          <span>© {{ year }} {{ companyName }} · {{ platformName }}</span>
          <a class="pt-icp" :href="icpQueryUrl" target="_blank" rel="noopener noreferrer">{{ icpNumber }}</a>
        </div>
        <div v-if="footerLinks.length" class="pt-footer-links">
          <a v-for="link in footerLinks" :key="link.label" :href="link.url"
             target="_blank" rel="noopener noreferrer">{{ link.label }}</a>
        </div>
      </div>
    </footer>

    <!-- 弹窗：业务流程 / 小程序二维码 -->
    <div v-if="modal" ref="modalRoot" class="pt-modal-backdrop" role="dialog" aria-modal="true"
         :aria-label="modal.title" tabindex="-1" @click.self="closeModal" @keydown.esc="closeModal">
      <div class="pt-modal">
        <div class="pt-modal-head">
          <h2 class="pt-modal-title">{{ modal.title }}</h2>
          <button ref="modalClose" class="pt-modal-close" type="button" aria-label="关闭" @click="closeModal">✕</button>
        </div>
        <div class="pt-modal-body">
          <ol v-if="modal.type === 'flow'" class="pt-flow">
            <li v-for="(step, idx) in modal.steps" :key="idx" class="pt-flow-step">
              <span class="pt-flow-mark">{{ idx + 1 }}</span>
              <span class="pt-flow-copy">
                <strong>{{ step.name }}</strong>
                <span class="pt-flow-who">{{ step.who }}</span>
                <span class="pt-flow-detail">{{ step.detail }}</span>
              </span>
            </li>
          </ol>
          <div v-else class="pt-qr-wrap">
            <img class="pt-qr" :src="modal.qr" :alt="modal.title + '二维码'" @error="onQrError" />
            <p v-if="qrBroken" class="pt-qr-note">二维码暂时无法加载，请联系学校管理员获取入口。</p>
            <p v-else class="pt-qr-note">请使用微信扫码进入{{ modal.title }}。</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
/**
 * 统一门户首页（公开根路由 /）。
 * 只做产品导航与真实入口分发：不实现登录认证、不调用业务接口、不读取用户数据。
 * 唯一的网络请求是公开的租户品牌接口（/api/v1/authz/tenant/brand），失败时静默降级为默认品牌。
 * 所有对外地址来自 config/portalConfig.js（构建期环境变量 + 同源相对路径默认值）。
 */
import { API_BASE_URL, API_PREFIX } from '../services/http/config'
import { HELP_FLOWS } from '../config/helpContent'
import {
  COMPANY_NAME,
  DEFAULT_PLATFORM_NAME,
  DEFAULT_PLATFORM_SUBTITLE,
  ICP_NUMBER,
  ICP_QUERY_URL,
  PORTAL_MODULES,
  PORTAL_VALUES,
  PRIVACY_URL,
  STATUS_PAGE_URL,
  STUDENT_LOGIN_URL,
  STUDENT_MINIPROGRAM_QR,
  SUPPORT_CONTACT,
  SUPPORT_URL,
  TEACHER_LOGIN_URL,
  TEACHER_MINIPROGRAM_QR,
  TERMS_URL
} from '../config/portalConfig'

export default {
  name: 'PortalHomeView',
  data() {
    return {
      menuOpen: false,
      modal: null,
      qrBroken: false,
      lastFocused: null,
      brand: null,
      companyName: COMPANY_NAME,
      icpNumber: ICP_NUMBER,
      icpQueryUrl: ICP_QUERY_URL,
      modules: PORTAL_MODULES,
      values: PORTAL_VALUES,
      statusPageUrl: STATUS_PAGE_URL,
      supportContact: SUPPORT_CONTACT,
      teacherLoginUrl: TEACHER_LOGIN_URL,
      studentLoginUrl: STUDENT_LOGIN_URL,
      heroPoints: ['统一身份认证', '权限与数据范围自动识别', 'PC 与微信小程序协同']
    }
  },
  computed: {
    year() {
      return new Date().getFullYear()
    },
    platformName() {
      return (this.brand && this.brand.platformName) || DEFAULT_PLATFORM_NAME
    },
    platformSubtitle() {
      return (this.brand && this.brand.platformSubtitle) || DEFAULT_PLATFORM_SUBTITLE
    },
    miniPrograms() {
      return [
        {
          key: 'teacher',
          name: '教师微信小程序',
          desc: '审批、巡访、批阅与风险处置',
          qr: TEACHER_MINIPROGRAM_QR
        },
        {
          key: 'student',
          name: '学生微信小程序',
          desc: '申请、打卡、材料提交与进度查询',
          qr: STUDENT_MINIPROGRAM_QR
        }
      ]
    },
    hasAnyQr() {
      return this.miniPrograms.some((mp) => !!mp.qr)
    },
    footerLinks() {
      return [
        { label: '隐私政策', url: PRIVACY_URL },
        { label: '用户协议', url: TERMS_URL },
        { label: '技术支持', url: SUPPORT_URL }
      ].filter((item) => !!item.url)
    }
  },
  mounted() {
    document.title = this.platformName
    this.loadBrand()
  },
  beforeUnmount() {
    document.body.style.overflow = ''
  },
  methods: {
    /** 公开品牌接口；任何失败都静默降级为默认品牌，绝不阻塞门户渲染 */
    async loadBrand() {
      try {
        const res = await fetch(`${API_BASE_URL}${API_PREFIX}/authz/tenant/brand`, {
          headers: { Accept: 'application/json' }
        })
        if (!res.ok) return
        const payload = await res.json()
        const data = payload && payload.data
        if (data && typeof data === 'object') {
          this.brand = data
          document.title = this.platformName
        }
      } catch {
        // 门户为纯静态导航页，品牌接口不可用时保持默认品牌即可
      }
    },
    flowOf(flowId) {
      return HELP_FLOWS.find((flow) => flow.id === flowId) || null
    },
    openFlow(mod) {
      const flow = this.flowOf(mod.flowId)
      if (!flow) return
      this.openModal({
        type: 'flow',
        title: `${mod.name} · ${flow.title}`,
        steps: flow.steps || []
      })
    },
    openQr(mp) {
      if (!mp.qr) return
      this.qrBroken = false
      this.openModal({ type: 'qr', title: mp.name, qr: mp.qr })
    },
    openModal(payload) {
      this.lastFocused = document.activeElement
      this.modal = payload
      document.body.style.overflow = 'hidden'
      this.$nextTick(() => {
        const el = this.$refs.modalClose
        if (el && el.focus) el.focus()
      })
    },
    closeModal() {
      this.modal = null
      document.body.style.overflow = ''
      const prev = this.lastFocused
      if (prev && prev.focus) prev.focus()
      this.lastFocused = null
    },
    onQrError() {
      this.qrBroken = true
    }
  }
}
</script>

<style scoped>
.pt {
  --pt-primary: #2563eb;
  --pt-ink: #10233f;
  --pt-muted: #64748b;
  --pt-line: #e5eaf1;
  --pt-canvas: #f4f7fb;
  --pt-shadow: 0 18px 48px rgba(31, 56, 92, 0.09);
  --pt-shadow-soft: 0 8px 24px rgba(31, 56, 92, 0.06);
  min-height: 100vh;
  color: var(--pt-ink);
  background:
    radial-gradient(circle at 15% 0%, rgba(37, 99, 235, 0.08), transparent 28%),
    radial-gradient(circle at 96% 20%, rgba(14, 165, 233, 0.06), transparent 24%),
    var(--pt-canvas);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  overflow-x: hidden;
}

.pt-shell { width: min(1180px, calc(100% - 40px)); margin: 0 auto; }
.pt-sr {
  position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip: rect(0 0 0 0); white-space: nowrap;
}

.pt a { color: inherit; text-decoration: none; }
.pt :focus-visible { outline: 2px solid var(--pt-primary); outline-offset: 2px; border-radius: 8px; }

/* ── 头部 ── */
.pt-topbar {
  position: sticky; top: 0; z-index: 20;
  background: rgba(255, 255, 255, 0.93);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(229, 234, 241, 0.9);
}
.pt-nav { height: 72px; display: flex; align-items: center; justify-content: space-between; gap: 24px; }
.pt-brand { display: flex; align-items: center; gap: 13px; min-width: 0; }
.pt-brand-mark {
  width: 42px; height: 42px; border-radius: 13px; display: grid; place-items: center;
  color: #fff; font-size: 18px; font-weight: 800; flex: 0 0 auto;
  background: linear-gradient(145deg, #2f75ef, #1546b1);
  box-shadow: 0 10px 24px rgba(37, 99, 235, 0.24);
}
.pt-brand-copy { display: flex; flex-direction: column; min-width: 0; }
.pt-brand-title {
  font-size: 17px; font-weight: 700; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis;
}
.pt-brand-sub { margin-top: 3px; color: var(--pt-muted); font-size: 12px; }

.pt-nav-actions { display: flex; align-items: center; gap: 6px; }
.pt-nav-link, .pt-nav-support {
  color: #4b5f79; font-size: 14px; padding: 9px 12px; border-radius: 9px;
  transition: background-color 0.18s ease, color 0.18s ease;
}
.pt-nav-link:hover { color: var(--pt-primary); background: #eaf2ff; }
.pt-nav-support { color: var(--pt-muted); font-size: 13px; white-space: nowrap; }
.pt-nav-login {
  margin-left: 6px; padding: 9px 18px; border-radius: 10px; font-size: 14px; font-weight: 600;
  color: #fff; background: var(--pt-primary);
  transition: background-color 0.18s ease;
}
.pt-nav-login:hover { background: #1746b3; }

.pt-menu-toggle {
  display: none; width: 40px; height: 40px; border: 1px solid var(--pt-line);
  border-radius: 10px; background: #fff; color: #4b5f79; cursor: pointer;
  align-items: center; justify-content: center;
}
.pt-menu-toggle svg { width: 20px; height: 20px; }
.pt-mobile-menu { display: none; flex-direction: column; padding-bottom: 12px; gap: 2px; }
.pt-mobile-menu a { padding: 12px 4px; border-top: 1px solid var(--pt-line); font-size: 15px; }

/* ── 主视觉 ── */
.pt-hero { padding: 48px 0 30px; }
.pt-hero-grid {
  display: grid; gap: 28px; align-items: stretch;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.82fr);
}
.pt-hero-main {
  position: relative; overflow: hidden; border-radius: 28px;
  padding: 52px 54px; color: #fff; box-shadow: var(--pt-shadow);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.1), transparent 48%),
    linear-gradient(138deg, #173f91 0%, #1f5fd2 58%, #2f7cf0 100%);
  display: flex; flex-direction: column; justify-content: center;
}
.pt-hero-main::before {
  content: ''; position: absolute; pointer-events: none; border-radius: 50%;
  width: 360px; height: 360px; right: -160px; top: -170px;
  border: 1px solid rgba(255, 255, 255, 0.15);
}
.pt-eyebrow {
  position: relative; z-index: 1; align-self: flex-start; margin: 0;
  padding: 7px 11px; border-radius: 999px; font-size: 12px; font-weight: 700;
  letter-spacing: 0.08em; color: #dce9ff;
  border: 1px solid rgba(255, 255, 255, 0.18); background: rgba(255, 255, 255, 0.09);
}
.pt-hero-title {
  position: relative; z-index: 1; margin: 24px 0 16px; max-width: 690px;
  font-size: clamp(30px, 3.4vw, 50px); line-height: 1.16; letter-spacing: -0.03em;
}
.pt-hero-lead {
  position: relative; z-index: 1; margin: 0; max-width: 650px;
  color: rgba(255, 255, 255, 0.84); font-size: 16px; line-height: 1.9;
}
.pt-hero-points {
  position: relative; z-index: 1; display: flex; flex-wrap: wrap; gap: 10px;
  margin: 32px 0 0; padding: 0; list-style: none;
}
.pt-hero-point {
  display: inline-flex; align-items: center; gap: 8px; padding: 10px 13px;
  border-radius: 12px; font-size: 13px; color: rgba(255, 255, 255, 0.92);
  background: rgba(255, 255, 255, 0.1); border: 1px solid rgba(255, 255, 255, 0.1);
}
.pt-hero-point svg { width: 16px; height: 16px; flex: 0 0 auto; }

/* ── 登录卡 ── */
.pt-login-card {
  display: flex; flex-direction: column; justify-content: center;
  padding: 30px; border-radius: 28px; background: #fff;
  border: 1px solid rgba(229, 234, 241, 0.95); box-shadow: var(--pt-shadow);
}
.pt-login-kicker { margin: 0; color: var(--pt-primary); font-size: 12px; font-weight: 800; letter-spacing: 0.12em; }
.pt-login-title { margin: 10px 0 8px; font-size: 25px; }
.pt-login-desc { margin: 0 0 22px; color: var(--pt-muted); font-size: 14px; line-height: 1.7; }
.pt-role-list { display: grid; gap: 12px; }
.pt-role {
  display: flex; align-items: center; gap: 13px; padding: 15px;
  border-radius: 15px; border: 1px solid var(--pt-line); background: #fff;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.pt-role-primary { color: #fff; border-color: transparent; background: linear-gradient(135deg, #2f70ea, #1f56c9); }
.pt-role-second { border-color: #bfd2f8; }
.pt-role:not(.pt-role-disabled):hover { transform: translateY(-1px); box-shadow: var(--pt-shadow-soft); }
.pt-role:not(.pt-role-disabled):active { transform: translateY(0); }
.pt-role-disabled { background: #f7f9fc; color: #94a3b8; cursor: not-allowed; }
.pt-role-icon {
  width: 44px; height: 44px; flex: 0 0 auto; display: grid; place-items: center;
  border-radius: 13px; background: #eaf2ff; color: var(--pt-primary);
}
.pt-role-primary .pt-role-icon { background: rgba(255, 255, 255, 0.16); color: #fff; }
.pt-role-icon svg { width: 23px; height: 23px; }
.pt-role-text { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.pt-role-title { font-weight: 700; font-size: 15px; }
.pt-role-sub { margin-top: 4px; font-size: 12px; color: var(--pt-muted); }
.pt-role-primary .pt-role-sub { color: rgba(255, 255, 255, 0.75); }
.pt-role-arrow { font-size: 20px; opacity: 0.72; }
.pt-login-tip {
  display: flex; gap: 9px; align-items: flex-start; margin: 18px 0 0;
  padding: 12px 13px; border-radius: 12px; color: #53667e; background: #f7f9fc;
  font-size: 12px; line-height: 1.6;
}
.pt-login-tip svg { width: 16px; height: 16px; margin-top: 1px; flex: 0 0 auto; color: var(--pt-primary); }

/* ── 区块 ── */
.pt-section { padding: 32px 0; }
.pt-section-head { margin-bottom: 18px; }
.pt-section-title { margin: 0 0 6px; font-size: 25px; }
.pt-section-desc { margin: 0; color: var(--pt-muted); font-size: 14px; line-height: 1.7; }

.pt-module-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.pt-module-card {
  position: relative; overflow: hidden; display: flex; flex-direction: column;
  padding: 22px; border-radius: 20px; border: 1px solid var(--pt-line);
  background: rgba(255, 255, 255, 0.94); box-shadow: var(--pt-shadow-soft);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}
.pt-module-card:hover { transform: translateY(-3px); box-shadow: var(--pt-shadow); border-color: #d5dfec; }
.pt-module-card::after {
  content: ''; position: absolute; width: 110px; height: 110px; border-radius: 50%;
  right: -48px; top: -52px; background: var(--mod-soft);
}
.pt-module-mark {
  position: relative; z-index: 1; width: 46px; height: 46px; border-radius: 14px;
  display: grid; place-items: center; font-size: 19px; font-weight: 800;
  color: var(--mod-color); background: var(--mod-soft);
}
.pt-module-name { position: relative; z-index: 1; margin: 18px 0 8px; font-size: 19px; }
.pt-module-desc { margin: 0; color: var(--pt-muted); font-size: 13px; line-height: 1.75; }
.pt-module-stages {
  display: flex; flex-wrap: wrap; gap: 6px; margin: 16px 0 18px; padding: 0; list-style: none;
}
.pt-module-stages li {
  color: #53667e; background: #f4f7fb; border: 1px solid #edf1f6;
  border-radius: 7px; padding: 5px 7px; font-size: 11px;
}
.pt-module-actions { margin-top: auto; display: flex; flex-wrap: wrap; gap: 8px; }
.pt-module-btn {
  padding: 8px 12px; border-radius: 9px; border: 1px solid transparent; cursor: pointer;
  font-size: 13px; font-weight: 600; color: #fff; background: var(--mod-color);
  transition: opacity 0.18s ease, transform 0.18s ease;
}
.pt-module-btn:hover { opacity: 0.9; }
.pt-module-btn:active { transform: translateY(1px); }
.pt-module-btn-ghost { color: var(--mod-color); background: var(--mod-soft); border-color: var(--mod-soft); }

/* ── 移动端 + 价值 ── */
.pt-access-grid { display: grid; grid-template-columns: 1.3fr 0.7fr; gap: 16px; }
.pt-mobile-card, .pt-value-card {
  padding: 25px; border-radius: 22px; border: 1px solid var(--pt-line);
  background: #fff; box-shadow: var(--pt-shadow-soft);
}
.pt-card-title { margin: 0 0 6px; font-size: 18px; }
.pt-card-desc { margin: 0 0 16px; color: var(--pt-muted); font-size: 13px; }
.pt-mobile-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.pt-mobile-entry {
  display: flex; align-items: center; gap: 13px; padding: 16px;
  border-radius: 16px; background: #f8fafc; border: 1px solid #edf1f6;
}
.pt-mobile-icon {
  width: 44px; height: 44px; flex: 0 0 auto; display: grid; place-items: center;
  border-radius: 13px; color: #0b7f5d; background: #e9f8f2;
}
.pt-mobile-icon svg { width: 23px; height: 23px; }
.pt-mobile-copy { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.pt-mobile-title { font-weight: 700; font-size: 14px; }
.pt-mobile-sub { margin-top: 4px; color: var(--pt-muted); font-size: 12px; }
.pt-mobile-btn {
  flex: 0 0 auto; padding: 8px 10px; border-radius: 9px; border: 0; cursor: pointer;
  font-size: 12px; font-weight: 700; color: var(--pt-primary); background: #eaf2ff;
}
.pt-mobile-btn:hover { background: #dbe8ff; }
.pt-mobile-pending {
  flex: 0 0 auto; padding: 8px 10px; border-radius: 9px;
  font-size: 12px; color: #7c8899; background: #eef1f5;
}
.pt-mobile-note { margin: 14px 0 0; color: var(--pt-muted); font-size: 12px; line-height: 1.7; }
.pt-value-list { margin: 0; padding: 0; list-style: none; display: grid; gap: 12px; }
.pt-value-list li { display: flex; align-items: flex-start; gap: 10px; color: #43566f; font-size: 13px; line-height: 1.7; }
.pt-value-check {
  width: 22px; height: 22px; flex: 0 0 auto; display: grid; place-items: center;
  border-radius: 50%; color: var(--pt-primary); background: #eaf2ff; font-size: 12px; font-weight: 900;
}

/* ── 页脚 ── */
.pt-footer { margin-top: 26px; border-top: 1px solid var(--pt-line); background: rgba(255, 255, 255, 0.72); }
.pt-footer-inner {
  min-height: 82px; display: flex; justify-content: space-between; align-items: center;
  gap: 24px; padding: 18px 0; color: #718096; font-size: 12px; flex-wrap: wrap;
}
.pt-footer-brand { display: flex; flex-direction: column; gap: 7px; }
.pt-icp { color: #64748b; transition: color 0.2s ease; }
.pt-icp:hover { color: var(--pt-primary); text-decoration: underline; }
.pt-footer-links { display: flex; gap: 18px; flex-wrap: wrap; }

/* ── 弹窗 ── */
.pt-modal-backdrop {
  position: fixed; inset: 0; z-index: 50; display: grid; place-items: center;
  padding: 20px; background: rgba(15, 30, 52, 0.48); backdrop-filter: blur(5px);
}
.pt-modal {
  width: min(600px, 100%); max-height: calc(100vh - 40px); overflow: auto;
  border-radius: 24px; background: #fff; box-shadow: 0 30px 90px rgba(15, 30, 52, 0.28);
}
.pt-modal-head {
  display: flex; justify-content: space-between; gap: 20px; align-items: center;
  padding: 22px 24px; border-bottom: 1px solid var(--pt-line);
}
.pt-modal-title { margin: 0; font-size: 18px; }
.pt-modal-close {
  width: 34px; height: 34px; flex: 0 0 auto; border: 0; border-radius: 10px;
  cursor: pointer; color: #64748b; background: #f1f5f9;
}
.pt-modal-close:hover { background: #e2e8f0; }
.pt-modal-body { padding: 24px; }
.pt-flow { margin: 0; padding: 0; list-style: none; }
.pt-flow-step { display: grid; grid-template-columns: 34px 1fr; gap: 13px; padding-bottom: 18px; }
.pt-flow-step:last-child { padding-bottom: 0; }
.pt-flow-mark {
  width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center;
  color: #fff; background: var(--pt-primary); font-size: 12px; font-weight: 800;
}
.pt-flow-copy { display: flex; flex-direction: column; min-width: 0; }
.pt-flow-copy strong { font-size: 14px; }
.pt-flow-who { margin-top: 4px; color: var(--pt-primary); font-size: 12px; }
.pt-flow-detail { margin-top: 4px; color: var(--pt-muted); font-size: 12px; line-height: 1.6; }
.pt-qr-wrap { text-align: center; }
.pt-qr {
  width: 220px; height: 220px; max-width: 100%; object-fit: contain;
  border-radius: 18px; border: 1px solid var(--pt-line);
}
.pt-qr-note { margin: 14px 0 0; color: var(--pt-muted); font-size: 13px; line-height: 1.7; }

/* ── 响应式 ── */
@media (max-width: 1080px) {
  .pt-hero-grid { grid-template-columns: 1fr; }
  .pt-module-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .pt-access-grid { grid-template-columns: 1fr; }
  .pt-hero-main { padding: 40px 34px; }
}

@media (max-width: 820px) {
  .pt-nav-actions { display: none; }
  .pt-menu-toggle { display: flex; }
  .pt-mobile-menu { display: flex; }
}

@media (max-width: 720px) {
  .pt-shell { width: min(100% - 24px, 1180px); }
  .pt-nav { height: 64px; }
  .pt-brand-sub { display: none; }
  .pt-brand-title { font-size: 15px; }
  .pt-hero { padding: 22px 0 18px; }
  .pt-hero-grid { gap: 14px; }
  .pt-hero-main { border-radius: 22px; padding: 32px 22px; }
  .pt-login-card { border-radius: 22px; padding: 22px; }
  .pt-module-grid { grid-template-columns: 1fr; }
  .pt-mobile-list { grid-template-columns: 1fr; }
  .pt-section-title { font-size: 22px; }
  .pt-footer-inner { flex-direction: column; align-items: flex-start; }
}

@media (prefers-reduced-motion: reduce) {
  .pt *, .pt *::before, .pt *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
  }
  .pt-module-card:hover, .pt-role:hover { transform: none; }
}
</style>
