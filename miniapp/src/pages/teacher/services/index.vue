<template>
  <view class="teacher-shell">
    <MobileTeacherHero title="服务大厅" subtitle="教师事务，便捷办理" :role-label="roleLabel" />
    <view class="ts-pad service-search-wrap"><view class="ts-search"><MobileShellIcon name="search" tone="gray" :size="22" /><input v-model="keyword" placeholder="搜索服务" maxlength="40" confirm-type="search" aria-label="搜索服务" /></view></view>
    <MobileGlobalState v-if="state !== 'ready'" :state="state" @retry="load" />
    <view v-else>
      <scroll-view v-show="!keyword.trim()" scroll-x class="ts-tabs">
        <view class="ts-tabs-inner"><button v-for="category in categories" :key="category" class="ts-tab ts-plain" :class="{ 'is-active': selectedCategory === category }" @click="selectedCategory = category">{{ category }}</button></view>
      </scroll-view>
      <view class="ts-pad service-content">
        <view v-if="batchName" class="ts-muted service-batch">当前实习批次：{{ batchName }}</view>
        <view v-if="groups.length" class="ts-panel">
          <view v-for="(group, index) in groups" :key="group.label" class="service-group">
            <view class="service-group__heading"><view class="ts-marker" :class="'service-marker-' + (index % 3)" /><text>{{ group.label }}</text><view class="service-rule" /></view>
            <view class="service-grid"><button v-for="service in group.items" :key="service.key" class="service-item ts-plain" @click="open(service)">
              <MobileShellIcon :name="visual(service.label).icon" :tone="visual(service.label).tone" :size="25" round />
              <view class="ts-body"><text class="service-name">{{ service.label }}</text><text v-if="service.disabledReason" class="ts-muted">{{ service.disabledReason }}</text></view>
            </button></view>
          </view>
        </view>
        <view v-else class="ts-panel ts-empty">{{ keyword.trim() ? '没有找到相关服务，请换个名称试试。' : '当前身份暂无可用服务。' }}</view>
        <button v-if="!keyword.trim()" class="service-integrity ts-plain" @click="go('/pages/teacher/platform-integrity/index')"><MobileShellIcon name="shield-check" tone="gray" :size="18" /><text>数据完整性核查</text><MobileShellIcon name="chevron-right" tone="gray" :size="16" /></button>
      </view>
    </view>
    <MobileTeacherTabBar ref="badges" active="service" />
  </view>
</template>
<script>
import { useSessionStore } from '@/stores/session'
import { useInternshipContextStore } from '@/stores/internshipContext'
import { me } from '@/services/realApi'
import { normalizeError } from '@/services/request'
import { currentSessionGeneration } from '@/services/sessionGeneration.mjs'
import { teacherServices, teacherVisual } from '@/services/teacherServiceCatalog.mjs'
import { go, toast } from '@/utils/nav'
export default {
  data: () => ({ state: 'loading', services: [], keyword: '', selectedCategory: '全部', roleLabel: '', batchName: '', loadSeq: 0 }),
  computed: {
    categories() { return ['全部', ...new Set(this.services.map(item => item.group))] },
    groups() {
      const query = this.keyword.trim().toLowerCase(), groups = []
      for (const item of this.services) {
        if (query ? !item.label.toLowerCase().includes(query) : this.selectedCategory !== '全部' && item.group !== this.selectedCategory) continue
        let group = groups.find(group => group.label === item.group)
        if (!group) { group = { label: item.group, items: [] }; groups.push(group) }
        group.items.push(item)
      }
      return groups
    }
  },
  onShow() { this.load(); this.$refs?.badges?.refresh() },
  onHide() { this.loadSeq++; this.$refs?.badges?.invalidate() },
  onUnload() { this.loadSeq++ },
  onPullDownRefresh() { this.load().finally(() => uni.stopPullDownRefresh()) },
  methods: {
    go, visual: teacherVisual,
    async load() {
      const seq = ++this.loadSeq, generation = currentSessionGeneration()
      const current = () => seq === this.loadSeq && generation === currentSessionGeneration()
      this.state = 'loading'; this.services = []; this.batchName = ''
      try {
        const session = useSessionStore(), identity = await me()
        if (!current()) return
        session.applyRealUser(identity)
        this.roleLabel = session.roleConfig.label
        if (!session.isTeacher) { this.state = 'forbidden'; return }
        if (this._role !== session.currentRole) { this.keyword = ''; this.selectedCategory = '全部' }
        this._role = session.currentRole
        let context = null
        if (session.currentRole === 'intern_mentor') {
          context = useInternshipContextStore(); context.restore(); await context.load()
          if (!current()) return
          this.batchName = context.selectedBatch?.name || ''
        }
        this.services = teacherServices(session.roleConfig, session.currentRole, context)
        if (!this.categories.includes(this.selectedCategory)) this.selectedCategory = '全部'
        this.state = 'ready'
      } catch (error) { if (current()) this.state = normalizeError(error).pageState || 'error' }
    },
    open(service) {
      if (this.state !== 'ready' || this._role !== useSessionStore().currentRole) return
      if (!service.path) return toast(service.disabledReason)
      go(service.path)
    }
  }
}
</script>
<style lang="scss">
@import '@/styles/teacher-shell.scss';
.teacher-shell {
.service-content { padding-top: 10px; }
.service-search-wrap { padding-top: 10px; }
.service-group { padding: 4px 0 14px; }
.service-group__heading { display: flex; align-items: center; gap: 8px; min-height: 50px; font-size: 17px; font-weight: 600; }
.service-rule { flex: 1; height: 1px; margin-left: 6px; background: #e4e9f1; }
.service-marker-1 { background: #12b88b !important; }.service-marker-2 { background: #e99a00 !important; }
.service-grid { display: grid; grid-template-columns: repeat(2,minmax(0,1fr)); column-gap: 10px; row-gap: 12px; }
.service-item { display: flex; align-items: center; gap: 8px; min-height: 72px; width: 100%; }
.service-item .shell-icon--round { width: 52px !important; height: 52px !important; }
.service-name { font-size: 14px; line-height: 1.6; color: #142440; overflow-wrap: anywhere; }
.service-integrity { display: flex; align-items: center; gap: 8px; min-height: 44px; margin: 8px 4px 0; color: #75839a; font-size: 12px; }
.service-batch { padding: 4px 8px 12px; }
}
</style>
