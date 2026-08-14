<template>
  <aside class="volunteer-board" aria-label="我的岗位志愿">
    <div class="board-heading">
      <div><strong>我的志愿</strong><span>{{ selectedCount }}/3</span></div>
      <span class="group-status">{{ statusLabel }}</span>
    </div>

    <div v-if="error" class="board-alert">{{ error }}</div>
    <div v-if="candidate && selectedCount >= 3 && editable" class="replace-tip">
      <strong>三志愿已满</strong>
      <span>选择一个位置替换为「{{ candidate.title }}」</span>
    </div>

    <div class="slots">
      <section v-for="slot in slots" :key="slot.volunteerNo" class="volunteer-slot" :class="{ 'is-empty': !slot.positionId }">
        <div class="slot-title-row">
          <strong>第{{ chineseNo(slot.volunteerNo) }}志愿</strong>
          <div v-if="slot.positionId && editable" class="slot-actions">
            <button type="button" :disabled="busy || slot.volunteerNo === 1 || !slots[slot.volunteerNo - 2]?.positionId" @click="$emit('move', slot.volunteerNo, 'UP')">上移</button>
            <button type="button" :disabled="busy || slot.volunteerNo === 3 || !slots[slot.volunteerNo]?.positionId" @click="$emit('move', slot.volunteerNo, 'DOWN')">下移</button>
            <button type="button" class="danger" :disabled="busy" @click="$emit('remove', slot.volunteerNo)">删除</button>
          </div>
        </div>

        <template v-if="slot.positionId">
          <div class="slot-position">
            <strong>{{ slot.position?.title || `岗位 #${slot.positionId}` }}</strong>
            <span>{{ slot.position?.companyName || '企业信息加载中' }}</span>
            <span>{{ slot.position?.workLocation || '' }}</span>
          </div>
          <label class="statement-field">
            <span>岗位申请说明</span>
            <textarea
              :value="slot.applicationStatement"
              rows="3"
              maxlength="500"
              :disabled="!editable || busy"
              placeholder="针对这个岗位说明你的申请动机与匹配点"
              @change="$emit('statement', slot.volunteerNo, $event.target.value)"
            />
          </label>
        </template>
        <div v-else class="empty-slot">从岗位详情点击“加入志愿”</div>

        <button
          v-if="candidate && editable && (selectedCount >= 3 || slot.positionId)"
          type="button"
          class="replace-button"
          :disabled="busy || String(slot.positionId) === String(candidate.id)"
          @click="$emit('replace', slot.volunteerNo, candidate)"
        >
          替换为当前岗位
        </button>
      </section>
    </div>

    <div class="board-foot">
      <p>公共实习档案只维护一份；每个志愿的岗位申请说明分别保存。</p>
      <button type="button" class="save-button" :disabled="busy || !editable || selectedCount < 1" @click="$emit('save')">
        {{ busy ? '保存中…' : '保存志愿' }}
      </button>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  group: { type: Object, required: true },
  slots: { type: Array, required: true },
  candidate: { type: Object, default: null },
  editable: { type: Boolean, default: false },
  busy: { type: Boolean, default: false },
  error: { type: String, default: '' }
})
defineEmits(['move', 'remove', 'replace', 'statement', 'save'])

const selectedCount = computed(() => props.slots.filter((slot) => slot.positionId).length)
const statusLabel = computed(() => ({
  DRAFT: '待提交', SUBMITTED: '已提交', LOCKED: '已锁定', NEEDS_REVISION: '可调整', CONFIRMED: '已落岗'
}[props.group.status] || props.group.status || '待加载'))

function chineseNo(value) {
  return ({ 1: '一', 2: '二', 3: '三' })[Number(value)] || value
}
</script>

<style scoped>
.volunteer-board { width:100%; box-sizing:border-box; border:1px solid #dfe8f8; border-radius:10px; background:#fff; overflow:hidden; }
.board-heading { display:flex; align-items:center; justify-content:space-between; gap:8px; padding:14px; border-bottom:1px solid #eef0f3; background:#f8fbff; }
.board-heading div { display:flex; align-items:baseline; gap:6px; }
.board-heading strong { color:#1a1a1a; font-size:15px; }
.board-heading div span { color:#2f6bff; font-size:12px; font-weight:700; }
.group-status { padding:3px 6px; border-radius:4px; background:#eef4ff; color:#34527a; font-size:11px; }
.board-alert { margin:10px 10px 0; padding:9px 10px; border-radius:7px; background:#fff2f0; color:#a8071a; font-size:12px; }
.replace-tip { display:grid; gap:3px; margin:10px 10px 0; padding:9px 10px; border-radius:7px; background:#fff7e6; color:#874d00; font-size:11px; }
.slots { display:grid; gap:8px; padding:10px; }
.volunteer-slot { padding:10px; border:1px solid #eef0f3; border-radius:8px; background:#fff; }
.volunteer-slot.is-empty { border-style:dashed; background:#fcfcfc; }
.slot-title-row { display:flex; align-items:center; justify-content:space-between; gap:6px; }
.slot-title-row > strong { color:#555; font-size:12px; }
.slot-actions { display:flex; gap:4px; }
.slot-actions button,.replace-button { border:0; border-radius:5px; padding:4px 6px; background:#f0f5ff; color:#2f6bff; cursor:pointer; font-size:10px; }
.slot-actions button:disabled,.replace-button:disabled { opacity:.45; cursor:not-allowed; }
.slot-actions .danger { background:#fff2f0; color:#cf1322; }
.slot-position { display:grid; gap:3px; margin-top:8px; }
.slot-position strong { color:#1a1a1a; font-size:13px; line-height:1.4; }
.slot-position span { color:#777; font-size:11px; }
.statement-field { display:grid; gap:5px; margin-top:9px; }
.statement-field span { color:#666; font-size:11px; }
.statement-field textarea { width:100%; box-sizing:border-box; border:1px solid #d9d9d9; border-radius:6px; padding:7px; resize:vertical; font:inherit; font-size:11px; line-height:1.5; }
.empty-slot { padding:14px 0 8px; color:#aaa; font-size:11px; text-align:center; }
.replace-button { width:100%; margin-top:8px; padding:6px; }
.board-foot { padding:11px 12px 12px; border-top:1px solid #eef0f3; }
.board-foot p { margin:0 0 8px; color:#8c8c8c; font-size:10px; line-height:1.5; }
.save-button { width:100%; height:34px; border:0; border-radius:6px; background:#2f6bff; color:#fff; cursor:pointer; font-weight:600; }
.save-button:disabled { background:#d9d9d9; cursor:not-allowed; }
</style>
