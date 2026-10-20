let sessionGeneration = 0

export function currentSessionGeneration() {
  return sessionGeneration
}

export function advanceSessionGeneration() {
  sessionGeneration += 1
  return sessionGeneration
}

export function captureSessionSnapshot(accessToken, refreshToken) {
  return {
    generation: currentSessionGeneration(),
    accessToken: String(accessToken || ''),
    refreshToken: String(refreshToken || '')
  }
}

export function isSessionSnapshotCurrent(snapshot, accessToken, refreshToken) {
  return !!snapshot &&
    snapshot.generation === currentSessionGeneration() &&
    snapshot.accessToken === String(accessToken || '') &&
    snapshot.refreshToken === String(refreshToken || '')
}

export function sessionChangedError() {
  return {
    code: 'SESSION_CHANGED',
    bizCode: 'SESSION_CHANGED',
    biz: true,
    staleSession: true,
    message: '登录状态已变化，请重试'
  }
}

export function assertSessionSnapshot(snapshot, accessToken, refreshToken) {
  if (!isSessionSnapshotCurrent(snapshot, accessToken, refreshToken)) throw sessionChangedError()
  return snapshot
}

export async function guardSessionPromise(promise, {
  snapshot,
  getAccessToken,
  getRefreshToken,
  onSuccess,
  onCurrentError
}) {
  try {
    const value = await promise
    assertSessionSnapshot(snapshot, getAccessToken(), getRefreshToken())
    return onSuccess ? await onSuccess(value) : value
  } catch (error) {
    if (!isSessionSnapshotCurrent(snapshot, getAccessToken(), getRefreshToken())) {
      throw sessionChangedError()
    }
    if (onCurrentError) return onCurrentError(error)
    throw error
  }
}

export function __resetSessionGenerationForTests(value = 0) {
  sessionGeneration = Number(value) || 0
}
