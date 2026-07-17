/**
 * 数据中心（数据驾驶舱）模块路由描述（moduleCode: DATA_CENTER）。
 * 已在 router/index.js 中 import dataCenterRoutes 并并入全局路由表（集成完成）。
 * 早期注释「禁止 import 到任何现有文件」为集成前的批次约束，现已过期，故订正。
 */
export const dataCenterRoutes = [
  {
    path: '/admin/data-center',
    component: () => import('@/views/admin/dataCenter/AdminDataCenterLayout.vue'),
    meta: { moduleCode: 'DATA_CENTER' },
    children: [
      {
        path: '',
        name: 'data-center-dashboard',
        component: () => import('@/views/admin/dataCenter/DataCenterDashboardView.vue'),
        meta: { moduleCode: 'DATA_CENTER', title: '数据驾驶舱', permissionKey: 'dataCenter.dashboard.view' }
      },
      {
        path: 'lifecycle',
        name: 'data-center-lifecycle',
        component: () => import('@/views/admin/dataCenter/DataCenterLifecycleView.vue'),
        meta: { moduleCode: 'DATA_CENTER', title: '学生生命周期总览', permissionKey: 'dataCenter.lifecycle.view' }
      },
      {
        path: 'rankings',
        name: 'data-center-rankings',
        component: () => import('@/views/admin/dataCenter/DataCenterRankingView.vue'),
        meta: { moduleCode: 'DATA_CENTER', title: '排行分析', permissionKey: 'dataCenter.ranking.view' }
      },
      {
        path: 'risk',
        name: 'data-center-risk',
        component: () => import('@/views/admin/dataCenter/DataCenterRiskView.vue'),
        meta: { moduleCode: 'DATA_CENTER', title: '风险预警数据', permissionKey: 'dataCenter.risk.view' }
      },
      {
        path: 'reports',
        name: 'data-center-reports',
        component: () => import('@/views/admin/dataCenter/DataCenterReportListView.vue'),
        meta: { moduleCode: 'DATA_CENTER', title: '专题报表', permissionKey: 'dataCenter.report.view' }
      },
      {
        path: 'reports/:reportId',
        name: 'data-center-report-detail',
        component: () => import('@/views/admin/dataCenter/DataCenterReportDetailView.vue'),
        meta: { moduleCode: 'DATA_CENTER', title: '报表详情', permissionKey: 'dataCenter.report.view' }
      }
    ]
  }
]

export default dataCenterRoutes
