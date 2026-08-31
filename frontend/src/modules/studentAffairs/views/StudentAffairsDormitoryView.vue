<template>
  <AppPageShell
    title="宿舍管理"
    subtitle="宿舍看板、楼栋、房间、床位、入住退宿、调宿审批、检查异常和夜不归宿风险入口。"
    data-scope-name="后端按宿舍/楼栋范围返回"
    watermark-purpose="宿舍管理查看"
  >
    <template #actions>
      <AppPermissionButton :allowed="canBtn('studentAffairs.dorm.view')" code="studentAffairs.dorm.view" variant="secondary" @click="load">
        刷新
      </AppPermissionButton>
      <AppPermissionButton :allowed="canBtn('studentAffairs.risk.view')" code="studentAffairs.risk.view" variant="secondary" @click="$router.push('/admin/student-affairs/risk')">
        宿舍风险
      </AppPermissionButton>
    </template>

    <AppGlobalState
      :state="pageState"
      :description="errorMessage"
      loading-text="正在加载宿舍管理数据…"
      @retry="load"
      @back="$router.push('/admin/student-affairs/dashboard')"
    >
      <div class="dorm-overview">
        <AppSectionCard title="住宿运行结论">
          <div class="dorm-conclusion">
            <AppStatusTag :type="dormConclusion.type" :label="dormConclusion.label" />
            <p>{{ dormConclusion.text }}</p>
          </div>
        </AppSectionCard>

        <AppSectionCard title="待办工作区">
          <div class="dorm-entry-list">
            <button
              v-for="item in todoEntries"
              :key="item.path"
              type="button"
              class="dorm-entry"
              :disabled="!canBtn(item.permission)"
              @click="go(item.path)"
            >
              <strong>{{ item.title }}</strong>
              <span>{{ item.description }}</span>
              <small>聚合待办数：后端未配置 · 进入工作区查看真实列表</small>
            </button>
          </div>
        </AppSectionCard>

        <AppSectionCard title="房态与入住入口">
          <div class="dorm-entry-list">
            <button
              v-for="item in roomStateEntries"
              :key="item.path"
              type="button"
              class="dorm-entry dorm-entry--primary"
              :disabled="!canBtn(item.permission)"
              @click="go(item.path)"
            >
              <strong>{{ item.title }}</strong>
              <span>{{ item.description }}</span>
            </button>
          </div>
        </AppSectionCard>
      </div>

      <div class="sa-grid">
        <AppMetricCard title="总床位" :value="occupancy.totalBeds || 0" unit="张" />
        <AppMetricCard title="已入住" :value="occupancy.occupiedBeds || 0" unit="张" accent="success" />
        <AppMetricCard title="空床" :value="occupancy.vacantBeds || 0" unit="张" />
        <AppMetricCard title="入住率" :value="rateLabel" accent="primary" />
      </div>

      <div class="sa-grid sa-grid--two">
        <AppSectionCard title="楼栋管理">
          <ul class="sa-list">
            <li v-for="b in buildings" :key="b.buildingId" :class="{ active: b.buildingId === selectedBuildingId }">
              <button type="button" @click="selectBuilding(b.buildingId)">
                <strong>{{ b.buildingName }}</strong>
                <small>{{ b.genderLimit }} · 空床 {{ b.vacantBeds ?? 0 }}/{{ b.totalBeds ?? 0 }}</small>
              </button>
              <AppStatusTag :status="b.status" />
            </li>
          </ul>
        </AppSectionCard>

        <AppSectionCard title="房间管理">
          <ul class="sa-list">
            <li v-for="room in rooms" :key="room.roomId" :class="{ active: room.roomId === selectedRoomId }">
              <button type="button" @click="selectRoom(room.roomId)">
                <strong>{{ room.roomNo }}</strong>
                <small>{{ room.floorNo }} 层 · 容量 {{ room.capacity }} · 空床 {{ room.vacantBeds }}</small>
              </button>
              <AppStatusTag :status="room.status" />
            </li>
          </ul>
        </AppSectionCard>

        <AppSectionCard title="床位管理 / 入住退宿">
          <div class="sa-bed-grid">
            <button
              v-for="bed in beds"
              :key="bed.bedId"
              type="button"
              class="sa-bed"
              :aria-label="`${bed.bedNo}号床，${bed.status === 'OCCUPIED' ? '查看入住与退宿' : '办理入住'}`"
              @click="openBedAction(bed)"
            >
              <strong>{{ bed.bedNo }}</strong>
              <AppStatusTag
                :type="bed.status === 'OCCUPIED' ? 'warning' : 'success'"
                :label="bed.status === 'OCCUPIED' ? '已入住' : '空床'"
                size="sm"
              />
              <small>{{ bed.occupantName || '空床' }}</small>
              <small class="sa-bed__action">{{ bed.status === 'OCCUPIED' ? '查看入住与退宿 →' : '办理入住 →' }}</small>
            </button>
          </div>
        </AppSectionCard>

        <AppSectionCard title="调宿申请 / 审批入口">
          <div class="sa-bridge">
            <AppStatusTag type="processing" label="审批流已接后端" />
            <p>调宿按“辅导员审核 → 宿管审核 → 执行”流转，执行后回写学生宿舍记录。</p>
          </div>
        </AppSectionCard>

        <AppSectionCard title="宿舍检查 / 夜不归宿">
          <div class="sa-bridge">
            <AppRiskTag level="MEDIUM" label="异常转风险" />
            <p>宿舍检查异常会回写宿舍异常并生成 DORM 来源风险，B3 风险预警页承接处置。</p>
          </div>
        </AppSectionCard>

        <AppSectionCard title="宿舍归档入口">
          <AppDescriptionList :items="configItems" bordered />
        </AppSectionCard>
      </div>
    </AppGlobalState>
  </AppPageShell>
</template>

<script>
import {
  AppDescriptionList,
  AppGlobalState,
  AppMetricCard,
  AppPageShell,
  AppPermissionButton,
  AppRiskTag,
  AppSectionCard,
  AppStatusTag
} from '@/components/common'
import studentAffairsApi from '@/modules/studentAffairs/api/studentAffairsB.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'


export default {
  name: 'StudentAffairsDormitoryView',
  props: { ctx: { type: Object, default: null } },
  components: {
    AppDescriptionList,
    AppGlobalState,
    AppMetricCard,
    AppPageShell,
    AppPermissionButton,
    AppRiskTag,
    AppSectionCard,
    AppStatusTag
  },
  data() {
    return {
      loading: true,
      errorMessage: '',
      occupancy: {},
      buildings: [],
      rooms: [],
      beds: [],
      config: {},
      selectedBuildingId: '',
      selectedRoomId: ''
    }
  },
  computed: {
    pageState() {
      if (this.loading) return 'loading'
      if (this.errorMessage) return 'error'
      return 'ready'
    },
    rateLabel() {
      return `${Math.round((this.occupancy.occupancyRate || 0) * 100)}%`
    },
    dormConclusion() {
      if (!this.buildings.length) {
        return {
          type: 'warning',
          label: '房源未配置',
          text: '当前数据范围内没有可见楼栋。请先进入房源管理配置，或联系管理员核对宿舍楼数据范围。'
        }
      }
      const total = Number(this.occupancy.totalBeds || 0)
      const vacant = Number(this.occupancy.vacantBeds || 0)
      return {
        type: vacant > 0 ? 'success' : 'warning',
        label: vacant > 0 ? '房态已同步' : '暂无空床',
        text: `当前范围共 ${this.buildings.length} 栋、${total} 张床，空床 ${vacant} 张；以下数据均来自宿舍正式接口。`
      }
    },
    todoEntries() {
      return [
        {
          title: '调宿与退宿',
          description: '审核、执行并回写住宿记录',
          path: '/admin/student-affairs/dorm/transfer',
          permission: 'studentAffairs.dorm.view'
        },
        {
          title: '宿舍检查',
          description: '创建检查任务并登记检查结果',
          path: '/admin/student-affairs/dorm/check',
          permission: 'studentAffairs.dorm.view'
        },
        {
          title: '宿舍异常',
          description: '处理检查异常与夜不归宿风险',
          path: '/admin/student-affairs/dorm/exception',
          permission: 'studentAffairs.dorm.view'
        }
      ]
    },
    roomStateEntries() {
      return [
        {
          title: '房源管理',
          description: '查看楼栋、房间、床位真实状态',
          path: '/admin/student-affairs/dorm/resource',
          permission: 'studentAffairs.dorm.view'
        },
        {
          title: '入住管理',
          description: '办理入住、换床与退宿',
          path: '/admin/student-affairs/dorm/checkin',
          permission: 'studentAffairs.dorm.view'
        },
        {
          title: '宿舍统计',
          description: '按楼栋查看入住率并下钻房态',
          path: '/admin/student-affairs/dorm/stats',
          permission: 'studentAffairs.dorm.view'
        }
      ]
    },
    configItems() {
      return [
        { label: '分配模式', value: this.config.assignMode || '未设置' },
        { label: '学生自选', value: this.config.selfSelectEnabled ? '已开放' : '未开放' },
        { label: '学生提示', value: this.config.studentNotice || '未设置', span: 2 },
        { label: '归档状态', value: this.config.archived ? '已归档' : '未归档' }
      ]
    }
  },
  created() {
    this.load()
  },
  methods: {
    canBtn(code) { return canCode(this.ctx, code) },
    go(path) { this.$router.push(path) },
    openBedAction(bed) {
      this.$router.push({
        name: 'student-affairs-dorm-checkin',
        query: {
          buildingId: String(this.selectedBuildingId),
          roomId: String(this.selectedRoomId),
          bedId: String(bed.bedId)
        }
      })
    },
    async load() {
      this.loading = true
      this.errorMessage = ''
      try {
        const [occRes, buildingRes, configRes] = await Promise.all([
          studentAffairsApi.getDormOccupancy(),
          studentAffairsApi.listDormBuildings({ page: 1, pageSize: 100 }),
          studentAffairsApi.getDormConfig().catch(() => ({ data: {} }))
        ])
        this.occupancy = occRes.data || {}
        this.buildings = buildingRes.data.items || []
        this.config = configRes.data || {}
        this.selectedBuildingId = this.selectedBuildingId || this.buildings[0]?.buildingId || ''
        await this.loadRooms()
      } catch (e) {
        this.errorMessage = e?.message || '宿舍管理数据加载失败'
      } finally {
        this.loading = false
      }
    },
    async loadRooms() {
      if (!this.selectedBuildingId) {
        this.rooms = []
        this.beds = []
        return
      }
      const res = await studentAffairsApi.listDormRooms(this.selectedBuildingId, { page: 1, pageSize: 100 })
      this.rooms = res.data.items || []
      this.selectedRoomId = this.rooms[0]?.roomId || ''
      await this.loadBeds()
    },
    async loadBeds() {
      if (!this.selectedRoomId) {
        this.beds = []
        return
      }
      const res = await studentAffairsApi.listDormBeds(this.selectedRoomId)
      this.beds = res.data.items || []
    },
    async selectBuilding(id) {
      this.selectedBuildingId = id
      await this.loadRooms()
    },
    async selectRoom(id) {
      this.selectedRoomId = id
      await this.loadBeds()
    }
  }
}
</script>

<style scoped>
.sa-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-4);
}
.dorm-overview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-4);
  margin-bottom: var(--space-4);
}
.dorm-conclusion {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
}
.dorm-conclusion p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}
.dorm-entry-list {
  display: grid;
  gap: var(--space-2);
}
.dorm-entry {
  width: 100%;
  display: grid;
  gap: 4px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  background: var(--bg-card);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
}
.dorm-entry--primary {
  border-color: var(--primary-200);
  background: var(--primary-50);
}
.dorm-entry span,
.dorm-entry small {
  color: var(--text-tertiary);
}
.dorm-entry:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}
.sa-grid--two {
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
}
.sa-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--space-2);
}
.sa-list li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
}
.sa-list li.active {
  border-color: var(--primary-300);
  background: var(--primary-50);
}
.sa-list button,
.sa-bed {
  border: 0;
  background: transparent;
  text-align: left;
  color: inherit;
  cursor: pointer;
}
.sa-bed__action {
  color: var(--primary-700, #1d4ed8) !important;
  font-weight: 600;
}
.sa-list small,
.sa-bed small {
  display: block;
  color: var(--text-tertiary);
  margin-top: 2px;
}
.sa-bed-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: var(--space-2);
}
.sa-bed {
  min-height: 76px;
  padding: var(--space-3);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-base);
  display: grid;
  gap: var(--space-1);
}
.sa-bridge {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  color: var(--text-secondary);
}
.sa-bridge p {
  margin: 0;
  line-height: 1.6;
}
</style>

