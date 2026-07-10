<template>
  <ModulePageShell
    :title="detail ? `${detail.name} · 模板详情` : '协议模板详情'"
    :subtitle="detail ? [detail.category || '未分类', detail.version].filter(Boolean).join(' · ') : ''"
    :role-name="roleName"
    :data-scope-name="dataScopeName"
    watermark-purpose="实习协议模板管理"
  >
    <template #actions>
      <AppButton variant="ghost" @click="goBack">← 返回模板库</AppButton>
    </template>

    <ErrorState v-if="error" :description="error" @retry="load" />
    <LoadingState v-else-if="loading" />
    <div v-else-if="detail" class="mp-grid-2">
      <!-- 左：模板信息 + 模板正文 + 变量清单 -->
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head">
            <span class="mp-card__title">模板信息<span v-if="detail.isDefault" class="atd-default">默认</span></span>
            <AppStatusTag :type="detail.statusTone" dot>{{ detail.statusLabel }}</AppStatusTag>
          </div>
          <div class="mp-card__body">
            <AppDescriptionList :items="infoItems" :columns="2" />
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">模板正文</span></div>
          <div class="mp-card__body">
            <pre class="atd-body">{{ detail.body || '（空）' }}</pre>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">变量清单</span></div>
          <div class="mp-card__body">
            <div v-if="detail.variables && detail.variables.length" class="atd-vars">
              <span v-for="v in detail.variables" :key="v.key" class="atd-var-tag">{{ v.label }} <code v-text="braced(v.key)"></code></span>
            </div>
            <p v-else class="mp-note" style="margin: 0">未设置变量</p>
          </div>
        </section>
      </div>

      <!-- 右：状态与操作 + 操作留痕 -->
      <div class="mp-stack">
        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">状态与操作</span></div>
          <div class="mp-card__body">
            <div class="atd-status">
              <span class="atd-status__lbl">当前状态</span>
              <AppStatusTag :type="detail.statusTone" dot>{{ detail.statusLabel }}</AppStatusTag>
            </div>
            <div class="atd-actions">
              <AppButton v-if="detail.status !== 'ARCHIVED'" variant="secondary" @click="goEdit">编辑</AppButton>
              <AppButton v-if="['DRAFT', 'DISABLED'].includes(detail.status)" variant="primary" @click="askStatus('ENABLE')">启用</AppButton>
              <AppButton v-else-if="detail.status === 'ENABLED'" variant="secondary" @click="askStatus('DISABLE')">停用</AppButton>
              <AppButton v-if="detail.status === 'ENABLED' && !detail.isDefault" variant="secondary" @click="askDefault(true)">设默认</AppButton>
              <AppButton v-if="detail.isDefault" variant="ghost" @click="askDefault(false)">取消默认</AppButton>
              <AppButton v-if="detail.status !== 'ARCHIVED'" variant="danger" @click="askStatus('ARCHIVE')">归档</AppButton>
            </div>
            <p v-if="detail.status === 'ARCHIVED'" class="mp-note" style="margin: var(--space-2) 0 0">
              模板已归档，仅可查看，不可再编辑或启用。
            </p>
          </div>
        </section>

        <section class="mp-card">
          <div class="mp-card__head"><span class="mp-card__title">操作留痕</span></div>
          <div class="mp-card__body">
            <AppAuditTrail :records="auditRecords" :show-ip="false" compact empty-text="暂无记录" />
          </div>
        </section>
      </div>
    </div>

    <!-- 启用 / 停用 / 归档 / 设默认 二次确认（沿用列表页文案与 reason 规则） -->
    <AppConfirmDialog
      v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message"
      :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason"
      :reason-label="confirm.reasonLabel" :submitting="submitting" @confirm="onConfirm"
    />
  </ModulePageShell>
</template>

<script>
/**
 * 实习协议模板独立详情页（/admin/internship/agreement-templates/:id，路由由主流程挂载）。
 * 原列表页详情抽屉收口至此：模板信息 + 模板正文 + 变量清单 + 状态动作（启用/停用/归档/设默认）
 * + 编辑入口（非归档态）+ 审计留痕。状态流转走真实 agreementTemplateApi，越权与非法状态由后端拦截。
 */
import { ModulePageShell, LoadingState, ErrorState } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppStatusTag, AppConfirmDialog, AppAuditTrail, AppDescriptionList } from '@/components/common'
import { agreementTemplateApi } from '@/modules/internship/api/agreement-template.api'
import { internshipApi } from '@/modules/internship/api/internship.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AgreementTemplateDetailView',
  components: {
    ModulePageShell, LoadingState, ErrorState, AppButton,
    AppStatusTag, AppConfirmDialog, AppAuditTrail, AppDescriptionList
  },
  data() {
    return {
      ctx: null,
      loading: true,
      error: '',
      detail: null,
      submitting: false,
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: null }
    }
  },
  computed: {
    roleName() {
      return this.ctx?.currentRole?.roleName || ''
    },
    dataScopeName() {
      return this.ctx?.dataScope?.name || ''
    },
    infoItems() {
      const d = this.detail
      if (!d) return []
      return [
        { label: '协议类型', value: d.category || '未分类' },
        { label: '版本号', value: d.version || '—' },
        { label: '适用范围', value: d.scopeSummary || '—' },
        { label: '备注', value: d.remark || '—' }
      ]
    },
    auditRecords() {
      return (this.detail?.auditTrail || []).map((t, i) => ({
        id: i, action: t.action, actor: t.operator, at: t.occurredAt
      }))
    }
  },
  watch: {
    '$route.params.id'(id, oldId) {
      if (!id || id === oldId) return
      this.detail = null
      this.load()
    }
  },
  created() {
    internshipApi.getContext().then((res) => {
      if (res.code === 0) this.ctx = res.data
    })
    this.load()
  },
  methods: {
    braced(key) {
      return '{' + '{' + key + '}' + '}'
    },
    goBack() {
      // 从列表进入时走历史返回（保留筛选/页码）；深链直入时兜底到模板库列表
      const back = this.$router.options.history.state && this.$router.options.history.state.back
      if (typeof back === 'string' && back.startsWith('/admin/internship/agreement-templates')) this.$router.back()
      else this.$router.push('/admin/internship/agreement-templates')
    },
    goEdit() {
      this.$router.push(`/admin/internship/agreement-templates/${this.detail.id}/edit`)
    },
    async load() {
      this.loading = true
      this.error = ''
      const id = this.$route.params.id
      const res = await agreementTemplateApi.getTemplateDetail(id)
      if (id !== this.$route.params.id) return
      this.loading = false
      if (res.code !== 0) {
        this.error = res.message || '模板不存在或无权查看'
        return
      }
      this.detail = res.data
    },
    askStatus(action) {
      const map = {
        ENABLE: { t: '启用模板', c: '确认启用', type: 'primary', reason: false },
        DISABLE: { t: '停用模板', c: '确认停用', type: 'warning', reason: false },
        ARCHIVE: { t: '归档模板', c: '确认归档', type: 'danger', reason: true }
      }
      const m = map[action]
      this.confirm = { visible: true, title: m.t, message: `确认对「${this.detail.name}」执行「${m.t}」？${action === 'ARCHIVE' ? '（归档后不可编辑、不可再启用）' : ''}`, type: m.type, confirmText: m.c, requireReason: m.reason, reasonLabel: '原因', action: 'STATUS_' + action }
    },
    askDefault(on) {
      this.confirm = { visible: true, title: on ? '设为默认模板' : '取消默认', message: on ? `确认将「${this.detail.name}」设为该类型默认协议模板？（同类型原默认会被替换）` : `确认取消「${this.detail.name}」的默认标记？`, type: 'primary', confirmText: '确认', requireReason: false, reasonLabel: '原因', action: on ? 'DEFAULT_ON' : 'DEFAULT_OFF' }
    },
    async onConfirm({ reason } = {}) {
      const { action } = this.confirm
      const id = this.detail && this.detail.id
      if (!id) return
      this.submitting = true
      try {
        let res
        if (action.startsWith('STATUS_')) res = await agreementTemplateApi.setStatus(id, { action: action.slice(7), reason: reason || '' })
        else if (action === 'DEFAULT_ON') res = await agreementTemplateApi.setDefault(id, true)
        else if (action === 'DEFAULT_OFF') res = await agreementTemplateApi.setDefault(id, false)
        if (res && res.code === 0) {
          toast.success('已更新并写入留痕')
          this.confirm.visible = false
          await this.load()
        } else if (res) {
          toast.error(res.message)
        }
      } finally {
        this.submitting = false
      }
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.atd-default {
  margin-left: var(--space-2);
  font-size: 11px;
  font-weight: normal;
  padding: 1px 6px;
  border-radius: 6px;
  background: var(--success-50, #ecfdf5);
  color: var(--success, #16a34a);
}
.atd-body {
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-subtle, #f8fafc);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 12px;
  font-size: 12.5px;
  line-height: 1.8;
  max-height: 480px;
  overflow: auto;
  margin: 0;
}
.atd-vars {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.atd-var-tag {
  display: inline-block;
  font-size: 12px;
  padding: 2px 8px;
  border: 1px solid var(--line, #d9dee8);
  border-radius: 8px;
}
.atd-var-tag code {
  background: var(--bg-subtle, #f1f5f9);
  padding: 0 4px;
  border-radius: 4px;
}
.atd-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: var(--space-3);
  margin-bottom: var(--space-3);
  border-bottom: 1px dashed var(--border-light);
}
.atd-status__lbl {
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.atd-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}
</style>
