// test-constants.ts — Production E2E test user
// For local dev seeding, run: scripts/functional-tests/seed-test-data.sh
//
// Override with environment variables for custom test users:
//   E2E_USER_EMAIL=greg@disruptiveconsult.com E2E_USER_PASSWORD=xxx npx playwright test

export const TEST_USER = {
  email: process.env.E2E_USER_EMAIL || 'greg@disruptiveconsult.com',
  password: process.env.E2E_USER_PASSWORD || 'Test1234',
};

export const SEEDED_IDS = {
  tenantId: '',
  baselineId: '',
  draftId: '',
  runId: '',
  afsEngagementId: '',
  budgetId: '',
  covenantId: '',
  boardPackId: '',
  workflowTemplateId: '',
};

export const BASE_URL = 'https://www.virtual-analyst.ai';
export const API_URL = 'https://www.virtual-analyst.ai/api/v1';
