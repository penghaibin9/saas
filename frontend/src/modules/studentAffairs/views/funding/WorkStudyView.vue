<template>
  <AppPageShell title="勤工助学" subtitle="部门发岗 → 学生申请 → 录用 → 上岗 → 终止。补贴金额按角色脱敏。"
    role-name="学工处 / 资助老师" data-scope-name="资助范围（辅导员限本班）" watermark-purpose="勤工助学管理">
    <AppGlobalState :state="pageState" :description="errorMessage" loading-text="加载中..." @retry="load"
                    @back="$router.push('/admin/student-affairs/funding')">
      <div class="ws-cols">
        <AppSectionCard title="岗位（部门发岗）" class="ws-posts">
          <div class="ws-add">
            <input v-model.trim="postForm.deptName" class="ws-input" placeholder="用人部门" />
            <input v-model.trim="postForm.postName" class="ws-input" placeholder="岗位名称" />
            <input v-model.number="postForm.salary" type="number" class="ws-input ws-sm" placeholder="月薪" />
            <AppPermissionButton code="studentAffairs.funding.workstudy.manage" size="sm" :loading="acting==='post'" @click="addPost">发岗</AppPermissionButton>
          </div>
          <ul class="ws-postlist">
            <li v-for="p in posts" :key="p.postId" class="ws-post" :class="{ 'is-on': selPost===p.postId }" @click="selectPost(p)">
              <strong>{{ p.postName }}</strong><span>{{ p.deptName }} · {{ p.salary != null ? ('¥'+p.salary) : '—' }} · {{ p.headcount || '—' }}人</span>
              <AppPermissionButton code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" @click.stop="applyTo(p)">代录申请</AppPermissionButton>
            </li>
            <li v-if="!posts.length" class="ws-empty">暂无岗位</li>
          </ul>
        </AppSectionCard>

        <AppSectionCard :title="selPost ? '上岗记录（本岗位）' : '上岗记录（全部）'" class="ws-recs">
          <table class="sa-table">
            <thead><tr><th>学生</th><th>状态</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="r in records" :key="r.recordId">
                <td><strong>{{ r.realName || ('#'+r.studentId) }}</strong></td>
                <td><StatusTag :type="wsType(r.status)" :label="r.statusLabel || r.status" dot /></td>
                <td class="ws-ops">
                  <AppPermissionButton v-if="r.status==='APPLIED'" code="studentAffairs.funding.workstudy.manage" size="sm" :loading="acting===r.recordId" @click="act(r,'APPROVE')">录用</AppPermissionButton>
                  <AppPermissionButton v-if="r.status==='APPLIED'" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" danger @click="act(r,'REJECT')">拒绝</AppPermissionButton>
                  <AppPermissionButton v-if="r.status==='APPROVED'" code="studentAffairs.funding.workstudy.manage" size="sm" @click="act(r,'ONBOARD')">上岗</AppPermissionButton>
                  <AppPermissionButton v-if="['APPROVED','ONBOARD'].includes(r.status)" code="studentAffairs.funding.workstudy.manage" size="sm" variant="secondary" danger @click="act(r,'TERMINATE')">终止</AppPermissionButton>
                </td>
              </tr>
              <tr v-if="!records.length"><td colspan="3" class="sa-empty">暂无记录</td></tr>
            </tbody>
          </table>
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import { AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, AppStatusTag } from '@/components/common'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'WorkStudyView',
  components: { AppGlobalState, AppPageShell, AppPermissionButton, AppSectionCard, StatusTag: AppStatusTag },
  data() {
    return { loading: true, acting: '', errorMessage: '', posts: [], records: [], selPost: '', postForm: { deptName: '', postName: '', salary: null } }
  },
  computed: { pageState() { return this.loading ? 'loading' : (this.errorMessage ? 'error' : 'ready') } },
  mounted() { this.load() },
  methods: {
    async load() {
      this.loading = true; this.errorMessage = ''
      const [ps, rs] = await Promise.all([studentAffairsApi.getWorkStudyPosts(), studentAffairsApi.getWorkStudyRecords({ postId: this.selPost })])
      if (ps.code === 0 && ps.data) this.posts = ps.data.items || []
      else this.errorMessage = ps.message || '加载失败'
      this.records = (rs.code === 0 && rs.data) ? (rs.data.items || []) : []
      this.loading = false
    },
    async addPost() {
      const f = this.postForm
      if (!f.deptName || !f.postName) { toast.error('部门与岗位名称必填'); return }
      this.acting = 'post'
      const res = await studentAffairsApi.createWorkStudyPost({ deptName: f.deptName, postName: f.postName, salary: f.salary != null ? Number(f.salary) : undefined })
      this.acting = ''
      if (res.code === 0) { toast.success('已发岗'); this.postForm = { deptName: '', postName: '', salary: null }; this.load() } else toast.error(res.message || '发岗失败')
    },
    selectPost(p) { this.selPost = this.selPost === p.postId ? '' : p.postId; this.load() },
    async applyTo(p) {
      const sid = window.prompt('学生主档ID：')
      if (!sid) return
      const res = await studentAffairsApi.applyWorkStudy(p.postId, Number(sid))
      if (res.code === 0) { toast.success('已申请'); this.load() } else toast.error(res.message || '申请失败')
    },
    async act(r, action) {
      let reason = ''
      if (action === 'TERMINATE') { reason = window.prompt('终止原因（至少5字）：') || ''; if (!reason) return }
      this.acting = r.recordId
      const res = await studentAffairsApi.actWorkStudy(r.recordId, action, reason)
      this.acting = ''
      if (res.code === 0) { toast.success('已处理'); this.load() } else toast.error(res.message || '操作失败')
    },
    wsType(s) { return ({ APPLIED: 'warning', APPROVED: 'processing', ONBOARD: 'success', REJECTED: 'default', TERMINATED: 'default' })[s] || 'default' }
  }
}
</script>

<style scoped>
.ws-cols { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.ws-add { display: flex; gap: var(--space-2); margin-bottom: var(--space-3); flex-wrap: wrap; }
.ws-input { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: 7px 10px; }
.ws-sm { width: 90px; }
.ws-postlist { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: var(--space-2); }
.ws-post { border: 1px solid var(--border-light); border-radius: var(--radius-md); padding: var(--space-3); cursor: pointer; display: flex; flex-direction: column; gap: 2px; }
.ws-post.is-on { border-color: var(--color-primary); box-shadow: 0 0 0 2px rgba(37,99,235,0.12); }
.ws-post span { font-size: var(--font-size-sm); color: var(--text-secondary); }
.ws-empty, .sa-empty { color: var(--text-tertiary); padding: var(--space-3); text-align: center; }
.sa-table { width: 100%; border-collapse: collapse; }
.sa-table th, .sa-table td { border-bottom: 1px solid var(--border-light); padding: var(--space-2) var(--space-3); text-align: left; }
.ws-ops { display: flex; gap: 6px; flex-wrap: wrap; }
@media (max-width: 960px) { .ws-cols { grid-template-columns: 1fr; } }
</style>
