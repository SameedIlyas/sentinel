import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import ToolEditor from '../ToolEditor';
import apiClient from '@/api/client';
import { I18nProvider } from '@/i18n';
import { clinic_basic as clinicBasicDict } from '@/i18n/dict/clinic_basic';
import type { ProductRole } from '@/auth/clinicProductRole';

vi.mock('@/api/client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    isAuthenticated: () => true,
    validateToken: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  },
}));

// Review HIGH #3 — ToolEditor now consumes useAuth().productRole, so
// tests stub the hook directly rather than re-mocking /v1/auth/me.
const mockUseAuth = vi.fn<[], { productRole: ProductRole | null }>();
vi.mock('@/contexts/AuthContext', () => ({
  useAuth: () => mockUseAuth(),
}));

const setupApi = (baaSigned: boolean) => {
  (apiClient.get as any).mockImplementation((url: string) => {
    if (url.startsWith('/v1/clinic/dashboard/summary'))
      return Promise.resolve({ baa_signed: baaSigned });
    return Promise.resolve(null);
  });
};

const wrap = (node: React.ReactNode) => (
  <BrowserRouter>
    <I18nProvider tier="clinic_basic">{node}</I18nProvider>
  </BrowserRouter>
);

describe('ToolEditor — training-status admin gate (PRD §6.8.2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('disables the Verified option for non-admin (practice_staff)', async () => {
    // Review HIGH #5 — projected literal renamed from 'staff'.
    mockUseAuth.mockReturnValue({ productRole: 'practice_staff' });
    setupApi(true);
    render(wrap(<ToolEditor />));
    await waitFor(() => {
      expect(
        screen.getByText('Only the Practice owner (Admin) can mark this Verified.'),
      ).toBeInTheDocument();
    });
  });

  it('omits the admin-only helper text when productRole is practice_owner', async () => {
    // Review HIGH #5 — projected literal renamed from 'admin'.
    mockUseAuth.mockReturnValue({ productRole: 'practice_owner' });
    setupApi(true);
    render(wrap(<ToolEditor />));
    await waitFor(() =>
      expect(screen.queryByText(/Only the Practice owner/i)).not.toBeInTheDocument(),
    );
  });

  it('shows the warning_no_baa banner when status is trains_on_customer_data + no BAA', async () => {
    mockUseAuth.mockReturnValue({ productRole: 'practice_owner' });
    setupApi(false);
    render(wrap(<ToolEditor />));
    // Wait for the form to render (the "Vendor" field is unique).
    await waitFor(() =>
      expect(screen.getByPlaceholderText('The company that makes it')).toBeInTheDocument(),
    );

    // The MUI Select renders as role="combobox". We have four selects in
    // this form (category, risk_level, model_training_status,
    // practice_opt_out_state) — pick the third one to flip the training
    // status. Note: react-testing-library returns combobox elements in
    // DOM order.
    const combos = screen.getAllByRole('combobox');
    expect(combos.length).toBeGreaterThanOrEqual(3);
    const trainingSelect = combos[2];
    fireEvent.mouseDown(trainingSelect);
    const opt = await screen.findByText('Vendor trains on customer prompts');
    fireEvent.click(opt);

    await waitFor(() =>
      expect(
        screen.getByText(clinicBasicDict['clinic.tools.training_status.warning_no_baa']),
      ).toBeInTheDocument(),
    );
  });
});
