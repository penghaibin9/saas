<template>
  <section class="share-preview">
    <div class="preview-heading">
      <div>
        <p class="eyebrow">提交前必看</p>
        <h2>企业将看到以下资料</h2>
        <p>以下内容来自服务端材料预览。正式投递时会冻结为不可变材料快照。</p>
      </div>
      <span class="policy">隐私策略 {{ preview.consentPolicyVersion || '待加载' }}</span>
    </div>

    <div v-if="loading" class="preview-state">正在生成企业视角材料预览…</div>
    <div v-else-if="error" class="preview-state preview-state--error">
      <span>{{ error }}</span>
      <button type="button" @click="$emit('refresh')">重新加载</button>
    </div>
    <template v-else>
      <div class="field-columns">
        <div class="field-group">
          <div class="group-title"><strong>学校已核验</strong><span>只读</span></div>
          <div v-if="!preview.schoolFields.length" class="empty">当前预览未返回学校字段明细。</div>
          <div v-for="field in preview.schoolFields" :key="field.key" class="preview-field">
            <span>{{ field.label }}</span><strong>{{ field.value || '—' }}</strong>
          </div>
        </div>
        <div class="field-group">
          <div class="group-title"><strong>学生自填</strong><span>按本次快照冻结</span></div>
          <div v-if="!preview.studentFields.length" class="empty">当前预览未返回学生自填字段明细。</div>
          <div v-for="field in preview.studentFields" :key="field.key" class="preview-field">
            <span>{{ field.label }}</span><strong>{{ field.value || '—' }}</strong>
          </div>
        </div>
      </div>

      <div v-if="preview.sharedFields.length" class="shared-list">
        <div class="group-title"><strong>其他共享资料</strong><span>服务端裁剪后字段</span></div>
        <div class="shared-grid">
          <div v-for="field in preview.sharedFields" :key="field.key" class="preview-field">
            <span>{{ field.label }}</span><strong>{{ field.value || '—' }}</strong>
          </div>
        </div>
      </div>

      <div class="contact-policy">
        <div>
          <strong>联系方式共享策略</strong>
          <p>当前预览：{{ preview.maskedContact || '联系方式默认脱敏展示' }}</p>
        </div>
        <select :value="contactSharingMode" @change="$emit('update:contactSharingMode', $event.target.value)">
          <option v-for="option in options" :key="option.value" :value="option.value">{{ option.label }}</option>
        </select>
        <p class="policy-help">{{ selectedOption.help }}</p>
      </div>

      <label class="consent-row">
        <input :checked="confirmed" type="checkbox" @change="$emit('update:confirmed', $event.target.checked)" />
        <span>我已查看企业将收到的资料，并同意按上述联系方式策略共享本次投递材料。</span>
      </label>

      <div class="pdf-panel">
        <div>
          <strong>《岗位实习申请简历》</strong>
          <p>PDF 由服务端材料快照派生；公共 PDF 不包含你投递的其它志愿。</p>
        </div>
        <button type="button" :disabled="pdfBusy || !preview.previewHash" @click="$emit('pdf-preview')">
          {{ pdfBusy ? '生成中…' : '生成 / 预览 PDF' }}
        </button>
      </div>

      <div v-if="pdfUrl" class="pdf-result">
        <a :href="pdfUrl" target="_blank" rel="noopener noreferrer">打开岗位实习申请简历 PDF</a>
      </div>
    </template>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { CONTACT_SHARING_OPTIONS } from '../../modules/internshipRecruitment/materialPreviewModel'

const props = defineProps({
  preview: { type: Object, required: true },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  contactSharingMode: { type: String, default: 'AFTER_INTERVIEW' },
  confirmed: { type: Boolean, default: false },
  pdfBusy: { type: Boolean, default: false },
  pdfUrl: { type: String, default: '' }
})
defineEmits(['refresh', 'pdf-preview', 'update:contactSharingMode', 'update:confirmed'])
const options = CONTACT_SHARING_OPTIONS
const selectedOption = computed(() => options.find((item) => item.value === props.contactSharingMode) || options[1])
</script>

<style scoped>
.share-preview { border:1px solid #dfe8f8; border-radius:12px; background:#fff; overflow:hidden; }
.preview-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:18px; padding:20px; border-bottom:1px solid #eef0f3; background:#f8fbff; }
.eyebrow { margin:0 0 3px; color:#2f6bff; font-size:11px; font-weight:700; }
.preview-heading h2 { margin:0; color:#1a1a1a; font-size:18px; }
.preview-heading p:last-child { margin:5px 0 0; color:#66758a; font-size:12px; }
.policy { flex-shrink:0; padding:4px 8px; border-radius:5px; background:#eef4ff; color:#34527a; font-size:11px; }
.preview-state { display:flex; align-items:center; justify-content:center; gap:10px; min-height:160px; padding:20px; color:#8c8c8c; }
.preview-state--error { color:#a8071a; }
.preview-state button { border:0; border-radius:6px; padding:7px 12px; background:#2f6bff; color:#fff; cursor:pointer; }
.field-columns { display:grid; grid-template-columns:1fr 1fr; gap:12px; padding:16px 20px; }
.field-group,.shared-list { min-width:0; padding:12px; border:1px solid #f0f0f0; border-radius:9px; }
.group-title { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px; }
.group-title strong { color:#333; font-size:13px; }
.group-title span { color:#8c8c8c; font-size:11px; }
.preview-field { display:flex; align-items:flex-start; justify-content:space-between; gap:12px; padding:7px 0; border-top:1px solid #f6f6f6; }
.preview-field span { color:#777; font-size:12px; }
.preview-field strong { color:#333; font-size:12px; text-align:right; overflow-wrap:anywhere; }
.empty { color:#aaa; font-size:12px; }
.shared-list { margin:0 20px 16px; }
.shared-grid { display:grid; grid-template-columns:1fr 1fr; gap:0 16px; }
.contact-policy { display:grid; grid-template-columns:1fr 220px; gap:8px 16px; margin:0 20px 16px; padding:14px; border-radius:9px; background:#fafafa; }
.contact-policy strong { color:#333; font-size:13px; }
.contact-policy p { margin:4px 0 0; color:#777; font-size:12px; }
.contact-policy select { height:36px; border:1px solid #d9d9d9; border-radius:7px; padding:0 9px; background:#fff; }
.policy-help { grid-column:1/-1; }
.consent-row { display:flex; align-items:flex-start; gap:8px; margin:0 20px 16px; padding:12px; border:1px solid #adc6ff; border-radius:8px; background:#f0f5ff; color:#34527a; font-size:12px; line-height:1.55; }
.consent-row input { margin-top:2px; }
.pdf-panel { display:flex; align-items:center; justify-content:space-between; gap:14px; padding:16px 20px; border-top:1px solid #eef0f3; }
.pdf-panel strong { color:#333; font-size:14px; }
.pdf-panel p { margin:4px 0 0; color:#8c8c8c; font-size:12px; }
.pdf-panel button { flex-shrink:0; border:0; border-radius:7px; padding:9px 14px; background:#2f6bff; color:#fff; cursor:pointer; }
.pdf-panel button:disabled { background:#d9d9d9; cursor:not-allowed; }
.pdf-result { padding:0 20px 16px; }
.pdf-result a { color:#2f6bff; font-size:13px; }
@media (max-width:899px) {
  .preview-heading { flex-direction:column; padding:14px; }
  .field-columns,.shared-grid { grid-template-columns:1fr; }
  .field-columns { padding:12px; }
  .shared-list,.contact-policy,.consent-row { margin-left:12px; margin-right:12px; }
  .contact-policy { grid-template-columns:1fr; }
  .policy-help { grid-column:auto; }
  .pdf-panel { align-items:flex-start; flex-direction:column; padding:14px; }
  .pdf-panel button { width:100%; }
}
</style>
