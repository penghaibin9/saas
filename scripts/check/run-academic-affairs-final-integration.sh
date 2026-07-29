#!/usr/bin/env bash
set -euo pipefail

: "${SOURCE_BRANCH:=refactor/academic-affairs-4ends}"
: "${FINAL_BRANCH:=integrate/academic-affairs-final-20260729}"
: "${SECOND_STAGE_MAIN:=7ffa498e8604c4ba6961e87807dbcbc522f67baa}"

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

git config user.name "academic-affairs-integration-bot"
git config user.email "academic-affairs-integration@users.noreply.github.com"
git fetch origin main "$SOURCE_BRANCH" --prune
MAIN_SHA=$(git rev-parse origin/main)
SOURCE_SHA=$(git rev-parse "origin/$SOURCE_BRANCH")
export MAIN_SHA SOURCE_SHA
printf 'MAIN_SHA=%s\nSOURCE_SHA=%s\n' "$MAIN_SHA" "$SOURCE_SHA" | tee /tmp/frozen-heads.env

echo "== 冻结基准 =="
echo "main=$MAIN_SHA"
echo "source=$SOURCE_SHA"
git diff --name-only "$SECOND_STAGE_MAIN" "$MAIN_SHA" | sort -u | tee /tmp/main-after-stage2.txt

# 施工源必须先满足第二阶段核心兼容合同；不满足则禁止创建最终分支。
git checkout --detach "$SOURCE_SHA"
(
  cd backend
  python -m compileall -q app tests
  pytest -q \
    tests/test_aa_main_migration_compat.py \
    tests/test_aa_model_extension_compat.py \
    tests/test_aa_route_registration_main_compat.py \
    tests/test_aa_route_uniqueness.py \
    tests/test_aa_shared_exception_compat.py \
    tests/test_aa_source_branch_dependency_closure.py \
    tests/test_aa_student_portal_route_main_compat.py \
    tests/test_aa_miniapp_main_compat.py \
    tests/test_aa_main_permission_middleware_compat.py \
    tests/test_aa_scope_fail_closed.py \
    tests/test_security_student_identity.py
)
echo source_compat=success > /tmp/source-validation.env

# 按用户要求真实执行一次 merge --squash，仅用于记录冲突；随后丢弃结果，
# 从最新 main 重建干净分支并按第二阶段白名单导入，避免旧分支覆盖共享能力。
git checkout -B __academic_squash_audit "$MAIN_SHA"
set +e
git merge --squash --no-commit "$SOURCE_SHA" > /tmp/squash-audit.log 2>&1
SQUASH_EXIT=$?
set -e
git diff --name-only --diff-filter=U | sort -u > /tmp/squash-conflicts.txt
printf 'SQUASH_EXIT=%s\nCONFLICT_COUNT=%s\n' "$SQUASH_EXIT" "$(wc -l < /tmp/squash-conflicts.txt)" | tee /tmp/squash-result.env
git reset --hard "$MAIN_SHA"
git clean -fd
git checkout -B "$FINAL_BRANCH" "$MAIN_SHA"

is_allowed() {
  case "$1" in
    backend/alembic/versions/0127_aa_*|\
    backend/alembic/versions/0128_aa_*|\
    backend/alembic/versions/0129_aa_*|\
    backend/alembic/versions/0130_aa_*|\
    backend/alembic/versions/0131_aa_*|\
    backend/alembic/versions/0132_aa_*|\
    backend/alembic/versions/0133_aa_*|\
    backend/alembic/versions/0134_aa_*|\
    backend/app/modules/academic_affairs/*|\
    backend/app/models/academic_affairs_*|\
    backend/app/models/academic_grade_extensions.py|\
    backend/tests/test_aa_*|\
    backend/tests/test_security_student_identity.py|\
    frontend/src/modules/academicAffairs/*|\
    student-portal/src/views/academic/*|\
    student-portal/src/router/academicRoutes.js|\
    miniapp/src/pages/student/academic-affairs/*|\
    miniapp/src/pages/teacher/academic-affairs/*|\
    miniapp/src/pages/teacher/academic-task/*|\
    miniapp/src/pages/teacher/academic-warning/*|\
    miniapp/src/pages/teacher/exam-defer/*|\
    miniapp/src/pages/teacher/my-schedule/*|\
    miniapp/src/services/academic*.js|\
    miniapp/src/stores/sessionAcademicPlugin.js)
      return 0 ;;

    backend/app/api/v1/route_registration.py|\
    backend/app/core/exceptions.py|\
    backend/app/models/__init__.py|\
    backend/app/services/mobile_student_identity_facade.py|\
    backend/app/student_portal/services/__init__.py|\
    backend/app/student_portal/services/academic_*.py|\
    frontend/src/config/adminMenu.js|\
    frontend/src/components/common/AppStatusTag.vue|\
    student-portal/src/components/StatusTag.vue|\
    student-portal/src/main.js|\
    student-portal/src/router/index.js|\
    student-portal/src/services/portalApi.js|\
    student-portal/src/views/home/HomeView.vue|\
    miniapp/src/components/AppInlineAlert.vue|\
    miniapp/src/components/MobileNavBar.vue|\
    miniapp/src/components/MobileStatusTag.vue|\
    miniapp/src/main.js|\
    miniapp/src/services/request.js|\
    miniapp/src/services/sensitiveDraftStorage.js|\
    miniapp/src/services/studentApi.js|\
    miniapp/src/services/teacherApi.js|\
    miniapp/src/stores/session.js|\
    miniapp/src/styles/tokens.css)
      return 0 ;;
  esac
  return 1
}

: > /tmp/imported-files.txt
: > /tmp/skipped-files.txt
while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  if is_allowed "$path"; then
    if git cat-file -e "$SOURCE_SHA:$path" 2>/dev/null; then
      git checkout "$SOURCE_SHA" -- "$path"
      echo "$path" >> /tmp/imported-files.txt
    fi
  else
    echo "$path" >> /tmp/skipped-files.txt
  fi
done < <(git diff --name-only --diff-filter=ACMRT "$MAIN_SHA" "$SOURCE_SHA")

while IFS= read -r path; do
  [[ -n "$path" ]] || continue
  if is_allowed "$path"; then
    git rm -f --ignore-unmatch -- "$path"
    echo "$path" >> /tmp/imported-files.txt
  fi
done < <(git diff --name-only --diff-filter=D "$MAIN_SHA" "$SOURCE_SHA")

sort -u -o /tmp/imported-files.txt /tmp/imported-files.txt
sort -u -o /tmp/skipped-files.txt /tmp/skipped-files.txt

# 不带入施工期临时合并迁移；在最新 main 图上生成最终单一 head。
rm -f backend/alembic/versions/aa_merge_main_20260728_heads.py
(
  cd backend
  mapfile -t HEADS < <(alembic heads | awk '/\(head\)/ {print $1}')
  if [[ ${#HEADS[@]} -gt 1 ]]; then
    alembic merge -r aa_final_20260729 -m "merge academic affairs final with main" heads
  fi
  test "$(alembic heads | grep -c '(head)')" -eq 1
  alembic heads | tee /tmp/alembic-heads.txt
)

{
  git diff --name-only "$MAIN_SHA"
  git ls-files --others --exclude-standard
} | sort -u > /tmp/final-files.txt

# 最终分支不得携带毕设、实习、学工施工成果，也不得覆盖这些高风险共享底座。
BAD=$(grep -E '(^|/)(graduation|internship|student_affairs|studentAffairs)(/|_)' /tmp/final-files.txt \
  | grep -vE '^backend/app/modules/academic_affairs/|^frontend/src/modules/academicAffairs/' || true)
if [[ -n "$BAD" ]]; then
  echo "发现跨域文件，拒绝集成："
  echo "$BAD"
  exit 1
fi
for forbidden in \
  backend/app/core/config.py \
  backend/app/core/context.py \
  backend/app/core/permissions.py \
  backend/app/middleware/context.py \
  backend/app/core/security.py; do
  if grep -Fxq "$forbidden" /tmp/final-files.txt; then
    echo "共享高风险文件不得由最终教务分支覆盖：$forbidden"
    exit 1
  fi
done

# 基础验证全部在提交和推送之前完成。
(
  cd backend
  python -m compileall -q app tests
  test "$(alembic heads | grep -c '(head)')" -eq 1
  python -c "from app.db.session import get_engine; from app.models.base import Base; import app.models; Base.metadata.create_all(bind=get_engine())"
  timeout 35m pytest -q tests/test_aa_*.py tests/test_security_student_identity.py -p no:warnings --durations=20
)
echo backend=success > /tmp/backend-validation.env

(
  cd frontend
  npm ci
  npm run build
)
echo teacher_pc=success > /tmp/teacher-pc-validation.env

(
  cd student-portal
  npm ci
  npm run build
)
echo student_pc=success > /tmp/student-pc-validation.env

(
  cd miniapp
  npm ci
  npm run build:h5
  npm run build:mp-weixin
)
echo miniapp=success > /tmp/miniapp-validation.env

# 精确暂存最终差异，不使用 git add -A。
git diff --name-only -z | xargs -0 -r git add --
git ls-files --others --exclude-standard -z | xargs -0 -r git add --
if git diff --cached --quiet; then
  echo "最终集成没有可提交差异"
  exit 1
fi

git commit -m "feat(academic-affairs): integrate four-end academic affairs delivery"
FINAL_SHA=$(git rev-parse HEAD)
CHANGED_FILES=$(git diff --name-only "$MAIN_SHA" "$FINAL_SHA" | wc -l)
COMMIT_COUNT=$(git rev-list --count "$MAIN_SHA..$FINAL_SHA")
export FINAL_SHA CHANGED_FILES COMMIT_COUNT
printf 'FINAL_SHA=%s\nCHANGED_FILES=%s\nCOMMIT_COUNT=%s\n' "$FINAL_SHA" "$CHANGED_FILES" "$COMMIT_COUNT" | tee /tmp/final-result.env
git push --set-upstream origin "$FINAL_BRANCH"

CONFLICT_COUNT=$(wc -l < /tmp/squash-conflicts.txt)
{
  echo "## 教务最终集成"
  echo
  echo "本 Draft PR 从最新 main 创建，以一个压缩交付提交导入教务四端最终成果，替代施工记录 PR #17。"
  echo
  echo "- 冻结 main：\`$MAIN_SHA\`"
  echo "- 教务施工源：\`$SOURCE_SHA\`"
  echo "- 最终分支：\`$FINAL_BRANCH\`"
  echo "- 最终 HEAD：\`$FINAL_SHA\`"
  echo "- 最终变更文件：$CHANGED_FILES"
  echo "- 最终提交数：$COMMIT_COUNT"
  echo "- merge --squash 冲突文件：$CONFLICT_COUNT"
  echo
  echo "### 冲突解决原则"
  echo "- 教务独占目录采用已通过专项验证的施工成果。"
  echo "- 公共共享目录以最新 main 为准，只接回第二阶段确认的教务扩展。"
  echo "- 毕设、岗位实习、学工文件不从施工源导入。"
  echo "- Alembic 不改写 main 已使用迁移，以新图合并 revision 收敛为单一 head。"
  echo
  echo "### 基础验证"
  echo "- [x] Python 编译与导入"
  echo "- [x] Alembic 单一 head"
  echo "- [x] MySQL create_all"
  echo "- [x] 教务后端定向测试"
  echo "- [x] 教师/教务 PC build"
  echo "- [x] 学生 PC build"
  echo "- [x] 小程序 H5 build"
  echo "- [x] 微信小程序 build"
  echo
  echo "PR #17 继续保持 Draft、Open、未合并；本 PR 不自动合并、不标记 Ready。"
  echo
  echo "<details><summary>merge --squash 实际冲突文件</summary>"
  echo
  sed 's/^/- `/' /tmp/squash-conflicts.txt | sed 's/$/`/'
  echo
  echo "</details>"
} > /tmp/final-pr-body.md

PR_URL=""
set +e
EXISTING=$(gh pr list --repo "$GITHUB_REPOSITORY" --state open --head "$FINAL_BRANCH" --json number --jq '.[0].number // empty' 2>/tmp/gh-pr-error.log)
if [[ -n "$EXISTING" ]]; then
  gh pr edit "$EXISTING" --repo "$GITHUB_REPOSITORY" --title "Draft: 教务四端最终集成" --body-file /tmp/final-pr-body.md
  PR_URL=$(gh pr view "$EXISTING" --repo "$GITHUB_REPOSITORY" --json url --jq .url)
else
  PR_URL=$(gh pr create --repo "$GITHUB_REPOSITORY" --draft --base main --head "$FINAL_BRANCH" \
    --title "Draft: 教务四端最终集成" --body-file /tmp/final-pr-body.md 2>>/tmp/gh-pr-error.log)
fi
PR_EXIT=$?
set -e
printf 'PR_EXIT=%s\nPR_URL=%s\n' "$PR_EXIT" "$PR_URL" | tee /tmp/pr-result.env

{
  echo "# 教务最终集成执行摘要"
  echo
  echo "- main: $MAIN_SHA"
  echo "- source: $SOURCE_SHA"
  echo "- final branch: $FINAL_BRANCH"
  echo "- final head: $FINAL_SHA"
  echo "- changed files: $CHANGED_FILES"
  echo "- commits: $COMMIT_COUNT"
  echo "- Draft PR: ${PR_URL:-需要由仓库管理员创建}"
  echo
  echo "## merge --squash 实际冲突文件（$CONFLICT_COUNT）"
  sed 's/^/- `/' /tmp/squash-conflicts.txt | sed 's/$/`/'
} >> "$GITHUB_STEP_SUMMARY"
