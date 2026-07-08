<template>
  <ModulePageShell
    :title="titleMap[tab]"
    :subtitle="subtitleMap[tab]"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar :actions="toolbar" @action="onToolbar" />
    </template>

    <div class="gm-tabs">
      <button class="gm-tabs__item" :class="{ 'is-active': tab === 'peer' }" @click="switchTab('peer')">成果互查整改</button>
      <button class="gm-tabs__item" :class="{ 'is-active': tab === 'experts' }" @click="switchTab('experts')">答辩专家库</button>
      <button class="gm-tabs__item" :class="{ 'is-active': tab === 'appeals' }" @click="switchTab('appeals')">成绩更正申诉</button>
    </div>

    <LoadingState v-if="loading" />

    <!-- 成果互查整改 -->
    <div v-else-if="tab === 'peer'" class="mp-stack">
      <EmptyState v-if="!rows.length" title="暂无互查记录" description="点右上「分配互查」为学生指定互查人" />
      <DataTable v-else :columns="peerCols" :rows="rows" row-key="id">
        <template #cell-pair="{ row }"><div class="mp-cell-main">{{ row.reviewerName }} 查 {{ row.studentName }}</div><div class="mp-cell-sub">{{ row.opinion || '（待互查）' }}{{ row.rectifyNote ? ' · 整改：' + row.rectifyNote : '' }}</div></template>
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'RECTIFIED' ? 'success' : row.status === 'REVIEWED' ? 'warning' : 'default'" :label="row.statusLabel" dot /></template>
      </DataTable>
    </div>

    <!-- 答辩专家库 -->
    <div v-else-if="tab === 'experts'" class="mp-stack">
      <EmptyState v-if="!rows.length" title="暂无答辩专家" description="点右上「新增专家」建立评委库（可标回避规则）" />
      <DataTable v-else :columns="expertCols" :rows="rows" row-key="id">
        <template #cell-expert="{ row }"><div class="mp-cell-main">{{ row.expertName }} <StatusTag v-if="row.isExternal" type="info" label="校外" /></div><div class="mp-cell-sub">{{ row.title || '—' }} · {{ row.collegeName || '—' }}{{ row.avoidNote ? ' · 回避：' + row.avoidNote : '' }}</div></template>
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'ACTIVE' ? 'success' : 'default'" :label="row.statusLabel" dot /></template>
        <template #cell-actions="{ row }"><button class="mp-link" @click="toggleExpert(row)">{{ row.status === 'ACTIVE' ? '停用' : '启用' }}</button></template>
      </DataTable>
    </div>

    <!-- 成绩更正申诉 -->
    <div v-else class="mp-stack">
      <div class="mp-tabs">
        <button v-for="s in appealTabs" :key="s.value" class="mp-tab" :class="{ 'is-active': appealStatus === s.value }" @click="appealStatus = s.value; load()">{{ s.label }}</button>
      </div>
      <EmptyState v-if="!rows.length" title="暂无成绩申诉" description="学生对已发布成绩发起申诉后在此复核" />
      <DataTable v-else :columns="appealCols" :rows="rows" row-key="id">
        <template #cell-student="{ row }"><div class="mp-cell-main">{{ row.studentName }}</div><div class="mp-cell-sub">{{ row.reason }}</div></template>
        <template #cell-status="{ row }"><StatusTag :type="row.status === 'APPROVED' ? 'success' : row.status === 'REJECTED' ? 'danger' : 'warning'" :label="row.statusLabel" dot /></template>
        <template #cell-actions="{ row }">
          <template v-if="row.status === 'PENDING'">
            <button class="mp-link" @click="askAppeal(row, 'APPROVE')">受理</button>
            <button class="mp-link mp-link--danger" style="margin-left:var(--space-2)" @click="askAppeal(row, 'REJECT')">驳回</button>
          </template>
          <span v-else class="mp-cell-sub">{{ row.reviewComment || '—' }}</span>
        </template>
      </DataTable>
    </div>

    <!-- 分配互查抽屉 -->
    <AppDrawer v-model:visible="peerDrawer" title="分配成果互查">
      <form class="ie-form" @submit.prevent="submitPeer">
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">被评学生（毕设学生ID）<i>*</i></span><input v-model.trim="peerForm.gdStudentId" class="ie-in" placeholder="被互查学生 t_gd_student.id" /></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">互查学生（毕设学生ID）<i>*</i></span><input v-model.trim="peerForm.reviewerGdStudentId" class="ie-in" placeholder="互查人 t_gd_student.id" /></label>
        <p v-if="err" class="ie-err">{{ err }}</p>
        <div class="ie-actions"><button type="button" class="mp-btn" @click="peerDrawer = false">取消</button><button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">分配</button></div>
      </form>
    </AppDrawer>

    <!-- 新增专家抽屉 -->
    <AppDrawer v-model:visible="expertDrawer" title="新增答辩专家">
      <form class="ie-form" @submit.prevent="submitExpert">
        <label class="ie-fld"><span class="ie-lbl">专家姓名 <i>*</i></span><input v-model.trim="expertForm.expertName" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">职称</span><input v-model.trim="expertForm.title" class="ie-in" placeholder="如 教授/副教授" /></label>
        <label class="ie-fld"><span class="ie-lbl">所属学院</span><input v-model.trim="expertForm.collegeName" class="ie-in" /></label>
        <label class="ie-fld"><span class="ie-lbl">是否校外</span><select v-model="expertForm.isExternal" class="ie-in"><option :value="false">校内</option><option :value="true">校外</option></select></label>
        <label class="ie-fld ie-fld--full"><span class="ie-lbl">回避说明</span><input v-model.trim="expertForm.avoidNote" class="ie-in" placeholder="如 不评本院学生 / 回避亲属" /></label>
        <p v-if="err" class="ie-err">{{ err }}</p>
        <div class="ie-actions"><button type="button" class="mp-btn" @click="expertDrawer = false">取消</button><button type="submit" class="mp-btn mp-btn--primary" :disabled="submitting">保存</button></div>
      </form>
    </AppDrawer>

    <AppConfirmDialog v-model:visible="confirm.visible" :title="confirm.title" :message="confirm.message" :type="confirm.type" :confirm-text="confirm.confirmText" :require-reason="confirm.requireReason" reason-label="驳回理由" :submitting="submitting" @confirm="onConfirmAppeal" />
  </ModulePageShell>
</template>

<script>
/** 互查整改 / 答辩专家库 / 成绩更正申诉（/admin/graduation/more?panel=peer|experts|appeals）。 */
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, EmptyState } from '@/components/business'
import { AppDrawer } from '@/components/ui'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { graduationMoreApi } from '@/modules/graduation/api/graduation-more.api'
import { toast } from '@/utils/toast'

export default {
  name: 'GraduationMoreView',
  components: { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, EmptyState, AppDrawer, AppConfirmDialog },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      tab: 'peer', loading: true, submitting: false, rows: [], err: '',
      appealStatus: '',
      peerDrawer: false, peerForm: { gdStudentId: '', reviewerGdStudentId: '' },
      expertDrawer: false, expertForm: { expertName: '', title: '', collegeName: '', isExternal: false, avoidNote: '' },
      confirm: { visible: false, title: '', message: '', type: 'primary', confirmText: '确定', requireReason: false, action: '', row: null },
      titleMap: { peer: '成果互查整改', experts: '答辩专家库', appeals: '成绩更正申诉' },
      subtitleMap: { peer: '学生互评+被评整改闭环', experts: '评委库 + 回避规则（对齐维普专家评审回避）', appeals: '学生对已发布成绩申诉→复核（受理即撤回成绩重核）' },
      appealTabs: [{ value: '', label: '全部' }, { value: 'PENDING', label: '待复核' }, { value: 'APPROVED', label: '已受理' }, { value: 'REJECTED', label: '已驳回' }],
      peerCols: [{ key: 'pair', title: '互查关系 / 意见' }, { key: 'status', title: '状态' }],
      expertCols: [{ key: 'expert', title: '专家' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '100px' }],
      appealCols: [{ key: 'student', title: '学生 / 申诉理由' }, { key: 'status', title: '状态' }, { key: 'actions', title: '操作', width: '160px' }]
    }
  },
  computed: {
    toolbar() {
      if (this.tab === 'peer') return [{ key: 'assignPeer', label: '＋ 分配互查', variant: 'primary' }]
      if (this.tab === 'experts') return [{ key: 'addExpert', label: '＋ 新增专家', variant: 'primary' }]
      return []
    }
  },
  watch: { '$route.query.panel': { immediate: true, handler(p) { this.tab = ['peer', 'experts', 'appeals'].includes(p) ? p : 'peer'; this.load() } } },
  methods: {
    switchTab(t) { this.tab = t; this.$router.replace({ query: { panel: t } }); this.load() },
    onToolbar(k) {
      if (k === 'assignPeer') { this.peerForm = { gdStudentId: '', reviewerGdStudentId: '' }; this.err = ''; this.peerDrawer = true }
      if (k === 'addExpert') { this.expertForm = { expertName: '', title: '', collegeName: '', isExternal: false, avoidNote: '' }; this.err = ''; this.expertDrawer = true }
    },
    async load() {
      this.loading = true
      let res
      if (this.tab === 'peer') res = await graduationMoreApi.getPeerReviews()
      else if (this.tab === 'experts') res = await graduationMoreApi.getExperts()
      else res = await graduationMoreApi.getAppeals(this.appealStatus ? { status: this.appealStatus } : {})
      this.rows = res.code === 0 ? res.data.list : []
      this.loading = false
    },
    async submitPeer() {
      this.err = ''
      if (!this.peerForm.gdStudentId || !this.peerForm.reviewerGdStudentId) { this.err = '两个学生ID必填'; return }
      this.submitting = true
      const res = await graduationMoreApi.assignPeer(this.peerForm.gdStudentId, this.peerForm.reviewerGdStudentId)
      this.submitting = false
      if (res.code === 0) { toast.success('已分配互查'); this.peerDrawer = false; this.load() } else this.err = res.message
    },
    async submitExpert() {
      this.err = ''
      if (!this.expertForm.expertName) { this.err = '专家姓名必填'; return }
      this.submitting = true
      const res = await graduationMoreApi.createExpert(this.expertForm)
      this.submitting = false
      if (res.code === 0) { toast.success('已新增专家'); this.expertDrawer = false; this.load() } else this.err = res.message
    },
    async toggleExpert(row) {
      const res = await graduationMoreApi.setExpertStatus(row.id, row.status === 'ACTIVE' ? 'DISABLE' : 'ENABLE')
      if (res.code === 0) this.load(); else toast.error(res.message)
    },
    askAppeal(row, action) {
      this.confirm = action === 'APPROVE'
        ? { visible: true, title: '受理申诉', message: `受理「${row.studentName}」的成绩申诉？受理后将撤回其成绩，走重新核算。`, type: 'primary', confirmText: '受理', requireReason: false, action: 'APPROVE', row }
        : { visible: true, title: '驳回申诉', message: `驳回「${row.studentName}」的申诉，请填写理由（≥5字）。`, type: 'danger', confirmText: '驳回', requireReason: true, action: 'REJECT', row }
    },
    async onConfirmAppeal({ reason } = {}) {
      this.submitting = true
      const res = await graduationMoreApi.reviewAppeal(this.confirm.row.id, this.confirm.action, reason || '')
      this.submitting = false
      if (res.code === 0) { toast.success('已复核'); this.confirm.visible = false; this.load() } else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.gm-tabs { display: flex; gap: var(--space-1); margin-bottom: var(--space-3); border-bottom: 1px solid var(--border-base); }
.gm-tabs__item { padding: 8px 16px; font-size: var(--font-size-sm); color: var(--text-secondary); background: none; border: none; border-bottom: 2px solid transparent; cursor: pointer; }
.gm-tabs__item.is-active { color: var(--brand-primary); border-bottom-color: var(--brand-primary); font-weight: var(--font-weight-medium); }
</style>
