# 学业过程中心文档（docs/03-业务模块设计/学业过程中心/）

> **中心定位**：课程成绩、学业预警、补考重修等「学业过程」能力；与教务中心 V1 边界有交叉。  
> **当前完成度**：**partial** — 既有 `/admin/academic` 模块与 `t_acad_grade` 等表已运行；独立中心文档仅为历史深化设计。  
> **主参考**：[04-学业过程中心深化设计 V1.0.md](./04-学业过程中心深化设计 V1.0.md)（历史 V1）  
> **实际施工入口**：[../教务中心/README.md](../教务中心/README.md) + 既有 `frontend/src/modules/academic/`

---

## 开发前必读

1. [../教务中心/README.md](../教务中心/README.md) — 尤其融合设计（`/admin/academic` vs `/admin/academic-affairs`）  
2. [../教务中心/13B-教务中心与现有系统融合设计.md](../教务中心/13B-教务中心与现有系统融合设计.md)  
3. 本目录深化设计（参考，不覆盖教务总册）

---

## 代码事实源

- `frontend/src/modules/academic/`  
- `backend/app/api/v1/academic.py`、`backend/app/models/academic.py`
