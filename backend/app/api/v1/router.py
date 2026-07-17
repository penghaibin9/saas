"""/api/v1 路由聚合（分端前缀对齐冻结契约 §一.3；BACKEND-OVERNIGHT 重建并补挂 students/approvals/audit）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_staff
from app.core.permissions import require_module
from app.core.graduation_permissions import require_graduation_request_permission
from app.api.v1 import academic, approval, audit, auth, authz, campus_service, dashboard, files, orientation, platform, rbac, student, system, tenant, transfer
from app.api.v1 import file as file_simple
from app.api.v1 import import_export
from app.api.v1 import message as message_simple
from app.api.v1 import todo as todo_simple
from app.api.v1 import mobile
from app.api.v1 import mobile_export
from app.api.v1 import mobile_orientation_teacher
from app.api.v1 import notification
from app.student_portal.router import router as student_portal_router
from app.api.v1 import onboarding
from app.api.v1 import user_preference  # 通用用户偏好（/me/preferences，新手引导「已看过」等）
from app.api.v1 import feedback  # 帮助与反馈工单（/feedback/*，本人提交 + 处理侧受理）
from app.modules.academic_affairs.routers import academic_affairs
from app.api.v1 import stats
from app.api.v1 import student_affairs
from app.modules.employment.routers import employment  # 就业/实习转化中心主路由（/employment/*）
from app.modules.internship.routers import internship  # 岗位实习中心主路由（/internship/*）
from app.modules.internship.routers import internship_position  # 岗位库（独立 router，/internship/positions/*）
from app.modules.internship.routers import internship_student  # 实习学生（独立 router，/internship/intern-students/*）
from app.modules.internship.routers import internship_match  # 岗位匹配（独立 router，/internship/match/*）
from app.modules.internship.routers import internship_application  # 正式实习申请（/internship/applications/*）
from app.modules.graduation.routers import graduation  # 毕设中心主路由（/graduation/*）
from app.modules.graduation.routers import graduation_batch  # 毕设批次（独立 router，/graduation/batches/*）
from app.modules.graduation.routers import graduation_student  # 毕设学生（独立 router，/graduation/gd-students/*）
from app.modules.graduation.routers import graduation_topic  # 题目库（独立 router，/graduation/gd-topics/*）
from app.modules.graduation.routers import graduation_topic_round  # 选题轮次（/graduation/gd-topic-rounds/*）
from app.modules.graduation.routers import graduation_topic_change  # 选题变更申请（/graduation/gd-topic-change-requests/*）
from app.modules.graduation.routers import graduation_mentor  # 导师管理+导师分配（/graduation/gd-mentors/*、/gd-mentor-assignments/*）
from app.modules.graduation.routers import graduation_taskbook  # 任务书（/graduation/gd-taskbooks/*）
from app.modules.graduation.routers import graduation_guidance  # 指导过程记录（/graduation/gd-guidances/*）
from app.modules.graduation.routers import graduation_midterm  # 中期检查（/graduation/gd-midterms/*）
from app.modules.graduation.routers import graduation_review  # 查重记录+教师评阅（/graduation/gd-plagiarism/*、/gd-reviews/*）
from app.modules.graduation.routers import graduation_defense_score  # 答辩评分（/graduation/gd-defense-scores/*）
from app.modules.graduation.routers import graduation_grade  # 成绩评定（/graduation/gd-grades/*）
from app.modules.graduation.routers import graduation_risk  # 问题预警（/graduation/gd-risks/*）
from app.modules.graduation.routers import graduation_archive  # 毕设归档（/graduation/gd-archives/*）
from app.modules.graduation.routers import graduation_stats  # 毕设统计（/graduation/gd-stats/*）
from app.modules.graduation.routers import graduation_template  # 模板中心（/graduation/gd-templates/*）
from app.modules.graduation.routers import graduation_more  # 互查整改/答辩专家/成绩申诉（Batch 7/8）
from app.api.v1 import excel  # 公共 Excel 底座（/excel/*，通用导入记录）
from app.modules.internship.routers import internship_agreement_template  # 实习协议模板库（/internship/agreement-templates/*）
from app.modules.internship.routers import internship_archive  # 实习归档（/internship/archive/*）
from app.modules.internship.routers import internship_stats  # 实习统计（/internship/stats/*）
from app.modules.internship.routers import internship_plan  # 实习计划书+任务完成度（/internship/plans/*、/plan-task-progress/*）
from app.modules.internship.routers import internship_insurance  # 实习保险（/internship/insurances/*）
from app.modules.internship.routers import internship_communication  # 企业沟通（/internship/communications/*，P4 §5.1）
from app.modules.internship.routers import internship_visit_plan  # 巡访计划（/internship/visit-plans/*，P4 §5.2）
from app.modules.internship.routers import internship_complaint  # 企业投诉（/internship/complaints/*，P4 §5.3）
from app.modules.internship.routers import internship_process  # 过程报告+实习变更（/internship/process-reports/*、/change-requests/*）
from app.api.v1.todos import make_router as make_todos_router

api_router = APIRouter()

# 毕设中心 PC 管理端统一角色门禁：学生令牌一律 403（学生合法入口是 /mobile/graduation/*）。
_GD_DEP = [
    Depends(require_staff),
    Depends(require_module("module.graduationDesign.enabled")),
    Depends(require_graduation_request_permission),
]

# 岗位实习中心 / 就业服务 PC 管理端统一角色门禁：学生令牌一律 403。
# 学生的合法入口是 /mobile/internship/*（打卡/周报/我的实习），不受此门禁影响。
_INTERN_DEP = [Depends(require_staff), Depends(require_module("internship"))]

# 全端共用底座
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])       # /api/v1/auth/*
api_router.include_router(authz.router)                                      # /api/v1/authz/*（冻结契约）
api_router.include_router(tenant.router, prefix="/tenant", tags=["tenant"])  # /api/v1/tenant/brand
api_router.include_router(rbac.router, prefix="/rbac", tags=["rbac"])        # /api/v1/rbac/*
api_router.include_router(files.router)                                      # /api/v1/files/*（正式两步契约）
api_router.include_router(file_simple.router, prefix="/files", tags=["files"])  # /api/v1/files/upload-placeholder

# 业务第一批
api_router.include_router(student.router)                                    # /api/v1/students/*
api_router.include_router(approval.router)                                   # /api/v1/approvals/*
api_router.include_router(internship.router, dependencies=_INTERN_DEP)                                 # /api/v1/internship/*（PC 管理端·学生 403）
api_router.include_router(internship_position.router, dependencies=_INTERN_DEP)                        # /api/v1/internship/positions/*（岗位库）
api_router.include_router(internship_agreement_template.router, dependencies=_INTERN_DEP)               # /api/v1/internship/agreement-templates/*（协议模板库）
api_router.include_router(internship_student.router, dependencies=_INTERN_DEP)                         # /api/v1/internship/intern-students/*（实习学生）
api_router.include_router(internship_match.router, dependencies=_INTERN_DEP)                           # /api/v1/internship/match/*（岗位匹配）
api_router.include_router(internship_application.router, dependencies=_INTERN_DEP)                     # /api/v1/internship/applications/*（正式申请审核）
api_router.include_router(internship_archive.router, dependencies=_INTERN_DEP)                         # /api/v1/internship/archive/*（实习归档）
api_router.include_router(internship_stats.router, dependencies=_INTERN_DEP)                           # /api/v1/internship/stats/*（实习统计）
api_router.include_router(internship_plan.router, dependencies=_INTERN_DEP)                            # /api/v1/internship/plans/*、plan-task-progress/*（计划书+完成度）
api_router.include_router(internship_insurance.router, dependencies=_INTERN_DEP)                       # /api/v1/internship/insurances/*（实习保险）
api_router.include_router(internship_process.router, dependencies=_INTERN_DEP)                         # /api/v1/internship/process-reports/*、change-requests/*（过程报告+变更）
api_router.include_router(internship_communication.router, dependencies=_INTERN_DEP)                   # /api/v1/internship/communications/*（企业沟通，P4 §5.1）
api_router.include_router(internship_visit_plan.router, dependencies=_INTERN_DEP)                      # /api/v1/internship/visit-plans/*（巡访计划，P4 §5.2）
api_router.include_router(internship_complaint.router, dependencies=_INTERN_DEP)                       # /api/v1/internship/complaints/*（企业投诉，P4 §5.3）
api_router.include_router(orientation.router)                                # /api/v1/orientation/*
api_router.include_router(campus_service.router)                             # /api/v1/campus-service/*
api_router.include_router(academic.router)                                   # /api/v1/academic/*
api_router.include_router(graduation.router, dependencies=_GD_DEP)                                 # /api/v1/graduation/*
api_router.include_router(graduation_batch.router, dependencies=_GD_DEP)                           # /api/v1/graduation/batches/*（毕设批次）
api_router.include_router(graduation_student.router, dependencies=_GD_DEP)                         # /api/v1/graduation/gd-students/*（毕设学生）
api_router.include_router(graduation_topic.router, dependencies=_GD_DEP)                           # /api/v1/graduation/gd-topics/*（题目库）
api_router.include_router(graduation_topic_round.router, dependencies=_GD_DEP)                     # /api/v1/graduation/gd-topic-rounds/*
api_router.include_router(graduation_topic_change.router, dependencies=_GD_DEP)                    # /api/v1/graduation/gd-topic-change-requests/*
api_router.include_router(graduation_mentor.router, dependencies=_GD_DEP)                          # /api/v1/graduation/gd-mentors/*、/gd-mentor-assignments/*
api_router.include_router(graduation_taskbook.router, dependencies=_GD_DEP)                        # /api/v1/graduation/gd-taskbooks/*
api_router.include_router(graduation_guidance.router, dependencies=_GD_DEP)                        # /api/v1/graduation/gd-guidances/*
api_router.include_router(graduation_midterm.router, dependencies=_GD_DEP)                        # /api/v1/graduation/gd-midterms/*
api_router.include_router(graduation_review.router, dependencies=_GD_DEP)                         # /api/v1/graduation/gd-plagiarism/*、/gd-reviews/*
api_router.include_router(graduation_defense_score.router, dependencies=_GD_DEP)                  # /api/v1/graduation/gd-defense-scores/*
api_router.include_router(graduation_grade.router, dependencies=_GD_DEP)                          # /api/v1/graduation/gd-grades/*
api_router.include_router(graduation_risk.router, dependencies=_GD_DEP)                           # /api/v1/graduation/gd-risks/*
api_router.include_router(graduation_archive.router, dependencies=_GD_DEP)                        # /api/v1/graduation/gd-archives/*
api_router.include_router(graduation_stats.router, dependencies=_GD_DEP)                         # /api/v1/graduation/gd-stats/*
api_router.include_router(graduation_template.router, dependencies=_GD_DEP)                       # /api/v1/graduation/gd-templates/*
api_router.include_router(graduation_more.router, dependencies=_GD_DEP)                           # /api/v1/graduation/gd-peer-reviews/*、gd-defense-experts/*、gd-grade-appeals/*
api_router.include_router(excel.router)                                       # /api/v1/excel/*（公共 Excel 底座·导入记录）
api_router.include_router(employment.router, dependencies=_INTERN_DEP)                                 # /api/v1/employment/*（PC 管理端·学生 403）
api_router.include_router(student_affairs.router)                            # /api/v1/student-affairs/*（13A 学工中心）
api_router.include_router(academic_affairs.router)                           # /api/v1/academic-affairs/*（13B 教务中心）

# 看板 / 待办 / 消息（扁平简化端点）
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(todo_simple.router, prefix="/todos", tags=["todos"])
api_router.include_router(message_simple.router, prefix="/messages", tags=["messages"])

# 分端：待办与消息（契约 04：/api/v1/{端}/todos、/messages）
api_router.include_router(make_todos_router("admin"))
api_router.include_router(make_todos_router("student-mini"))
api_router.include_router(make_todos_router("teacher-mobile"))

# 导入导出（占位）
api_router.include_router(import_export.import_router, prefix="/import", tags=["import-export"])
api_router.include_router(import_export.export_router, prefix="/export", tags=["import-export"])
api_router.include_router(transfer.router)                                   # /api/v1/admin/students/import|export（正式契约占位）

# 审计
api_router.include_router(audit.router)                                       # /api/v1/admin/audit-logs（PC 管理端）
api_router.include_router(audit.alias_router)                                 # /api/v1/audit/*（任务规定路径）

# P6 平台总控（仅 PLATFORM_SUPER_ADMIN，后端强校验 + 拒绝审计）
api_router.include_router(platform.router)                                    # /api/v1/platform/*

# 系统
api_router.include_router(stats.router)                                       # /api/v1/stats/*
api_router.include_router(mobile_export.router)
api_router.include_router(mobile_orientation_teacher.router)
api_router.include_router(mobile.router)                                      # /api/v1/mobile/*（含 /me/portal-config）
api_router.include_router(student_portal_router)                              # /api/v1/portal/*（学生PC门户·重活+家长代理，学生令牌，服务层收口本人）
from app.api.v1 import student_portal_admin                                    # noqa: E402
api_router.include_router(student_portal_admin.router)                        # /api/v1/admin/tenants/{id}/student-portal-config
api_router.include_router(onboarding.router)                                  # /api/v1/onboarding/*
api_router.include_router(notification.router)                                # /api/v1/notification/*
api_router.include_router(user_preference.router)                             # /api/v1/me/preferences（本人偏好·全端共用）
api_router.include_router(feedback.router)                                     # /api/v1/feedback/*（帮助与反馈工单）
api_router.include_router(system.router, tags=["system"])                     # /api/v1/system/info
