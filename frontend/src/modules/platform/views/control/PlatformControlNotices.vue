<template>
  <ModulePageShell title="平台公告" subtitle="面向全平台或指定学校发布公告 / 到期提醒 / 维护通知" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <template #actions>
      <AppButton variant="primary" @click="createVisible = true">+ 新建公告</AppButton>
    </template>
    <LoadingState v-if="loading" text="正在加载公告…" />
    <template v-else>
      <DataTable :columns="columns" :rows="rows" row-key="noticeId">
        <template #cell-tenantId="{ row }">{{ row.tenantId === '0' ? '全平台' : row.tenantId }}</template>
        <template #cell-status="{ row }">
          <StatusTag :type="row.status === 'PUBLISHED' ? 'success' : row.status === 'DRAFT' ? 'warning' : 'default'" :label="row.status === 'PUBLISHED' ? '已发布' : row.status === 'DRAFT' ? '草稿' : '已下线'" />
        </template>
        <template #cell-publishAt="{ row }">{{ (row.publishAt || '').replace('T', ' ').slice(0, 16) || '—' }}</template>
        <template #cell-actions="{ row }">
          <div class="pcn__ops">
            <AppButton v-if="row.status !== 'PUBLISHED'" variant="primary" @click="act(row, 'publish')">发布</AppButton>
            <AppButton v-else variant="warning" @click="act(row, 'offline')">下线</AppButton>
          </div>
        </template>
      </DataTable>
      <EmptyState v-if="!rows.length" text="暂无公告" />
    </template>

    <AppDrawer :visible="createVisible" title="新建公告" mode="modal" size="medium" @update:visible="createVisible = $event">
      <div class="pcn__form">
        <label class="pcn__field"><span>标题 *</span><AppTextInput v-model="form.title" /></label>
        <label class="pcn__field"><span>类型</span>
          <AppSelect v-model="form.noticeType" :options="noticeTypeOptions" />
        </label>
        <label class="pcn__field"><span>内容</span><AppTextarea v-model="form.content" :rows="5" /></label>
        <div class="pcn__form-ops">
          <AppButton variant="primary" :loading="saving" @click="submit">保存草稿</AppButton>
          <AppButton @click="createVisible = false">取消</AppButton>
        </div>
      </div>
    </AppDrawer>
  </ModulePageShell>
</template>

<script>
import { AppButton, AppDrawer } from '@/components/ui'
import { DataTable, EmptyState, LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { AppSelect, AppTextInput, AppTextarea } from '@/components/common'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformControlNotices',
  components: { AppButton, AppDrawer, DataTable, EmptyState, LoadingState, ModulePageShell, StatusTag, AppSelect, AppTextInput, AppTextarea },
  data() {
    return {
      loading: true,
      saving: false,
      rows: [],
      noticeTypeOptions: [
        { value: 'ANNOUNCEMENT', label: '全平台公告' },
        { value: 'EXPIRE_REMIND', label: '到期提醒' },
        { value: 'MAINTENANCE', label: '维护通知' },
        { value: 'TRIAL_REMIND', label: '试用提醒' }
      ],
      createVisible: false,
      form: { title: '', noticeType: 'ANNOUNCEMENT', content: '', tenantId: 0 },
      columns: [
        { key: 'title', title: '标题', width: '260px' },
        { key: 'noticeType', title: '类型', width: '130px' },
        { key: 'tenantId', title: '范围', width: '110px' },
        { key: 'status', title: '状态', width: '90px' },
        { key: 'publishAt', title: '发布时间', width: '150px' },
        { key: 'actions', title: '操作', width: '120px' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      const res = await platformControlApi.listNotices()
      this.loading = false
      if (res.code === 0) this.rows = res.data.list || []
      else toast.error(res.message)
    },
    async submit() {
      if (!this.form.title) {
        toast.error('标题必填')
        return
      }
      this.saving = true
      const res = await platformControlApi.createNotice({ ...this.form })
      this.saving = false
      if (res.code === 0) {
        toast.success('公告已保存为草稿')
        this.createVisible = false
        this.form = { title: '', noticeType: 'ANNOUNCEMENT', content: '', tenantId: 0 }
        this.load()
      } else {
        toast.error(res.message)
      }
    },
    async act(row, action) {
      const res = await platformControlApi.noticeAction(row.noticeId, action)
      if (res.code === 0) {
        toast.success(action === 'publish' ? '已发布' : '已下线')
        this.load()
      } else {
        toast.error(res.message)
      }
    }
  }
}
</script>

<style scoped>
.pcn__ops {
  display: flex;
  gap: var(--space-1);
}
.pcn__form {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.pcn__field {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  font-size: var(--font-size-sm);
  color: var(--text-secondary);
}
.pcn__input {
  padding: 0 10px;
  height: 34px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--t1);
  font-size: 13px;
  font-family: inherit;
}
.pcn__textarea {
  height: auto;
  padding: 8px 10px;
  resize: vertical;
}
.pcn__input:focus {
  outline: none;
  border-color: var(--glow);
}
.pcn__form-ops {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}
</style>
