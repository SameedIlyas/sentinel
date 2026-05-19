/**
 * Regression test for CRIT-012 — ProtectedRoute must support a
 * ``requiredTiers`` prop that 403s callers whose org tier is not in the
 * allowed list. Without this, an enterprise-tier user typing
 * /clinic/settings/compliance into the URL bar would render the BAA
 * form (client-side guard absent, server-side guard authoritative but
 * not visible at the routing layer).
 *
 * The server-side gate (`require_clinic_tier` on every /v1/clinic/*
 * API) remains the authoritative check; this test exercises only the
 * presentation layer.
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ProtectedRoute from '../ProtectedRoute';
import { AuthProvider } from '@/contexts/AuthContext';
import { UserRole, CLINIC_TIERS, type TierKey, type User } from '@/types';

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

async function flush() {
  await act(async () => {
    await new Promise((r) => setTimeout(r, 0));
  });
}

function renderWithAuth(child: React.ReactElement) {
  return render(
    <MemoryRouter>
      <AuthProvider>{child}</AuthProvider>
    </MemoryRouter>
  );
}

beforeEach(() => {
  mockUser.mockReset();
  mockIsAuthenticated.mockReturnValue(true);
});

describe('ProtectedRoute — requiredTiers (CRIT-012)', () => {
  it('renders children when the caller tier matches', async () => {
    mockUser.mockResolvedValue(makeUser(UserRole.ADMIN, 'clinic_basic'));
    renderWithAuth(
      <ProtectedRoute requiredTiers={CLINIC_TIERS}>
        <div data-testid="clinic-child">clinic content</div>
      </ProtectedRoute>
    );
    await flush();
    expect(screen.getByTestId('clinic-child')).toBeInTheDocument();
  });

  it('blocks enterprise tier from a clinic-only route', async () => {
    mockUser.mockResolvedValue(makeUser(UserRole.ADMIN, 'enterprise'));
    renderWithAuth(
      <ProtectedRoute requiredTiers={CLINIC_TIERS}>
        <div data-testid="clinic-child">clinic content</div>
      </ProtectedRoute>
    );
    await flush();
    expect(screen.queryByTestId('clinic-child')).not.toBeInTheDocument();
    expect(screen.getByText(/access denied/i)).toBeInTheDocument();
  });

  it('blocks undefined tier (legacy enterprise default) from a clinic route', async () => {
    mockUser.mockResolvedValue(makeUser(UserRole.ADMIN, undefined));
    renderWithAuth(
      <ProtectedRoute requiredTiers={CLINIC_TIERS}>
        <div data-testid="clinic-child">clinic content</div>
      </ProtectedRoute>
    );
    await flush();
    expect(screen.queryByTestId('clinic-child')).not.toBeInTheDocument();
  });

  it('renders for each of the three clinic tiers', async () => {
    for (const tier of CLINIC_TIERS) {
      mockUser.mockResolvedValueOnce(makeUser(UserRole.ADMIN, tier));
      const { unmount } = renderWithAuth(
        <ProtectedRoute requiredTiers={CLINIC_TIERS}>
          <div data-testid={`clinic-${tier}`}>ok</div>
        </ProtectedRoute>
      );
      await flush();
      expect(screen.getByTestId(`clinic-${tier}`)).toBeInTheDocument();
      unmount();
    }
  });
});
