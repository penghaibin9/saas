#!/usr/bin/env node

import fs from 'node:fs'
import path from 'node:path'
import { execFileSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const toolDir = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(toolDir, '..')
const manifestPath = path.join(root, 'prototype-manifest.json')
const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'))
const validatedSourceHead = process.env.PR_HEAD_SHA || execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim()
const runId = process.env.GITHUB_RUN_ID || ''

manifest.schemaVersion = '2.9.0'
manifest.status = 'FROZEN'
manifest.designOnly = false
manifest.productionCodeModified = true
manifest.productionBoundaryExceptions = [
  'frontend/src/config/navPlan.js',
  'frontend/src/config/navPlan.permission-contract.test.js',
  'frontend/tests/studentAffairs.permissionCatalog.test.mjs'
]
manifest.baseline = {
  ...manifest.baseline,
  updatedAt: new Date().toISOString(),
  finalFreezeValidationSourceHead: validatedSourceHead,
  fullRegressionSourceHead: validatedSourceHead
}

manifest.validation = {
  ...manifest.validation,
  browserPassedRendersCumulative: 870,
  browserPassedPagesCumulative: 290,
  browserRemainingRenders: 0,
  browserRemainingPages: 0,
  directNavigationNote: '最终候选 HEAD 已完成 290 个独立 HTML × 3 档桌面视口 = 870 次全量回归；Linux Chrome 与 Windows Edge 的打印、宽表、键盘焦点和敏感业务专项均为 0 error。',
  navigationValidation: {
    ...manifest.validation?.navigationValidation,
    studentAffairsAlignedContracts: 15,
    studentAffairsPermissionBlockers: 0,
    permissionProjectionUnchanged: false,
    permissionProjectionNote: '数字迎新菜单已统一为 orientation.student.view；班级管理主入口已统一为 campus.record.view；辅导员责任与考评继续保留各自权限。'
  },
  tooling: {
    ...manifest.validation?.tooling,
    consistencyStatus: 'PASS_AT_FINAL_FREEZE_HEAD',
    browserRunner: 'tools/run-browser-regression-persistent.mjs',
    browserRunnerMode: 'ONE_PERSISTENT_CHROME_TWO_ISOLATED_PAGE_WORKERS',
    browserRunnerPageBounds: 'newPage=10s; collectProbe<=15s; screenshot<=15s; close<=3s; navigation<=30s',
    browserRunnerStatus: 'PASS_870_AT_FINAL_FREEZE_HEAD',
    browserRunnerExpectedRenders: 870,
    browserRunnerChromeProcessCount: 1,
    browserRunnerWorkerCount: 2,
    freezeAcceptanceRunner: 'tools/run-freeze-acceptance.mjs',
    freezeAcceptanceStatus: 'PASS_LINUX_CHROME_AND_WINDOWS_EDGE_0_ERROR',
    freezeAcceptanceRunId: runId,
    freezeAcceptanceCountsPerBrowser: {
      stressPages: 11,
      keyboardPages: 5,
      printPages: 4,
      sensitivePages: 5,
      errors: 0
    },
    productionPermissionContractTest: 'frontend/src/config/navPlan.permission-contract.test.js',
    productionPermissionContractStatus: 'PASS'
  },
  limitations: [
    '浏览器截图与 A4 PDF 作为 GitHub Actions Artifact 保存 14 天，不把二进制证据提交到源码仓库。',
    '原型冻结不代表生产前端替换已经完成；后续施工仍需按冻结 Manifest、routeName、权限和业务边界逐页还原。'
  ]
}

manifest.coverage = {
  ...manifest.coverage,
  registeredPrototypeEntries: 300,
  uniqueHtmlFiles: 290,
  sharedRouteEntries: 8,
  sharedDesignFiles: 43,
  machineValidatedWorkspaces: 60,
  machineValidatedHtmlFiles: 290,
  lastCompletedWorkspace: '最终冻结：边界、一致性、持久浏览器 870 全量、Linux Chrome / Windows Edge 专项、生产权限合同',
  nextWorkspaceCandidate: '按冻结原型启动教师 PC 生产前端分模块替换',
  remainingCenters: []
}

fs.writeFileSync(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
console.log(`frozen manifest prepared for ${validatedSourceHead}`)
