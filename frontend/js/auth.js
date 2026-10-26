/**
 * FarmerLinkage — Authentication & Session Manager
 * Handles login, registration, role verification, and route protection.
 */
const Auth = {
  /**
   * Get current auth token
   */
  getToken() {
    return localStorage.getItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN);
  },

  /**
   * Get authenticated user profile object
   */
  getUser() {
    try {
      const data = localStorage.getItem(CONFIG.STORAGE_KEYS.USER_DATA);
      return data ? JSON.parse(data) : null;
    } catch {
      return null;
    }
  },

  /**
   * Check if user is logged in
   */
  isAuthenticated() {
    return !!this.getToken() && !!this.getUser();
  },

  /**
   * Set user session in localStorage
   */
  setSession(token, user) {
    if (token) {
      localStorage.setItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN, token);
    }
    if (user) {
      localStorage.setItem(CONFIG.STORAGE_KEYS.USER_DATA, JSON.stringify(user));
    }
  },

  /**
   * Clear session and log out
   */
  logout() {
    localStorage.removeItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN);
    localStorage.removeItem(CONFIG.STORAGE_KEYS.USER_DATA);
    window.location.href = 'login.html';
  },

  /**
   * Authenticate with backend: POST /api/auth/login
   */
  async login(usernameOrEmail, password) {
    if (!usernameOrEmail || !password) {
      throw new Error('Please provide both username/email and password.');
    }

    const payload = {
      username_or_email: usernameOrEmail.trim(),
      password: password,
    };

    const response = await api.post('/auth/login', payload);

    if (!response || !response.access_token || !response.user) {
      throw new Error('Authentication succeeded but server returned incomplete session data.');
    }

    this.setSession(response.access_token, response.user);
    return response.user;
  },

  /**
   * Register new user with backend: POST /api/auth/register
   */
  async register(registrationData) {
    const { full_name, email, phone_number, password, role } = registrationData;

    if (!['FARMER', 'BUYER'].includes(role)) {
      throw new Error('Public registration only supports Farmer or Buyer accounts.');
    }

    const payload = {
      full_name: full_name.trim(),
      email: email.trim(),
      phone_number: phone_number.trim(),
      password: password,
      role: role,
    };

    const response = await api.post('/auth/register', payload);
    return response;
  },

  /**
   * Verify authenticated user against GET /api/auth/me
   */
  async refreshUser() {
    try {
      const user = await api.get('/auth/me');
      if (user) {
        localStorage.setItem(CONFIG.STORAGE_KEYS.USER_DATA, JSON.stringify(user));
        return user;
      }
    } catch (err) {
      if (err.status === 401) {
        this.logout();
      }
      throw err;
    }
  },

  /**
   * Route Guard: Require authentication and optionally specific role(s)
   */
  requireAuth(allowedRoles = []) {
    if (!this.isAuthenticated()) {
      window.location.href = `login.html?redirect=${encodeURIComponent(window.location.pathname)}`;
      return false;
    }

    const user = this.getUser();
    if (allowedRoles.length > 0 && (!user || !allowedRoles.includes(user.role))) {
      // User is authenticated but does not have the required role
      Utils.showToast(`Access restricted: this page requires a ${allowedRoles.join('/')} account.`, 'error');
      // Redirect to user's authorized dashboard
      const target = CONFIG.ROLE_REDIRECTS[user.role] || 'index.html';
      setTimeout(() => {
        window.location.href = target;
      }, 1500);
      return false;
    }

    return true;
  },

  /**
   * Route Guard: Redirect already-authenticated users away from login/register
   */
  redirectIfAuthenticated() {
    if (this.isAuthenticated()) {
      const user = this.getUser();
      const target = (user && CONFIG.ROLE_REDIRECTS[user.role]) ? CONFIG.ROLE_REDIRECTS[user.role] : 'index.html';
      window.location.href = target;
    }
  },

  /**
   * Get role dashboard destination
   */
  getDashboardUrl() {
    const user = this.getUser();
    if (!user) return 'login.html';
    return CONFIG.ROLE_REDIRECTS[user.role] || 'index.html';
  },
};

// Global session expired event listener
window.addEventListener('session-expired', () => {
  Utils.showToast('Your session has expired. Please sign in again.', 'warning');
  setTimeout(() => {
    window.location.href = 'login.html';
  }, 1000);
});
