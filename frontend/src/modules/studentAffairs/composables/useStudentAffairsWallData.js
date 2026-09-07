import { computed, onBeforeUnmount, onMounted, ref, unref, watch } from 'vue'
import { studentAffairsApi } from '@/modules/studentAffairs/api/studentAffairs.api'
import { leaveApi } from '@/modules/studentAffairs/api/leave.api'
import { canCode } from '@/modules/studentAffairs/composables/permission'
import { WALL_ROUTES } from '@/modules/studentAffairs/config/studentAffairsWall.contract'
import { projectStudentAffairsWall, wallPacket } from './studentAffairsWallProjection.js'

const blankSnapshot = () => ({ metrics: {}, breakdown: [], breakdownStatus: 'MISSING', scope: '当前授权范围', brand: '学工中心', receivedAt: '', sourceTimes: {}, reconcile: null })
const contextIdentity = ctx => JSON.stringify([ctx?.ctxKey || '', ctx?.currentRole?.roleCode || '', ctx?.dataScope || null, ctx?.permissionPatterns || null])

export function useStudentAffairsWallData(contextRef, { interval = 60000 } = {}) {
  const snapshot = ref(blankSnapshot())
  const loading = ref(false)
  const errorMessage = ref('')
  const autoRefresh = ref(true)
  let timer = null
  let epoch = 0
  const context = computed(() => unref(contextRef) || null)
  const contextKey = computed(() => contextIdentity(context.value))

  async function load() {
    if (loading.value || !context.value) return
    const run = ++epoch
    const owner = contextKey.value
    loading.value = true
    errorMessage.value = ''
    const ctx = context.value
    try {
      // Each source can fail independently; never retain a previous successful
      // value as current data when that source becomes unavailable.
      const read = async (permission, request) => {
        if (!Array.isArray(ctx.permissionPatterns) || !canCode(ctx, permission)) return { status: 'RESTRICTED' }
        try { return wallPacket(await request()) } catch (error) {
          return wallPacket({ code: error?.response?.data?.code ?? error?.response?.status ?? error?.status ?? error?.code, message: '统计暂不可用，请重试' })
        }
      }
      const [dashboard, cockpit, leaveTypes] = await Promise.all([
        read('studentAffairs.dashboard.view', () => studentAffairsApi.getDashboard()),
        read('studentAffairs.stats.view', () => studentAffairsApi.getStatsCockpit()),
        read('studentAffairs.leave.view', () => leaveApi.stats({ groupBy: 'TYPE' }))
      ])
      if (run !== epoch || owner !== contextKey.value) return
      snapshot.value = projectStudentAffairsWall({ dashboard, cockpit, leaveTypes, context: ctx, receivedAt: new Date().toISOString() })
      if ([dashboard, cockpit, leaveTypes].some(packet => packet.status === 'ERROR') || Object.values(snapshot.value.metrics).some(item => item.status === 'ERROR')) errorMessage.value = '部分统计暂不可用，失败指标已标记，请重试。'
    } catch {
      if (run === epoch) {
        snapshot.value = blankSnapshot()
        errorMessage.value = '学工大屏暂时无法更新，请重试'
      }
    } finally {
      if (run === epoch) loading.value = false
    }
  }

  async function authorize(routeKey) {
    const target = WALL_ROUTES[routeKey]
    const owner = contextKey.value
    if (!target || !canCode(context.value, target.permission)) return null
    try {
      const latest = await studentAffairsApi.getContext()
      if (owner !== contextKey.value || latest.code !== 0 || contextIdentity(latest.data) !== owner || !Array.isArray(latest.data?.permissionPatterns) || !canCode(latest.data, target.permission)) return null
      return target.path
    } catch {
      if (owner === contextKey.value) errorMessage.value = '无法确认当前访问权限，请重试'
      return null
    }
  }

  function onVisibility() { if (!document.hidden && autoRefresh.value) load() }
  watch(contextKey, () => { ++epoch; loading.value = false; errorMessage.value = ''; snapshot.value = blankSnapshot(); load() }, { flush: 'sync' })
  onMounted(() => { load(); timer = window.setInterval(() => { if (autoRefresh.value && !document.hidden) load() }, interval); document.addEventListener('visibilitychange', onVisibility) })
  onBeforeUnmount(() => { ++epoch; window.clearInterval(timer); document.removeEventListener('visibilitychange', onVisibility) })
  return { snapshot, loading, errorMessage, autoRefresh, load, authorize }
}
