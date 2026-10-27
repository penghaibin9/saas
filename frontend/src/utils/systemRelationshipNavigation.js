export function systemRelationshipReturnTo(value) {
  return typeof value === 'string' && /^\/admin\/system\/(?:role-assignments|master-data|business-relations)(?:\?|$)/.test(value) ? value : ''
}

export function relationshipObjectDestination(item, returnTo) {
  const route = item?.route
  if (!route || !/^\/admin\/(?:campus-service\/classes|academic-affairs\/teaching-tasks|academic-affairs\/roster|graduation\/students|internship\/students)\/\d+$/.test(route.path)) return null
  if (Object.entries(route.query || {}).some(([key, value]) => !['batchId', 'teachingTaskId'].includes(key) || !/^\d+$/.test(String(value)))) return null
  return { path: route.path, query: { ...route.query, returnTo: systemRelationshipReturnTo(returnTo) || undefined } }
}
