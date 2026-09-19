/**
 * Frontend configuration for Agent Office
 *
 * Controls sync strategy, validation, and backend integration
 */

export const CONFIG = {
  // Phase 1: Backend Integration
  USE_PYTHON_BACKEND: true,
  PYTHON_BACKEND_URL: import.meta.env.VITE_PYTHON_BACKEND_URL || 'http://localhost:8000',

  // Phase 2: Type Validation
  VALIDATE_RESPONSES: true,
  VALIDATION_MODE: 'strict', // 'strict', 'warn', 'silent'

  // Phase 3: Real-Time Events
  SYNC_STRATEGY: 'sse', // 'sse', 'polling'
  SSE_CONFIG: {
    MAX_RETRIES: 5,
    INITIAL_DELAY: 1000,
    MAX_DELAY: 30000,
    TIMEOUT: 300000,
  },

  // Phase 4: Frontend State Management
  FRONTEND_TASK_CREATION: false, // All tasks created on backend
  TASK_CACHE_SIZE: 1000,

  // Phase 5: Polling Deprecation
  POLLING_ENABLED: false,
  POLLING_FALLBACK_ONLY: true, // Use polling only if SSE fails
  POLLING_INTERVAL: 10000, // 10 seconds (was 6 in Phase 1)

  // API Configuration
  API_TIMEOUT: 5000,
  API_RETRY_COUNT: 3,
};

// Derived config
export const API_URL = CONFIG.PYTHON_BACKEND_URL;
export const USE_SSE = CONFIG.SYNC_STRATEGY === 'sse';
export const USE_POLLING_ONLY = CONFIG.SYNC_STRATEGY === 'polling' ||
  (USE_SSE && CONFIG.POLLING_FALLBACK_ONLY);

// Export feature flags
export function isFeatureEnabled(feature) {
  const key = `FEATURE_${feature.toUpperCase()}`;
  return CONFIG[key] !== false;
}
