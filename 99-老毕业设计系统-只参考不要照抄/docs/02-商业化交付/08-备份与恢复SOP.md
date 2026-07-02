# 数据备份与恢复 SOP（私有化交付）

> 面向职院 IT 的可执行手册。目标：任何一台装有 MySQL 客户端的机器，都能在 10 分钟内从备份恢复出可用系统，并支持「迁校 / 换机」。

## 一、前置

- 已安装 `mysqldump` 与 `mysql` 客户端，且在 PATH 中。
- `internship-backend/.env` 中 `DB_HOST / DB_USER / DB_PASSWORD / DB_NAME` 配置正确。

## 二、备份（建议每日 + 上线前）

```bash
cd internship-backend
npm run backup:db                 # 默认输出到 ./backups/backup-<库>-<时间>.sql
npm run backup:db /data/db-backups   # 也可指定目录
```

- 脚本用 `--single-transaction --routines --triggers`，导出一致性快照，含存储过程/触发器。
- **建议**：用系统定时任务每日凌晨执行，并把 `backups/` 同步到异地对象存储；保留近 30 天。

```cron
# Linux crontab 示例：每天 02:30 备份
30 2 * * * cd /opt/internship-backend && /usr/bin/npm run backup:db >> /var/log/intern-backup.log 2>&1
```

## 三、恢复 / 迁校

```bash
cd internship-backend
npm run restore:db backups/backup-internship_management-2026-06-23T03-00-00.sql
# 恢复到指定库（迁校/改名）：
node scripts/restore-db.js <备份.sql> internship_xxxschool
# 非交互（CI/脚本）跳过确认：
node scripts/restore-db.js <备份.sql> --yes
```

- 恢复脚本会**自动创建目标库**（不存在时，utf8mb4），再通过 stdin 管道导入（跨平台）。
- 恢复**有二次确认**（覆盖同名表数据），脚本化场景加 `--yes`。
- 恢复后建议执行 `npm run migrate:up` 补齐可能的新增结构（幂等）。

## 四、SaaS 多租户说明

多租户（`TENANCY_MODE=multi`）为 **DB-per-tenant**：每所学校一个独立库。
- 备份：对每个租户库分别 `npm run backup:db <db>`（或写循环遍历 `t_tenant.db_name`）。
- 恢复/迁校：`node scripts/restore-db.js <备份.sql> <租户库名>`，互不影响。

## 五、恢复演练（验收必做）

1. 在**测试机**新建空库；
2. 用最近一次生产备份执行 `restore:db`；
3. 启动服务 `npm start`，用管理员登录，抽查：用户列表、实习分配、报酬台账、家长签署、报表总览；
4. 记录 RTO（恢复耗时）与抽查结果，留存到验收报告。

> 演练通过标准：恢复后核心数据完整、可登录、关键页面正常。建议每季度演练一次。
