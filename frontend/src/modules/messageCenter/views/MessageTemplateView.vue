<template>
  <ModulePageShell title="消息模板" subtitle="系统业务模板与人工发布模板（可新建/启停）">
    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else class="mc-tpl">
      <div class="mc-toolbar">
        <input v-model="keyword" placeholder="搜索模板编码 / 标题 / 事件码" @keyup.enter="load" />
        <button type="button" class="mc-btn" @click="load">搜索</button>
        <button type="button" class="mc-btn mc-btn--primary" @click="showCreate = !showCreate">新建模板</button>
      </div>
      <div v-if="showCreate" class="mc-create">
        <label>编码 <input v-model="form.templateCode" placeholder="如 HUMAN_ANNOUNCE" /></label>
        <label>标题 <input v-model="form.title" /></label>
        <label>渠道
          <select v-model="form.channel">
            <option value="IN_APP">IN_APP</option>
            <option value="SMS">SMS</option>
            <option value="WECHAT">WECHAT</option>
          </select>
        </label>
        <label>正文 <textarea v-model="form.content" rows="3" /></label>
        <button type="button" class="mc-btn mc-btn--primary" :disabled="saving" @click="doCreate">保存</button>
      </div>
      <EmptyState v-if="!items.length" title="暂无模板" description="可新建人工发布模板，或从运行预设安装。" />
      <div v-else class="mc-list">
        <article v-for="t in items" :key="t.templateId + t.channel" class="mc-item">
          <header>
            <strong>{{ t.title || t.templateCode }}</strong>
            <span class="tag">{{ t.kind === 'SYSTEM' ? '系统业务' : '人工/通用' }}</span>
            <span class="tag">{{ t.channel }}</span>
            <span class="tag" :class="t.enabled ? 'ok' : 'off'">{{ t.enabled ? '启用' : '停用' }}</span>
          </header>
          <div class="meta">编码 {{ t.templateCode }} · 事件 {{ t.eventCode || '—' }} · 版本 {{ t.version }}</div>
          <pre class="preview">{{ t.previewSample }}</pre>
          <div class="mc-actions">
            <button type="button" class="mc-btn" @click="toggle(t)">
              {{ t.enabled ? '停用' : '启用' }}
            </button>
          </div>
        </article>
      </div>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, LoadingState, ErrorState, EmptyState } from '@/components/business'
import {
  createMessageTemplate,
  fetchMessageTemplates,
  updateMessageTemplate
} from '@/modules/messageCenter/api/message-campaign.api'

export default {
  name: 'MessageTemplateView',
  components: { ModulePageShell, LoadingState, ErrorState, EmptyState },
  data() {
    return {
      loading: false,
      error: '',
      items: [],
      keyword: '',
      showCreate: false,
      saving: false,
      form: { templateCode: '', title: '', content: '', channel: 'IN_APP' }
    }
  },
  created() { this.load() },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const data = await fetchMessageTemplates({ keyword: this.keyword || undefined, pageSize: 100 })
        this.items = (data && data.items) || []
      } catch (e) {
        this.error = (e && e.message) || '加载模板失败'
      } finally {
        this.loading = false
      }
    },
    async doCreate() {
      this.saving = true
      this.error = ''
      try {
        await createMessageTemplate({ ...this.form, enabled: true })
        this.showCreate = false
        this.form = { templateCode: '', title: '', content: '', channel: 'IN_APP' }
        await this.load()
      } catch (e) {
        this.error = (e && e.message) || '创建失败'
      } finally {
        this.saving = false
      }
    },
    async toggle(t) {
      try {
        await updateMessageTemplate(t.templateId, { enabled: !t.enabled })
        await this.load()
      } catch (e) {
        this.error = (e && e.message) || '更新失败'
      }
    }
  }
}
</script>

<style scoped>
.mc-toolbar { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
.mc-toolbar input {
  flex: 1; max-width: 360px; height: 32px; padding: 0 10px;
  border: 1px solid var(--border-base); border-radius: 6px;
}
.mc-btn { height: 32px; padding: 0 14px; border: 1px solid var(--border-base); border-radius: 6px; background: var(--bg-card); cursor: pointer; }
.mc-btn--primary { background: var(--primary-500); border-color: var(--primary-500); color: #fff; }
.mc-create {
  border: 1px dashed var(--border-base); border-radius: 8px; padding: 12px; margin-bottom: 12px;
  display: grid; gap: 8px;
}
.mc-create label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--text-secondary); }
.mc-create input, .mc-create textarea, .mc-create select {
  border: 1px solid var(--border-base); border-radius: 6px; padding: 8px; font: inherit;
}
.mc-item { border: 1px solid var(--border-base); border-radius: 8px; padding: 14px; margin-bottom: 10px; background: var(--bg-card); }
.mc-item header { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.tag { font-size: 11px; padding: 2px 6px; border-radius: 4px; background: var(--bg-subtle, #f1f5f9); color: var(--text-secondary); }
.tag.ok { background: #dcfce7; color: #166534; }
.tag.off { background: #fee2e2; color: #991b1b; }
.meta { margin-top: 6px; font-size: 12px; color: var(--text-tertiary); }
.preview {
  margin: 10px 0 0; white-space: pre-wrap; font-family: inherit; font-size: 13px;
  background: var(--bg-subtle, #f8fafc); padding: 10px; border-radius: 6px;
}
.mc-actions { margin-top: 8px; }
</style>
