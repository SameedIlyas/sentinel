import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import ToolEditor from '../ToolEditor';
import apiClient from '@/api/client';
import { I18nProvider } from '@/i18n';
import { clinic_basic as clinicBasicDict } from '@/i18n/dict/clinic_basic';

vi.mock('@/api/client', () => ({
  default: { get: vi.fn(), post: vi.fn(), put: vi.fn() },
}));

const mockApi = (role: string, baaSigned: boolean) => {
  (apiClient.get as any).mockImplementation((url: string) => {
    if (url === '/v1/auth/me') return Promise.resolve({ role });
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

  it('disables the Verified option for non-admin (compliance_officer)', async () => {
    mockApi('compliance_officer', true);
    render(wrap(<ToolEditor />));
    // Wait for the api/me + summary fetches to settle.
    await waitFor(() => {
      expect(
        screen.getByText('Only the Practice owner (Admin) can mark this Verified.'),
      ).toBeInTheDocument();
    });
  });

  it('omits the admin-only helper text when productRole is admin', async () => {
    mockApi('admin', true);
    render(wrap(<ToolEditor />));
    // Wait briefly for the role to settle then assert the helper text is gone.
    await waitFor(() =>
      expect(screen.queryByText(/Only the Practice owner/i)).not.toBeInTheDocument(),
    );
  });

  it('shows the warning_no_baa banner when status is trains_on_customer_data + no BAA', async () => {
    mockApi('admin', false);
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
