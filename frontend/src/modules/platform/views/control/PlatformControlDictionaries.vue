<template>
  <ModulePageShell title="字典管理" subtitle="平台默认字典（学校类型 / 状态 / 风险等级等 12 类），可增改字典项" role-name="平台超级管理员" data-scope-name="全平台（跨租户）">
    <LoadingState v-if="loading" text="正在加载字典…" />
    <div v-else class="pcd__grid">
      <AppCard v-for="(items, code) in dicts" :key="code" class="pcd__card">
        <AppSectionHeader :title="dictLabels[code] || code" />
        <ul class="pcd__items">
          <li v-for="(it, i) in items" :key="code + i" class="pcd__item">
            <input v-model="it.code" class="pcd__input pcd__input--code" placeholder="code" />
            <input v-model="it.label" class="pcd__input" placeholder="显示名" />
            <input v-model="it.enabled" type="checkbox" title="启用" />
          </li>
        </ul>
        <div class="pcd__ops">
          <AppButton variant="ghost" @click="items.push({ code: '', label: '', enabled: true })">+ 加项</AppButton>
          <AppButton variant="primary" @click="save(code, items)">保存</AppButton>
        </div>
      </AppCard>
    </div>
  </ModulePageShell>
</template>

<script>
import { AppButton, AppCard, AppSectionHeader } from '@/components/ui'
import { LoadingState, ModulePageShell } from '@/components/business'
import { platformControlApi } from '@/modules/platform/api/platformControl.api'
import { toast } from '@/utils/toast'

export default {
  name: 'PlatformControlDictionaries',
  components: { AppButton, AppCard, AppSectionHeader, LoadingState, ModulePageShell },
  data() {
    return {
      loading: true,
      dicts: {},
      dictLabels: {
        schoolType: '学校类型', studentStatus: '学生状态', riskLevel: '风险等级',
        approvalStatus: '审批状态', fileType: '文件类型', serviceType: '在校服务类型',
        internshipStatus: '实习状态', graduationStatus: '毕设阶段', employmentStatus: '就业状态',
        noticeType: '公告类型', tenantStatus: '租户状态', packageType: '套餐类型'
      }
    }
  },
  created() {
    this.load()
  },
  methods: {
    async load() {
      this.loading = true
      const res = await platformControlApi.getDictionaries()
      this.loading = false
      if (res.code === 0) this.dicts = res.data.dictionaries
      else toast.error(res.message)
    },
    async save(code, items) {
      const valid = items.filter((i) => i.code && i.label)
      const res = await platformControlApi.putDictionary(code, valid)
      if (res.code === 0) toast.success('「' + (this.dictLabels[code] || code) + '」已保存')
      else toast.error(res.message)
    }
  }
}
</script>

<style scoped>
.pcd__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-3);
}
.pcd__card {
  padding: var(--space-4);
}
.pcd__items {
  list-style: none;
  margin: var(--space-2) 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}
.pcd__item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.pcd__input {
  flex: 1;
  height: 30px;
  padding: 0 8px;
  border: 1px solid var(--card-b);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.85);
  color: var(--t1);
  font-size: 12px;
  font-family: inherit;
  min-width: 0;
}
.pcd__input--code {
  flex: 0 0 96px;
}
.pcd__input:focus {
  outline: none;
  border-color: var(--glow);
}
.pcd__ops {
  display: flex;
  gap: var(--space-2);
  justify-content: flex-end;
}
</style>
