import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

vi.mock('@/api/healthcare');

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}><BrowserRouter>{children}</BrowserRouter></QueryClientProvider>
  );
};

import * as api from '@/api/healthcare';
import DriftMonitor from '../DriftMonitor';
import type { DriftMeasurement, PaginatedResponse } from '@/types';

const mockMeasurements: DriftMeasurement[] = [
  {
    id: 'dm-1',
    baseline_id: 'bl-aaa',
    psi_score: 0.05,
    ks_statistic: 0.03,
    status: 'ok',
    measured_at: '2024-01-20T08:00:00Z',
  },
  {
    id: 'dm-2',
    baseline_id: 'bl-bbb',
    psi_score: 0.15,
    ks_statistic: 0.12,
    status: 'warning',
    measured_at: '2024-01-20T09:00:00Z',
  },
  {
    id: 'dm-3',
    baseline_id: 'bl-ccc',
    psi_score: 0.35,
    status: 'alert',
    measured_at: '2024-01-20T10:00:00Z',
  },
];

const mockPage: PaginatedResponse<DriftMeasurement> = {
  items: mockMeasurements,
  total: 3,
  page: 1,
  page_size: 50,
  total_pages: 1,
};

const emptyPage: PaginatedResponse<DriftMeasurement> = {
  items: [],
  total: 0,
  page: 1,
  page_size: 50,
  total_pages: 0,
};

describe('DriftMonitor', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('shows skeleton while loading', () => {
    vi.mocked(api.listDriftMeasurements).mockReturnValue(new Promise(() => {}));
    const Wrapper = createWrapper();
    render(<Wrapper><DriftMonitor /></Wrapper>);
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders drift measurements', async () => {
    vi.mocked(api.listDriftMeasurements).mockResolvedValue(mockPage);
    const Wrapper = createWrapper();
    render(<Wrapper><DriftMonitor /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('bl-aaa')).toBeInTheDocument();
    });
    expect(screen.getByText('bl-bbb')).toBeInTheDocument();
    expect(screen.getByText('bl-ccc')).toBeInTheDocument();
    expect(screen.getByText('0.0500')).toBeInTheDocument();
    expect(screen.getByText('0.1500')).toBeInTheDocument();
  });

  it('shows ok/warning/alert summary counts', async () => {
    vi.mocked(api.listDriftMeasurements).mockResolvedValue(mockPage);
    const Wrapper = createWrapper();
    render(<Wrapper><DriftMonitor /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('OK: 1')).toBeInTheDocument();
    });
    expect(screen.getByText('Warning: 1')).toBeInTheDocument();
    expect(screen.getByText('Alert: 1')).toBeInTheDocument();
  });

  it('filters by status', async () => {
    vi.mocked(api.listDriftMeasurements).mockResolvedValue(mockPage);
    const Wrapper = createWrapper();
    render(<Wrapper><DriftMonitor /></Wrapper>);
    await waitFor(() => screen.getByText('bl-aaa'));

    const warningChip = screen.getByRole('button', { name: /^Warning$/i });
    fireEvent.click(warningChip);

    await waitFor(() => {
      expect(screen.getByText('bl-bbb')).toBeInTheDocument();
      expect(screen.queryByText('bl-aaa')).not.toBeInTheDocument();
      expect(screen.queryByText('bl-ccc')).not.toBeInTheDocument();
    });
  });

  it('shows empty state', async () => {
    vi.mocked(api.listDriftMeasurements).mockResolvedValue(emptyPage);
    const Wrapper = createWrapper();
    render(<Wrapper><DriftMonitor /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('No drift measurements found')).toBeInTheDocument();
    });
  });
});
