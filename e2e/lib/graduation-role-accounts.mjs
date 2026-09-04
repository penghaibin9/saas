const account = (prefix, fallback) => ({
  tenant: process.env[`${prefix}_TENANT`] || fallback.tenant,
  username: process.env[`${prefix}_USERNAME`] || fallback.username,
  password: process.env[`${prefix}_PASSWORD`] || fallback.password
})

/**
 * Graduation-only browser actors. Keeping these identities outside the shared
 * E2E config prevents unrelated module workflows from depending on Graduation
 * role semantics while retaining environment-variable overrides in CI.
 */
export const graduationRoles = Object.freeze({
  reviewer: account('E2E_GRADUATION_REVIEWER', {
    tenant: 'sandbox-school', username: 'e2e_reviewer', password: 'E2eTest@2026'
  }),
  defenseExpert: account('E2E_GRADUATION_DEFENSE', {
    tenant: 'sandbox-school', username: 'e2e_defense_a', password: 'E2eTest@2026'
  }),
  defenseChair: account('E2E_GRADUATION_DEFENSE_B', {
    tenant: 'sandbox-school', username: 'e2e_defense_b', password: 'E2eTest@2026'
  }),
  defenseSecretary: account('E2E_GRADUATION_SECRETARY', {
    tenant: 'sandbox-school', username: 'e2e_college_secretary', password: 'E2eTest@2026'
  })
})
