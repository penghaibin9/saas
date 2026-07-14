<template>
  <ModulePageShell
    title="注册名单"
    subtitle="批次内已注册学生；从下方检索在籍学生并逐个注册"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <button class="mp-btn" @click="$router.push('/admin/academic-affairs/registration')">返回批次列表</button>
    </template>

    <div class="mp-stack">
      <AppSectionCard title="注册学生">
        <div class="aa-reg-search">
          <input v-model.trim="kw" class="aa-input aa-input--grow" placeholder="按姓名/学号检索在籍学生" @keyup.enter="searchStudents" />
          <button class="mp-btn" :disabled="searching" @click="searchStudents">检索</button>
        </div>
        <div v-if="searched" class="aa-reg-cands">
          <EmptyState v-if="!candidates.length" title="无匹配学生" description="换个关键字，或确认学生在当前数据范围内" />
          <ul v-else class="aa-cand-list">
            <li v-for="s in candidates" :key="s.studentId" class="aa-cand-item">
              <span>{{ s.realName }} · 学号 {{ s.studentNo }}</span>
              <button class="mp-link" :disabled="registeringId === s.studentId" @click="doRegister(s)">
                {{ registeringId === s.studentId ? '注册中…' : '注册' }}
              </button>
            </li>
          </ul>
        </div>
      </AppSectionCard>

      <AppSectionCard title="已注册名单">
        <ErrorState v-if="error" :description="error" @retry="load" />
        <LoadingState v-else-if="loading" />
        <EmptyState v-else-if="!rows.length" title="本批次暂无注册记录" description="用上方检索为学生完成注册" />
        <DataTable
          v-else
          :columns="columns"
          :rows="rows"
          row-key="registrationId"
          :pagination="pagination"
          @page-change="onPageChange"
        >
          <template #cell-status="{ row }">
            <AppStatusTag type="success" dot>{{ row.status === 'REGISTERED' ? '已注册' : row.status }}</AppStatusTag>
          </template>
        </DataTable>
      </AppSectionCard>
    </div>
  </ModulePageShell>
</template>

<script>
/** 注册名单（/admin/academic-affairs/registration/:batchId）：注册记录 + roster 检索注册。 */
import { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState } from '@/components/business'
import { AppSectionCard, AppStatusTag } from '@/components/common'
import { academicAffairsApi } from '@/modules/academicAffairs/api/academic-affairs.api'
import { toast } from '@/utils/toast'

export default {
  name: 'AaRegistrationDetailView',
  components: { ModulePageShell, DataTable, LoadingState, ErrorState, EmptyState, AppSectionCard, AppStatusTag },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      rows: [],
      pagination: { page: 1, pageSize: 50, total: 0 },
      kw: '',
      searching: false,
      searched: false,
      candidates: [],
      registeringId: '',
      columns: [
        { key: 'realName', title: '学生' },
        { key: 'registerAt', title: '注册时间' },
        { key: 'status', title: '状态' }
      ]
    }
  },
  computed: {
    batchId() {
      return this.$route.params.batchId
    }
  },
  created() {
    this.load()
  },
  methods: {
    onPageChange(page) {
      this.pagination.page = page
      this.load()
    },
    async searchStudents() {
      if (this.searching) return
      this.searching = true
      const res = await academicAffairsApi.getRoster({ keyword: this.kw || undefined, status: 'PENDING_REGISTER', page: 1, pageSize: 20 })
      // 若按待注册筛选无结果，退回不限状态，方便学年注册（已在籍学生）
      let list = res.code === 0 ? res.data.list : []
      if (res.code === 0 && !list.length) {
        const r2 = await academicAffairsApi.getRoster({ keyword: this.kw || undefined, page: 1, pageSize: 20 })
        if (r2.code === 0) list = r2.data.list
      }
      this.candidates = list
      this.searched = true
      this.searching = false
    },
    async doRegister(s) {
      if (this.registeringId) return
      this.registeringId = s.studentId
      const res = await academicAffairsApi.registerStudent(this.batchId, s.studentId)
      this.registeringId = ''
      if (res.code === 0) {
        toast.success(`${s.realName} 注册成功`)
        this.candidates = this.candidates.filter((c) => c.studentId !== s.studentId)
        this.load()
      } else {
        toast.error(res.message || '注册失败')
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      const res = await academicAffairsApi.getRegistrations(this.batchId, { page: this.pagination.page, pageSize: this.pagination.pageSize })
      if (res.code === 0) {
        this.rows = res.data.list
        this.pagination.total = res.data.total
      } else {
        this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.aa-reg-search { display: flex; gap: 12px; align-items: center; }
.aa-input { height: 34px; padding: 0 12px; border: 1px solid var(--border-300, #d0d3d9); border-radius: 6px; background: var(--bg-white, #fff); color: var(--text-900, #1f2329); font-size: 14px; box-sizing: border-box; }
.aa-input--grow { flex: 1; }
.aa-cand-list { list-style: none; margin: 12px 0 0; padding: 0; }
.aa-cand-item { display: flex; align-items: center; justify-content: space-between; padding: 10px 4px; border-bottom: 1px solid var(--border-100, #f0f1f2); font-size: 14px; }
</style>
