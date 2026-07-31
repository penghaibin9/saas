import fs from 'node:fs/promises'
import path from 'node:path'

const outputDir = path.resolve(process.env.REVIEW_OUTPUT || '../docs/reviews/student-portal-v5-full-review')
const report = JSON.parse(await fs.readFile(path.join(outputDir, 'review-results.json'), 'utf8'))
const md = []
md.push('# Student Portal V5 第一阶段真实页面复审报告')
md.push('')
md.push(`- 生成时间：${report.generatedAt}`)
md.push(`- 执行方式：${report.source}`)
md.push(`- 页面：${report.summary.passedRoutes}/${report.summary.totalRoutes} 通过；有问题 ${report.summary.problemRoutes}；阻塞 ${report.summary.blockedRoutes}；未检查 ${report.summary.uncheckedRoutes}`)
md.push(`- 三级 tab / 子工作区：检查 ${report.summary.tabsChecked}；有问题 ${report.summary.tabProblems}`)
md.push(`- 关键交互：检查 ${report.summary.functionalChecks}；有问题 ${report.summary.functionalProblems}`)
md.push(`- 六套主题：检查 ${report.summary.themesChecked}；有问题 ${report.summary.themeProblems}`)
md.push(`- 多分辨率：检查 ${report.summary.viewportCases}；有问题 ${report.summary.viewportProblems}`)
md.push(`- 控制台错误：${report.summary.consoleErrors}；失败网络请求：${report.summary.networkFailures}`)
md.push('')
md.push('## 页面验收矩阵')
md.push('')
md.push('| 路由 | 页面 | 模块 | 结果 | 子工作区 | 主要问题 | 证据 |')
md.push('|---|---|---|---|---:|---|---|')
for (const row of report.routes) {
  const issues = [...row.issues, ...row.tabs.flatMap((tab) => tab.issues.map((issue) => `${tab.label}: ${issue}`))]
  const shots = row.screenshots.map((shot) => `[截图](${shot})`).join(' ')
  md.push(`| \`${row.path}\` | ${row.name} | ${row.module} | ${row.result} | ${row.tabs.length} | ${issues.join('；') || '—'} | ${shots} |`)
}
md.push('')
md.push('## 三级 tab 与子工作区检查')
md.push('')
for (const row of report.routes.filter((entry) => entry.tabs.length)) {
  md.push(`### ${row.name}（${row.path}）`)
  for (const tab of row.tabs) md.push(`- ${tab.issues.length ? '❌' : '✅'} ${tab.label}${tab.screenshot ? ` · [截图](${tab.screenshot})` : ''}${tab.issues.length ? ` · ${tab.issues.join('；')}` : ''}`)
  md.push('')
}
md.push('## 关键真实交互')
md.push('')
for (const row of report.functionalChecks) {
  md.push(`- ${row.passed ? '✅' : '❌'} ${row.name}${row.screenshot ? ` · [截图](${row.screenshot})` : ''}`)
  if (!row.passed) md.push(`  - 实际：\`${JSON.stringify(row.actual || {})}\``)
}
md.push('')
md.push('## 六套主题代表证据')
md.push('')
for (const row of report.themeChecks) {
  md.push(`- ${row.passed ? '✅' : '❌'} ${row.label} · ${row.route} · 对比度候选问题 ${row.layout?.contrastIssues?.length || 0} · [截图](${row.screenshot})`)
  for (const issue of (row.layout?.contrastIssues || []).slice(0, 12)) {
    md.push(`  - ${issue.text} · 对比度 ${issue.ratio}/${issue.minimum} · ${issue.color} on ${issue.background}`)
  }
}
md.push('')
md.push('## 多分辨率')
md.push('')
const viewportProblems = report.viewportChecks.filter((row) => !row.passed)
if (!viewportProblems.length) md.push('- 自动横向溢出和视口越界检查未发现问题；仍需结合代表截图人工判断视觉质量。')
for (const row of viewportProblems) md.push(`- ❌ ${row.viewport} ${row.route}：${row.issues.join('；')}${row.screenshot ? ` · [截图](${row.screenshot})` : ''}`)
md.push('')
md.push('## 登录、权限与刷新')
md.push('')
for (const row of report.authChecks) md.push(`- ${row.passed ? '✅' : '❌'} ${row.name} · ${row.url || ''}`)
md.push('')
md.push('## 控制台与网络错误')
md.push('')
if (!report.consoleErrors.length) md.push('- 未捕获 console error 或 pageerror。')
for (const row of report.consoleErrors.slice(0, 80)) md.push(`- console · ${row.scope} · ${row.text}`)
if (!report.networkFailures.length) md.push('- 未捕获 HTTP 4xx/5xx 或 requestfailed。')
for (const row of report.networkFailures.slice(0, 120)) md.push(`- network · ${row.scope} · ${row.method} ${row.status} ${row.url}${row.error ? ` · ${row.error}` : ''}`)
md.push('')
md.push('## 判定边界')
md.push('')
md.push('- 本报告使用真实数据库、真实账号密码和真实接口，不调用 `/auth/mock-login`。')
md.push('- 动态安装的全部教务独立路由已纳入，不再只检查 `/academic` 工作台。')
md.push('- 自动化能够证明页面可达、子工作区可切换、刷新不丢失、主题生效以及常见溢出问题。')
md.push('- 自动化不会因为公共 CSS 已命中就判定“逐页设计完成”；还必须对截图进行人工视觉复审并形成 P0–P3 问题清单。')
await fs.writeFile(path.join(outputDir, 'REVIEW_REPORT.md'), md.join('\n'), 'utf8')
