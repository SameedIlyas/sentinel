import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import PriorAuthTrail from '../PriorAuthTrail';
import * as healthcareApi from '@/api/healthcare';

vi.mock('@/api/healthcare');

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}><BrowserRouter>{children}</BrowserRouter></QueryClientProvider>
  );
};

const mockRecord = {
  id: 'par-1',
  claim_id: 'CLM-20240115-001',
  service_type: 'MRI Brain',
  ai_recommendation: 'Approve — imaging clinically indicated for headache with red flags',
  ai_confidence: 0.91,
  final_decision: 'approved',
  record_hash: 'abcdef1234567890abcdef',
  prev_record_hash: '0000000000000000000000',
  created_at: '2024-01-15T10:00:00Z',
};

const mockResponse = {
  items: [mockRecord],
  total: 1,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

describe('PriorAuthTrail', () => {
  it('shows skeleton while loading', () => {
    vi.mocked(healthcareApi.listPriorAuthRecords).mockReturnValue(new Promise(() => {}));
    const Wrapper = createWrapper();
    render(<Wrapper><PriorAuthTrail /></Wrapper>);
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders records with claim ID and decision chip', async () => {
    vi.mocked(healthcareApi.listPriorAuthRecords).mockResolvedValue(mockResponse);
    const Wrapper = createWrapper();
    render(<Wrapper><PriorAuthTrail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('CLM-20240115-001')).toBeInTheDocument();
    });
    expect(screen.getByText('MRI Brain')).toBeInTheDocument();
    expect(screen.getByText('approved')).toBeInTheDocument();
    expect(screen.getByText('91%')).toBeInTheDocument();
  });

  it('shows CMS-0057-F compliance alert', () => {
    vi.mocked(healthcareApi.listPriorAuthRecords).mockReturnValue(new Promise(() => {}));
    const Wrapper = createWrapper();
    render(<Wrapper><PriorAuthTrail /></Wrapper>);
    expect(screen.getByText(/append-only per CMS-0057-F/i)).toBeInTheDocument();
  });

  it('shows error alert on failure', async () => {
    vi.mocked(healthcareApi.listPriorAuthRecords).mockRejectedValue(new Error('Network error'));
    const Wrapper = createWrapper();
    render(<Wrapper><PriorAuthTrail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText(/Failed to load prior authorization records/i)).toBeInTheDocument();
    });
  });

  it('calls verifyPriorAuthChain when verify button clicked', async () => {
    vi.mocked(healthcareApi.listPriorAuthRecords).mockResolvedValue(mockResponse);
    vi.mocked(healthcareApi.verifyPriorAuthChain).mockResolvedValue({
      valid: true,
      message: 'Chain integrity verified.',
    });
    const Wrapper = createWrapper();
    render(<Wrapper><PriorAuthTrail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /verify chain/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /verify chain/i }));
    await waitFor(() => {
      expect(healthcareApi.verifyPriorAuthChain).toHaveBeenCalledWith('par-1');
    });
  });
});
