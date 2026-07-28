import { clearSensitiveLocalDrafts } from '@/services/sensitiveDraftStorage'

const STORAGE_KEY = 'gx_session_v1'

function readSnapshot() {
  try {
    const raw = uni.getStorageSync(STORAGE_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (e) {
    return null
  }
}

function writeIdentity(store) {
  try {
    const snapshot = readSnapshot() || {}
    snapshot.identity = {
      tenantId: store.identity?.tenantId ?? null,
      userId: store.identity?.userId ?? null,
      activeContextId: store.identity?.activeContextId ?? null,
      studentId: store.identity?.studentId ?? null,
      studentNo: store.identity?.studentNo ?? null,
      realName: store.identity?.realName ?? null,
      roleCode: store.identity?.roleCode ?? null,
      roleName: store.identity?.roleName ?? null
    }
    uni.setStorageSync(STORAGE_KEY, JSON.stringify(snapshot))
  } catch (e) {
    // 本地持久化失败不影响服务端令牌和当前内存会话。
  }
}

/**
 * 教务四端对会话的增量增强。
 *
 * 共享 session store 保持当前 main 原样；本插件仅补充稳定 studentId、租户/身份上下文
 * 持久化和敏感成绩草稿清理，避免覆盖主线新增的实习批次清理与角色切换回滚。
 */
export function academicSessionPlugin({ store }) {
  if (store.$id !== 'session') return

  store.$patch({
    identity: {
      tenantId: null,
      activeContextId: null,
      ...(store.identity || {})
    }
  })

  const basePersist = store.persist.bind(store)
  store.persist = (...args) => {
    const result = basePersist(...args)
    writeIdentity(store)
    return result
  }

  const baseRestore = store.restore.bind(store)
  store.restore = (...args) => {
    const result = baseRestore(...args)
    const snapshot = readSnapshot()
    if (snapshot?.identity) {
      store.identity = {
        tenantId: null,
        activeContextId: null,
        ...(store.identity || {}),
        ...snapshot.identity
      }
    }
    return result
  }

  const baseApplyRealUser = store.applyRealUser.bind(store)
  store.applyRealUser = (data) => {
    const result = baseApplyRealUser(data)
    if (data) {
      const role = data.currentRole || {}
      store.identity = {
        ...store.identity,
        tenantId: data.tenantId != null ? data.tenantId : store.identity.tenantId,
        activeContextId: data.activeContextId || role.contextId || store.identity.activeContextId
      }
      store.persist()
    }
    return result
  }

  const baseSetStudentIdentity = store.setStudentIdentity.bind(store)
  store.setStudentIdentity = (profile) => {
    const result = baseSetStudentIdentity(profile)
    store.persist()
    return result
  }

  const baseHydrateStudentProfile = store.hydrateStudentProfile.bind(store)
  store.hydrateStudentProfile = (profile) => {
    const result = baseHydrateStudentProfile(profile)
    const base = profile?.base || {}
    if (base.studentId != null) {
      store.identity = { ...store.identity, studentId: base.studentId }
      store.persist()
    }
    return result
  }

  const baseLogout = store.logout.bind(store)
  store.logout = (...args) => {
    clearSensitiveLocalDrafts()
    return baseLogout(...args)
  }
}

export default academicSessionPlugin
