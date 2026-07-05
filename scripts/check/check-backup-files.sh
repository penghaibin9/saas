#!/usr/bin/env bash
# 备份文件检查：存在性 + 新鲜度 + gzip 完整性。不写死密码/路径。
# 用法：bash scripts/check/check-backup-files.sh [备份目录]
set -u
DIR="${1:-/var/backups/school-lifecycle}"
MAX_AGE_H="${MAX_AGE_HOURS:-26}"   # 最近一份备份不应超过 26 小时（每日备份留余量）
FAIL=0
echo "== 备份检查：$DIR =="
if [ ! -d "$DIR" ]; then echo "  [FAIL] 备份目录不存在"; exit 1; fi

LATEST=$(ls -t "$DIR"/*.sql.gz 2>/dev/null | head -1)
if [ -z "$LATEST" ]; then echo "  [FAIL] 无 .sql.gz 备份文件"; exit 1; fi
echo "  最新备份：$LATEST"

# 新鲜度
NOW=$(date +%s); MT=$(date -r "$LATEST" +%s 2>/dev/null || stat -c %Y "$LATEST")
AGE_H=$(( (NOW - MT) / 3600 ))
if [ "$AGE_H" -le "$MAX_AGE_H" ]; then echo "  [PASS] 新鲜度 ${AGE_H}h ≤ ${MAX_AGE_H}h"; \
  else echo "  [FAIL] 最新备份已 ${AGE_H}h，超过 ${MAX_AGE_H}h（备份任务可能没跑）"; FAIL=$((FAIL+1)); fi

# 完整性
if gzip -t "$LATEST" 2>/dev/null; then echo "  [PASS] gzip 完整性通过"; \
  else echo "  [FAIL] gzip 完整性校验失败（备份损坏）"; FAIL=$((FAIL+1)); fi

# 数量
CNT=$(ls "$DIR"/*.sql.gz 2>/dev/null | wc -l)
echo "  备份文件数：$CNT"
[ "$CNT" -ge 1 ] && echo "  [PASS] 存在备份" || { echo "  [FAIL] 无备份"; FAIL=$((FAIL+1)); }

echo "== 结束：FAIL=$FAIL =="
[ "$FAIL" -eq 0 ] || exit 1
exit 0
