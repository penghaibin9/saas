import { spawnSync } from 'node:child_process'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// Use the installed WeChat compiler: Vite accepting CSS does not prove WXSS accepts it.
const compiler = process.argv[2] || process.env.WECHAT_WCSC_PATH
if (!compiler || !existsSync(compiler)) {
  console.error('请通过参数或 WECHAT_WCSC_PATH 指定微信开发者工具自带的 wcsc 编译器。')
  process.exit(1)
}
const output = fileURLToPath(new URL('../dist/build/mp-weixin/', import.meta.url))
const files = [
  'pages/student/home/index.wxss', 'pages/student/campus-service/index.wxss',
  'pages/student/messages/index.wxss', 'pages/student/me/index.wxss',
  'components/MobileStudentHero.wxss', 'components/MobileShellIcon.wxss', 'components/MobileTabBar.wxss'
]
for (const file of files) {
  const result = spawnSync(compiler, [file], { cwd: output, encoding: 'utf8', windowsHide: true })
  if (result.error || result.status !== 0) {
    console.error(`微信样式检查失败：${file}`)
    console.error(result.error?.message || result.stderr || result.stdout)
    process.exit(1)
  }
  console.log(`PASS ${file}`)
}
