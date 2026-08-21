<template>
  <section class="tenant-profile">
    <div class="tenant-profile__head">
      <div>
        <strong>学校基础资料维护</strong>
        <p>联系人、地区、学校类型属于基础资料；运行环境只读，不能从这里把 production 改成 demo。</p>
      </div>
      <AppButton v-if="tenant?.canEdit && !editing" variant="secondary" @click="editing = true">编辑基础资料</AppButton>
      <span v-else-if="tenant && !tenant.canEdit" class="tenant-profile__readonly">当前职责仅可查看</span>
    </div>

    <div v-if="loading" class="tenant-profile__muted">正在读取学校基础资料…</div>
    <div v-else-if="error" class="tenant-profile__error">{{ error }}</div>
    <template v-else-if="tenant">
      <div v-if="!editing" class="tenant-profile__summary">
        <span><b>学校类型</b>{{ tenant.schoolType || '—' }}</span>
        <span><b>地区</b>{{ [tenant.province, tenant.city].filter(Boolean).join(' / ') || '—' }}</span>
        <span><b>联系人</b>{{ tenant.contactName || '—' }}</span>
        <span><b>联系电话</b>{{ tenant.contactPhone || '—' }}</span>
        <span><b>微信</b>{{ tenant.contactWechat || '—' }}</span>
        <span><b>运行环境（只读）</b>{{ tenant.environment || 'production' }}</span>
      </div>

      <div v-else class="tenant-profile__form">
        <label><span>学校类型</span><input v-model.trim="form.schoolType" maxlength="50" /></label>
        <label><span>省份</span><input v-model.trim="form.province" maxlength="64" /></label>
        <label><span>城市</span><input v-model.trim="form.city" maxlength="64" /></label>
        <label><span>联系人</span><input v-model.trim="form.contactName" maxlength="64" /></label>
        <label><span>联系电话</span><input v-model.trim="form.contactPhone" inputmode="tel" maxlength="32" /></label>
        <label><span>联系微信</span><input v-model.trim="form.contactWechat" maxlength="64" /></label>
        <label><span>运行环境</span><input :value="tenant.environment || 'production'" disabled /></label>
        <label class="tenant-profile__wide"><span>备注</span><textarea v-model.trim="form.remark" rows="2" maxlength="1000" /></label>
        <label class="tenant-profile__wide"><span>变更原因（必填）</span><input v-model.trim="reason" maxlength="200" placeholder="至少 5 个字，用于审计追溯" /></label>
        <div class="tenant-profile__actions">
          <AppButton variant="ghost" :disabled="saving" @click="cancel">取消</AppButton>
          <AppButton variant="primary" :loading="saving" @click="save">保存并同步详情</AppButton>
        </div>
      </div>
    </template>
  </section>
</template>

<script>
import { AppButton } from '@/components/ui'
import { platformP1ClosureApi } from '@/modules/platform/api/platformP1Closure.api'
import { toast } from '@/utils/toast'

const pickForm = (tenant = {}) => ({
  schoolType: tenant.schoolType || 'VOCATIONAL',
  province: tenant.province || '',
  city: tenant.city || '',
  contactName: tenant.contactName || '',
  contactPhone: tenant.contactPhone || '',
  contactWechat: tenant.contactWechat || '',
  remark: tenant.remark || ''
})

export default {
  name: 'TenantProfileEditor',
  components: { AppButton },
  props: { tenantId: { type: [String, Number], required: true } },
  emits: ['saved'],
  data() {
    return { loading: true, saving: false, error: '', tenant: null, form: pickForm(), reason: '', editing: false }
  },
  created() { this.load() },
  watch: { tenantId() { this.editing = false; this.reason = ''; this.load() } },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        this.tenant = await platformP1ClosureApi.getTenantProfile(this.tenantId)
        this.form = pickForm(this.tenant)
        if (!this.tenant?.canEdit) {
          this.editing = false
          this.reason = ''
        }
      } catch (error) {
        this.error = error.message || '学校基础资料加载失败'
      } finally {
        this.loading = false
      }
    },
    cancel() { this.form = pickForm(this.tenant); this.reason = ''; this.editing = false },
    async save() {
      if (!this.tenant?.canEdit) return toast.error('当前平台主管职责仅可查看学校基础资料')
      if (!this.form.schoolType.trim()) return toast.error('学校类型不能为空')
      if (this.reason.trim().length < 5) return toast.error('变更原因不少于 5 个字')
      this.saving = true
      try {
        const updated = await platformP1ClosureApi.updateTenantProfile(this.tenantId, {
          ...this.form,
          reason: this.reason.trim(),
          expectedVersion: this.tenant.version
        })
        this.tenant = updated
        this.form = pickForm(updated)
        this.reason = ''
        this.editing = false
        toast.success('学校基础资料已保存并写入审计')
        this.$emit('saved', updated)
      } catch (error) {
        toast.error(error.message || '学校基础资料保存失败')
        await this.load()
      } finally {
        this.saving = false
      }
    }
  }
}
</script>

<style scoped>
.tenant-profile { margin-bottom: 14px; padding: 14px 16px; border: 1px solid var(--card-b,#e5e6eb); border-radius: 12px; background: linear-gradient(180deg,rgba(37,99,235,.035),#fff 90px); }
.tenant-profile__head { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }
.tenant-profile__head strong { color:var(--t1); font-size:15px; }.tenant-profile__head p { margin:4px 0 0; color:var(--text-secondary); font-size:12px; }
.tenant-profile__readonly { padding:6px 9px; border-radius:8px; background:var(--fill-secondary,#f3f4f6); color:var(--text-secondary); font-size:12px; white-space:nowrap; }
.tenant-profile__summary { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin-top:12px; }
.tenant-profile__summary span { display:grid; gap:3px; padding:9px 10px; border:1px solid var(--card-b,#e5e6eb); border-radius:9px; color:var(--text-secondary); font-size:12px; background:#fff; }.tenant-profile__summary b { color:var(--t1); }
.tenant-profile__form { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:12px; }
.tenant-profile__form label { display:grid; gap:5px; color:var(--text-secondary); font-size:12px; }.tenant-profile__form input,.tenant-profile__form select,.tenant-profile__form textarea { width:100%; box-sizing:border-box; border:1px solid var(--card-b,#e5e6eb); border-radius:8px; padding:8px 10px; background:#fff; color:var(--t1); font:inherit; }.tenant-profile__form input:disabled{background:var(--fill-secondary,#f3f4f6);color:var(--text-tertiary)}.tenant-profile__wide { grid-column:span 2; }
.tenant-profile__actions { grid-column:1/-1; display:flex; justify-content:flex-end; gap:8px; }.tenant-profile__muted { margin-top:10px; color:var(--text-secondary); font-size:12px; }.tenant-profile__error { margin-top:10px; padding:9px; border-radius:8px; background:#fff2f0; color:#b42318; font-size:12px; }
@media (max-width:900px){.tenant-profile__form{grid-template-columns:repeat(2,minmax(0,1fr));}}@media (max-width:620px){.tenant-profile__head{display:grid}.tenant-profile__form{grid-template-columns:1fr}.tenant-profile__wide{grid-column:auto}}
</style>