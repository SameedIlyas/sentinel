import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';

import ToolList from '../ToolList';
import apiClient from '@/api/client';
import { I18nProvider } from '@/i18n';
import { clinic_basic as clinicBasicDict } from '@/i18n/dict/clinic_basic';

vi.mock('@/api/client', () => ({
  default: { get: vi.fn() },
}));

const makeTool = (overrides: Partial<Record<string, unknown>> = {}) => ({
  id: 't1',
  name: 'Test Tool',
  vendor: 'VendorCo',
  category: 'documentation',
  handles_phi: false,
  risk_level: 'low',
  status: 'active',
  source: 'manual',
  created_at: '2026-05-01T00:00:00Z',
  model_training_status: 'no_training',
  practice_opt_out_state: 'not_applicable',
  opt_out_verified_at: null,
  opt_out_verified_by_user_id: null,
  model_training_status_evidence: null,
  ...overrides,
});

const wrap = (node: React.ReactNode) => (
  <BrowserRouter>
    <I18nProvider tier="clinic_basic">{node}</I18nProvider>
  </BrowserRouter>
);

describe('ToolList — training banner', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the no-BAA warning banner when training + no BAA', async () => {
    (apiClient.get as any).mockImplementation((url: string) => {
      if (url.startsWith('/v1/clinic/tools')) {
        return Promise.resolve([
          makeTool({ model_training_status: 'trains_on_customer_data' }),
        ]);
      }
      if (url.startsWith('/v1/clinic/dashboard/summary')) {
        return Promise.resolve({ baa_signed: false });
      }
      return Promise.resolve(null);
    });

    render(wrap(<ToolList />));
    await waitFor(() => {
      expect(screen.getByText('Test Tool')).toBeInTheDocument();
    });
    await waitFor(() => {
      expect(
        screen.getByText(clinicBasicDict['clinic.tools.training_status.warning_no_baa']),
      ).toBeInTheDocument();
    });
  });

  it('suppresses the banner when model_training_status is no_training', async () => {
    (apiClient.get as any).mockImplementation((url: string) => {
      if (url.startsWith('/v1/clinic/tools')) {
        return Promise.resolve([makeTool({ model_training_status: 'no_training' })]);
      }
      if (url.startsWith('/v1/clinic/dashboard/summary')) {
        return Promise.resolve({ baa_signed: false });
      }
      return Promise.resolve(null);
    });

    render(wrap(<ToolList />));
    await waitFor(() => expect(screen.getByText('Test Tool')).toBeInTheDocument());
    expect(
      screen.queryByText(clinicBasicDict['clinic.tools.training_status.warning_no_baa']),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(clinicBasicDict['clinic.tools.training_status.unknown']),
    ).not.toBeInTheDocument();
  });

  it('renders the BAA-present banner when training + BAA signed', async () => {
    (apiClient.get as any).mockImplementation((url: string) => {
      if (url.startsWith('/v1/clinic/tools')) {
        return Promise.resolve([
          makeTool({ model_training_status: 'trains_on_customer_data' }),
        ]);
      }
      if (url.startsWith('/v1/clinic/dashboard/summary')) {
        return Promise.resolve({ baa_signed: true });
      }
      return Promise.resolve(null);
    });

    render(wrap(<ToolList />));
    await waitFor(() =>
      expect(
        screen.getByText(
          clinicBasicDict['clinic.tools.training_status.warning_baa_present'],
        ),
      ).toBeInTheDocument(),
    );
  });
});
