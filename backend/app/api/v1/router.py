"""/api/v1 路由聚合（分端前缀对齐冻结契约 §一.3；BACKEND-OVERNIGHT 重建并补挂 students/approvals/audit）。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.security import require_staff

from app.api.v1 import academic, approval, audit, auth, authz, campus_service, dashboard, employment, files, graduation, internship, orientation, platform, rbac, student, system, tenant, transfer
from app.api.v1 import file as file_simple
from app.api.v1 import import_export
from app.api.v1 import message as message_simple
from app.api.v1 import todo as todo_simple
from app.api.v1 import mobile
from app.api.v1 import notification
from app.api.v1 import onboarding
from app.api.v1 import academic_affairs
from app.api.v1 import stats
from app.api.v1 import student_affairs
from app.api.v1 import internship_position  # 岗位库（独立 router，/internship/positions/*）
from app.api.v1 import graduation_batch  # 毕设批次（独立 router，/graduation/batches/*）
from app.api.v1 import graduation_student  # 毕设学生（独立 router，/graduation/gd-students/*）
from app.api.v1 import graduation_topic  # 题目库（独立 router，/graduation/gd-topics/*）
from app.api.v1 import graduation_topic_round  # 选题轮次（/graduation/gd-topic-rounds/*）
from app.api.v1 import graduation_topic_change  # 选题变更申请（/graduation/gd-topic-change-requests/*）
from app.api.v1 import graduation_mentor  # 导师管理+导师分配（/graduation/gd-mentors/*、/gd-mentor-assignments/*）
from app.api.v1 import graduation_taskbook  # 任务书（/graduation/gd-taskbooks/*）
from app.api.v1 import graduation_guidance  # 指导过程记录（/graduation/gd-guidances/*）
from app.api.v1 import graduation_midterm  # 中期检查（/graduation/gd-midterms/*）
from app.api.v1 import graduation_review  # 查重记录+教师评阅（/graduation/gd-plagiarism/*、/gd-reviews/*）
from app.api.v1 import graduation_defense_score  # 答辩评分（/graduation/gd-defense-scores/*）
from app.api.v1 import graduation_grade  # 成绩评定（/graduation/gd-grades/*）
from app.api.v1 import graduation_risk  # 问题预警（/graduation/gd-risks/*）
from app.api.v1 import graduation_archive  # 毕设归档（/graduation/gd-archives/*）
from app.api.v1 import graduation_stats  # 毕设统计（/graduation/gd-stats/*）
from app.api.v1 import graduation_template  # 模板中心（/graduation/gd-templates/*）
from app.api.v1 import graduation_more  # 互查整改/答辩专家/成绩申诉（Batch 7/8）
from app.api.v1.todos import make_router as make_todos_router

api_router = APIRouter()

# 毕设中心 PC 管理端统一角色门禁：学生令牌一律 403（学生合法入口是 /mobile/graduation/*）。
_GD_DEP = [Depends(require_staff)]

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
api_router.include_router(internship.router)                                 # /api/v1/internship/*
api_router.include_router(internship_position.router)                        # /api/v1/internship/positions/*（岗位库）
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
api_router.include_router(employment.router)                                 # /api/v1/employment/*
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
api_router.include_router(mobile.router)                                      # /api/v1/mobile/*（含 /me/portal-config）
from app.api.v1 import student_portal_admin                                    # noqa: E402
api_router.include_router(student_portal_admin.router)                        # /api/v1/admin/tenants/{id}/student-portal-config
api_router.include_router(onboarding.router)                                  # /api/v1/onboarding/*
api_router.include_router(notification.router)                                # /api/v1/notification/*
api_router.include_router(system.router, tags=["system"])                     # /api/v1/system/info
