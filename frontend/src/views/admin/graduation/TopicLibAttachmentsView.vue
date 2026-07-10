<template>
  <GraduationFormPageShell
    layout="inline"
    :ctx="ctx"
    title="题目附件管理"
    :subtitle="topic ? `${topic.title} · 已挂 ${attachments.length} 个附件` : ''"
    :back-to="backTo"
  >
    <LoadingState v-if="loading" />
    <ErrorState v-else-if="error" :description="error" @retry="load" />
    <div v-else-if="topic">
      <div v-for="(a, idx) in attachments" :key="idx" class="att-row">
        <input v-model.trim="a.name" class="ie-in" placeholder="附件名称" />
        <input v-model.trim="a.url" class="ie-in" placeholder="文件地址 / 存储路径" />
        <button type="button" class="mp-link" @click="removeAttachment(idx)">删除</button>
      </div>
      <button type="button" class="mp-btn" style="margin-top: var(--space-3)" @click="addAttachment">＋ 添加附件</button>
      <p v-if="formError" class="ie-err">{{ formError }}</p>
    </div>
    <template v-if="topic" #footer>
      <button type="button" class="mp-btn" @click="$router.push(backTo)">取消</button>
      <button type="button" class="mp-btn mp-btn--primary" :disabled="submitting" @click="submit">保存</button>
    </template>
  </GraduationFormPageShell>
</template>

<script>
import GraduationFormPageShell from './_shared/GraduationFormPageShell.vue'
import { LoadingState, ErrorState } from '@/components/business'
import { gdTopicApi } from '@/modules/graduation/api/graduation-topic.api'
import { toast } from '@/utils/toast'

export default {
  name: 'TopicLibAttachmentsView',
  components: { GraduationFormPageShell, LoadingState, ErrorState },
  props: { ctx: { type: Object, required: true } },
  data() {
    return { loading: true, error: '', topic: null, attachments: [], formError: '', submitting: false }
  },
  computed: {
    backTo() {
      const panel = this.$route.query.returnPanel || 'attachments'
      return `/admin/graduation/topic-lib?panel=${panel}`
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const d = await gdTopicApi.getTopicDetail(this.$route.params.id)
      if (d.code !== 0) { this.error = d.message; this.loading = false; return }
      this.topic = d.data
      this.attachments = (d.data.attachments || []).map((a) => ({ ...a }))
      if (!this.attachments.length) this.addAttachment()
      this.loading = false
    },
    addAttachment() {
      this.attachments.push({ name: '', url: '', size: 0, uploadedAt: new Date().toISOString() })
    },
    removeAttachment(idx) {
      this.attachments.splice(idx, 1)
    },
    async submit() {
      const valid = this.attachments.filter((a) => (a.name || '').trim() && (a.url || '').trim())
      if (!valid.length) { this.formError = '至少填写一个有效附件（名称+地址）'; return }
      this.submitting = true
      const r = await gdTopicApi.updateAttachments(this.topic.id, valid)
      this.submitting = false
      if (r.code !== 0) { this.formError = r.message; return }
      toast.success('附件已保存')
      this.$router.push(this.backTo)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.att-row { display: grid; grid-template-columns: 1fr 1fr auto; gap: var(--space-2); margin-bottom: var(--space-2); align-items: center; }
.mp-btn { padding: 7px 16px; border: 1px solid var(--line, #d9dee8); border-radius: 8px; background: #fff; cursor: pointer; font-size: 13px; }
.mp-btn--primary { background: var(--pri, #2563eb); color: #fff; border-color: var(--pri, #2563eb); }
.mp-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.mp-link { color: var(--pri, #2563eb); background: none; border: none; cursor: pointer; font-size: 13px; }
</style>
