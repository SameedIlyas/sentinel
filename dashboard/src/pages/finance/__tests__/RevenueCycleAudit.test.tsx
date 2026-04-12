import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import RevenueCycleAudit from '../RevenueCycleAudit';
import * as healthcareApi from '@/api/healthcare';

vi.mock('@/api/healthcare');

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}><BrowserRouter>{children}</BrowserRouter></QueryClientProvider>
  );
};

const mockAudit = {
  id: 'rca-1',
  claim_id: 'CLM-20240201-007',
  risk_score: 82,
  upcoding_flags: 2,
  unbundling_flags: 0,
  modifier_flags: 1,
  recommendation: 'Review upcoding of E&M level — documented complexity does not support 99215',
  audited_at: '2024-02-01T14:00:00Z',
};

const mockAuditClean = {
  id: 'rca-2',
  claim_id: 'CLM-20240202-010',
  risk_score: 12,
  upcoding_flags: 0,
  unbundling_flags: 0,
  modifier_flags: 0,
  recommendation: 'No issues detected. Claim appears compliant.',
  audited_at: '2024-02-02T09:00:00Z',
};

const mockResponse = {
  items: [mockAudit, mockAuditClean],
  total: 2,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

describe('RevenueCycleAudit', () => {
  it('shows skeleton while loading', () => {
    vi.mocked(healthcareApi.listRevenueCycleAudits).mockReturnValue(new Promise(() => {}));
    const Wrapper = createWrapper();
    render(<Wrapper><RevenueCycleAudit /></Wrapper>);
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders claim IDs and risk scores', async () => {
    vi.mocked(healthcareApi.listRevenueCycleAudits).mockResolvedValue(mockResponse);
    const Wrapper = createWrapper();
    render(<Wrapper><RevenueCycleAudit /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('CLM-20240201-007')).toBeInTheDocument();
    });
    expect(screen.getByText('CLM-20240202-010')).toBeInTheDocument();
    expect(screen.getByText('82')).toBeInTheDocument();
    expect(screen.getByText('12')).toBeInTheDocument();
  });

  it('shows summary chips with flagged/clean counts', async () => {
    vi.mocked(healthcareApi.listRevenueCycleAudits).mockResolvedValue(mockResponse);
    const Wrapper = createWrapper();
    render(<Wrapper><RevenueCycleAudit /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText(/Total Audited: 2/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/Flagged: 1/i)).toBeInTheDocument();
    expect(screen.getByText(/Clean: 1/i)).toBeInTheDocument();
  });

  it('shows error alert on failure', async () => {
    vi.mocked(healthcareApi.listRevenueCycleAudits).mockRejectedValue(new Error('Server error'));
    const Wrapper = createWrapper();
    render(<Wrapper><RevenueCycleAudit /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText(/Failed to load revenue cycle audit data/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when no audits', async () => {
    vi.mocked(healthcareApi.listRevenueCycleAudits).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      total_pages: 0,
    });
    const Wrapper = createWrapper();
    render(<Wrapper><RevenueCycleAudit /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText(/No audit records found/i)).toBeInTheDocument();
    });
  });
});
