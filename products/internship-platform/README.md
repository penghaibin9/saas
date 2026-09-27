# 跃科岗位实习管理平台 · Standalone

> 分拆基线：`penghaibin9/saas@adea054e2fd59cc0b83bbdb22f10ec98a8e2fd8c`
> 需求基线：《益阳职业技术学院学生实习管理平台服务项目采购需求》及 2026-09-27 对照审计/整改文档。

## 目标

从现有学生全生命周期 SaaS 中无损抽离岗位实习业务域，形成可独立部署、独立 MySQL、独立升级的岗位实习产品。

固定路线：

```text
现有岗位实习业务域无损抽离
→ 最小公共底座
→ 去就业/平台强耦合
→ 全新 Standalone 数据库基线
→ 管理/教师PC + 学生PC + 移动端 + 企业协同端独立运行
→ 按益阳 88 项采购需求补齐
→ G01～G20 真链路验收
```

## 施工阶段

- W0：冻结 main、源码闭包、依赖图、禁止跨域边界。
- W1：Standalone 后端骨架、最小公共底座、独立数据库基线。
- W2：岗位实习后端全部接活，消除对教务/学工/毕设/迎新/平台生命周期的强依赖。
- W3：管理/教师 PC、学生 PC、移动端、企业协同端五个交付面运行。
- W4：按 C01～C08 补齐益阳采购 88 项需求。
- W5：执行 G01～G20，形成真实验收证据。

## 红线

1. 不修改原 SaaS 岗位实习生产实现来“迁就”Standalone；抽离代码位于本目录。
2. 不复制整个 SaaS；共享依赖必须进入抽离 Manifest，并解释保留理由。
3. Standalone 后端禁止直接依赖 `academic_affairs`、`student_affairs`、`graduation`、`orientation`、`campus_service`。
4. 就业衔接、学生生命周期回写统一通过 Gateway。
5. 原 SaaS 的历史 Alembic 链不直接作为 Standalone 安装链；Standalone 从新的 `0001` 基线开始。
6. 无真实授权/回执时，不宣称已完成工商公示系统或监管平台真实对接。


## PR #275 施工总控

后续所有智能体、Codex、Claude Code 或人工施工，都必须先阅读：

`products/internship-platform/docs/01-PR275-Standalone-总体任务与施工总控.md`

该文档是本分支的唯一总体任务基线；不得另起一套产品、不得跳过阶段、不得把未验收功能写成已完成。
