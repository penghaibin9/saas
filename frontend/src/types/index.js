/**
 * UI 演示数据类型定义（JSDoc，项目为 JS 工程，与 V2.1 §3.3.1 契约一致）
 * UI-P2 阶段仅用于 mock/store/aggregate 层，后续接真实 API 时字段口径以此为准。
 */

/**
 * @typedef {Object} Student
 * @property {string} id                内部 id
 * @property {string} studentId         学生编码（student_id 体系，如 S2026-000001）
 * @property {string} name
 * @property {string} college
 * @property {string} major
 * @property {string} classId
 * @property {string} className
 * @property {string} stage             当前阶段：如 毕业设计 / 岗位实习 / 毕业就业
 * @property {'ACTIVE'|'RISK'|'ARCHIVED'} status
 * @property {'LOW'|'MEDIUM'|'HIGH'|'CRITICAL'} riskLevel
 * @property {string} counselorId       辅导员 id
 * @property {string} [gdAdvisorId]     毕设导师 id
 * @property {string} [internAdvisorId] 实习指导教师 id
 * @property {string} [phone]           敏感字段，展示必须走 AppSensitiveText
 * @property {string} [lastActivity]    最近动态
 */

/**
 * @typedef {Object} Teacher
 * @property {string} id
 * @property {string} name
 * @property {string[]} identities      多身份：辅导员 / 毕设导师 / 实习指导教师 / 就业老师
 * @property {string} college
 * @property {string} dataScope         当前数据范围说明
 */

/**
 * @typedef {Object} Enterprise
 * @property {string} id
 * @property {string} name
 * @property {string} industry
 * @property {'NORMAL'|'HIGH_RISK'} riskFlag
 * @property {string} mentorName        企业导师
 * @property {string} [mentorPhone]     敏感字段
 */

/**
 * @typedef {Object} GdNode 毕设节点
 * @property {'NOT_STARTED'|'PENDING_SUBMIT'|'PENDING_REVIEW'|'REVIEWING'|'APPROVED'|'RETURNED'|'OVERDUE'} status
 * @property {string} deadline
 * @property {string} [submittedAt]
 * @property {string} [score]           如 优秀 / 良好 / 合格
 * @property {string} [returnReason]
 */

/**
 * @typedef {Object} GraduationDesignTask
 * @property {string} id
 * @property {string} studentId
 * @property {string} title             课题名
 * @property {string} advisorId         毕设导师
 * @property {string} batch             批次
 * @property {{opening: GdNode, midterm: GdNode, final: GdNode}} nodes
 */

/**
 * @typedef {Object} InternshipRecord
 * @property {string} id
 * @property {string} studentId
 * @property {string} enterpriseId
 * @property {string} post              岗位
 * @property {string} advisorId         校内实习指导教师
 * @property {'PENDING'|'ONBOARD'|'FINISHED'|'TERMINATED'} status
 * @property {'LOW'|'MEDIUM'|'HIGH'|'CRITICAL'} riskLevel
 * @property {string} startDate
 * @property {boolean} [intendedHire]   企业是否拟录用
 */

/**
 * @typedef {Object} CheckinRecord
 * @property {string} id
 * @property {string} studentId
 * @property {string} date              YYYY-MM-DD
 * @property {'NORMAL'|'ABNORMAL'|'MISSING'} status
 * @property {string} [note]            异常说明
 */

/**
 * @typedef {Object} WeeklyReport
 * @property {string} id
 * @property {string} studentId
 * @property {number} week              第几周
 * @property {'SUBMITTED'|'APPROVED'|'RETURNED'|'MISSING'} status
 * @property {string} [submittedAt]
 * @property {string} [reviewerId]
 * @property {string} [returnReason]
 */

/**
 * @typedef {Object} EmploymentRecord
 * @property {string} id
 * @property {string} studentId
 * @property {'EMPLOYED'|'INTENTION'|'PENDING'} direction
 * @property {string} [company]
 * @property {'PENDING'|'VERIFIED'|'RETURNED'} materialStatus
 * @property {string} [returnReason]
 * @property {string} [verifierId]
 */

/**
 * @typedef {Object} TodoItem
 * @property {string} id
 * @property {'student'|'teacher'|'enterprise'} ownerType
 * @property {string} ownerId
 * @property {string} title
 * @property {string} sourceModule      来源模块：毕业设计 / 岗位实习 / 毕业就业
 * @property {string} [studentId]       关联学生
 * @property {string} deadline
 * @property {'high'|'medium'|'low'} priority
 * @property {string} status            状态码（对齐 AppStatusTag）
 * @property {boolean} overdue
 * @property {string} [returnReason]    被退回待办的原因摘要
 */

/**
 * @typedef {Object} MessageItem
 * @property {string} id
 * @property {'student'|'teacher'|'enterprise'} toType
 * @property {string} toId
 * @property {string} title
 * @property {string} source            来源模块
 * @property {string} time
 * @property {boolean} read
 * @property {boolean} needHandle
 * @property {string} [studentId]
 */

/**
 * @typedef {Object} MetricCardData  指标卡数据契约（V2.1 §3.3.1，冻结）
 * @property {string} id
 * @property {string} title
 * @property {number|string} value
 * @property {string} [unit]
 * @property {string} [description]
 * @property {'up'|'down'|'flat'} [trendType]        数学方向
 * @property {'good'|'bad'|'neutral'} [trendQuality] 业务好坏——趋势颜色唯一依据
 * @property {string} [trendLabel]
 * @property {boolean} [drillable]
 * @property {string} [drillTarget]
 * @property {string} [updatedAt]
 */

export {}
