import axios, {
  AxiosInstance,
  AxiosError,
  InternalAxiosRequestConfig,
} from 'axios';
import { LoginRequest, TokenResponse, User } from '@/types';
import { parseUser } from '@/types/userSchema';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const CSRF_COOKIE_NAME = 'csrf_token';
const CSRF_HEADER_NAME = 'X-CSRF-Token';
const MUTATING_METHODS = new Set(['post', 'put', 'delete', 'patch']);

function formatApiDetail(detail: unknown): string {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: any) =>
        typeof d === 'object' && d.msg ? d.msg : JSON.stringify(d)
      )
      .join('; ');
  }
  if (typeof detail === 'object' && detail !== null) {
    return JSON.stringify(detail);
  }
  return String(detail);
}

/**
 * Read a cookie value from document.cookie. Used for the JS-readable
 * ``csrf_token`` cookie issued by /v1/auth/login. The ``access_token``
 * cookie is HttpOnly (CRIT-011 close) and is intentionally NOT
 * accessible to JS — the browser sends it on every same-site request
 * automatically.
 */
function readCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const target = name + '=';
  for (const part of document.cookie.split(';')) {
    const trimmed = part.trim();
    if (trimmed.startsWith(target)) {
      return decodeURIComponent(trimmed.slice(target.length));
    }
  }
  return null;
}

class ApiClient {
  private client: AxiosInstance;
  private tokenRefreshPromise: Promise<void> | null = null;
  /** In-memory CSRF token cache — primed at login/refresh. */
  private csrfToken: string | null = null;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 30000,
      // CRIT-011 — cookies must travel cross-origin to the API. The
      // JWT lives in an HttpOnly cookie now; if withCredentials is
      // false the browser drops it and every request 401s.
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor: echo the CSRF token on mutating requests
    // (double-submit pattern enforced by the backend).
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        if (
          config.method &&
          MUTATING_METHODS.has(config.method.toLowerCase())
        ) {
          const token = this.csrfToken || readCookie(CSRF_COOKIE_NAME);
          if (token && config.headers) {
            config.headers[CSRF_HEADER_NAME] = token;
            this.csrfToken = token;
          }
        }
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor — refresh on 401, normalise error detail.
    this.client.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const originalRequest = error.config as InternalAxiosRequestConfig & {
          _retry?: boolean;
        };

        if (error.response?.status === 401 && !originalRequest._retry) {
          originalRequest._retry = true;

          try {
            await this.refreshToken();
            return this.client(originalRequest);
          } catch (refreshError) {
            this.clearAuth();
            // Redirect to login. Do not include any tokens in the URL.
            if (typeof window !== 'undefined') {
              window.location.href = '/login';
            }
            return Promise.reject(refreshError);
          }
        }

        if (error.response?.data && typeof error.response.data === 'object') {
          const data = error.response.data as Record<string, unknown>;
          if (data.detail && typeof data.detail !== 'string') {
            data.detail = formatApiDetail(data.detail);
          }
        }

        return Promise.reject(error);
      }
    );
  }

  // ── User cache (JS-readable, schema-validated) ─────────────────────

  private getUser(): User | null {
    // CRIT-011 — every cached value goes through a strict schema. A
    // forged ``{role: 'system_admin'}`` written to localStorage by an
    // attacker (or a stale entry from a previous version with a
    // different shape) returns null here, never a partially-typed
    // User. Callers must then take the server-validateToken path,
    // which re-derives role/tier from the authoritative response.
    //
    // HIGH-025 history — also clears the corrupt entry so the next
    // render boots into the login flow cleanly.
    const userStr = localStorage.getItem('user');
    if (!userStr) return null;
    let raw: unknown;
    try {
      raw = JSON.parse(userStr);
    } catch {
      this.clearUser();
      return null;
    }
    const validated = parseUser(raw);
    if (validated === null) {
      this.clearUser();
      return null;
    }
    return validated as User;
  }

  private setUser(user: User): void {
    localStorage.setItem('user', JSON.stringify(user));
  }

  private clearUser(): void {
    localStorage.removeItem('user');
  }

  private clearAuth(): void {
    // CRIT-011 — the access token now lives in an HttpOnly cookie.
    // There is nothing in localStorage to clear for the credential
    // itself; we still drop any legacy `access_token` value to clean
    // up after the migration. Logout is delivered by the backend
    // clearing the cookie on the response.
    this.clearUser();
    this.csrfToken = null;
    try {
      localStorage.removeItem('access_token');
    } catch (_e) {
      /* ignore */
    }
  }

  // ── Token refresh ──────────────────────────────────────────────────

  private async refreshToken(): Promise<void> {
    if (this.tokenRefreshPromise) {
      return this.tokenRefreshPromise;
    }

    this.tokenRefreshPromise = (async () => {
      try {
        const response = await this.client.post<TokenResponse>(
          '/v1/auth/refresh'
        );
        const { user, csrf_token } = response.data;
        this.setUser(user);
        if (csrf_token) this.csrfToken = csrf_token;
      } finally {
        this.tokenRefreshPromise = null;
      }
    })();

    return this.tokenRefreshPromise;
  }

  // ── Authentication ─────────────────────────────────────────────────

  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const response = await this.client.post<TokenResponse>(
      '/v1/auth/login',
      credentials
    );
    const { user, csrf_token } = response.data;
    this.setUser(user);
    if (csrf_token) this.csrfToken = csrf_token;
    return response.data;
  }

  async logout(): Promise<void> {
    try {
      await this.client.post('/v1/auth/logout');
    } finally {
      this.clearAuth();
    }
  }

  async validateToken(): Promise<User> {
    const response = await this.client.get<User>('/v1/auth/validate');
    this.setUser(response.data);
    return response.data;
  }

  getCurrentUser(): User | null {
    return this.getUser();
  }

  isAuthenticated(): boolean {
    // CRIT-011 — the HttpOnly access-token cookie is invisible to JS, so
    // we cannot probe its presence directly. The cached user record is
    // a good-enough heuristic: AuthContext's bootstrap calls
    // validateToken() against the server and gates on the response.
    return !!this.getUser();
  }

  // ── Generic API methods ────────────────────────────────────────────

  async get<T>(url: string, params?: any): Promise<T> {
    const response = await this.client.get<T>(url, { params });
    return response.data;
  }

  async post<T>(url: string, data?: any): Promise<T> {
    const response = await this.client.post<T>(url, data);
    return response.data;
  }

  async put<T>(url: string, data?: any): Promise<T> {
    const response = await this.client.put<T>(url, data);
    return response.data;
  }

  async delete<T>(url: string): Promise<T> {
    const response = await this.client.delete<T>(url);
    return response.data;
  }

  async patch<T>(url: string, data?: any): Promise<T> {
    const response = await this.client.patch<T>(url, data);
    return response.data;
  }

  async getBlob(url: string, params?: any): Promise<Blob> {
    const response = await this.client.get(url, {
      params,
      responseType: 'blob',
    });
    return response.data;
  }
}

// Export singleton instance
export const apiClient = new ApiClient();
export default apiClient;
