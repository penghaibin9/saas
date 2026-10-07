let studentHomeVersion = 0
let teacherWorkbenchVersion = 0

export function getStudentHomeVersion() {
  return studentHomeVersion
}

export function getTeacherWorkbenchVersion() {
  return teacherWorkbenchVersion
}

export function markStudentHomeDirty() {
  studentHomeVersion += 1
  return studentHomeVersion
}

export function markTeacherWorkbenchDirty() {
  teacherWorkbenchVersion += 1
  return teacherWorkbenchVersion
}

export function markMobileViewsDirty(rawPath) {
  const requestPath = String(rawPath || '')
  if (requestPath.startsWith('/auth/')) {
    markStudentHomeDirty()
    markTeacherWorkbenchDirty()
    return
  }
  if (requestPath.startsWith('/mobile/teacher/') ||
      requestPath.startsWith('/teacher-mobile/') ||
      requestPath.startsWith('/todos/')) {
    markTeacherWorkbenchDirty()
    return
  }
  if (requestPath.startsWith('/mobile/')) markStudentHomeDirty()
}
