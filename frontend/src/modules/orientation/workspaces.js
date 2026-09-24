const base = '/admin/orientation'
const page = (label, suffix = '') => ({ label, path: base + suffix })

// 每项能力仍有正式页面；侧栏按办理任务收敛，页内导航承接原入口。
export const ORIENTATION_WORKSPACES = [
  { label: '迎新工作台', pages: [page('待办与概览')] },
  { label: '批次准备', pages: [page('批次与名单', '/batches'), page('流程设置', '/flow-config'), page('报到点', '/checkin-points')] },
  { label: '新生办理', pages: [page('新生名单', '/students'), page('信息核验', '/verify'), page('入学确认', '/qualification')] },
  { label: '审核与缴费', pages: [page('材料审核', '/materials'), page('缴费核验', '/payment'), page('绿色通道', '/green-channels')] },
  { label: '现场报到', pages: [page('扫码报到', '/checkin'), page('报到进度', '/progress')] },
  { label: '住宿安排', pages: [page('分配床位', '/dorm-preassign'), page('确认入住', '/dorm')] },
  { label: '异常跟进', pages: [page('异常处理', '/exceptions'), page('未报到跟进', '/no-show'), page('迎新通知', '/notices')] },
  { label: '统计归档', pages: [page('迎新统计', '/statistics'), page('新生查询', '/data'), page('迎新归档', '/archive')] }
]

export function orientationWorkspace(path) {
  return ORIENTATION_WORKSPACES.find(group => group.pages.some(page => page.path === path))
    || (path.startsWith(base + '/students/') ? ORIENTATION_WORKSPACES[2] : null)
}

export function orientationNavigation() {
  return ORIENTATION_WORKSPACES.map(group => ({
    label: group.label, path: group.pages[0].path,
    status: 'implemented', disabled: false, badge: '',
    permissionKey: 'studentAffairs.orientation.view',
    workspacePaths: group.pages.map(page => page.path),
    searchAliases: group.pages.map(page => page.label)
  }))
}
