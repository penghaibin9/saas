/**
 * 消息中心路由（/admin/messages，moduleCode: WORKBENCH）。
 */
export const messageCenterRoutes = [
  {
    path: '/admin/messages',
    component: () => import('@/modules/messageCenter/views/MessageCenterLayout.vue'),
    meta: { moduleCode: 'WORKBENCH' },
    redirect: '/admin/messages/inbox',
    children: [
      {
        path: 'inbox',
        name: 'message-inbox',
        component: () => import('@/modules/messageCenter/views/MessageInboxView.vue'),
        meta: {
          moduleCode: 'WORKBENCH',
          title: '我的消息',
          permissionKey: 'workbench.message.view'
        }
      },
      {
        path: 'compose',
        name: 'message-compose',
        component: () => import('@/modules/messageCenter/views/MessageComposeView.vue'),
        meta: {
          moduleCode: 'WORKBENCH',
          title: '通知发布',
          permissionKey: 'workbench.message.publish'
        }
      },
      {
        path: 'outbox',
        name: 'message-outbox',
        component: () => import('@/modules/messageCenter/views/MessageOutboxView.vue'),
        meta: {
          moduleCode: 'WORKBENCH',
          title: '发布记录',
          permissionKey: 'workbench.message.publish'
        }
      },
      {
        path: 'outbox/:campaignId',
        name: 'message-campaign-detail',
        component: () => import('@/modules/messageCenter/views/MessageCampaignDetailView.vue'),
        meta: {
          moduleCode: 'WORKBENCH',
          title: '发布详情',
          permissionKey: 'workbench.message.publish'
        }
      },
      {
        path: 'statistics',
        name: 'message-statistics',
        component: () => import('@/modules/messageCenter/views/MessageStatisticsView.vue'),
        meta: {
          moduleCode: 'WORKBENCH',
          title: '发送统计',
          permissionKey: 'workbench.message.statistics.view'
        }
      },
      {
        path: 'templates',
        name: 'message-templates',
        component: () => import('@/modules/messageCenter/views/MessageTemplateView.vue'),
        meta: {
          moduleCode: 'WORKBENCH',
          title: '消息模板',
          permissionKey: 'workbench.message.template.manage'
        }
      },
      {
        path: 'settings',
        name: 'message-settings',
        component: () => import('@/modules/messageCenter/views/MessageSettingsView.vue'),
        meta: {
          moduleCode: 'WORKBENCH',
          title: '消息设置',
          permissionKey: 'workbench.message.view'
        }
      },
      {
        path: 'ops',
        name: 'message-ops',
        component: () => import('@/modules/messageCenter/views/MessageOpsView.vue'),
        meta: {
          moduleCode: 'WORKBENCH',
          title: '投递运维',
          permissionKey: 'workbench.message.statistics.view'
        }
      }
    ]
  }
]

export default messageCenterRoutes
