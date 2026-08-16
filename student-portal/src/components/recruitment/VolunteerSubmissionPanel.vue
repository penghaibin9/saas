<template>
  <section class="submission-panel" :class="`is-${status.toLowerCase()}`">
    <div class="status-head">
      <div>
        <strong>{{ meta.label }}</strong>
        <p>{{ stateMessage }}</p>
      </div>
      <span v-if="status === 'LOCKED'" class="locked-mark">已锁定</span>
    </div>

    <div v-if="status === 'LOCKED' && group.teacherConfirmDeadline" class="deadline">
      学校确认截止：<strong>{{ deadlineText }}</strong>
    </div>

    <div v-if="submitError.message" class="submit-error">
      <strong>{{ submitError.message }}</strong>
      <ul v-if="submitError.invalidItems.length">
        <li v-for="item in submitError.invalidItems" :key="`${item.volunteerNo}-${item.positionId}`">
          第{{ item.volunteerNo }}志愿 · 岗位 {{ item.positionId || '未知' }}：{{ item.reason }}
        </li>
      </ul>
    </div>

    <div v-if="confirmOpen" class="confirm-box">
      <div class="confirm-title">
        <strong>确认整组投递</strong>
        <button type="button" :disabled="busy" @click="$emit('cancel-confirm')">取消</button>
      </div>
      <ol class="confirm-volunteers">
        <li v-for="slot in activeSlots" :key="slot.volunteerNo">
          <span>第{{ slot.volunteerNo }}志愿</span>
          <strong>{{ slot.position?.title || `岗位 #${slot.positionId}` }}</strong>
          <small>{{ slot.position?.companyName || '' }}</small>
        </li>
      </ol>
      <div class="material-version">
        <span>材料版本</span><strong>Profile v{{ preview.profileVersion || '—' }} / Group v{{ group.version || 0 }}</strong>
      </div>
      <label class="contact-field">
        <span>联系方式策略</span>
        <select :value="contactSharingMode" :disabled="busy" @change="$emit('update:contactSharingMode', $event.target.value)">
          <option value="MASKED_ONLY">仅脱敏</option>
          <option value="AFTER_INTERVIEW">面试后可查看</option>
          <option value="AFTER_ACCEPT_INTENT">拟接收后可查看</option>
          <option value="IMMEDIATE">立即允许查看</option>
        </select>
      </label>
      <div class="preview-hash">企业视角预览：{{ preview.previewHash ? '已确认服务端版本' : '尚未生成' }}</div>
      <label class="consent">
        <input :checked="confirmed" type="checkbox" :disabled="busy" @change="$emit('update:confirmed', $event.target.checked)" />
        <span>我确认以上 1–3 志愿、材料版本与联系方式共享范围，并同意整组投递。</span>
      </label>
      <button type="button" class="primary" :disabled="busy || !confirmed || !preview.previewHash" @click="$emit('submit')">
        {{ busy ? '整组提交中…' : '确认整组投递' }}
      </button>
    </div>

    <div v-else class="actions">
      <button v-if="canSubmit" type="button" class="primary" :disabled="busy || activeSlots.length < 1" @click="$emit('prepare-submit')">准备整组投递</button>
      <button v-if="canWithdraw" type="button" class="secondary" :disabled="busy" @click="$emit('withdraw')">整组撤回并修改</button>
      <button v-if="canUnlock" type="button" class="secondary" :disabled="busy" @click="$emit('unlock')">申请改志愿</button>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import {
  VOLUNTEER_STATUS_META,
  canRequestVolunteerUnlock,
  canSubmitVolunteerGroup,
  canWithdrawVolunteerGroup,
  formatSchoolConfirmDeadline,
  submissionStateMessage
} from '../../modules/internshipRecruitment/submissionModel.js'

const props = defineProps({
  group: { type: Object, required: true },
  slots: { type: Array, required: true },
  preview: { type: Object, required: true },
  contactSharingMode: { type: String, default: 'MASKED_ONLY' },
  confirmed: { type: Boolean, default: false },
  confirmOpen: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  submitError: { type: Object, default: () => ({ message: '', invalidItems: [] }) }
})
const emit = defineEmits(['prepare-submit', 'cancel-confirm', 'submit', 'withdraw', 'unlock', 'update:contactSharingMode', 'update:confirmed'])

onMounted(() => {
  // A03 production privacy seal: historical parent default was AFTER_INTERVIEW.
  // Normalize only the initial mounted value; later explicit student choices are preserved.
  if (props.contactSharingMode === 'AFTER_INTERVIEW') emit('update:contactSharingMode', 'MASKED_ONLY')
})

const status = computed(() => String(props.group.status || 'DRAFT').toUpperCase())
const meta = computed(() => VOLUNTEER_STATUS_META[status.value] || { label: status.value, tone: 'neutral' })
const activeSlots = computed(() => props.slots.filter((slot) => slot.positionId))
const canSubmit = computed(() => canSubmitVolunteerGroup(props.group))
const canWithdraw = computed(() => canWithdrawVolunteerGroup(props.group))
const canUnlock = computed(() => canRequestVolunteerUnlock(props.group))
const stateMessage = computed(() => submissionStateMessage(props.group))
const deadlineText = computed(() => formatSchoolConfirmDeadline(props.group.teacherConfirmDeadline))
</script>

<style scoped>
.submission-panel { margin-top:8px; padding:12px; border:1px solid #eef0f3; border-radius:9px; background:#fff; }
.submission-panel.is-locked { border-color:#ffd591; background:#fffdf7; }
.submission-panel.is-needs_revision { border-color:#adc6ff; background:#f8fbff; }
.status-head { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; }
.status-head strong { color:#333; font-size:13px; }
.status-head p { margin:4px 0 0; color:#777; font-size:11px; line-height:1.55; }
.locked-mark { flex-shrink:0; padding:3px 6px; border-radius:4px; background:#fff1b8; color:#874d00; font-size:10px; font-weight:800; }
.deadline { margin-top:9px; padding:8px 9px; border-radius:6px; background:#fff7e6; color:#874d00; font-size:11px; }
.submit-error { margin-top:9px; padding:9px; border-radius:7px; background:#fff2f0; color:#a8071a; font-size:11px; }
.submit-error > strong { display:block; }
.submit-error ul { margin:6px 0 0; padding-left:18px; line-height:1.55; }
.actions { display:grid; gap:7px; margin-top:10px; }
.primary,.secondary { width:100%; min-height:34px; border:0; border-radius:6px; cursor:pointer; font-weight:600; }
.primary { background:#2f6bff; color:#fff; }
.secondary { background:#eef4ff; color:#2f6bff; }
.primary:disabled,.secondary:disabled { opacity:.5; cursor:not-allowed; }
.confirm-box { display:grid; gap:10px; margin-top:10px; padding-top:10px; border-top:1px solid #eef0f3; }
.confirm-title { display:flex; align-items:center; justify-content:space-between; gap:8px; }
.confirm-title strong { color:#1a1a1a; font-size:13px; }
.confirm-title button { border:0; background:transparent; color:#2f6bff; cursor:pointer; font-size:11px; }
.confirm-volunteers { display:grid; gap:6px; margin:0; padding-left:20px; }
.confirm-volunteers li { color:#666; font-size:11px; }
.confirm-volunteers li span { display:block; color:#8c8c8c; font-size:10px; }
.confirm-volunteers li strong { display:block; margin-top:1px; color:#333; font-size:12px; }
.confirm-volunteers li small { color:#777; }
.material-version,.contact-field { display:grid; grid-template-columns:82px 1fr; align-items:center; gap:8px; }
.material-version span,.contact-field span { color:#8c8c8c; font-size:10px; }
.material-version strong { color:#333; font-size:11px; }
.contact-field select { min-width:0; height:32px; border:1px solid #d9d9d9; border-radius:6px; padding:0 7px; background:#fff; font-size:11px; }
.preview-hash { padding:7px 8px; border-radius:6px; background:#f6f9ff; color:#45658c; font-size:10px; }
.consent { display:flex; align-items:flex-start; gap:7px; color:#555; font-size:10px; line-height:1.55; }
.consent input { margin-top:2px; }
</style>
