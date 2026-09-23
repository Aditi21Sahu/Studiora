/**
 * STUDIORA — API Client
 * Centralized fetch wrapper with JWT bearer token support & auto-redirect on 401.
 */

const API_BASE_URL = '/api';

const api = {
  getToken() {
    return localStorage.getItem('studiora_token');
  },

  setToken(token) {
    localStorage.setItem('studiora_token', token);
  },

  getUser() {
    const userStr = localStorage.getItem('studiora_user');
    return userStr ? JSON.parse(userStr) : null;
  },

  setUser(user) {
    localStorage.setItem('studiora_user', JSON.stringify(user));
  },

  clearAuth() {
    localStorage.removeItem('studiora_token');
    localStorage.removeItem('studiora_user');
  },

  async request(endpoint, options = {}) {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;
    const headers = options.headers || {};
    
    // Attach authorization header if token exists
    const token = this.getToken();
    if (token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    // Set JSON content-type if body is JSON string and not FormData
    if (options.body && !(options.body instanceof FormData) && !headers['Content-Type']) {
      headers['Content-Type'] = 'application/json';
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      // Handle 401 Unauthorized
      if (response.status === 401) {
        this.clearAuth();
        const path = window.location.pathname;
        if (!path.includes('login.html') && !path.includes('register.html') && !path.includes('index.html')) {
          window.location.href = '/login.html';
        }
        throw new Error('Authentication expired. Please log in again.');
      }

      // Handle other HTTP errors
      if (!response.ok) {
        let errorDetail = `Request failed (${response.status})`;
        try {
          const errorJson = await response.json();
          errorDetail = errorJson.detail || errorJson.message || errorDetail;
        } catch (e) {
          // not json
        }
        throw new Error(errorDetail);
      }

      // If response is a download or no content
      if (response.status === 204) return null;
      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        return await response.json();
      }
      return await response.blob();
    } catch (err) {
      console.error(`API Error on [${options.method || 'GET'}] ${endpoint}:`, err);
      throw err;
    }
  },

  get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  },

  post(endpoint, data, isFormData = false) {
    return this.request(endpoint, {
      method: 'POST',
      body: isFormData ? data : JSON.stringify(data),
    });
  },

  put(endpoint, data) {
    return this.request(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  },

  delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }
};
