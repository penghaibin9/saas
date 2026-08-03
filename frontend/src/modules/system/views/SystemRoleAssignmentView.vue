<template>
  <ModulePageShell
    title="角色成员与业务身份"
    subtitle="固定角色看有效期与来源 · 自动业务身份由业务表实时计算，本页不写业务终态"
    :role-name="ctx.currentRole.roleName"
    :data-scope-name="ctx.dataScope.scopeName"
  >
    <template #actions>
      <ModuleToolbar
        :actions="[{ key: 'sweep', label: '立即回收到期授权', variant: 'primary' }, { key: 'refresh', label: '刷新' }]"
        @action="onAction"
      />
    </template>

    <div class="mp-stack">
      <div class="ra-tabs" role="tablist">
        <button class="mp-link" :class="{ 'is-active': tab === 'members' }" @click="switchTab('members')">固定角色成员</button>
        <button class="mp-link" :class="{ 'is-active': tab === 'identities' }" @click="switchTab('identities')">自动业务身份</button>
      </div>

      <ErrorState v-if="error" :description="error" @retry="load" />
      <LoadingState v-else-if="loading" />

      <template v-else-if="tab === 'members'">
        <section class="mp-card">
          <header class="mp-card__head"><span class="mp-card__title">首屏结论</span></header>
          <div class="mp-card__body ra-buckets">
            <button v-for="b in bucketList" :key="b.key" class="ra-bucket"
                    :class="{ 'is-active': bucket === b.key }" @click="pickBucket(b.key)">
              <span class="ra-bucket__num">{{ b.count }}</span>
              <span class="ra-bucket__label">{{ b.label }}</span>
            </button>
          </div>
        </section>

        <EmptyState v-if="!rows.length" title="没有符合条件的角色成员"
                    description="换一个分类，或先在账号页面授予角色" />
        <DataTable v-else :columns="memberColumns" :rows="rows" row-key="userRoleId">
          <template #cell-user="{ row }">
            <div class="mp-cell-main">{{ row.realName || row.loginName }}</div>
            <div class="mp-cell-sub">{{ row.loginName }} · {{ row.roleCode }}</div>
          </template>
          <template #cell-validity="{ row }">
            <div class="mp-cell-sub">生效 {{ row.effectiveAt || '—' }}</div>
            <div class="mp-cell-sub">
              到期 {{ row.expiresAt || '长期有效' }}
              <span v-if="row.daysLeft !== null && row.daysLeft !== undefined">（剩 {{ row.daysLeft }} 天）</span>
            </div>
          </template>
          <template #cell-source="{ row }">
            <StatusTag :type="row.sourceType === 'UNKNOWN' ? 'warning' : 'default'"
                       :label="row.sourceType" dot />
            <div class="mp-cell-sub">{{ row.reason || '—' }}</div>
          </template>
          <template #cell-status="{ row }">
            <StatusTag :type="statusTone(row.status)" :label="row.status" dot />
            <div v-if="row.lastReviewedAt" class="mp-cell-sub">复核 {{ row.lastReviewedTerm }}</div>
            <div v-else class="mp-cell-sub">未复核</div>
          </template>
          <template #cell-ops="{ row }">
            <template v-if="row.assignmentId">
              <button class="mp-link" @click="ask('review', row)">复核</button>
              <button class="mp-link" @click="ask('transfer', row)">转交</button>
              <button class="mp-link" @click="ask('revoke', row)">回收</button>
            </template>
            <span v-else class="mp-cell-sub">历史授权，先补登记</span>
          </template>
        </DataTable>
      </template>

      <template v-else>
        <section class="mp-card">
          <header class="mp-card__head">
            <span class="mp-card__title">自动业务身份</span>
            <span class="mp-note">{{ identityNote }}</span>
          </header>
          <div class="mp-card__body">
            <EmptyState v-if="!identities.length" title="当前没有自动业务身份"
                        description="业务身份来自任课、毕设、实习等业务关系，先在对应业务模块建立关系" />
            <DataTable v-else :columns="identityColumns" :rows="identities" row-key="subjectKey">
              <template #cell-identity="{ row }">
                <div class="mp-cell-main">{{ row.label }}</div>
                <div class="mp-cell-sub">{{ row.identityType }}</div>
              </template>
              <template #cell-subject="{ row }">
                <div class="mp-cell-main">{{ row.name || row.subjectKey }}</div>
                <div class="mp-cell-sub">
                  <StatusTag v-if="!row.subjectResolved" type="warning" label="未映射到账号" dot />
                  <span v-else>userId {{ row.userId }}</span>
                </div>
              </template>
              <template #cell-scope="{ row }">
                <div class="mp-cell-sub">{{ row.objectCount }} 个对象</div>
                <div class="mp-cell-sub">{{ (row.objects || []).slice(0, 5).join('、') }}</div>
              </template>
              <template #cell-owner="{ row }">
                <div class="mp-cell-sub">{{ row.ownerModule }}</div>
                <div class="mp-cell-sub">{{ row.source }}</div>
              </template>
            </DataTable>
          </div>
        </section>
      </template>
    </div>

    <AppConfirmDialog
      v-model:visible="dialogOpen"
      :type="pendingAction === 'revoke' ? 'warning' : 'info'"
      :title="dialogTitle"
      :message="dialogMessage"
      :confirm-text="dialogTitle"
      require-reason
      reason-label="原因"
      :submitting="submitting"
      @confirm="submit"
    >
      <label v-if="pendingAction === 'transfer'" class="ra-field">
        转交给（账号 userId）
        <input v-model.trim="transferTo" class="ra-input" placeholder="填写接手人的 userId" />
      </label>
      <label v-if="pendingAction === 'review'" class="ra-field">
        复核所属学期
        <input v-model.trim="reviewTerm" class="ra-input" placeholder="如 2026-2027-1" />
      </label>
    </AppConfirmDialog>
  </ModulePageShell>
</template>

<script>
import { ModulePageShell, ModuleToolbar, DataTable, StatusTag, LoadingState, ErrorState, EmptyState } from '@/components/business'
import AppConfirmDialog from '@/components/common/AppConfirmDialog.vue'
import { systemApi } from '@/modules/system/api/system.api'
import { toast } from '@/utils/toast'

const BUCKET_LABELS = {
  EXPIRING_SOON: '即将到期',
  EXPIRED_NOT_RECLAIMED: '过期未回收',
  UNREVIEWED_ACROSS_TERM: '跨学期未复核',
  UNKNOWN_SOURCE: '来源不明',
  HIGH_PRIV_MULTI: '多人持有高权角色'
}

export default {
  name: 'SystemRoleAssignmentView',
  components: {
    ModulePageShell, ModuleToolbar, DataTable, StatusTag,
    LoadingState, ErrorState, EmptyState, AppConfirmDialog
  },
  props: { ctx: { type: Object, required: true } },
  data() {
    return {
      loading: true,
      error: '',
      tab: 'members',
      bucket: '',
      rows: [],
      summary: {},
      identities: [],
      identityNote: '',
      dialogOpen: false,
      submitting: false,
      pendingAction: '',
      pendingRow: null,
      transferTo: '',
      reviewTerm: '',
      memberColumns: [
        { key: 'user', title: '成员与角色' },
        { key: 'validity', title: '有效期' },
        { key: 'source', title: '来源与原因' },
        { key: 'status', title: '状态' },
        { key: 'ops', title: '操作' }
      ],
      identityColumns: [
        { key: 'identity', title: '身份' },
        { key: 'subject', title: '人' },
        { key: 'scope', title: '覆盖对象' },
        { key: 'owner', title: '归属与权威表' }
      ]
    }
  },
  computed: {
    bucketList() {
      return Object.keys(BUCKET_LABELS).map((key) => ({
        key, label: BUCKET_LABELS[key], count: this.summary[key] || 0
      }))
    },
    dialogTitle() {
      return { revoke: '回收授权', transfer: '转交工作', review: '记录复核' }[this.pendingAction] || '确认'
    },
    dialogMessage() {
      if (!this.pendingRow) return ''
      const who = `${this.pendingRow.realName || this.pendingRow.loginName}（${this.pendingRow.roleCode}）`
      return {
        revoke: `回收 ${who} 的角色，下一次请求即失效，无需等待重新登录。`,
        transfer: `${who} 将立即失去该角色，接手人按同一有效期获得授权。`,
        review: `确认 ${who} 的长期授权仍然需要保留。`
      }[this.pendingAction] || ''
    }
  },
  created() { this.load() },
  methods: {
    statusTone(s) {
      return { ACTIVE: 'success', EXPIRED: 'warning', REVOKED: 'default' }[s] || 'default'
    },
    onAction(key) {
      if (key === 'refresh') return this.load()
      if (key === 'sweep') return this.sweep()
    },
    switchTab(tab) {
      if (this.tab === tab) return
      this.tab = tab
      this.load()
    },
    pickBucket(key) {
      this.bucket = this.bucket === key ? '' : key
      this.load()
    },
    ask(action, row) {
      this.pendingAction = action
      this.pendingRow = row
      this.transferTo = ''
      this.reviewTerm = ''
      this.dialogOpen = true
    },
    async sweep() {
      const res = await systemApi.sweepExpiredAssignments()
      if (res.code === 0) {
        toast.success(`已回收 ${res.data.count} 个账号的到期授权`)
        await this.load()
      } else toast.error(res.message)
    },
    async submit({ reason }) {
      if (!this.pendingRow) return
      const id = this.pendingRow.assignmentId
      this.submitting = true
      let res
      if (this.pendingAction === 'revoke') {
        res = await systemApi.revokeRoleAssignment(id, { reason, expectedVersion: this.pendingRow.version })
      } else if (this.pendingAction === 'transfer') {
        if (!/^\d+$/.test(this.transferTo)) {
          this.submitting = false
          toast.error('请填写接手人的 userId（纯数字）')
          return
        }
        res = await systemApi.transferRoleAssignment(id, {
          toUserId: this.transferTo, reason, expectedVersion: this.pendingRow.version
        })
      } else {
        res = await systemApi.reviewRoleAssignment(id, { term: this.reviewTerm, reason })
      }
      this.submitting = false
      if (res.code === 0) {
        toast.success('已完成')
        this.dialogOpen = false
        this.pendingRow = null
        await this.load()
      } else {
        toast.error(res.message)
        if (res.bizCode === 'DATA_CONFLICT') {
          this.dialogOpen = false
          await this.load()
        }
      }
    },
    async load() {
      this.loading = true
      this.error = ''
      if (this.tab === 'members') {
        const res = await systemApi.listRoleAssignments({ bucket: this.bucket })
        if (res.code === 0) {
          this.rows = res.data.list || []
          this.summary = res.data.summary || {}
        } else this.error = res.message
      } else {
        const res = await systemApi.listBusinessIdentities()
        if (res.code === 0) {
          this.identities = res.data.list || []
          this.identityNote = res.data.note || ''
        } else this.error = res.message
      }
      this.loading = false
    }
  }
}
</script>

<style scoped>
@import '@/styles/module-page.css';
.ra-tabs {
  display: flex;
  gap: var(--space-3);
  border-bottom: 1px solid var(--border-light);
  padding-bottom: var(--space-2);
}
.ra-tabs .is-active { color: var(--primary-600); font-weight: var(--font-weight-semibold); }
.ra-buckets { display: flex; flex-wrap: wrap; gap: var(--space-3); }
.ra-bucket {
  min-width: 132px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  background: var(--bg-container);
  cursor: pointer;
  text-align: left;
}
.ra-bucket.is-active { border-color: var(--color-primary); }
.ra-bucket__num { display: block; font-size: var(--font-size-xl); font-weight: var(--font-weight-semibold); }
.ra-bucket__label { display: block; color: var(--text-secondary); font-size: var(--font-size-xs); }
.ra-field { display: block; margin: var(--space-2) 0; }
.ra-input {
  display: block;
  width: 100%;
  margin-top: 4px;
  padding: 6px 10px;
  border: 1px solid var(--border-base);
  border-radius: var(--radius-sm);
}
</style>
