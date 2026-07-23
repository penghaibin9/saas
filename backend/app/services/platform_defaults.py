"""P6 · 平台默认配置（全局兜底；租户/套餐可覆盖）。改动经 /platform 接口落 t_platform_config。"""
from __future__ import annotations

FEATURE_KEYS = [
    "studentProfile", "student360", "orientation", "campusService", "approval", "todoMessage",
    "fileUpload", "studentImport", "studentExport", "auditLog", "graduation", "internship",
    "employment", "riskWarning", "miniapp", "customBrand", "workflowConfig", "dataExport", "apiAccess",
    "studentAffairs",
]

DEFAULT_FEATURES = {k: True for k in FEATURE_KEYS}

DEFAULT_PACKAGES = {
    "trial": {"packageCode": "trial", "packageName": "试用版", "price": 0, "durationDays": 30,
              "maxStudents": 200, "maxUsers": 20, "storageLimitMb": 512,
              "features": {**DEFAULT_FEATURES, "customBrand": False, "workflowConfig": False, "apiAccess": False},
              "enabled": True, "remark": "默认 30 天试用"},
    "basic": {"packageCode": "basic", "packageName": "基础版", "price": 19800, "durationDays": 365,
              "maxStudents": 3000, "maxUsers": 100, "storageLimitMb": 5120,
              "features": {**DEFAULT_FEATURES, "customBrand": False, "apiAccess": False},
              "enabled": True, "remark": ""},
    "standard": {"packageCode": "standard", "packageName": "标准版", "price": 49800, "durationDays": 365,
                 "maxStudents": 10000, "maxUsers": 300, "storageLimitMb": 20480,
                 "features": {**DEFAULT_FEATURES, "apiAccess": False}, "enabled": True, "remark": ""},
    "professional": {"packageCode": "professional", "packageName": "专业版", "price": 99800, "durationDays": 365,
                     "maxStudents": 30000, "maxUsers": 1000, "storageLimitMb": 51200,
                     "features": dict(DEFAULT_FEATURES), "enabled": True, "remark": ""},
    "private": {"packageCode": "private", "packageName": "私有化版", "price": 0, "durationDays": 3650,
                "maxStudents": 100000, "maxUsers": 5000, "storageLimitMb": 204800,
                "features": dict(DEFAULT_FEATURES), "enabled": True, "remark": "私有化部署，价格面议"},
}

DEFAULT_RULES = {
    "student": {"studentNoRequired": True, "idCardRequired": False, "phoneRequired": False,
                "allowDuplicatePhone": True, "allowDuplicateIdCard": False,
                "studentArchiveVoidNeedReason": True, "studentVoidReasonMinLength": 5,
                "studentEditAuditRequired": True},
    "approval": {"rejectReasonRequired": True, "rejectReasonMinLength": 5,
                 "transferReasonRequired": False, "approvalTimeoutHours": 48,
                 "autoReminderEnabled": True, "approvalCanWithdraw": True, "approvalCanTransfer": True},
    "import": {"importMaxRows": 5000, "importAllowSkipError": False, "importRequireConfirm": True,
               "importCheckDuplicateStudentNo": True, "importCheckDuplicatePhone": False,
               "importCheckDuplicateIdCard": True},
    "export": {"exportNeedPurpose": True, "exportPurposeMinLength": 5, "exportWatermarkEnabled": True,
               "exportPhoneMasked": True, "exportIdCardMasked": True, "exportMaxRows": 10000,
               "exportRateLimitPerMinute": 5},
    "file": {"uploadMaxSizeMb": 50, "allowedFileTypes": "pdf,doc,docx,xls,xlsx,ppt,pptx,png,jpg,jpeg,gif,zip,txt,csv",
             "blockedFileTypes": "exe,js,bat,sh,php,jsp,html,svg", "fileNameRandomize": True,
             "fileDownloadNeedAudit": True, "fileRetentionDays": 365},
    "risk": {"riskWarningEnabled": True, "highRiskScoreThreshold": 80, "mediumRiskScoreThreshold": 50,
             "absenceDaysThreshold": 3, "internshipWeeklyReportDelayDays": 7, "graduationTaskDelayDays": 7},
    "message": {"todoReminderEnabled": True, "messageUnreadReminderEnabled": True,
                "trialExpireReminderDays": 7, "tenantExpireReminderDays": 30},
    "security": {"loginFailLockEnabled": True, "loginFailMaxTimes": 5, "loginFailLockMinutes": 15,
                 "accessTokenExpireMinutes": 120, "refreshTokenExpireDays": 7, "forceStrongPassword": False},
    "trial": {"trialDefaultDays": 30, "trialExpireReadOnly": True, "trialExpireAllowLogin": True,
              "trialExpireShowContactPhone": True},
}

DEFAULT_WORKFLOWS = {
    "student_edit": {"workflowCode": "student_edit", "workflowName": "学生信息修改审批", "enabled": True,
                     "needApproval": False, "approverRoleCodes": ["COUNSELOR"], "ccRoleCodes": [],
                     "timeoutHours": 48, "allowTransfer": True, "allowReject": True, "allowWithdraw": True},
    "student_void": {"workflowCode": "student_void", "workflowName": "学生作废审批", "enabled": True,
                     "needApproval": False, "approverRoleCodes": ["SCHOOL_ADMIN"], "ccRoleCodes": [],
                     "timeoutHours": 48, "allowTransfer": True, "allowReject": True, "allowWithdraw": False},
    "student_import": {"workflowCode": "student_import", "workflowName": "学生导入审批", "enabled": True,
                       "needApproval": False, "approverRoleCodes": ["SCHOOL_ADMIN"], "ccRoleCodes": [],
                       "timeoutHours": 24, "allowTransfer": False, "allowReject": True, "allowWithdraw": False},
    "data_export": {"workflowCode": "data_export", "workflowName": "数据导出审批", "enabled": True,
                    "needApproval": False, "approverRoleCodes": ["SCHOOL_ADMIN"], "ccRoleCodes": [],
                    "timeoutHours": 24, "allowTransfer": False, "allowReject": True, "allowWithdraw": False},
    "leave": {"workflowCode": "leave", "workflowName": "请假申请审批", "enabled": True,
              "needApproval": True, "approverRoleCodes": ["COUNSELOR", "COLLEGE_ADMIN"], "ccRoleCodes": [],
              "timeoutHours": 48, "allowTransfer": True, "allowReject": True, "allowWithdraw": True},
    "campus_service": {"workflowCode": "campus_service", "workflowName": "在校服务申请审批", "enabled": True,
                       "needApproval": True, "approverRoleCodes": ["COUNSELOR"], "ccRoleCodes": [],
                       "timeoutHours": 72, "allowTransfer": True, "allowReject": True, "allowWithdraw": True},
    "intern_weekly": {"workflowCode": "intern_weekly", "workflowName": "实习周报教师确认", "enabled": True,
                      "needApproval": True, "approverRoleCodes": ["GD_MENTOR"], "ccRoleCodes": [],
                      "timeoutHours": 168, "allowTransfer": False, "allowReject": True, "allowWithdraw": False},
    "gd_task": {"workflowCode": "gd_task", "workflowName": "毕设任务导师确认", "enabled": True,
                "needApproval": True, "approverRoleCodes": ["GD_MENTOR"], "ccRoleCodes": [],
                "timeoutHours": 168, "allowTransfer": False, "allowReject": True, "allowWithdraw": False},
}

DEFAULT_DICTIONARIES = {
    "schoolType": [{"code": "VOCATIONAL", "label": "高职院校", "enabled": True},
                   {"code": "UNDERGRAD", "label": "本科院校", "enabled": True},
                   {"code": "TECHNICIAN", "label": "技师学院", "enabled": True}],
    "studentStatus": [{"code": "NORMAL", "label": "正常在籍", "enabled": True},
                      {"code": "SUSPENDED", "label": "休学", "enabled": True},
                      {"code": "RECYCLED", "label": "已作废", "enabled": True}],
    "riskLevel": [{"code": "HIGH", "label": "高风险", "enabled": True},
                  {"code": "MEDIUM", "label": "中风险", "enabled": True},
                  {"code": "LOW", "label": "低风险", "enabled": True},
                  {"code": "NONE", "label": "无", "enabled": True}],
    "approvalStatus": [{"code": "PENDING", "label": "待审批", "enabled": True},
                       {"code": "APPROVED", "label": "已通过", "enabled": True},
                       {"code": "REJECTED", "label": "已驳回", "enabled": True},
                       {"code": "TRANSFERRED", "label": "已转办", "enabled": True}],
    "fileType": [{"code": "IMPORT", "label": "导入文件", "enabled": True},
                 {"code": "EXPORT", "label": "导出文件", "enabled": True},
                 {"code": "ATTACHMENT", "label": "业务附件", "enabled": True}],
    "serviceType": [{"code": "LEAVE", "label": "请假", "enabled": True},
                    {"code": "DORM", "label": "宿舍服务", "enabled": True},
                    {"code": "GRANT", "label": "奖助申请", "enabled": True}],
    "internshipStatus": [{"code": "ONBOARD", "label": "在岗", "enabled": True},
                         {"code": "CHANGED", "label": "已换岗", "enabled": True},
                         {"code": "FINISHED", "label": "已结束", "enabled": True}],
    "graduationStatus": [{"code": "TOPIC", "label": "选题", "enabled": True},
                         {"code": "MIDTERM", "label": "中期", "enabled": True},
                         {"code": "DEFENSE", "label": "答辩", "enabled": True}],
    "employmentStatus": [{"code": "SEEKING", "label": "求职中", "enabled": True},
                         {"code": "EMPLOYED", "label": "已就业", "enabled": True},
                         {"code": "FURTHER_STUDY", "label": "升学", "enabled": True}],
    "noticeType": [{"code": "ANNOUNCEMENT", "label": "全平台公告", "enabled": True},
                   {"code": "EXPIRE_REMIND", "label": "到期提醒", "enabled": True},
                   {"code": "MAINTENANCE", "label": "维护通知", "enabled": True},
                   {"code": "TRIAL_REMIND", "label": "试用提醒", "enabled": True}],
    "tenantStatus": [{"code": "trial", "label": "试用", "enabled": True},
                     {"code": "active", "label": "正式", "enabled": True},
                     {"code": "expired", "label": "已到期", "enabled": True},
                     {"code": "disabled", "label": "已停用", "enabled": True}],
    "packageType": [{"code": k, "label": v["packageName"], "enabled": True} for k, v in DEFAULT_PACKAGES.items()],
}

DEFAULT_SECURITY = {
    "loginFailMaxTimes": 5, "loginFailLockMinutes": 15, "accessTokenExpireMinutes": 120,
    "refreshTokenExpireDays": 7,
    "corsAllowedOrigins": "http://localhost:5173,http://localhost:5188,http://localhost:5199,http://127.0.0.1:5173,http://127.0.0.1:5199",
    "uploadMaxSizeMb": 50, "exportRateLimitPerMinute": 5, "uploadRateLimitPerMinute": 20,
    "normalApiRateLimitPerMinute": 300, "docsEnabledInProduction": False,
}

DEFAULT_BRAND = {
    "schoolName": "", "platformName": "高校学生全生命周期管理平台", "logoUrl": "", "faviconUrl": "",
    "watermarkText": "", "primaryColor": "#2563EB", "loginBackground": "",
    "topBarName": "高校学生全生命周期管理平台", "copyrightText": "", "contactPhone": "13549666867",
}

# 安全设置合法范围（保存校验：不允许放开为不设防）
SECURITY_BOUNDS = {
    "loginFailMaxTimes": (3, 10), "loginFailLockMinutes": (5, 120),
    "accessTokenExpireMinutes": (15, 720), "refreshTokenExpireDays": (1, 30),
    "uploadMaxSizeMb": (1, 200), "exportRateLimitPerMinute": (1, 60),
    "uploadRateLimitPerMinute": (1, 120), "normalApiRateLimitPerMinute": (30, 3000),
}
