import test from 'node:test'
import assert from 'node:assert/strict'

import {
  GD_MATERIAL_STAGES,
  graduationArchiveStatusLabel,
  graduationMaterialStageLabel,
  graduationReviewStatusLabel,
  graduationScanStatusLabel
} from '../graduation-material.constants.js'
import {
  messageCampaignStatusLabel,
  messageCategoryLabel,
  messageDeliveryStatusLabel
} from '../../../messageCenter/constants/message-center.constants.js'
import {
  academicExchangeTypeLabel,
  academicStatusLabel
} from '../../../academicAffairs/constants/academic-display.constants.js'
import { platformStatusLabel } from '../../../platform/constants/platform-display.constants.js'

const ENGLISH_ENUM = /^[A-Z][A-Z0-9_]*$/

test('毕业材料阶段全部展示为中文，接口值仍保持稳定枚举', () => {
  assert.equal(GD_MATERIAL_STAGES.length, 12)
  for (const item of GD_MATERIAL_STAGES) {
    assert.match(item.value, ENGLISH_ENUM)
    assert.match(item.label, /[\u4e00-\u9fff]/)
    assert.equal(graduationMaterialStageLabel(item.value), item.label)
  }
})

test('毕业材料关联状态不会把英文枚举直接暴露给用户', () => {
  assert.equal(graduationScanStatusLabel('SCANNING'), '扫描中')
  assert.equal(graduationReviewStatusLabel('APPROVED'), '已通过')
  assert.equal(graduationArchiveStatusLabel('ARCHIVED'), '已归档')
  assert.equal(graduationScanStatusLabel('NEW_BACKEND_CODE'), '扫描状态待确认')
})

test('消息、教务和平台常用状态统一中文展示', () => {
  assert.equal(messageCampaignStatusLabel('PUBLISHED'), '已发布')
  assert.equal(messageCategoryLabel('EMERGENCY'), '紧急消息')
  assert.equal(messageDeliveryStatusLabel('DELIVERED'), '已送达')
  assert.equal(academicStatusLabel('VALIDATED'), '预检通过')
  assert.equal(academicExchangeTypeLabel('ROSTER'), '学籍名册')
  assert.equal(platformStatusLabel('NEEDS_MANUAL_REVIEW'), '需人工复核')
})

test('未知枚举使用中文兜底，不回显技术码', () => {
  for (const label of [
    academicStatusLabel('UNKNOWN_NEW_STATUS'),
    platformStatusLabel('UNKNOWN_NEW_STATUS'),
    messageCampaignStatusLabel('UNKNOWN_NEW_STATUS')
  ]) {
    assert.doesNotMatch(label, ENGLISH_ENUM)
    assert.match(label, /[\u4e00-\u9fff]/)
  }
})
