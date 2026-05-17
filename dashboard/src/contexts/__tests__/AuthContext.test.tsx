/**
 * R2 — AuthContext exposes the projected `productRole` so consumer
 * components (AppLayout user menu, future "preview as staff" affordances)
 * never have to recompute the projection.
 *
 * Backend RBAC is untouched; the projection is presentation-only.
 */

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { AuthProvider, useAuth } from '../AuthContext';
import { UserRole, type TierKey, type User } from '@/types';

// ── apiClient mock ─────────────────────────────────────────────────────
type ApiUser = User;

const mockUser = vi.fn<[], Promise<ApiUser>>();
const mockLogin = vi.fn();
const mockLogout = vi.fn();
const mockIsAuthenticated = vi.fn(() => true);

vi.mock('@/api/client', () => ({
  default: {
    isAuthenticated: () => mockIsAuthenticated(),
    validateToken: () => mockUser(),
    login: (creds: unknown) => mockLogin(creds),
    logout: () => mockLogout(),
  },
}));

function makeUser(role: UserRole, tier: TierKey | undefined): ApiUser {
  return {
    id: 'u1',
    username: 'jane',
    email: 'jane@example.com',
    role,
    is_active: true,
    organization_id: 'org-1',
    tier,
    created_at: '2026-01-01T00:00:00Z',
  };
}

function Probe() {
  const { productRole, tier, user } = useAuth() as ReturnType<typeof useAuth> & {
    productRole: string | null;
  };
  return (
    <>
      <span data-testid="role">{user?.role ?? 'null'}</span>
      <span data-testid="tier">{tier}</span>
      <span data-testid="product-role">{productRole ?? 'null'}</span>
    </>
  );
}

async function flush() {
  // Wait one microtask + one macrotask for AuthProvider's effect.
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
}

describe('AuthContext productRole projection (R2)', () => {
  beforeEach(() => {
    mockUser.mockReset();
    mockLogin.mockReset();
    mockLogout.mockReset();
    mockIsAuthenticated.mockReturnValue(true);
  });

  it('projects ADMIN on clinic_basic to "practice_owner"', async () => {
    mockUser.mockResolvedValue(makeUser(UserRole.ADMIN, 'clinic_basic'));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await flush();
    expect(screen.getByTestId('tier').textContent).toBe('clinic_basic');
    // Review HIGH #5 — projected literal renamed from 'admin'.
    expect(screen.getByTestId('product-role').textContent).toBe('practice_owner');
  });

  it('projects CMIO on clinic_basic to "practice_staff"', async () => {
    mockUser.mockResolvedValue(makeUser(UserRole.CMIO, 'clinic_basic'));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await flush();
    // Review HIGH #5 — projected literal renamed from 'staff'.
    expect(screen.getByTestId('product-role').textContent).toBe('practice_staff');
  });

  it('leaves CMIO on enterprise as the backend role (identity)', async () => {
    mockUser.mockResolvedValue(makeUser(UserRole.CMIO, 'enterprise'));
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await flush();
    expect(screen.getByTestId('product-role').textContent).toBe('cmio');
  });

  it('returns null productRole when no user is authenticated', async () => {
    mockIsAuthenticated.mockReturnValue(false);
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await flush();
    expect(screen.getByTestId('role').textContent).toBe('null');
    expect(screen.getByTestId('product-role').textContent).toBe('null');
  });
});
