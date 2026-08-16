import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '../..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

test('跃科公开门户提供企业注册/登录真实入口', () => {
  const config = read('frontend/src/config/portalConfig.js')
  const home = read('frontend/src/views/PortalHomeView.vue')

  assert.match(config, /VITE_PORTAL_ENTERPRISE_LOGIN_URL/)
  assert.match(config, /'\/enterprise\/login'/)
  assert.match(home, /ENTERPRISE_LOGIN_URL/)
  assert.match(home, /企业注册 \/ 登录/)
  assert.match(home, /首次注册由学校邀请激活/)
  assert.match(home, /:href="enterpriseLoginUrl"/)
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
