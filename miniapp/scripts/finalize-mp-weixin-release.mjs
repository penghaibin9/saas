import { promises as fs } from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const ROOT = process.cwd()
const OUTPUT_DIR = path.resolve(ROOT, 'dist/build/mp-weixin')
const APP_JSON = path.join(OUTPUT_DIR, 'app.json')
const PROJECT_JSON = path.join(OUTPUT_DIR, 'project.config.json')
const RELEASE_INFO = path.join(OUTPUT_DIR, 'RELEASE_INFO.txt')
const ENV_PRODUCTION = path.resolve(ROOT, '.env.production')
const SRC_MANIFEST = path.resolve(ROOT, 'src/manifest.json')
const APPID_PATTERN = /^wx[0-9a-fA-F]{16}$/
/** 微信开发者工具的游客/测试号：可以预览调试，但无法上传代码。 */
const TOURIST_APPID = 'touristappid'
const TEXT_EXTENSIONS = new Set(['.js', '.json', '.wxml', '.wxss', '.wxs', '.sjs', '.txt'])
const MAIN_PACKAGE_SPLIT_TRIGGER = Math.floor(1.8 * 1024 * 1024)
const MAIN_PACKAGE_LIMIT = 2 * 1024 * 1024
const TOTAL_PACKAGE_LIMIT = 20 * 1024 * 1024

function fail(message) {
  throw new Error(`[mp-weixin release] ${message}`)
}

async function readJson(file) {
  try {
    return JSON.parse(await fs.readFile(file, 'utf8'))
  } catch (error) {
    fail(`无法读取 ${path.relative(ROOT, file)}：${error.message}`)
  }
}

async function walk(dir) {
  const entries = await fs.readdir(dir, { withFileTypes: true })
  const files = []
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name)
    if (entry.isDirectory()) files.push(...await walk(fullPath))
    else files.push(fullPath)
  }
  return files
}

function normalizeRelative(file) {
  return path.relative(OUTPUT_DIR, file).split(path.sep).join('/')
}

async function readTextOrEmpty(file) {
  try { return await fs.readFile(file, 'utf8') } catch (error) { return '' }
}

/**
 * 解析小程序 AppID，按优先级：环境变量 → .env.production → src/manifest.json。
 * 目的是让非技术使用者只改 .env.production 一个文件就能打出可上传的包。
 */
async function resolveAppId() {
  const fromEnv = String(process.env.WECHAT_APPID || '').trim()
  if (fromEnv) return { appid: fromEnv, source: '环境变量 WECHAT_APPID' }

  const envText = await readTextOrEmpty(ENV_PRODUCTION)
  const envMatch = envText.match(/^\s*VITE_WECHAT_APPID\s*=\s*(.+?)\s*$/m)
  if (envMatch && envMatch[1]) return { appid: envMatch[1].trim(), source: '.env.production 的 VITE_WECHAT_APPID' }

  const manifestText = await readTextOrEmpty(SRC_MANIFEST)
  try {
    const manifest = JSON.parse(manifestText || '{}')
    const fromManifest = String((manifest['mp-weixin'] || {}).appid || '').trim()
    if (fromManifest) return { appid: fromManifest, source: 'src/manifest.json 的 mp-weixin.appid' }
  } catch (error) { /* manifest 解析失败不阻断，走未配置分支 */ }

  return { appid: '', source: '' }
}

function collectPages(appConfig) {
  const pages = new Set(appConfig.pages || [])
  const subPackages = appConfig.subPackages || appConfig.subpackages || []
  for (const subPackage of subPackages) {
    const root = String(subPackage.root || '').replace(/^\/+|\/+$/g, '')
    for (const page of subPackage.pages || []) {
      pages.add([root, page].filter(Boolean).join('/'))
    }
  }
  return { pages, subPackages }
}

function isInsideSubPackage(relativeFile, subPackageRoots) {
  return subPackageRoots.some((root) => relativeFile === root || relativeFile.startsWith(`${root}/`))
}

async function main() {
  const expectedApiBase = String(process.env.VITE_API_BASE_URL || 'https://api.hnyueke.com').replace(/\/+$/, '')
  if (!/^https:\/\//i.test(expectedApiBase)) {
    fail(`生产 API 必须使用 HTTPS，当前为 ${expectedApiBase}`)
  }

  const { appid, source: appidSource } = await resolveAppId()
  if (appid && !APPID_PATTERN.test(appid)) {
    fail(`AppID 格式错误（来自${appidSource}）：应为 wx 开头 + 16 位十六进制字符，当前为 ${appid}`)
  }

  await fs.access(OUTPUT_DIR).catch(() => fail('未找到 dist/build/mp-weixin，请先执行微信小程序构建'))
  const appConfig = await readJson(APP_JSON)
  const projectConfig = await readJson(PROJECT_JSON)

  const { pages, subPackages } = collectPages(appConfig)
  const requiredPages = [
    'pages/login/index',
    'pages/login/student/index',
    'pages/login/teacher/index',
    'pages/student/home/index',
    'pages/teacher/workbench/index'
  ]
  const missingPages = requiredPages.filter((page) => !pages.has(page))
  if (missingPages.length) fail(`构建产物缺少关键页面：${missingPages.join(', ')}`)

  projectConfig.projectname = projectConfig.projectname || '跃科校园通'
  projectConfig.setting = {
    ...(projectConfig.setting || {}),
    urlCheck: true,
    es6: true,
    minified: true
  }
  // 绝不写入空 appid：空值会让微信开发者工具在导入时直接报错，比保留 touristappid 更糟
  // （touristappid 至少能导入预览，只是不能上传）。未配置时保留占位并在末尾醒目提示。
  projectConfig.appid = appid || String(projectConfig.appid || '').trim() || TOURIST_APPID
  const uploadReady = APPID_PATTERN.test(projectConfig.appid)
  await fs.writeFile(PROJECT_JSON, `${JSON.stringify(projectConfig, null, 2)}\n`, 'utf8')

  let files = await walk(OUTPUT_DIR)
  const sourceMaps = files.filter((file) => file.endsWith('.map'))
  await Promise.all(sourceMaps.map((file) => fs.unlink(file)))
  files = files.filter((file) => !file.endsWith('.map'))

  const textFiles = files.filter((file) => TEXT_EXTENSIONS.has(path.extname(file).toLowerCase()))
  let apiBaseFound = false
  const cleartextApiFiles = []
  for (const file of textFiles) {
    const text = await fs.readFile(file, 'utf8')
    if (text.includes(expectedApiBase)) apiBaseFound = true
    if (/http:\/\/(?!localhost|127\.0\.0\.1)/i.test(text)) cleartextApiFiles.push(normalizeRelative(file))
  }
  if (!apiBaseFound) fail(`构建产物未注入正式 API：${expectedApiBase}`)
  if (cleartextApiFiles.length) {
    fail(`构建产物包含非本机 HTTP 明文地址：${[...new Set(cleartextApiFiles)].join(', ')}`)
  }

  const subPackageRoots = subPackages
    .map((item) => String(item.root || '').replace(/^\/+|\/+$/g, ''))
    .filter(Boolean)

  let totalBytes = 0
  let mainPackageBytes = 0
  for (const file of files) {
    const size = (await fs.stat(file)).size
    const relativeFile = normalizeRelative(file)
    totalBytes += size
    if (!isInsideSubPackage(relativeFile, subPackageRoots)) mainPackageBytes += size
  }

  if (totalBytes > TOTAL_PACKAGE_LIMIT) {
    fail(`小程序总包约 ${(totalBytes / 1024 / 1024).toFixed(2)} MiB，超过 20 MiB`)
  }
  if (mainPackageBytes >= MAIN_PACKAGE_SPLIT_TRIGGER) {
    fail(
      `主包约 ${(mainPackageBytes / 1024 / 1024).toFixed(2)} MiB，达到 1.80 MiB 主动分包线；` +
      '必须实施 pages.json 分包后再发布'
    )
  }
  if (mainPackageBytes > MAIN_PACKAGE_LIMIT) {
    fail(`主包约 ${(mainPackageBytes / 1024 / 1024).toFixed(2)} MiB，超过 2 MiB`)
  }

  const apiHost = expectedApiBase.replace(/^https:\/\//i, '')
  const privacyApis = appConfig.requiredPrivateInfos || []

  const info = [
    '跃科校园通 · 微信小程序生产构建产物',
    '',
    '── 构建结果 ──',
    `API: ${expectedApiBase}`,
    `AppID: ${uploadReady ? projectConfig.appid : `${projectConfig.appid}（占位，未配置真实 AppID）`}`,
    `AppID 来源: ${appidSource || '未配置'}`,
    `主包大小: ${(mainPackageBytes / 1024 / 1024).toFixed(2)} MiB（主动分包线 1.80 MiB / 上限 2 MiB）`,
    `总包大小: ${(totalBytes / 1024 / 1024).toFixed(2)} MiB（上限 20 MiB）`,
    `分包数量: ${subPackages.length}`,
    '学生端入口: pages/login/student/index',
    '教师端入口: pages/login/teacher/index',
    '',
    '── 能否直接上传 ──',
    uploadReady
      ? '✅ 可以上传：AppID 已注入，微信开发者工具导入本目录后即可点「上传」。'
      : [
          '❌ 还不能上传：当前是占位 AppID，微信开发者工具的「上传」按钮不可用。',
          '   解决办法（二选一）：',
          '     A. 打开 miniapp/.env.production，填写 VITE_WECHAT_APPID=你的小程序AppID，重新执行',
          '        npm run build:mp-weixin:release',
          '     B. 在微信开发者工具里导入本目录后，点右上角「详情 → 基本信息 → AppID」改为你的正式 AppID'
        ].join('\n'),
    '',
    '── 上传前必须在「微信公众平台」后台完成的配置 ──',
    `1. 开发管理 → 开发设置 → 服务器域名 → request 合法域名，添加：https://${apiHost}`,
    '   （不加会导致小程序真机上所有接口请求失败，开发者工具里勾了"不校验域名"看不出来）',
    privacyApis.length
      ? `2. 设置 → 服务内容与类目 → 用户隐私保护指引，声明本小程序会收集：${privacyApis.includes('getLocation') ? '位置信息' : privacyApis.join('、')}` +
        '\n   （未声明时 wx.getLocation 会直接报错 errno 112，实习打卡的定位拿不到）'
      : '2. 用户隐私保护指引：本次构建未声明隐私接口，无需配置',
    '3. 若后续把《用户协议》《隐私政策》改为外链（配置 VITE_TERMS_URL / VITE_PRIVACY_URL），',
    '   还需在 开发管理 → 开发设置 → 业务域名 中添加对应域名并上传校验文件；',
    '   当前为小程序内置正文，无需配置业务域名。',
    '',
    '── 导入方式 ──',
    '微信开发者工具 → 导入项目 → 目录选择：本文件所在的 mp-weixin 文件夹',
    '（该目录已含 project.config.json，无需手动填项目配置）'
  ].join('\n')
  await fs.writeFile(RELEASE_INFO, `${info}\n`, 'utf8')

  console.log(info)
  if (!uploadReady) {
    console.log('\n[mp-weixin release] 提示：本次产物可导入预览，但不能上传。原因与解决办法见上方「能否直接上传」。')
  }
}

main().catch((error) => {
  console.error(error.stack || error.message || error)
  process.exit(1)
})
