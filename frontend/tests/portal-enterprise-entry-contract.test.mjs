import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

test('跃科公开门户提供企业注册/登录真实入口', () => {
  const config = read('frontend/src/config/portalConfig.js')
  const home = read('frontend/src/views/PortalLegacyView.vue')
  const enhanced = read('frontend/src/views/official-site/ApprovedShowcaseView.vue')
  const markup = read('frontend/src/components/official-site/showcase/approved-home.html')
  assert.match(enhanced, /enterprise: ENTERPRISE_LOGIN_URL/)
  assert.match(markup, /data-entry="enterprise"/)
  assert.match(markup, /首次注册由学校邀请激活/)

  assert.match(config, /VITE_PORTAL_ENTERPRISE_LOGIN_URL/)
  assert.match(config, /'\/enterprise\/login'/)
  assert.match(home, /ENTERPRISE_LOGIN_URL/)
  assert.match(home, /企业注册 \/ 登录/)
  assert.match(home, /首次注册由学校邀请激活/)
  assert.match(home, /:href="enterpriseLoginUrl"/)
})

test('学校入口按身份提供教师与学生 H5，并为两端微信小程序码保留真实配置位', () => {
  const config = read('frontend/src/config/portalConfig.js')
  const enhanced = read('frontend/src/views/official-site/ApprovedShowcaseView.vue')
  const markup = read('frontend/src/components/official-site/showcase/approved-home.html')
  const runtime = read('frontend/src/components/official-site/showcase/runtime.js')

  assert.match(config, /VITE_PORTAL_TEACHER_H5_LOGIN_URL/)
  assert.match(config, /VITE_PORTAL_STUDENT_H5_LOGIN_URL/)
  assert.match(config, /\/miniapp\/#\/pages\/login\/teacher\/index/)
  assert.match(config, /\/miniapp\/#\/pages\/login\/student\/index/)
  assert.match(enhanced, /teacherH5: TEACHER_H5_LOGIN_URL/)
  assert.match(enhanced, /studentH5: STUDENT_H5_LOGIN_URL/)
  assert.match(enhanced, /teacherMiniQr: TEACHER_MINIPROGRAM_QR/)
  assert.match(enhanced, /studentMiniQr: STUDENT_MINIPROGRAM_QR/)
  assert.match(markup, /data-entry="teacherH5"/)
  assert.match(markup, /data-entry="studentH5"/)
  assert.match(markup, /data-entry-qr="teacherMiniQr"/)
  assert.match(markup, /data-entry-qr="studentMiniQr"/)
  assert.match(markup, /正式小程序码待运营配置/)
  assert.match(runtime, /\[data-entry-qr\]/)
  assert.match(runtime, /node\.src = value/)
})

test('高校人事系统在部署前保留安全占位，配置真实地址后自动启用', () => {
  const config = read('frontend/src/config/portalConfig.js')
  const enhanced = read('frontend/src/views/official-site/ApprovedShowcaseView.vue')
  const markup = read('frontend/src/components/official-site/showcase/approved-home.html')
  const runtime = read('frontend/src/components/official-site/showcase/runtime.js')

  assert.match(config, /VITE_PORTAL_HR_LOGIN_URL/)
  assert.match(enhanced, /humanResources: HR_LOGIN_URL/)
  assert.match(markup, /data-entry="humanResources"/)
  assert.match(markup, /data-entry-placeholder/)
  assert.match(markup, /高校人事系统/)
  assert.match(markup, /待部署/)
  assert.match(runtime, /hasAttribute\('data-entry-placeholder'\)/)
  assert.match(runtime, /removeAttribute\('href'\)/)
  assert.match(runtime, /setAttribute\('aria-disabled', 'true'\)/)
})

test('企业注册保持学校邀请激活 Authority，不开放自由注册', () => {
  const router = read('enterprise-portal/src/router/index.js')
  const login = read('enterprise-portal/src/views/EnterpriseLoginView.vue')

  assert.match(router, /path:\s*['"]\/login['"]/)
  assert.match(router, /path:\s*['"]\/invite\/accept['"]/)
  assert.doesNotMatch(router, /path:\s*['"]\/register['"]/)
  assert.match(login, /不提供开放式企业自注册/)
  assert.match(login, /学校发送的企业邀请链接/)
})

test('生产 Nginx 和 Compose 真正托管 enterprise-portal', () => {
  const vite = read('enterprise-portal/vite.config.js')
  const nginx = read('deploy/nginx/nginx.mysql.conf')
  const compose = read('deploy/docker/docker-compose.mysql.yml')

  assert.match(vite, /VITE_BASE\s*\|\|\s*['"]\/enterprise\/['"]/)
  assert.match(nginx, /location \^~ \/enterprise\//)
  assert.match(nginx, /try_files \$uri \$uri\/ \/enterprise\/index\.html/)
  assert.match(compose, /enterprise-portal\/dist:\/usr\/share\/nginx\/html\/enterprise:ro/)
})
