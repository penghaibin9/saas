import { promises as fs } from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const ROOT = process.cwd()
const OUTPUT_DIR = path.resolve(ROOT, 'dist/build/mp-weixin')
const APP_JSON = path.join(OUTPUT_DIR, 'app.json')
const PROJECT_JSON = path.join(OUTPUT_DIR, 'project.config.json')
const RELEASE_INFO = path.join(OUTPUT_DIR, 'RELEASE_INFO.txt')
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

  const appid = String(process.env.WECHAT_APPID || '').trim()
  if (appid && !/^wx[0-9a-zA-Z]{16}$/.test(appid)) {
    fail('WECHAT_APPID 格式错误，应为 wx 开头的 18 位小程序 AppID')
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
  projectConfig.appid = appid
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

  const info = [
    '跃科校园通 · 微信小程序生产构建产物',
    `API: ${expectedApiBase}`,
    `AppID: ${appid || '未注入，请在微信开发者工具导入时选择你的小程序 AppID'}`,
    '学生端入口: pages/login/student/index',
    '教师端入口: pages/login/teacher/index',
    `主包大小: ${(mainPackageBytes / 1024 / 1024).toFixed(2)} MiB`,
    `总包大小: ${(totalBytes / 1024 / 1024).toFixed(2)} MiB`,
    `分包数量: ${subPackages.length}`,
    '主动分包线: 1.80 MiB',
    '导入目录: 本文件所在的 mp-weixin 文件夹'
  ].join('\n')
  await fs.writeFile(RELEASE_INFO, `${info}\n`, 'utf8')

  console.log(info)
}

main().catch((error) => {
  console.error(error.stack || error.message || error)
  process.exit(1)
})
