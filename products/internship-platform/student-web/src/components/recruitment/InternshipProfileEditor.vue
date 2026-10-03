<template>
  <div class="profile-editor">
    <section class="profile-summary">
      <div>
        <span class="eyebrow">投递准备度</span>
        <strong>{{ completeness.percent }}%</strong>
        <p>{{ completeness.ready ? '当前实习档案已满足投递要求' : '请先补齐阻塞项，再提交岗位志愿' }}</p>
      </div>
      <div class="progress" aria-label="实习档案完成度"><span :style="{ width: `${completeness.percent}%` }" /></div>
      <ul v-if="completeness.blockers.length" class="blockers">
        <li v-for="item in completeness.blockers" :key="String(item.code || item)">{{ item.message || item.label || item }}</li>
      </ul>
    </section>

    <section class="profile-card">
      <div class="section-heading">
        <div><h2>学校正式信息</h2><p>来自学校学生主档，学生不可修改。</p></div>
        <span class="verified-badge">学校已核验</span>
      </div>
      <div class="school-grid">
        <div v-for="field in schoolFields" :key="field.key"><span>{{ field.label }}</span><strong>{{ profile.school[field.key] || '—' }}</strong></div>
      </div>
    </section>

    <section class="profile-card">
      <div class="section-heading">
        <div><h2>我的实习档案</h2><p>这些内容由你维护，提交志愿时会按授权范围冻结为投递快照。</p></div>
        <span class="self-badge">学生自填</span>
      </div>

      <div class="form-grid">
        <label class="field field--full"><span>自我介绍</span><textarea v-model.trim="draft.selfIntroduction" rows="5" maxlength="1000" placeholder="介绍你的专业方向、学习经历和实习目标" /></label>
        <label class="field field--full"><span>个人优势</span><textarea v-model.trim="draft.strengths" rows="4" maxlength="1000" placeholder="如设备操作、沟通协作、竞赛经历等" /></label>
        <label class="field"><span>技能标签</span><input v-model="skillText" placeholder="用逗号分隔，如 CAD, PLC, 数控编程" /></label>
        <label class="field"><span>可到岗时间</span><AppDatePicker v-model="draft.availableFrom" aria-label="可到岗时间" /></label>
        <label class="field field--full"><span>地点偏好</span><input v-model="locationText" placeholder="用逗号分隔，如 长沙, 株洲" /></label>
      </div>
      <div class="form-actions">
        <button type="button" class="primary" :disabled="busy" @click="save">{{ busy ? '保存中…' : '保存实习档案' }}</button>
      </div>
    </section>

    <section class="profile-card">
      <div class="section-heading">
        <div><h2>项目 / 实践 / 证书 / 获奖 / 作品</h2><p>只维护岗位实习需要的材料，不建立全站人才简历中心。</p></div>
        <span class="self-badge">学生自填</span>
      </div>

      <div class="item-groups">
        <div v-for="type in itemTypes" :key="type.value" class="item-group">
          <h3>{{ type.label }}</h3>
          <div v-if="!itemsByType(type.value).length" class="empty-item">暂无{{ type.label }}</div>
          <div v-for="item in itemsByType(type.value)" :key="item.id" class="profile-item">
            <div>
              <strong>{{ item.title || type.label }}</strong>
              <p v-if="item.description">{{ item.description }}</p>
              <span>{{ [item.issuedBy, item.occurredAt, item.fileName].filter(Boolean).join(' · ') }}</span>
            </div>
            <button type="button" :disabled="busy" @click="$emit('delete-item', item)">删除</button>
          </div>
        </div>
      </div>

      <div class="new-item">
        <select v-model="newItem.type"><option v-for="type in itemTypes" :key="type.value" :value="type.value">{{ type.label }}</option></select>
        <input v-model.trim="newItem.title" placeholder="名称 / 标题" />
        <input v-model.trim="newItem.issuedBy" placeholder="组织 / 发证单位（可选）" />
        <AppDatePicker v-model="newItem.occurredAt" aria-label="发生日期" />
        <textarea v-model.trim="newItem.description" rows="3" placeholder="简要说明你做了什么、掌握了什么" />
        <button type="button" class="secondary" :disabled="busy || !newItem.title" @click="addItem">添加</button>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import AppDatePicker from '../AppDatePicker.vue'
import { PROFILE_ITEM_TYPES, buildInternshipProfileUpdate } from '../../modules/internshipRecruitment/profileModel'

const props = defineProps({
  profile: { type: Object, required: true },
  completeness: { type: Object, required: true },
  items: { type: Array, default: () => [] },
  busy: { type: Boolean, default: false }
})
const emit = defineEmits(['save', 'add-item', 'delete-item'])
const itemTypes = PROFILE_ITEM_TYPES
const schoolFields = [
  { key: 'name', label: '姓名' }, { key: 'studentNo', label: '学号' }, { key: 'college', label: '学院' },
  { key: 'major', label: '专业' }, { key: 'grade', label: '年级' }, { key: 'className', label: '班级' }
]
const draft = reactive({ ...props.profile })
const skillText = ref((props.profile.skillTags || []).join(', '))
const locationText = ref((props.profile.locationPreferences || []).join(', '))
const newItem = reactive({ type: 'PROJECT', title: '', description: '', issuedBy: '', occurredAt: '' })

watch(() => props.profile, (value) => {
  Object.assign(draft, value || {})
  skillText.value = (value?.skillTags || []).join(', ')
  locationText.value = (value?.locationPreferences || []).join(', ')
}, { deep: true })

const normalizedSkills = computed(() => skillText.value.split(/[,，]/).map((item) => item.trim()).filter(Boolean))
const normalizedLocations = computed(() => locationText.value.split(/[,，]/).map((item) => item.trim()).filter(Boolean))

function itemsByType(type) {
  return props.items.filter((item) => item.type === type)
}
function save() {
  emit('save', buildInternshipProfileUpdate({
    ...draft,
    skillTags: normalizedSkills.value,
    locationPreferences: normalizedLocations.value
  }))
}
function addItem() {
  if (!newItem.title) return
  emit('add-item', { ...newItem })
  Object.assign(newItem, { type: newItem.type, title: '', description: '', issuedBy: '', occurredAt: '' })
}
</script>

<style scoped>
.profile-editor { display:grid; gap:14px; }
.profile-summary,.profile-card { border:1px solid #eef0f3; border-radius:12px; background:#fff; }
.profile-summary { padding:18px 20px; }
.profile-summary .eyebrow { display:block; color:#8c8c8c; font-size:12px; }
.profile-summary strong { display:block; margin-top:3px; color:#1a1a1a; font-size:28px; }
.profile-summary p { margin:4px 0 0; color:#666; font-size:13px; }
.progress { height:7px; margin-top:12px; border-radius:999px; background:#eef1f5; overflow:hidden; }
.progress span { display:block; height:100%; border-radius:inherit; background:#2f6bff; }
.blockers { margin:12px 0 0; padding:10px 12px 10px 28px; border-radius:8px; background:#fff7e6; color:#874d00; font-size:12px; }
.profile-card { padding:20px; }
.section-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:16px; }
.section-heading h2 { margin:0; color:#1a1a1a; font-size:17px; }
.section-heading p { margin:5px 0 0; color:#8c8c8c; font-size:12px; }
.verified-badge,.self-badge { flex-shrink:0; padding:3px 7px; border-radius:4px; font-size:11px; }
.verified-badge { border:1px solid #adc6ff; color:#2f6bff; background:#f0f5ff; }
.self-badge { border:1px solid #d9d9d9; color:#666; background:#fafafa; }
.school-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }
.school-grid div { padding:11px 12px; border-radius:8px; background:#fafafa; }
.school-grid span { display:block; color:#8c8c8c; font-size:11px; }
.school-grid strong { display:block; margin-top:4px; color:#333; font-size:13px; }
.form-grid { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.field { display:grid; gap:6px; }
.field--full { grid-column:1/-1; }
.field span { color:#555; font-size:12px; font-weight:600; }
.field input,.field textarea,.new-item input,.new-item textarea,.new-item select { width:100%; box-sizing:border-box; border:1px solid #d9d9d9; border-radius:7px; padding:9px 10px; background:#fff; color:#333; font:inherit; font-size:13px; }
.field input:focus,.field textarea:focus,.new-item input:focus,.new-item textarea:focus,.new-item select:focus { outline:none; border-color:#2f6bff; box-shadow:0 0 0 2px rgba(47,107,255,.08); }
.form-actions { display:flex; justify-content:flex-end; margin-top:14px; }
.primary,.secondary { border:0; border-radius:7px; padding:9px 15px; cursor:pointer; }
.primary { background:#2f6bff; color:#fff; }
.secondary { background:#eef4ff; color:#2f6bff; }
.primary:disabled,.secondary:disabled { opacity:.55; cursor:not-allowed; }
.item-groups { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.item-group { min-width:0; padding:12px; border:1px solid #f0f0f0; border-radius:9px; }
.item-group h3 { margin:0 0 9px; color:#333; font-size:13px; }
.empty-item { color:#b0b0b0; font-size:12px; }
.profile-item { display:flex; align-items:flex-start; justify-content:space-between; gap:10px; padding:9px 0; border-top:1px solid #f3f3f3; }
.profile-item:first-of-type { border-top:0; }
.profile-item strong { color:#333; font-size:13px; }
.profile-item p { margin:4px 0; color:#666; font-size:12px; line-height:1.5; }
.profile-item span { color:#999; font-size:11px; }
.profile-item button { border:0; background:transparent; color:#d4380d; cursor:pointer; font-size:12px; }
.new-item { display:grid; grid-template-columns:160px 1fr 1fr 160px; gap:10px; margin-top:14px; padding-top:14px; border-top:1px solid #f0f0f0; }
.new-item textarea { grid-column:1/-2; }
.new-item .secondary { align-self:end; }
@media (max-width:899px) {
  .profile-card,.profile-summary { padding:14px; }
  .school-grid,.form-grid,.item-groups { grid-template-columns:1fr; }
  .field--full { grid-column:auto; }
  .new-item { grid-template-columns:1fr; }
  .new-item textarea { grid-column:auto; }
}
</style>
