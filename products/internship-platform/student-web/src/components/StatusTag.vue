<template>
  <span class="sp-tag" :class="'sp-tag--' + displayTone">{{ displayText }}</span>
</template>

<script setup>
import { computed } from 'vue'
import { safeVisibleEnumLabel } from '../services/visibleEnumLocalization'

const props = defineProps({
  status: { type: String, default: '' },
  text: { type: String, default: '' },
  tone: { type: String, default: '' } // default / success / warn / danger
})

// 学生PC与管理PC/微信端保持同一业务含义；ARCHIVED绝不翻译成“已作废”。
const STATUS_MAP = {
  DRAFT: ['草稿', 'default'],
  PENDING: ['待处理', 'warn'],
  PENDING_CONFIRM: ['待确认', 'warn'],
  PENDING_REVIEW: ['待审核', 'warn'],
  PENDING_HANDLE: ['待处理', 'warn'],
  NOT_SUBMITTED: ['未提交', 'default'],
  PENDING_LOTTERY: ['待摇号', 'warn'],
  SUBMITTED: ['已提交', 'warn'],
  REVIEWING: ['审核中', 'warn'],
  INPUTTING: ['录入中', 'warn'],
  CLASS_REVIEW: ['班级审核中', 'warn'],
  COLLEGE_REVIEW: ['学院审核中', 'warn'],
  ACADEMIC_REVIEW: ['教务终审中', 'warn'],
  CHANGE_REVIEW: ['更正审核中', 'warn'],
  PRE_PUBLISHED: ['预发布', 'warn'],
  OPEN: ['开放中', 'success'],
  CLOSED: ['已截止', 'default'],
  SELECTED: ['已选中', 'success'],
  LOCKED: ['名单已锁定', 'success'],
  DROPPED: ['已退选', 'default'],
  LOTTERY_LOST: ['未中签', 'danger'],
  COURSE_CANCELLED: ['课程已取消', 'danger'],
  APPROVED: ['已通过', 'success'],
  CONFIRMED: ['已确认', 'success'],
  READY: ['已就绪', 'success'],
  PUBLISHED: ['已发布', 'success'],
  FINISHED: ['已结束', 'success'],
  ARCHIVED: ['已归档', 'default'],
  VOIDED: ['已作废', 'danger'],
  RETURNED: ['已退回', 'warn'],
  REJECTED: ['已驳回', 'danger'],
  FAILED: ['未通过', 'danger'],
  PRESENT: ['到考', 'success'],
  ABSENT: ['缺考', 'danger'],
  LATE: ['迟到', 'warn'],
  LEAVE: ['请假', 'default'],
  CHEAT: ['作弊', 'danger'],
  DEFERRED: ['缓考', 'warn'],
  EXEMPT: ['免修', 'default'],
  REMOVED: ['已移除', 'default']
}
const ENUM_TOKEN_RE = /^[A-Z][A-Z0-9_]*$/

const mapped = computed(() => STATUS_MAP[String(props.status || '').toUpperCase()] || null)
const explicitMapped = computed(() => STATUS_MAP[String(props.text || '').trim().toUpperCase()] || null)
const displayText = computed(() => {
  const explicit = String(props.text || '').trim()
  if (explicit && (!props.status || explicit !== props.status)) {
    if (!ENUM_TOKEN_RE.test(explicit)) return explicit
    return explicitMapped.value?.[0] || safeVisibleEnumLabel(explicit, '状态待确认')
  }
  if (mapped.value) return mapped.value[0]
  return safeVisibleEnumLabel(props.status, '状态待确认')
})
const displayTone = computed(() => props.tone || (mapped.value ? mapped.value[1] : (explicitMapped.value ? explicitMapped.value[1] : 'default')))
</script>
