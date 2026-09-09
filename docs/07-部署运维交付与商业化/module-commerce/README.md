> **前端办理入口与本轮续工**：见 [商业工作区落点与验收边界](CURRENT-UI-workbench.md)。实际HEAD以远端PR为准；下方保留历史施工记录。

> **当前进度入口（2026-09-09）**：见 [M3 销售工作区施工与剩余范围](CURRENT-M3-sales-workspace.md)。下面保留最初开工记录，其中的旧 main / #261 状态和“尚未完成”列表仅描述当时，不代表当前分支；运行验收以 PR #263 当前精确 HEAD 的回执为准。

# 模块商业化｜当前施工记录

## 已核实基线与并行边界

- 用户授权：按上传的 b44526b 商业化施工包，从 GitHub 最新 main 单独开工。
- 本轮 main：`6eda6b9e866b1b8eb51323a9926d3734b3be8fd7`。
- 分支：`feat/platform-module-commerce`；Draft PR #263。
- #261 读取时仍未合并，HEAD 为 `26b9f269d3c918c73c13dea10d08ea5b68d92c44`。
- 当前 main 的 `commercial_entitlement_authority_service.py` 路径尚不存在；不能把 #261 的商业权威或其通过记录当作本分支已有能力。
- 用户本地四中心 UI 和流程测试保持原样。本分支不修改业务页面、公共权限、现有运行授权、订单写入、主档、文件清理或退租执行器。

设计来源为上传总册第2/4/5/11节、施工卡T01–T06，以及用户后续对隔离并行开发的明确授权。
本轮只提前开发不接入客户授权的纯校验层；没有把M0或M1整个阶段改成完成。

## 本轮实际代码

### M0 只读资源普查

`scripts/check/module-commercial-inventory.py`：静态解析 backend/app 及 Alembic，核对规范模块/feature映射，枚举模型、继承字段、显式外键和待追踪逻辑ID；记录源文件指纹、动态表候选、重复表、迁移缺父/多头/循环。

CLI要求干净的精确HEAD，拒绝错版本、脏文件、仓库内输出、覆盖既有报告及不安全符号链接；结束前重新校验文件集与内容。不会导入业务、访问数据库或执行删除。

全部资源维持 UNKNOWN / UNREVIEWED / purgeAuthorized=false；报告固定标识 STATIC_ONLY。输出本身不构成销毁登记，不证明运行metadata、MySQL实表或消费者闭包。

### M1 不可变商品/订单草稿合同

`backend/app/services/commercial_catalog_contract.py`：

- `compile_sku`校验 MODULE / BUNDLE / ADDON 草稿，默认全false，规范模块与功能键一致，不隐式赠送其他中心、就业或API附加能力。
- 调用方必须提供服务端已审能力集合；它不是客户端可提交的批准依据。这里仅验证合同内容，不负责证明政策已经发布或批准人身份。
- 已编译内容保存为不可变canonical JSON；读取返回副本。组合商品绑定精确组件revision/hash；不按后来目录重新计算旧快照。
- `compile_order_draft`核对BIGINT字符串、版本/代次、十进制金额、每项独立UTC半开服务期、总分对账；Decimal运算不依赖调用者降低后的精度。
- 不接受浮点、NaN、隐式舍入、重复行号、错商品指纹、混币种或非法期间。组合订单尚缺经评审的分项价分摊时明确拒绝，不编造历史模块价格。
- 输出标明validationOnly=true、paymentRecorded=false、rightsMaterialized=false。

**尚未完成**：商品发布持久化与审计、订单项MySQL写入、同事务幂等、新迁移、历史回填、接口鉴权接入、前端录单、xlsx正式导入导出、模块订阅权威切换。本轮没有新增生产可调用路由，不能报告单模块销售已经可用。

## 本轮本地测试

```sh
python -B backend/tests/test_module_commercial_inventory.py -v
python -B backend/tests/test_commercial_catalog_contract.py -v
```

分别19和32项通过，合计51项。包括只读CLI临时Git夹具，不涉及真实客户库；不等同原施工包95个端到端场景通过。

测试所读取的现有 `platform_defaults.py` 与 `module-manifest.json` 逐文件Git blob hash对照固定main：

| 路径 | main blob |
|---|---|
| backend/app/services/platform_defaults.py | fdbae56d728eeae9bf26bf31a69a341b82b93fab |
| shared/contracts/module-manifest.json | 28cc00512601fdad27a09e55eb535ce3cfa01650 |
| backend/app/models/platform.py | 3da52dbdc753880989ff5aaf73f41e63692c268d |
| backend/app/models/base.py | 41b35b30b8fc286e48c54d8584f7f810c133e325 |

新增 `.github/workflows/module-commerce-foundation.yml` 会在真实checkout上复测并输出同HEAD的静态库存与源码归档；它不替代Main、CI或MySQL验收。尚未取得结果时只能写pending，不使用旧版本绿灯。

## 下一道完成门

1. 收取本分支exact-head扫描结果，对照动态metadata与隔离MySQL实表；逐类处理所有权/消费者/共享基础能力及政策缺口，M0仍为进行中。
2. #261合并后安全吸收main，再检查冻结Owner与模型/迁移接点；不恢复旧FEATURES，不把纯函数编译器当授权账本。
3. T05/T06接入既有控制面时，复用现有订单头和同事务审计/幂等机制；补上商品发布、订单项持久化和真实迁移/接口/浏览器/xlsx证据后，才逐项验收。
4. 本阶段禁止物理销毁、自动停校、真实付款或短信。用户尚未提供的价格与保留政策不由测试夹具代替。
