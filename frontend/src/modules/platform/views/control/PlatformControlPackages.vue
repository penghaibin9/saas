<template>
  <ModulePageShell title="套餐管理" subtitle="5 档套餐：价格 / 时长 / 容量 / 功能，修改全平台生效" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <LoadingState v-if="loading" text="正在加载套餐…" />
    <div v-else class="pcp__grid">
      <AppCard v-for="p in list" :key="p.packageCode" class="pcp__card" :variant="p.packageCode === 'professional' ? 'elevated' : 'subtle'">
        <div class="pcp__head">
          <b>{{ p.packageName }}</b>
          <StatusTag :type="p.enabled ? 'success' : 'default'" :label="p.enabled ? '在售' : '停售'" />
        </div>
        <label class="pcp__field"><span>价格（元/年）</span><input v-model.number="p.price" type="number" class="pcp__input" /></label>
        <label class="pcp__field"><span>时长（天）</span><input v-model.number="p.durationDays" type="number" class="pcp__input" /></label>
        <label class="pcp__field"><span>学生上限</span><input v-model.number="p.maxStudents" type="number" class="pcp__input" /></label>
        <label class="pcp__field"><span>账号上限</span><input v-model.number="p.maxUsers" type="number" class="pcp__input" /></label>
        <label class="pcp__field"><span>存储（MB）</span><input v-model.number="p.storageLimitMb" type="number" class="pcp__input" /></label>
        <AppButton variant="primary" @click="save(p)">保存</AppButton>
      </AppCard>
    </div>
  </ModulePageShell>
</template>

<script>
import { AppButton, AppCard } from '@/components/ui'
import { LoadingState, ModulePageShell, StatusTag } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformControlPackages',
  components: { AppButton, AppCard, LoadingState, ModulePageShell, StatusTag },
  data() {
    return { loading: true, list: [] }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      const res = await platformControlApi.listPackages()
      this.loading = false
      if (res.code === 0) this.list = res.data.list
      else toast.error(res.message)
    },
    async save(p) {
      const reason = window.prompt('请输入套餐变更原因（至少 5 个字符）')
      if (!reason || reason.trim().length < 5) return
      const res = await platformControlApi.updatePackage(p.packageCode, {
        price: p.price, durationDays: p.durationDays, maxStudents: p.maxStudents,
        maxUsers: p.maxUsers, storageLimitMb: p.storageLimitMb,
        expectedVersion: Number(p.version || 0), reason: reason.trim()
      })
      if (res.code === 0) { toast.success('「' + p.packageName + '」已保存'); this.load() }
      else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
.pcp__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-3);
}
.pcp__card {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
.pcp__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--t1);
}
.pcp__field {
  display: flex;
  flex-direction: column;
  gap: 2px;
  font-size: 12px;
  color: var(--text-secondary);
}
.pcp__input {
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--card-b);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--t1);
  font-size: 13px;
  font-family: inherit;
}
.pcp__input:focus {
  outline: none;
  border-color: var(--glow);
}
</style>
