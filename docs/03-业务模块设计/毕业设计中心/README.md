# 毕业设计中心（docs/03-业务模块设计/毕业设计中心/）

> **文档关联索引（任务路由）**：[文档关联索引.md](./文档关联索引.md)  
> **施工总控**：[05-毕业设计中心生产级商业化开发总册.md](./05-毕业设计中心生产级商业化开发总册.md)

---

## 中心定位

毕业设计全过程：批次、选题、导师、开题、过程、成果、查重、答辩、成绩、归档、统计。

---

## 真实代码目录

| 端 | 路径 |
|---|---|
| PC | `frontend/src/views/admin/graduation/`、`navPlan.js` → `graduationDesign` |
| API | `backend/app/api/v1/graduation*.py` |
| 模型 | `backend/app/models/graduation.py`、`backend/app/services/graduation_*` |
| 测试 | `backend/tests/test_graduation*.py` |
| 小程序 | `miniapp/src/pages/student/graduation/`、`teacher/graduation-guide/` |

---

## 当前真实完成度

以施工归档与 `navPlan.js` 为准，多子模块 **implemented/partial** 并存；长跑欠账见 [历史欠账](../../06-开发施工与质量验收/施工记录/历史欠账.md)。**文档齐全 ≠ 代码已实现。**

---

## 唯一主总册

[05-毕业设计中心生产级商业化开发总册.md](./05-毕业设计中心生产级商业化开发总册.md)；业务字段/状态机细节：[05-毕业设计中心反向建模与深化设计 V1.0.md](./05-毕业设计中心反向建模与深化设计 V1.0.md)

---

## 开发入口

索引 §1（答辩/成果等专题 §4）→ 主总册 → 施工归档 → 权限总控

---

## 已归档

原 11 份分散 `施工记录` → [毕业设计中心-施工与验收归档.md](./毕业设计中心-施工与验收归档.md)；`08/source-design/05-*` 仅追溯。
