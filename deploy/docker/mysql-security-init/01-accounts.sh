#!/usr/bin/env bash
# Official MySQL EMPTY-volume initialization only. Never delete an existing
# volume to trigger this script; existing grants need a reviewed migration.
# Non-executable .sh files are SOURCED by the official entrypoint. Keep every
# option/variable in this subshell: leaking nounset breaks its optional variables.
(
  set -euo pipefail
  [[ "${MYSQL_DATABASE:-}" == "saas_lifecycle" ]] || { echo 'Unexpected database' >&2; exit 1; }
  [[ "${MYSQL_USER:-}" == "saas_runtime" ]] || { echo 'Unexpected runtime account' >&2; exit 1; }
  [[ "${MIGRATOR_PASSWORD:-}" =~ ^[a-f0-9]{64}$ ]] || { echo 'Invalid migrator credential' >&2; exit 1; }
  # Credentials never enter argv; respect the temporary server's actual socket.
  export MYSQL_PWD="${MYSQL_ROOT_PASSWORD:?}"
  # Database-level GRANT treats _ as a wildcard on MySQL 8.0. Escape it even
  # inside backticks, so a similarly named schema is not accidentally authorized.
  mysql --protocol=socket --socket="${SOCKET:-/var/run/mysqld/mysqld.sock}" -uroot <<SQL
CREATE USER 'saas_migrator'@'%' IDENTIFIED BY '${MIGRATOR_PASSWORD}';
GRANT ALL PRIVILEGES ON \`saas\\_lifecycle\`.* TO 'saas_migrator'@'%';
REVOKE ALL PRIVILEGES, GRANT OPTION FROM 'saas_runtime'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE ON \`saas\\_lifecycle\`.* TO 'saas_runtime'@'%';
SQL
)
