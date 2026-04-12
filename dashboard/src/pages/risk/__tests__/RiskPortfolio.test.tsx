import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import React from 'react';
import RiskPortfolio from '../RiskPortfolio';
import { RiskPortfolio as RiskPortfolioType } from '@/types/index';

vi.mock('@/api/healthcare');

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}><BrowserRouter>{children}</BrowserRouter></QueryClientProvider>
  );
};

const mockPortfolio: RiskPortfolioType = {
  total_models: 3,
  avg_risk: 62.5,
  by_risk_level: { low: 1, medium: 1, high: 0, critical: 1 },
  models: [
    {
      model_id: 'model-abc',
      total_risk: 88,
      risk_level: 'critical',
      trend: 'up',
      computed_at: '2024-01-15T10:00:00Z',
    },
    {
      model_id: 'model-xyz',
      total_risk: 42,
      risk_level: 'medium',
      trend: 'stable',
      computed_at: '2024-01-15T10:00:00Z',
    },
  ],
};

describe('RiskPortfolio', () => {
  beforeEach(async () => {
    const api = await import('@/api/healthcare');
    vi.mocked(api.getRiskPortfolio).mockResolvedValue(mockPortfolio);
  });

  it('shows skeleton while loading', async () => {
    const api = await import('@/api/healthcare');
    vi.mocked(api.getRiskPortfolio).mockReturnValue(new Promise(() => {}));
    const Wrapper = createWrapper();
    render(<Wrapper><RiskPortfolio /></Wrapper>);
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders portfolio summary stats', async () => {
    const Wrapper = createWrapper();
    render(<Wrapper><RiskPortfolio /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('62.5')).toBeInTheDocument();
    });
    expect(screen.getByText('Total Models')).toBeInTheDocument();
    expect(screen.getByText('Avg Risk Score')).toBeInTheDocument();
    expect(screen.getByText('Critical Count')).toBeInTheDocument();
    expect(screen.getByText('High Count')).toBeInTheDocument();
  });

  it('renders models table with risk levels', async () => {
    const Wrapper = createWrapper();
    render(<Wrapper><RiskPortfolio /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('model-abc')).toBeInTheDocument();
      expect(screen.getByText('model-xyz')).toBeInTheDocument();
    });
    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getByText('medium')).toBeInTheDocument();
  });

  it('shows empty state when no models', async () => {
    const api = await import('@/api/healthcare');
    vi.mocked(api.getRiskPortfolio).mockResolvedValue({
      ...mockPortfolio,
      models: [],
      total_models: 0,
    });
    const Wrapper = createWrapper();
    render(<Wrapper><RiskPortfolio /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('No models found')).toBeInTheDocument();
    });
  });

  it('shows error alert on failure', async () => {
    const api = await import('@/api/healthcare');
    vi.mocked(api.getRiskPortfolio).mockRejectedValue(new Error('Network error'));
    const Wrapper = createWrapper();
    render(<Wrapper><RiskPortfolio /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText(/Failed to load risk portfolio/i)).toBeInTheDocument();
    });
  });
});
