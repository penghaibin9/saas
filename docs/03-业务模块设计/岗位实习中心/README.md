# 岗位实习中心（docs/03-业务模块设计/岗位实习中心/）

> **文档关联索引（任务路由）**：[文档关联索引.md](./文档关联索引.md)  
> **施工总控**：[06-岗位实习中心生产级商业化开发总册.md](./06-岗位实习中心生产级商业化开发总册.md)

---

## 中心定位

校外岗位实习全周期：批次、学生、企业岗位、协议、打卡、周报、请假异常、风险、指导巡访、归档、统计、就业跟进。

---

## 真实代码目录

| 端 | 路径 |
|---|---|
| PC | `frontend/src/views/admin/internship/`、`navPlan.js` → `internship` |
| API | `backend/app/api/v1/internship*.py` |
| 模型/服务 | `backend/app/models/internship.py`、`backend/app/services/internship_*` |
| 测试 | `backend/tests/test_internship*.py` |
| 小程序 | `miniapp/src/pages/student/internship/`、`teacher/internship-review/` |

---

## 当前真实完成度

**partial～implemented 混合**（以 `navPlan.js` 与施工归档为准）：企业/学生/匹配/协议/周报/归档/统计等已有代码与测试；商业化差距见设计补强总册与历史欠账。**文档齐全 ≠ 全部 production。**

---

## 唯一主总册与页面树

| 文档 | 角色 |
|---|---|
| [06-岗位实习中心生产级商业化开发总册.md](./06-岗位实习中心生产级商业化开发总册.md) | **唯一主总册** |
| [06-岗位实习中心页面树与路由重构设计.md](./06-岗位实习中心页面树与路由重构设计.md) | 12 二级菜单冻结 |

---

## 开发入口

索引 §1 任务路由 → 主总册 → [岗位实习中心-施工与验收归档.md](./岗位实习中心-施工与验收归档.md) → 历史欠账

---

## 公共文档与归档

权限总控、文件上传、Excel、审计 — 见索引 §1–§2；历史 `source-design`、合并前施工记录见索引 §3。
