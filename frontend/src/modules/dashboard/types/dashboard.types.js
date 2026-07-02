/**
 * Dashboard 领域模型（JSDoc）
 * 前端生产级 UI 架构 V1 — 页面与组件仅依赖此处定义的结构。
 */

/** @typedef {'LOW'|'MEDIUM'|'HIGH'|'CRITICAL'} RiskLevel */
/** @typedef {'pending'|'processing'|'resolved'|'ignored'} RiskStatus */
/** @typedef {'todo'|'doing'|'done'} TaskStatus */
/** @typedef {'high'|'medium'|'low'} TaskPriority */

/**
 * @typedef {Object} Student
 * @property {string} studentId
 * @property {string} name
 * @property {string} studentNo
 * @property {string} college
 * @property {string} major
 * @property {string} className
 * @property {string} [phone]
 * @property {string} currentStage
 * @property {RiskLevel} riskLevel
 * @property {string} [avatar]
 * @property {string} [advisorName]
 * @property {string} [enterpriseName]
 * @property {string} [lastActivity]
 * @property {string} [handleDeadline]
 * @property {string[]} [suggestions]
 */

/**
 * @typedef {Object} RiskEvent
 * @property {string} riskId
 * @property {string} [studentId]
 * @property {string} riskType
 * @property {string} riskTitle
 * @property {RiskLevel} riskLevel
 * @property {string} reason
 * @property {RiskStatus} status
 * @property {string} ownerTeacher
 * @property {string} triggeredAt
 * @property {string} [deadline]
 * @property {string} [durationText]
 * @property {string[]} [suggestions]
 * @property {string[]} [relatedTaskIds]
 * @property {number} [affectedCount]
 * @property {string} [statusLabel]
 */

/**
 * @typedef {Object} TeacherTask
 * @property {string} taskId
 * @property {string} title
 * @property {string} module
 * @property {string} [studentId]
 * @property {string} [studentName]
 * @property {string} [relatedRiskId]
 * @property {TaskPriority} priority
 * @property {string} deadline
 * @property {TaskStatus} status
 * @property {string} [description]
 * @property {boolean} [overdue]
 */

/**
 * @typedef {Object} OperationLog
 * @property {string} recordId
 * @property {string} time
 * @property {string} operator
 * @property {string} action
 * @property {string} [target]
 * @property {string} result
 * @property {string} [status]
 * @property {string} [studentId]
 * @property {string} [relatedRiskId]
 * @property {string} [relatedTaskId]
 * @property {boolean} [closed]
 */

/**
 * @typedef {Object} LifecycleStage
 * @property {string} stageId
 * @property {string} name
 * @property {'done'|'active'|'pending'} status
 * @property {number} completionRate
 * @property {number} riskCount
 * @property {string} [description]
 * @property {string} [actionText]
 * @property {string} [key]
 * @property {string} [label]
 * @property {string} [cardStatus]
 * @property {string} [statusType]
 * @property {string} [actionLabel]
 * @property {string} [detail]
 */

/**
 * @typedef {Object} DashboardMetric
 * @property {string} metricId
 * @property {string} title
 * @property {number|string} value
 * @property {string} [unit]
 * @property {string} [trendText]
 * @property {string} [status]
 * @property {string} [updatedAt]
 * @property {string} [id]
 * @property {string} [trendType]
 * @property {string} [trendQuality]
 * @property {string} [trendLabel]
 * @property {boolean} [drillable]
 * @property {string} [drillTarget]
 */

/**
 * @typedef {Object} DataQualityInfo
 * @property {string} baseDate
 * @property {string} updatedAt
 * @property {string[]} dataSources
 * @property {string} statisticScope
 * @property {string} statisticRules
 * @property {string} [environment]
 * @property {string} [baselineDate]
 */

/**
 * @typedef {Object} TeacherProfile
 * @property {string} teacherId
 * @property {string} name
 * @property {string} identity
 * @property {string} dataScope
 */

/**
 * @typedef {Object} HandleDrawerDetail
 * @property {string} studentName
 * @property {string} riskType
 * @property {string} riskReason
 * @property {string} responsibleTeacher
 * @property {string} deadline
 * @property {string} status
 * @property {string[]} suggestions
 */

/**
 * @typedef {Object} DashboardState
 * @property {Student[]} students
 * @property {RiskEvent[]} risks
 * @property {TeacherTask[]} tasks
 * @property {OperationLog[]} operationLogs
 * @property {LifecycleStage[]} lifecycleStages
 * @property {LifecycleStage[]} lifecycleBannerStages
 * @property {LifecycleStage[]} lifecycleStageCards
 * @property {DashboardMetric[]} overviewMetrics
 * @property {DashboardMetric[]} gdMetrics
 * @property {DashboardMetric[]} internshipMetrics
 * @property {DashboardMetric[]} dashboardMetrics
 * @property {DataQualityInfo} dataQuality
 * @property {TeacherProfile} teacher
 */

export const RISK_LEVELS = /** @type {const} */ (['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'])
export const HIGH_RISK_LEVELS = /** @type {const} */ (['HIGH', 'CRITICAL'])
export const FOCUS_RISK_LEVELS = /** @type {const} */ (['MEDIUM', 'HIGH', 'CRITICAL'])
export const ACTIVE_RISK_STATUSES = /** @type {const} */ (['pending', 'processing'])
export const LATEST_LOG_LIMIT = 10
