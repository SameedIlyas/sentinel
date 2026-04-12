import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';

vi.mock('@/api/healthcare');

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useParams: () => ({ id: 'bias-1' }) };
});

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}><BrowserRouter>{children}</BrowserRouter></QueryClientProvider>
  );
};

import * as api from '@/api/healthcare';
import BiasAuditDetail from '../BiasAuditDetail';
import type { BiasAudit } from '@/types';

const completedAudit: BiasAudit = {
  id: 'bias-1',
  model_card_id: 'mc-123',
  status: 'completed',
  subgroups: ['race', 'gender', 'age'],
  overall_score: 82.5,
  disparate_impact_ratio: 0.91,
  findings_summary: 'Model performs equitably across subgroups with minor variance in age group.',
  created_at: '2024-01-10T08:00:00Z',
  completed_at: '2024-01-10T10:30:00Z',
};

const pendingAudit: BiasAudit = {
  id: 'bias-1',
  model_card_id: 'mc-123',
  status: 'pending',
  subgroups: ['race', 'gender'],
  created_at: '2024-01-10T08:00:00Z',
};

describe('BiasAuditDetail', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it('shows skeleton while loading', () => {
    vi.mocked(api.getBiasAudit).mockReturnValue(new Promise(() => {}));
    const Wrapper = createWrapper();
    render(<Wrapper><BiasAuditDetail /></Wrapper>);
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders completed audit with metrics', async () => {
    vi.mocked(api.getBiasAudit).mockResolvedValue(completedAudit);
    const Wrapper = createWrapper();
    render(<Wrapper><BiasAuditDetail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('mc-123')).toBeInTheDocument();
    });
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('race')).toBeInTheDocument();
    expect(screen.getByText('gender')).toBeInTheDocument();
    expect(screen.getByText('age')).toBeInTheDocument();
    expect(screen.getByText('0.910')).toBeInTheDocument();
    expect(screen.getByText(/model performs equitably/i)).toBeInTheDocument();
  });

  it('shows run audit button for pending audits', async () => {
    vi.mocked(api.getBiasAudit).mockResolvedValue(pendingAudit);
    vi.mocked(api.runBiasAudit).mockResolvedValue({ ...pendingAudit, status: 'running' });
    const Wrapper = createWrapper();
    render(<Wrapper><BiasAuditDetail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /run audit/i })).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /run audit/i }));
    await waitFor(() => {
      expect(api.runBiasAudit).toHaveBeenCalledWith('bias-1');
    });
  });

  it('shows error on load failure', async () => {
    vi.mocked(api.getBiasAudit).mockRejectedValue(new Error('Network error'));
    const Wrapper = createWrapper();
    render(<Wrapper><BiasAuditDetail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText(/failed to load bias audit/i)).toBeInTheDocument();
  });
});
