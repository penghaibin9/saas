<template>
  <ModulePageShell flat title="现场报到" watermark-purpose="现场报到核验">
    <template #actions><AppButton variant="secondary" @click="$router.push({path:'/admin/orientation/qualification',query:{...($route.query.batchId ? {batchId:$route.query.batchId} : {})}})">学院确认</AppButton><AppButton variant="ghost" @click="load">刷新记录</AppButton></template>
    <p v-if="error" class="checkin-error" role="alert">{{ error }}</p>
    <div class="checkin-workspace">
      <section class="checkin-entry">
        <h2>扫描学生报到码</h2>
        <label>报到点<select v-model="pointId"><option value="">请选择报到点</option><option v-for="p in points" :key="p.id" :value="String(p.id)">{{ p.name }}{{ p.location ? ` · ${p.location}` : '' }}</option></select></label>
        <form @submit.prevent="preflight"><label>报到凭证<input v-model.trim="token" autocomplete="off" aria-label="报到凭证" placeholder="使用扫码枪，或粘贴学生报到凭证" :disabled="busy" @input="preview = null" /></label><AppButton type="button" :disabled="busy || !token || !pointId" @click="preflight">核验凭证</AppButton></form>
        <p class="checkin-note">学生在 PC 或小程序出示报到码，核对本人后确认。</p>
        <template v-if="preview"><h2>{{ preview.student.name }}</h2><dl><div><dt>录取编号</dt><dd>{{ preview.student.admissionNo }}</dd></div><div><dt>学院 / 班级</dt><dd>{{ preview.student.collegeName }} / {{ preview.student.className || '待分班' }}</dd></div><div><dt>住宿安排</dt><dd>{{ preview.dorm.label }}</dd></div><div><dt>有效至</dt><dd>{{ formatTime(preview.expiresAt) }}</dd></div></dl><p v-if="preview.qualification.blockers?.length" class="checkin-note">其他待办：{{ preview.qualification.blockers.map(b => b.message).join('；') }}</p><AppButton :disabled="busy || !pointId" @click="confirmVisible = true">确认现场报到</AppButton></template>
        <p v-if="receipt" class="checkin-success" role="status">{{ receipt.name }} 已完成报到 · {{ receipt.checkinPointName }}</p>
      </section>
      <section class="checkin-records"><h2>今日报到记录 <small>{{ records.length }}</small></h2><DataTable :columns="columns" :rows="records" row-key="id"><template #cell-time="{ row }">{{ formatTime(row.checkinTime) }}</template></DataTable><p v-if="!records.length" class="checkin-note">暂无报到记录。</p></section>
    </div>
    <AppConfirmDialog v-model:visible="confirmVisible" title="确认现场报到" :message="preview ? `确认 ${preview.student.name} 已到校，并在 ${points.find(p => String(p.id) === pointId)?.name || ''} 完成核验。` : ''" confirm-text="确认报到" :submitting="busy" @confirm="confirm"><p v-if="error" class="checkin-error" role="alert">{{ error }}</p></AppConfirmDialog>
  </ModulePageShell>
</template>
<script>
import { ModulePageShell, DataTable } from '@/components/business'
import { AppButton } from '@/components/ui'
import { AppConfirmDialog } from '@/components/common'
import { request } from '@/services/http/client'
import { formatDateTime } from '@/utils/dateUtils'
export default {
  components: { ModulePageShell, DataTable, AppButton, AppConfirmDialog },
  data() { return { points: [], pointId: '', token: '', preview: null, receipt: null, records: [], busy: false, error: '', confirmVisible: false, columns: [{ key: 'name', title: '学生' }, { key: 'className', title: '班级' }, { key: 'checkinPointName', title: '报到点' }, { key: 'time', title: '报到时间' }] } },
  mounted() { this.load() },
  methods: {
    formatTime(v) { return formatDateTime(v) },
    async load() { this.error = ''; try { const [p, r] = await Promise.all([request('/mobile/teacher/orientation/checkin-points'), request('/mobile/teacher/orientation/today-checkins')]); this.points = p.items || []; this.records = r.list || r.items || []; if (!this.points.some(p => String(p.id) === this.pointId)) this.pointId = String(this.points[0]?.id || '') } catch (e) { this.error = e.message } },
    async preflight() { if (this.busy || !this.token || !this.pointId) return; this.busy = true; this.error = ''; this.preview = null; this.receipt = null; try { this.preview = await request('/mobile/teacher/orientation/checkin/preflight', { method: 'POST', body: { token: this.token } }) } catch (e) { this.error = e.message } finally { this.busy = false } },
    async confirm() { if (this.busy || !this.preview || !this.pointId) return; this.busy = true; this.error = ''; try { this.receipt = await request('/mobile/teacher/orientation/checkin/confirm', { method: 'POST', body: { token: this.token, checkinPointId: this.pointId } }); this.confirmVisible = false; this.token = ''; this.preview = null; await this.load() } catch (e) { this.error = e.message } finally { this.busy = false } }
  }
}
</script>
<style scoped>
.checkin-workspace{display:grid;grid-template-columns:minmax(300px,1fr) minmax(360px,1.4fr);gap:28px}.checkin-entry{border-right:1px solid var(--border-light);padding-right:28px}.checkin-workspace h2{font-size:16px;margin:12px 0 20px}.checkin-workspace small{font-weight:400;color:var(--text-secondary);margin-left:8px}.checkin-entry label{display:flex;flex-direction:column;gap:8px;font-size:13px;margin:16px 0}.checkin-entry input,.checkin-entry select{width:100%;min-height:40px;border:1px solid var(--border-light);border-radius:5px;padding:8px;background:var(--bg-card);color:var(--text-primary);box-sizing:border-box}.checkin-note{font-size:13px;color:var(--text-secondary);line-height:1.7}.checkin-error{color:var(--danger-600,#b42318);font-size:13px}.checkin-success{color:var(--success-700,#15803d)}dl div{display:flex;justify-content:space-between;gap:16px;padding:12px 0;border-bottom:1px solid var(--border-light);font-size:13px}dt{color:var(--text-secondary);white-space:nowrap}dd{margin:0;text-align:right}input:focus-visible,select:focus-visible{outline:2px solid var(--primary-500);outline-offset:2px}@media(max-width:1000px){.checkin-workspace{grid-template-columns:1fr}.checkin-entry{border-right:0;border-bottom:1px solid var(--border-light);padding:0 0 20px}}
</style>
