# 容量与可观测性验收报告

> 本报告只记录已真实执行的结果。未执行的档位必须写“未验证”，不得推测为可承载。
> Teacher V3 T9 必须把 `cold` 身份容量证据与 `warm` 缓存诊断分开：warm 即使延迟很好，也不能证明并发身份规模。

## 1. 验收结论

- 测试日期：
- Git 提交：
- 测试环境：预发 / 生产影子环境
- 目标域名：
- 测试档位：smoke / baseline / p300 / p500 / p1000 / p3000
- 场景：student / teacher / mixed
- 身份模式：cold / warm
- warm 身份池大小（仅 warm）：
- 最终结论：通过 / 有条件通过 / 不通过
- 当前可承诺容量：
- 明确不可承诺口径：
- `productionCapacityEvidenceEligible`：true / false

## 2. 环境基线

| 项目 | 实际配置 |
|---|---|
| 腾讯云实例规格 |  |
| CPU / 内存 |  |
| 操作系统 |  |
| Nginx 版本与 worker_connections |  |
| 后端实例数 |  |
| WEB_CONCURRENCY |  |
| MULTI_INSTANCE |  |
| SCHEDULER_MODE |  |
| Redis 规格与连接方式 |  |
| MySQL 规格 |  |
| DB_POOL_SIZE / DB_MAX_OVERFLOW |  |
| 数据规模：租户 / 学生 / 教师 |  |
| UnifiedMessage 数据规模 |  |

## 3. 数据与账号口径

- 学生令牌池总数：
- 教师令牌池总数：
- 本次实际唯一学生身份数：
- 本次实际唯一教师身份数：
- 本次实际唯一教师 context 数：
- 教师角色比例 `teacherRoleRatios`：
- 学生占比：
- 身份模式：`cold` / `warm`
- warm 模式有效身份池：
- 是否使用真实租户隔离：
- 是否包含文件上传下载：否（E阶段明确禁止）
- 是否包含写操作：否（第一批只读容量基线）

判定口径：

- `cold`：目标并发档位需要足够的独立 token/identity；用于容量证明。
- `warm`：故意复用小身份池观察缓存效果；只作 `warm-cache-diagnostic`，禁止用于对外容量承诺。
- 本地 p300/p500 自包含 Runner 是稳定性/功能诊断；生产容量结论仍需 HTTPS 预发或生产影子环境证据。

## 4. 核心指标

| 档位 | 身份模式 | 持续时间 | 请求数 | RPS | P50 | P95 | P99 | 最大耗时 | 错误率 | 检查通过率 | 结论 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| smoke | cold |  |  |  |  |  |  |  |  |  |  |
| baseline | cold |  |  |  |  |  |  |  |  |  |  |
| baseline | warm |  |  |  |  |  |  |  |  |  |  |
| p300 | cold |  |  |  |  |  |  |  |  |  |  |
| p500 | cold |  |  |  |  |  |  |  |  |  |  |
| p1000 | cold |  |  |  |  |  |  |  |  |  |  |
| p3000 | cold |  |  |  |  |  |  |  |  |  |  |

验收线：

- HTTP错误率 `< 0.5%`
- 业务检查通过率 `> 99.5%`
- 核心读接口 `P95 < 1000ms`
- 核心读接口 `P99 < 2000ms`
- 无跨租户数据、无连接池耗尽、无持续502/504
- `missingRoutes=[]`
- cold 模式的相关学生/教师唯一身份池达到目标峰值 VU

## 5. 路由明细

| 路由标签 | P50 | P95 | P99 | 错误率 | 主要SQL/缓存 | 结论 |
|---|---:|---:|---:|---:|---|---|
| student_home |  |  |  |  |  |  |
| student_todos |  |  |  |  |  |  |
| student_messages |  |  |  |  |  |  |
| student_profile |  |  |  |  |  |  |
| student_agenda |  |  |  |  |  |  |
| student_cases |  |  |  |  |  |  |
| student_search |  |  |  |  |  |  |
| teacher_workbench |  |  |  |  |  |  |
| teacher_todos |  |  |  |  |  |  |
| teacher_risk_students |  |  |  |  |  |  |
| teacher_my_students |  |  |  |  | keyset + SQL visibility |  |
| teacher_student360 |  |  |  |  | object-scope projection |  |
| teacher_messages |  |  |  |  | eventAt/id keyset |  |
| teacher_visit |  |  |  |  | server-authoritative target list |  |
| teacher_employment |  |  |  |  | scoped overview |  |
| teacher_employment_verification |  |  |  |  | scoped single-object verification |  |

## 6. Teacher Messages / EXPLAIN 证据

| 热路径 | rows examined | access type | key | filesort | 预算 | 结论 |
|---|---:|---|---|---|---:|---|
| teacher_messages_page |  |  |  |  | 2000 |  |
| teacher_messages_badges |  |  |  |  | 2000 |  |

- 是否需要 targeted index：是 / 否
- 若新增索引，对应 migration：
- 修复前 EXPLAIN artifact：
- 修复后 EXPLAIN artifact：
- rollback 验证：

## 7. 资源与可观测性

| 指标 | 峰值 | 稳态 | 是否异常 |
|---|---:|---:|---|
| CPU |  |  |  |
| 内存 |  |  |  |
| 后端Worker利用率 |  |  |  |
| Nginx活跃连接 |  |  |  |
| MySQL活跃连接 |  |  |  |
| MySQL连接池等待 |  |  |  |
| Redis命中率 |  |  |  |
| Redis错误率 |  |  |  |
| 慢SQL数量 |  |  |  |
| 499 / 502 / 504 |  |  |  |
| pageLatency |  |  |  |
| scopeMode |  |  |  |
| unknownAction |  |  |  |
| focusFail |  |  |  |
| conflict409 |  |  |  |

隐私复核：上述可观测性只允许匿名路由/动作/范围/耗时分桶，不记录姓名、学号、手机号、消息正文、SQL 参数。

## 8. 首个瓶颈与修复

- 首个瓶颈：
- 证据：
- 根因：
- 修复内容：
- 修复前后对比：
- 是否需要扩容：

## 9. 风险与容量边界

- 已验证最大 cold 档位：
- warm-cache 对照结果：
- 最大稳定RPS：
- 注册用户规模验证：
- 日活规模推算依据：
- 未验证场景：
- 禁止对外宣传的容量口径：

## 10. 上线裁决

- [ ] Redis已启用并验证
- [ ] 多Worker/多实例配置已验证
- [ ] Scheduler已从Web进程拆出
- [ ] MySQL连接池按实例数核算
- [ ] Nginx超时与连接数已核对
- [ ] smoke cold 与 baseline cold 全绿
- [ ] baseline warm-cache 对照已执行并明确标记“不可作为容量证明”
- [ ] Teacher V3 MyStudents / Student360 / Messages / Visit / Employment Verification 全部出现在同头 route artifact
- [ ] Teacher Messages EXPLAIN 在预算内，或已用 targeted index + migration + rollback 收口
- [ ] 至少完成一个目标高峰 cold 档位
- [ ] 监控和告警可定位P95、错误率、慢SQL与502/504
- [ ] 压测后数据完整性复核通过
- [ ] 容量结论没有夸大为“10万人同时在线”
