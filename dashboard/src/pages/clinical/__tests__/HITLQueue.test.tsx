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
import HITLQueue from '../HITLQueue';
import type { HITLReview, PaginatedResponse } from '@/types';

const mockReview: HITLReview = {
  id: 'hitl-1',
  model_id: 'model-abc',
  ai_decision: 'High risk — recommend denial',
  ai_confidence: 0.87,
  risk_score: 78,
  status: 'pending',
  sla_deadline: '2030-01-01T00:00:00Z',
  created_at: '2024-01-15T10:00:00Z',
};

const mockPage: PaginatedResponse<HITLReview> = {
  items: [mockReview],
  total: 1,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

const emptyPage: PaginatedResponse<HITLReview> = {
  items: [],
  total: 0,
  page: 1,
  page_size: 10,
  total_pages: 0,
};

describe('HITLQueue', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('shows skeleton while loading', () => {
    vi.mocked(api.listHITLReviews).mockReturnValue(new Promise(() => {}));
    const Wrapper = createWrapper();
    render(<Wrapper><HITLQueue /></Wrapper>);
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders pending reviews', async () => {
    vi.mocked(api.listHITLReviews).mockResolvedValue(mockPage);
    const Wrapper = createWrapper();
    render(<Wrapper><HITLQueue /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('model-abc')).toBeInTheDocument();
    });
    expect(screen.getByText('High risk — recommend denial')).toBeInTheDocument();
    expect(screen.getByText('87%')).toBeInTheDocument();
    expect(screen.getByText('pending')).toBeInTheDocument();
  });

  it('filters by status', async () => {
    vi.mocked(api.listHITLReviews).mockResolvedValue(mockPage);
    const Wrapper = createWrapper();
    render(<Wrapper><HITLQueue /></Wrapper>);
    await waitFor(() => screen.getByText('model-abc'));

    const pendingChip = screen.getByRole('button', { name: /^Pending$/i });
    fireEvent.click(pendingChip);

    await waitFor(() => {
      expect(vi.mocked(api.listHITLReviews)).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'pending' })
      );
    });
  });

  it('shows empty state', async () => {
    vi.mocked(api.listHITLReviews).mockResolvedValue(emptyPage);
    const Wrapper = createWrapper();
    render(<Wrapper><HITLQueue /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('No reviews in queue')).toBeInTheDocument();
    });
  });

  it('shows error alert on failure', async () => {
    vi.mocked(api.listHITLReviews).mockRejectedValue(new Error('Network error'));
    const Wrapper = createWrapper();
    render(<Wrapper><HITLQueue /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText(/failed to load reviews/i)).toBeInTheDocument();
  });
});
