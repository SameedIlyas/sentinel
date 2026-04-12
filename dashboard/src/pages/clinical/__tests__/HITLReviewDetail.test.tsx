import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

vi.mock('@/api/healthcare');

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: () => ({ id: 'hitl-1' }) };
});

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}><BrowserRouter>{children}</BrowserRouter></QueryClientProvider>
  );
};

import * as api from '@/api/healthcare';
import HITLReviewDetail from '../HITLReviewDetail';
import type { HITLReview } from '@/types';

const pendingReview: HITLReview = {
  id: 'hitl-1',
  model_id: 'model-abc',
  ai_decision: 'High risk — recommend denial',
  ai_confidence: 0.87,
  risk_score: 78,
  status: 'pending',
  sla_deadline: '2030-01-01T00:00:00Z',
  created_at: '2024-01-15T10:00:00Z',
};

const approvedReview: HITLReview = {
  ...pendingReview,
  status: 'approved',
  reviewer_decision: 'Clinician approves treatment',
  reviewer_notes: 'Patient history reviewed',
  reviewed_at: '2024-01-16T09:00:00Z',
};

describe('HITLReviewDetail', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('shows skeleton while loading', () => {
    vi.mocked(api.getHITLReview).mockReturnValue(new Promise(() => {}));
    const Wrapper = createWrapper();
    render(<Wrapper><HITLReviewDetail /></Wrapper>);
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders review detail for pending review', async () => {
    vi.mocked(api.getHITLReview).mockResolvedValue(pendingReview);
    const Wrapper = createWrapper();
    render(<Wrapper><HITLReviewDetail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('High risk — recommend denial')).toBeInTheDocument();
    });
    expect(screen.getByText('model-abc')).toBeInTheDocument();
    expect(screen.getByLabelText(/reviewer decision/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /submit decision/i })).toBeInTheDocument();
  });

  it('renders read-only panel for completed review', async () => {
    vi.mocked(api.getHITLReview).mockResolvedValue(approvedReview);
    const Wrapper = createWrapper();
    render(<Wrapper><HITLReviewDetail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('Clinician approves treatment')).toBeInTheDocument();
    });
    expect(screen.getByText('Patient history reviewed')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /submit decision/i })).not.toBeInTheDocument();
  });

  it('submits decision successfully', async () => {
    vi.mocked(api.getHITLReview).mockResolvedValue(pendingReview);
    vi.mocked(api.submitHITLDecision).mockResolvedValue({ ...pendingReview, status: 'approved' });
    const Wrapper = createWrapper();
    render(<Wrapper><HITLReviewDetail /></Wrapper>);

    await waitFor(() => screen.getByLabelText(/reviewer decision/i));

    fireEvent.change(screen.getByLabelText(/reviewer decision/i), {
      target: { value: 'Treatment approved after review' },
    });

    fireEvent.click(screen.getByRole('button', { name: /submit decision/i }));

    await waitFor(() => {
      expect(api.submitHITLDecision).toHaveBeenCalledWith('hitl-1', expect.objectContaining({
        status: 'approved',
        reviewer_decision: 'Treatment approved after review',
      }));
    });

    await waitFor(() => {
      expect(screen.getByText(/decision submitted successfully/i)).toBeInTheDocument();
    });
  });
});
