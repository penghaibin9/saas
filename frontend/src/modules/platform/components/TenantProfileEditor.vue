<template>
  <section class="tenant-profile">
    <div class="tenant-profile__head">
      <div>
        <strong>学校基础资料维护</strong>
        <p>联系人、地区、学校类型和环境直接写入租户真实配置；保存后下方租户详情同步刷新。</p>
      </div>
      <AppButton v-if="!editing" variant="secondary" @click="editing = true">编辑基础资料</AppButton>
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
        <span><b>环境</b>{{ tenant.environment || 'production' }}</span>
      </div>

      <div v-else class="tenant-profile__form">
        <label><span>学校类型</span><input v-model.trim="form.schoolType" /></label>
        <label><span>省份</span><input v-model.trim="form.province" /></label>
        <label><span>城市</span><input v-model.trim="form.city" /></label>
        <label><span>联系人</span><input v-model.trim="form.contactName" /></label>
        <label><span>联系电话</span><input v-model.trim="form.contactPhone" inputmode="tel" /></label>
        <label><span>联系微信</span><input v-model.trim="form.contactWechat" /></label>
        <label><span>环境</span>
          <select v-model="form.environment">
            <option value="production">production</option>
            <option value="demo">demo</option>
            <option value="staging">staging</option>
          </select>
        </label>
        <label class="tenant-profile__wide"><span>备注</span><textarea v-model.trim="form.remark" rows="2" /></label>
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
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

const pickForm = (tenant = {}) => ({
  schoolType: tenant.schoolType || 'VOCATIONAL',
  province: tenant.province || '',
  city: tenant.city || '',
  contactName: tenant.contactName || '',
  contactPhone: tenant.contactPhone || '',
  contactWechat: tenant.contactWechat || '',
  environment: tenant.environment || 'production',
  remark: tenant.remark || ''
})

export default {
  name: 'TenantProfileEditor',
  components: { AppButton },
  props: { tenantId: { type: [String, Number], required: true } },
  emits: ['saved'],
  data() {
    return { loading: true, saving: false, error: '', tenant: null, form: pickForm(), editing: false }
  },
  created() { this.load() },
  watch: { tenantId() { this.editing = false; this.load() } },
  methods: {
    async load() {
      this.loading = true
      this.error = ''
      const res = await platformControlApi.getTenant(this.tenantId)
      this.loading = false
      if (res.code !== 0) { this.error = res.message; return }
      this.tenant = res.data
      this.form = pickForm(res.data)
    },
    cancel() { this.form = pickForm(this.tenant); this.editing = false },
    async save() {
      this.saving = true
      const res = await platformControlApi.updateTenant(this.tenantId, { ...this.form })
      this.saving = false
      if (res.code !== 0) return toast.error(res.message)
      this.tenant = res.data
      this.form = pickForm(res.data)
      this.editing = false
      toast.success('学校基础资料已保存')
      this.$emit('saved', res.data)
    }
  }
}
</script>

<style scoped>
.tenant-profile { margin-bottom: 14px; padding: 14px 16px; border: 1px solid var(--card-b,#e5e6eb); border-radius: 12px; background: linear-gradient(180deg,rgba(37,99,235,.035),#fff 90px); }
.tenant-profile__head { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }
.tenant-profile__head strong { color:var(--t1); font-size:15px; }.tenant-profile__head p { margin:4px 0 0; color:var(--text-secondary); font-size:12px; }
.tenant-profile__summary { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:10px; margin-top:12px; }
.tenant-profile__summary span { display:grid; gap:3px; padding:9px 10px; border:1px solid var(--card-b,#e5e6eb); border-radius:9px; color:var(--text-secondary); font-size:12px; background:#fff; }.tenant-profile__summary b { color:var(--t1); }
.tenant-profile__form { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:12px; }
.tenant-profile__form label { display:grid; gap:5px; color:var(--text-secondary); font-size:12px; }.tenant-profile__form input,.tenant-profile__form select,.tenant-profile__form textarea { width:100%; box-sizing:border-box; border:1px solid var(--card-b,#e5e6eb); border-radius:8px; padding:8px 10px; background:#fff; color:var(--t1); font:inherit; }.tenant-profile__wide { grid-column:span 2; }
.tenant-profile__actions { grid-column:1/-1; display:flex; justify-content:flex-end; gap:8px; }.tenant-profile__muted { margin-top:10px; color:var(--text-secondary); font-size:12px; }.tenant-profile__error { margin-top:10px; padding:9px; border-radius:8px; background:#fff2f0; color:#b42318; font-size:12px; }
@media (max-width:900px){.tenant-profile__form{grid-template-columns:repeat(2,minmax(0,1fr));}}@media (max-width:620px){.tenant-profile__head{display:grid}.tenant-profile__form{grid-template-columns:1fr}.tenant-profile__wide{grid-column:auto}}
</style>
