<template>
  <ModulePageShell
    title="通知发布"
    subtitle="本班/本院范围发布；全校重要与紧急消息将进入审核"
    :role-name="roleName"
    :data-scope-name="scopeName"
  >
    <ErrorState v-if="error" :description="error" @retry="error = ''" />
    <p v-if="readonlyTenant" class="mc-warn mc-readonly">
      {{ readonlyReason || '当前学校为正式演示只读环境，不能真正发布。请用沙箱账号 admin2（密码 123456，学校编码 sandbox-school）体验发布与发布记录。' }}
    </p>

    <div class="mc-compose">
      <ol class="mc-steps">
        <li :class="{ 'is-on': step === 1 }">1 内容</li>
        <li :class="{ 'is-on': step === 2 }">2 范围</li>
        <li :class="{ 'is-on': step === 3 }">3 确认发布</li>
      </ol>

      <section v-show="step === 1" class="mc-card">
        <label class="mc-field">
          <span>消息类型</span>
          <select v-model="form.category">
            <option value="ANNOUNCEMENT">公告</option>
            <option value="BUSINESS">业务通知</option>
            <option value="REMINDER">提醒</option>
            <option value="EMERGENCY">紧急消息</option>
          </select>
        </label>
        <label class="mc-field">
          <span>标题（4–100 字）</span>
          <input v-model="form.title" maxlength="100" placeholder="请输入标题" @input="scheduleAutosave" />
        </label>
        <label class="mc-field">
          <span>正文</span>
          <textarea v-model="form.contentPlain" rows="8" placeholder="正文将按白名单清洗；勿粘贴脚本" @input="scheduleAutosave" />
        </label>
        <label class="mc-check">
          <input v-model="form.requireAck" type="checkbox" />
          要求接收人确认回执
        </label>
        <label class="mc-field">
          <span>消息有效期（可选）</span>
          <input v-model="form.expireAt" type="datetime-local" />
        </label>
        <label v-if="form.requireAck || form.category === 'EMERGENCY'" class="mc-field">
          <span>确认截止时间（催办用）</span>
          <input v-model="form.ackDeadlineAt" type="datetime-local" />
        </label>
        <label class="mc-field">
          <span>业务深链（可选，仅白名单）</span>
          <select v-model="form.actionKey" @change="onActionKeyChange">
            <option value="">无深链</option>
            <option v-for="a in actionKeys" :key="a.actionKey" :value="a.actionKey">
              {{ a.label || a.actionKey }}
            </option>
          </select>
        </label>
        <label v-if="form.actionKey && requiredParamHints.length" class="mc-field">
          <span>深链参数（JSON，必填：{{ requiredParamHints.join(', ') }}）</span>
          <input v-model="form.actionParamsText" placeholder='例如 {"leaveId": 123}' @input="scheduleAutosave" />
        </label>
        <p v-if="autosaveHint" class="mc-muted">{{ autosaveHint }}</p>
        <div class="mc-actions">
          <button type="button" class="mc-btn mc-btn--primary" @click="goStep2">下一步</button>
        </div>
      </section>

      <section v-show="step === 2" class="mc-card">
        <p class="mc-hint">按权限选择本班、本院或全校范围；可见选项由后端数据范围收敛。</p>
        <AudienceSelector
          v-model="audiences"
          :permission-patterns="permissionPatterns"
          @change="onAudienceChange"
        />
        <div class="mc-actions">
          <button type="button" class="mc-btn" @click="step = 1">上一步</button>
          <button type="button" class="mc-btn mc-btn--primary" :disabled="previewing" @click="doPreview">
            {{ previewing ? '预览中…' : '预览人数' }}
          </button>
        </div>
        <div v-if="preview" class="mc-preview">
          <div>预计接收：<strong>{{ preview.recipientCount }}</strong> 人</div>
          <div v-for="e in preview.excluded || []" :key="e.reasonCode" class="mc-muted">
            已排除 {{ excludeLabel(e.reasonCode) }}：{{ e.count }}
          </div>
          <p v-if="!(preview.recipientCount > 0)" class="mc-warn">
            接收人为 0，无法发布。常见原因：所选班级/学院学籍尚未开通登录账号（学号需与账号一致）。
          </p>
        </div>
        <div v-if="preview" class="mc-actions">
          <button
            type="button"
            class="mc-btn mc-btn--primary"
            :disabled="!(preview.recipientCount > 0)"
            @click="step = 3"
          >下一步</button>
        </div>
      </section>

      <section v-show="step === 3" class="mc-card">
        <h3>{{ form.title }}</h3>
        <p class="mc-muted">
          类型 {{ form.category }} · 预计 {{ preview && preview.recipientCount }} 人
          <template v-if="needsReviewHint"> · 将进入审核</template>
        </p>
        <pre class="mc-body">{{ form.contentPlain }}</pre>
        <label class="mc-check">
          <input v-model="form.scheduleEnabled" type="checkbox" />
          定时发布
        </label>
        <label v-if="form.scheduleEnabled" class="mc-field">
          <span>计划发布时间</span>
          <input v-model="form.scheduledAt" type="datetime-local" />
        </label>
        <p class="mc-warn">
          确认后将向约 {{ preview && preview.recipientCount }} 人投递；全校/紧急将先审核。
          大名单将异步分批投递，请勿重复点击。
        </p>
        <div class="mc-actions">
          <button type="button" class="mc-btn" @click="step = 2">上一步</button>
          <button
            type="button"
            class="mc-btn mc-btn--primary"
            :disabled="publishing || readonlyTenant"
            @click="doPublish"
          >
            {{ publishing ? '提交中…' : publishButtonLabel }}
          </button>
        </div>
      </section>
    </div>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ErrorState } from '@/components/business'
import AudienceSelector from '@/modules/messageCenter/components/AudienceSelector.vue'
import {
  createCampaign,
  previewAudience,
  publishCampaign,
  fetchActionKeys
} from '@/modules/messageCenter/api/message-campaign.api'

export default {
  name: 'MessageComposeView',
  components: { ModulePageShell, ErrorState, AudienceSelector },
  props: { ctx: { type: Object, default: null } },
  data() {
    return {
      step: 1,
      form: {
        title: '',
        contentPlain: '',
        category: 'ANNOUNCEMENT',
        requireAck: false,
        scheduleEnabled: false,
        scheduledAt: '',
        expireAt: '',
        ackDeadlineAt: '',
        actionKey: '',
        actionParamsText: ''
      },
      actionKeys: [],
      audiences: [],
      preview: null,
      previewing: false,
      publishing: false,
      error: '',
      draft: null,
      autosaveHint: '',
      _autosaveTimer: null
    }
  },
  created() {
    this.loadActionKeys()
    try {
      const raw = localStorage.getItem('mc-compose-draft')
      if (raw) {
        const saved = JSON.parse(raw)
        if (saved && saved.form) this.form = { ...this.form, ...saved.form }
        if (saved && saved.audiences) this.audiences = saved.audiences
        this.autosaveHint = '已恢复本地草稿'
      }
    } catch { /* ignore */ }
  },
  beforeUnmount() {
    if (this._autosaveTimer) clearTimeout(this._autosaveTimer)
  },
  computed: {
    roleName() {
      return (this.ctx && this.ctx.currentRole && this.ctx.currentRole.roleName) || ''
    },
    scopeName() {
      return (this.ctx && this.ctx.dataScope && this.ctx.dataScope.scopeName) || ''
    },
    permissionPatterns() {
      return (this.ctx && this.ctx.permissionPatterns) || null
    },
    readonlyTenant() {
      return !!(this.ctx && this.ctx.readonlyTenant)
    },
    readonlyReason() {
      return (this.ctx && this.ctx.readonlyReason) || ''
    },
    needsReviewHint() {
      if (this.form.category === 'EMERGENCY') return true
      const types = (this.audiences || []).map((a) => String(a.type || '').toUpperCase())
      return types.some((t) => ['ALL_STUDENT', 'ALL_STAFF', 'ALL_USERS'].includes(t))
    },
    publishButtonLabel() {
      if (this.needsReviewHint) return '提交审核'
      if (this.form.scheduleEnabled) return '预约发布'
      return '确认发布'
    },
    requiredParamHints() {
      const hit = (this.actionKeys || []).find((a) => a.actionKey === this.form.actionKey)
      return (hit && hit.requiredParams) || []
    }
  },
  methods: {
    async loadActionKeys() {
      try {
        const data = await fetchActionKeys()
        this.actionKeys = (data && data.items) || []
      } catch {
        this.actionKeys = []
      }
    },
    onActionKeyChange() {
      this.form.actionParamsText = ''
      this.scheduleAutosave()
    },
    parseActionParams() {
      if (!this.form.actionKey) return undefined
      const raw = (this.form.actionParamsText || '').trim()
      if (!raw) return {}
      try {
        return JSON.parse(raw)
      } catch {
        throw new Error('深链参数必须是合法 JSON')
      }
    },
    scheduleAutosave() {
      if (this._autosaveTimer) clearTimeout(this._autosaveTimer)
      this._autosaveTimer = setTimeout(() => {
        try {
          localStorage.setItem('mc-compose-draft', JSON.stringify({
            form: this.form,
            audiences: this.audiences,
            savedAt: Date.now()
          }))
          this.autosaveHint = '草稿已自动保存'
        } catch {
          this.autosaveHint = ''
        }
      }, 800)
    },
    goStep2() {
      this.error = ''
      if ((this.form.title || '').trim().length < 4) {
        this.error = '标题至少 4 字'
        return
      }
      if (!(this.form.contentPlain || '').trim()) {
        this.error = '正文不能为空'
        return
      }
      this.step = 2
    },
    onAudienceChange() {
      this.preview = null
      this.scheduleAutosave()
    },
    async doPreview() {
      this.error = ''
      if (!(this.audiences || []).length) {
        this.error = '请选择受众范围'
        return
      }
      if ((this.form.title || '').trim().length < 4) {
        this.error = '标题至少 4 字'
        this.step = 1
        return
      }
      if (!(this.form.contentPlain || '').trim()) {
        this.error = '正文不能为空'
        this.step = 1
        return
      }
      this.previewing = true
      try {
        this.preview = await previewAudience({
          audiences: this.audiences,
          recipientTypes: ['STUDENT', 'STAFF']
        })
      } catch (e) {
        this.error = (e && e.message) || '受众预览失败'
        this.preview = null
      } finally {
        this.previewing = false
      }
    },
    excludeLabel(code) {
      const map = {
        ACCOUNT_UNLINKED: '学籍未开通账号',
        STUDENT_STATUS_EXCLUDED: '学籍状态不可发',
        ACCOUNT_DISABLED: '账号已停用'
      }
      return map[code] || code
    },
    async doPublish() {
      if (this.readonlyTenant) {
        this.error = this.readonlyReason || '当前为只读演示环境，无法发布'
        return
      }
      if (!this.preview) {
        this.error = '请先预览受众'
        return
      }
      const n = this.preview.recipientCount || 0
      if (n <= 0) {
        this.error = '接收人为 0，无法发布。请返回上一步重新选择范围并预览。'
        this.step = 2
        return
      }
      if (this.form.scheduleEnabled && !this.form.scheduledAt) {
        this.error = '请填写计划发布时间'
        return
      }
      const ok = window.confirm(
        `确认向约 ${n} 人${this.needsReviewHint ? '提交审核' : '发布'}？\n标题：${this.form.title}\n\n发布后请在「发布记录」查看；「我的消息」只显示别人发给你的通知。`
      )
      if (!ok) return
      this.publishing = true
      this.error = ''
      let draft = null
      try {
        const toDt = (v) => (v ? String(v).replace('T', ' ') + ':00' : undefined)
        let actionParams
        try {
          actionParams = this.parseActionParams()
        } catch (pe) {
          this.error = (pe && pe.message) || '深链参数无效'
          return
        }
        draft = await createCampaign({
          title: this.form.title.trim(),
          contentPlain: this.form.contentPlain.trim(),
          category: this.form.category,
          requireAck: this.form.requireAck || this.form.category === 'EMERGENCY',
          emergency: this.form.category === 'EMERGENCY',
          audiences: this.audiences,
          actionKey: this.form.actionKey || undefined,
          actionParams,
          publishMode: this.form.scheduleEnabled ? 'SCHEDULED' : 'IMMEDIATE',
          scheduledAt: this.form.scheduleEnabled
            ? String(this.form.scheduledAt).replace('T', ' ') + ':00'
            : undefined,
          expireAt: toDt(this.form.expireAt),
          ackDeadlineAt: toDt(this.form.ackDeadlineAt),
          idempotencyKey: `compose-${Date.now()}`
        })
        this.draft = draft
        const result = await publishCampaign(draft.campaignId, {
          previewToken: this.preview.previewToken,
          audienceFingerprint: this.preview.audienceFingerprint,
          version: draft.version
        })
        try { localStorage.removeItem('mc-compose-draft') } catch { /* ignore */ }
        this.$router.push(`/admin/messages/outbox/${result.campaignId || draft.campaignId}`)
      } catch (e) {
        const msg = (e && e.message) || '发布失败'
        // 草稿已入库时仍应在「发布记录」可见；避免用户以为完全没发出去
        if (draft && draft.campaignId) {
          this.error = `${msg}。草稿已保存，正在打开发布记录…`
          try { localStorage.removeItem('mc-compose-draft') } catch { /* ignore */ }
          setTimeout(() => {
            this.$router.push(`/admin/messages/outbox/${draft.campaignId}`).catch(() => {
              this.$router.push('/admin/messages/outbox')
            })
          }, 600)
        } else {
          this.error = msg
        }
      } finally {
        this.publishing = false
      }
    }
  }
}
</script>

<style scoped>
.mc-steps {
  display: flex; gap: var(--space-4); list-style: none; padding: 0; margin: 0 0 var(--space-4);
  font-size: var(--font-size-sm); color: var(--text-tertiary);
}
.mc-steps .is-on { color: var(--primary-700); font-weight: 600; }
.mc-card {
  border: 1px solid var(--border-base); border-radius: var(--radius-md);
  background: var(--bg-card); padding: var(--space-5);
  max-width: 720px;
}
.mc-field { display: flex; flex-direction: column; gap: 6px; margin-bottom: var(--space-3); }
.mc-field span { font-size: var(--font-size-sm); color: var(--text-secondary); }
.mc-field input, .mc-field textarea, .mc-field select {
  border: 1px solid var(--border-base); border-radius: var(--radius-sm);
  padding: 8px 10px; font: inherit; background: var(--bg-card);
}
.mc-check { display: flex; align-items: center; gap: 8px; margin: var(--space-3) 0; font-size: var(--font-size-sm); }
.mc-actions { display: flex; gap: var(--space-2); margin-top: var(--space-4); }
.mc-btn {
  height: 32px; padding: 0 14px; border-radius: var(--radius-sm);
  border: 1px solid var(--border-base); background: var(--bg-card); cursor: pointer;
}
.mc-btn--primary { background: var(--primary-500); border-color: var(--primary-500); color: #fff; }
.mc-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.mc-hint, .mc-muted { font-size: var(--font-size-sm); color: var(--text-tertiary); }
.mc-warn {
  margin-top: var(--space-3); padding: var(--space-3); border-radius: var(--radius-sm);
  background: #fff7ed; color: #9a3412; font-size: var(--font-size-sm);
}
.mc-preview { margin-top: var(--space-3); padding: var(--space-3); background: var(--bg-subtle, #f8fafc); border-radius: var(--radius-sm); }
.mc-body { white-space: pre-wrap; font-family: inherit; background: var(--bg-subtle, #f8fafc); padding: var(--space-3); border-radius: var(--radius-sm); }
</style>
