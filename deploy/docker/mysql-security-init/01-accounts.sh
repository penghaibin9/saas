#!/usr/bin/env bash
# Official MySQL EMPTY-volume initialization only. Never delete an existing
# volume to trigger this script; existing grants need an independently reviewed migration.
set -euo pipefail
[[ "${MYSQL_DATABASE:-}" == "saas_lifecycle" ]] || { echo 'Unexpected database' >&2; exit 1; }
[[ "${MYSQL_USER:-}" == "saas_runtime" ]] || { echo 'Unexpected runtime account' >&2; exit 1; }
[[ "${MIGRATOR_PASSWORD:-}" =~ ^[a-f0-9]{64}$ ]] || { echo 'Invalid migrator credential' >&2; exit 1; }
# The official entrypoint may source non-executable scripts. Confine MYSQL_PWD
# to a subshell and never enable xtrace or include a password in command arguments.
(
  export MYSQL_PWD="${MYSQL_ROOT_PASSWORD:?}"
  mysql --protocol=socket -uroot <<SQL
CREATE USER 'saas_migrator'@'%' IDENTIFIED BY '${MIGRATOR_PASSWORD}';
GRANT ALL PRIVILEGES ON \`saas_lifecycle\`.* TO 'saas_migrator'@'%';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'saas_runtime'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON \`saas_lifecycle\`.* TO 'saas_runtime'@'%';
SQL
)
