/**
 * FarmerLinkage — Central Configuration
 * All API routes and environment defaults are defined here.
 */
const CONFIG = {
  // Backend API Base URL (defaults to current origin /api or http://127.0.0.1:8000/api)
  API_BASE_URL: window.API_BASE_URL || (window.location && window.location.origin && window.location.origin.startsWith('http') ? window.location.origin + '/api' : 'http://127.0.0.1:8000/api'),


  // Supported User Roles matching backend UserRole enum
  ROLES: {
    FARMER: 'FARMER',
    BUYER: 'BUYER',
    ADMIN: 'ADMIN',
  },

  // Role dashboard destinations
  ROLE_REDIRECTS: {
    FARMER: 'farmer.html',
    BUYER: 'buyer.html',
    ADMIN: 'admin.html',
  },

  // Pagination defaults
  PAGINATION: {
    DEFAULT_LIMIT: 20,
    MAX_LIMIT: 100,
  },

  // Storage keys
  STORAGE_KEYS: {
    AUTH_TOKEN: 'farmerlinkage_token',
    USER_DATA: 'farmerlinkage_user',
    LANGUAGE: 'farmerlinkage_lang',
  },

  // Default Language
  DEFAULT_LANGUAGE: 'en',
  SUPPORTED_LANGUAGES: ['en', 'mr', 'hi'],
};

// Freeze configuration to prevent tampering
Object.freeze(CONFIG);
Object.freeze(CONFIG.ROLES);
Object.freeze(CONFIG.ROLE_REDIRECTS);
Object.freeze(CONFIG.PAGINATION);
Object.freeze(CONFIG.STORAGE_KEYS);
