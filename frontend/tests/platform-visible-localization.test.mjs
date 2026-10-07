import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { optionsInstance } from './platform-workspace-test-support.mjs'

import {
  PLATFORM_FEATURE_LABELS,
  PLATFORM_RULE_GROUP_LABELS,
  PLATFORM_RULE_LABELS,
  platformEnumLabel,
  platformRoleLabel,
  platformServiceLabel,
  platformStatusLabel
} from '../src/modules/platform/constants/platform-display.constants.js'

const ruleKeys = [
  'studentNoRequired', 'idCardRequired', 'phoneRequired', 'allowDuplicatePhone', 'allowDuplicateIdCard',
  'studentArchiveVoidNeedReason', 'studentVoidReasonMinLength', 'studentEditAuditRequired',
  'rejectReasonRequired', 'rejectReasonMinLength', 'transferReasonRequired', 'approvalTimeoutHours',
  'autoReminderEnabled', 'approvalCanWithdraw', 'approvalCanTransfer',
  'importMaxRows', 'importAllowSkipError', 'importRequireConfirm', 'importCheckDuplicateStudentNo',
  'importCheckDuplicatePhone', 'importCheckDuplicateIdCard', 'exportNeedPurpose', 'exportPurposeMinLength',
  'exportWatermarkEnabled', 'exportPhoneMasked', 'exportIdCardMasked', 'exportMaxRows',
  'exportRateLimitPerMinute', 'uploadMaxSizeMb', 'allowedFileTypes', 'blockedFileTypes',
  'fileNameRandomize', 'fileDownloadNeedAudit', 'fileRetentionDays', 'riskWarningEnabled',
  'highRiskScoreThreshold', 'mediumRiskScoreThreshold', 'absenceDaysThreshold',
  'internshipWeeklyReportDelayDays', 'graduationTaskDelayDays', 'todoReminderEnabled',
  'messageUnreadReminderEnabled', 'trialExpireReminderDays', 'tenantExpireReminderDays',
  'loginFailLockEnabled', 'loginFailMaxTimes', 'loginFailLockMinutes', 'accessTokenExpireMinutes',
  'refreshTokenExpireDays', 'forceStrongPassword', 'trialDefaultDays', 'trialExpireReadOnly',
  'trialExpireAllowLogin', 'trialExpireShowContactPhone', 'disciplineBlocks'
]

test('平台规则中心的全部后端默认字段都有中文名称', () => {
  for (const key of ruleKeys) {
    assert.match(PLATFORM_RULE_LABELS[key] || '', /[\u4e00-\u9fff]/, `${key} 缺少中文名称`)
  }
  for (const key of ['student', 'approval', 'import', 'export', 'file', 'risk', 'message', 'security', 'trial', 'departure']) {
    assert.match(PLATFORM_RULE_GROUP_LABELS[key] || '', /[\u4e00-\u9fff]/, `${key} 缺少中文分组名`)
  }
})

test('平台功能和常用枚举统一输出中文', () => {
  for (const key of ['studentAffairs', 'academicAffairs', 'apiAccess']) {
    assert.match(PLATFORM_FEATURE_LABELS[key] || '', /[\u4e00-\u9fff]/)
  }
  assert.equal(platformStatusLabel('PUBLISHED'), '已发布')
  assert.equal(platformStatusLabel('trial'), '试用中')
  assert.equal(platformEnumLabel('PLATFORM'), '平台端')
  assert.equal(platformEnumLabel('CRITICAL'), '严重')
  assert.equal(platformRoleLabel('COUNSELOR'), '辅导员')
  assert.equal(platformServiceLabel('API_GATEWAY'), '后端接口服务')
  assert.equal(platformServiceLabel('MYSQL'), '关系型数据库')
  assert.equal(platformStatusLabel('NEW_BACKEND_STATUS'), '状态待确认')
})

test('访问治理表单用中文选项代替英文编码输入', () => {
  const source = readFileSync(new URL('../src/modules/platform/views/control/PlatformAccessView.vue', import.meta.url), 'utf8')
  assert.match(source, /capabilityOptions/)
  assert.match(source, /scopeOptions/)
  assert.doesNotMatch(source, /请输入能力编码/)
  assert.doesNotMatch(source, /请输入范围编码/)
})

test('租户规则页不再把未知英文键名直接显示给用户', () => {
  const source = readFileSync(new URL('../src/modules/platform/views/control/PlatformControlTenantDetail.vue', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /ruleLabels\[k\]\s*\|\|\s*k/)
  assert.doesNotMatch(source, /featureLabels\[k\]\s*\|\|\s*k/)
  const rules = readFileSync(new URL('../src/modules/platform/components/TenantRulesWorkspace.vue', import.meta.url), 'utf8')
  assert.match(source, /TenantRulesWorkspace/)
  assert.match(rules, /PLATFORM_RULE_LABELS/)
  assert.match(source, /platformRoleLabel/)
  const { state } = optionsInstance('../src/modules/platform/components/TenantRulesWorkspace.vue', {}, {
    PLATFORM_RULE_GROUP_LABELS, PLATFORM_RULE_LABELS
  })
  assert.equal(state.fieldLabel('studentNoRequired'), '学号必填')
  assert.equal(state.groupLabel('approval'), '审批规则')
  assert.equal(state.fieldLabel('unknownRawKey'), '待命名规则项')
  assert.equal(state.groupLabel('unknownRawGroup'), '其他规则')
})
