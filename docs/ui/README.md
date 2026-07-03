# UI 设计稿归档总说明

> **后续 AI 开发前，必须先阅读 [`docs/00-只看这个-项目入口.md`](../00-只看这个-项目入口.md)。**

---

## 目录一览

| 端 | 目录 | 说明 |
| --- | --- | --- |
| **PC 管理端** | [`fable5-pc-final/`](./fable5-pc-final/) | PC 最终设计稿归档，已基本定型 |
| **小程序 / 移动工作台** | [`fable5-miniapp-final/`](./fable5-miniapp-final/) | 学生小程序、教师移动工作台设计稿归档 |

---

## PC 设计稿

**路径**：`docs/ui/fable5-pc-final/`

存放：PC 管理端最终设计稿、zip、PDF、HTML、截图、README。

后续开发 PC 页面 **必须参考本目录**。

---

## 小程序设计稿

**路径**：`docs/ui/fable5-miniapp-final/`

存放：学生小程序、教师移动工作台最终设计稿、zip、PDF、HTML、截图、README。

后续开发小程序 **必须参考本目录**，并同时读取 08A / 08B 业务文档。

---

## 重要规则

1. **PC 和小程序不能混用** — PC 设计稿不能代替小程序设计稿，小程序不能做成 PC 缩小版。
2. **设计稿只作为视觉参考** — 不是生产代码，不得把导出的 HTML 直接复制进 `frontend/src`。
3. **不得把设计稿放进 `backend/`**。
4. 学校品牌必须来自 `tenantBrandConfig`，禁止硬编码学校名称。

---

## 快速入口

- 项目总入口（新手必读）：[`docs/00-只看这个-项目入口.md`](../00-只看这个-项目入口.md)
- PC 设计稿详情：[`fable5-pc-final/README.md`](./fable5-pc-final/README.md)
- 小程序设计稿详情：[`fable5-miniapp-final/README.md`](./fable5-miniapp-final/README.md)
