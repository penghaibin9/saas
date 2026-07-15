/**
 * 系统管理中心 模块路由描述（PC-SYSTEM-PLATFORM-RUN）。
 * ⚠️ 本文件不自动接入全局 router（避免与并行任务冲突）。
 * 接入方式：在 src/router/index.js 的 routes 数组中加入：
 *   import systemRoutes from '@/modules/system/system.routes'
 *   routes: [...,  systemRoutes]
 * meta 口径与既有模块一致（moduleCode / permissionKey / requiresAuth），供统一路由守卫消费。
 */
const systemRoutes = {
  path: '/admin/system',
  component: () => import('@/modules/system/views/AdminSystemLayout.vue'),
  meta: { moduleCode: 'SYSTEM' },
  children: [
    {
      path: '',
      name: 'system-dashboard',
      component: () => import('@/modules/system/views/SystemDashboardView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '系统管理中心', requiresAuth: true, permissionKey: 'system.dashboard.view' }
    },
    {
      path: 'users',
      name: 'system-users',
      component: () => import('@/modules/system/views/SystemUserListView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '师生账号管理', requiresAuth: true,
        permissionKey: 'systemAdmin.user.view' }
    },
    {
      path: 'identity-import',
      name: 'system-identity-import',
      component: () => import('@/modules/system/views/SystemUserListView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '导入老师和学生', requiresAuth: true,
        permissionKey: 'systemAdmin.user.import', openImport: true }
    },
    {
      path: 'roles',
      name: 'system-roles',
      component: () => import('@/modules/system/views/SystemRoleListView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '角色权限管理', requiresAuth: true, permissionKey: 'system.role.view' }
    },
    {
      path: 'menus',
      name: 'system-menus',
      component: () => import('@/modules/system/views/SystemMenuView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '菜单权限管理', requiresAuth: true, permissionKey: 'system.menu.view' }
    },
    {
      path: 'scopes',
      name: 'system-scopes',
      component: () => import('@/modules/system/views/SystemDataScopeView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '数据范围管理', requiresAuth: true, permissionKey: 'system.scope.view' }
    },
    {
      path: 'org',
      name: 'system-org',
      component: () => import('@/modules/system/views/SystemOrgView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '组织结构管理', requiresAuth: true, permissionKey: 'system.org.view' }
    },
    {
      path: 'config',
      name: 'system-config',
      component: () => import('@/modules/system/views/SystemConfigView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '系统与品牌配置', requiresAuth: true, permissionKey: 'system.config.view' }
    },
    {
      path: 'logs',
      name: 'system-logs',
      component: () => import('@/modules/system/views/SystemLogView.vue'),
      meta: { moduleCode: 'SYSTEM', title: '日志中心', requiresAuth: true, permissionKey: 'system.log.view' }
    }
  ]
}

export default systemRoutes
