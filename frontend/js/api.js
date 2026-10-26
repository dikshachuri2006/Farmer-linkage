/**
 * FarmerLinkage — Central API Client
 * Secure wrapper around Fetch API supporting authentication, error parsing, and file downloads.
 */
class ApiClient {
  constructor(baseUrl) {
    this.baseUrl = baseUrl || CONFIG.API_BASE_URL;
  }

  /**
   * Get the current authorization header if a token exists
   */
  _getAuthHeader() {
    const token = localStorage.getItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN);
    if (token) {
      return { Authorization: `Bearer ${token}` };
    }
    return {};
  }

  /**
   * Process and parse API response
   */
  async _handleResponse(response) {
    // Check for HTTP 401 Unauthorized
    if (response.status === 401) {
      // If unauthorized on protected route, clear stale token and notify
      if (localStorage.getItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN)) {
        localStorage.removeItem(CONFIG.STORAGE_KEYS.AUTH_TOKEN);
        localStorage.removeItem(CONFIG.STORAGE_KEYS.USER_DATA);
        // Dispatch session expired event
        window.dispatchEvent(new CustomEvent('session-expired'));
      }
    }

    // Try parsing JSON or fallback to text
    const contentType = response.headers.get('content-type') || '';
    let data;
    if (contentType.includes('application/json')) {
      try {
        data = await response.json();
      } catch (err) {
        data = null;
      }
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      // Extract detailed error message from FastAPI shape
      let message = 'An unexpected server error occurred.';
      if (data && typeof data === 'object') {
        if (typeof data.detail === 'string') {
          message = data.detail;
        } else if (Array.isArray(data.detail)) {
          // Pydantic validation error array
          message = data.detail.map(item => `${item.loc ? item.loc.join('.') + ': ' : ''}${item.msg}`).join(', ');
        } else if (data.message) {
          message = data.message;
        }
      } else if (typeof data === 'string' && data.trim()) {
        message = data;
      }

      const error = new Error(message);
      error.status = response.status;
      error.data = data;
      throw error;
    }

    return data;
  }

  /**
   * Generic request method
   */
  async request(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${this.baseUrl}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    
    const headers = {
      'Content-Type': 'application/json',
      ...this._getAuthHeader(),
      ...(options.headers || {}),
    };

    // If body is FormData or not JSON, remove Content-Type
    if (options.body instanceof FormData) {
      delete headers['Content-Type'];
    }

    const config = {
      ...options,
      headers,
    };

    try {
      const response = await fetch(url, config);
      return await this._handleResponse(response);
    } catch (err) {
      if (err.name === 'TypeError' && err.message.includes('fetch')) {
        const netErr = new Error('Backend connection failed. Please verify that the FarmerLinkage backend service is running on ' + this.baseUrl);
        netErr.status = 0;
        netErr.isNetworkError = true;
        throw netErr;
      }
      throw err;
    }
  }

  get(endpoint, params = {}) {
    let url = endpoint;
    const query = new URLSearchParams();
    for (const [key, val] of Object.entries(params)) {
      if (val !== undefined && val !== null && val !== '') {
        query.append(key, val);
      }
    }
    const qStr = query.toString();
    if (qStr) {
      url += (url.includes('?') ? '&' : '?') + qStr;
    }
    return this.request(url, { method: 'GET' });
  }

  post(endpoint, data = {}) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  put(endpoint, data = {}) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }

  /**
   * Download file (e.g. PDF receipt) as a Blob and trigger browser download
   */
  async downloadFile(endpoint, filename = 'download.pdf') {
    const url = endpoint.startsWith('http') ? endpoint : `${this.baseUrl}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    const headers = {
      ...this._getAuthHeader(),
    };

    try {
      const response = await fetch(url, { headers });
      if (!response.ok) {
        return this._handleResponse(response);
      }
      const blob = await response.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = downloadUrl;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(downloadUrl);
      a.remove();
      return true;
    } catch (err) {
      if (err.name === 'TypeError') {
        throw new Error('Network error downloading file from server.');
      }
      throw err;
    }
  }
}

// Global API instance
const api = new ApiClient();
