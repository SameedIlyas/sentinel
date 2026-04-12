import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import React from 'react';
import RiskScoreDetail from '../RiskScoreDetail';
import * as healthcareApi from '@/api/healthcare';

vi.mock('@/api/healthcare');

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/risk/model-abc`]}>
        <Routes>
          <Route path="/risk/:modelId" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

const mockScore = {
  id: 'score-1',
  model_id: 'model-abc',
  severity_score: 45,
  exposure_score: 30,
  regulatory_penalty: 3.5,
  org_multiplier: 1.0,
  total_risk: 78.5,
  risk_level: 'high' as const,
  severity_factors: { patient_safety_impact: 8, data_sensitivity: 7 },
  exposure_factors: { patient_volume: 6, automation_level: 9 },
  regulatory_flags: { hipaa: true, fda: false },
  computed_at: '2024-01-15T10:00:00Z',
};

const mockHistory = [
  {
    id: 'h1',
    model_id: 'model-abc',
    total_risk: 78.5,
    risk_level: 'high' as const,
    trend: 'up' as const,
    delta: 3.2,
    computed_at: '2024-01-15T10:00:00Z',
  },
  {
    id: 'h2',
    model_id: 'model-abc',
    total_risk: 75.3,
    risk_level: 'high' as const,
    trend: 'stable' as const,
    delta: 0,
    computed_at: '2024-01-10T10:00:00Z',
  },
];

describe('RiskScoreDetail', () => {
  it('shows skeleton while loading', () => {
    vi.mocked(healthcareApi.getRiskScore).mockReturnValue(new Promise(() => {}));
    vi.mocked(healthcareApi.getRiskHistory).mockReturnValue(new Promise(() => {}));
    const Wrapper = createWrapper();
    render(<Wrapper><RiskScoreDetail /></Wrapper>);
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders risk score and level after loading', async () => {
    vi.mocked(healthcareApi.getRiskScore).mockResolvedValue(mockScore);
    vi.mocked(healthcareApi.getRiskHistory).mockResolvedValue(mockHistory);
    const Wrapper = createWrapper();
    render(<Wrapper><RiskScoreDetail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getAllByText('78.5').length).toBeGreaterThan(0);
    });
    expect(screen.getAllByText('high').length).toBeGreaterThan(0);
  });

  it('renders severity and exposure factor bars', async () => {
    vi.mocked(healthcareApi.getRiskScore).mockResolvedValue(mockScore);
    vi.mocked(healthcareApi.getRiskHistory).mockResolvedValue(mockHistory);
    const Wrapper = createWrapper();
    render(<Wrapper><RiskScoreDetail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('patient safety impact')).toBeInTheDocument();
    });
    expect(screen.getByText('patient volume')).toBeInTheDocument();
  });

  it('renders regulatory flags', async () => {
    vi.mocked(healthcareApi.getRiskScore).mockResolvedValue(mockScore);
    vi.mocked(healthcareApi.getRiskHistory).mockResolvedValue(mockHistory);
    const Wrapper = createWrapper();
    render(<Wrapper><RiskScoreDetail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText('HIPAA')).toBeInTheDocument();
    });
    expect(screen.getByText('FDA')).toBeInTheDocument();
  });

  it('shows error alert on failure', async () => {
    vi.mocked(healthcareApi.getRiskScore).mockRejectedValue(new Error('Server error'));
    vi.mocked(healthcareApi.getRiskHistory).mockRejectedValue(new Error('Server error'));
    const Wrapper = createWrapper();
    render(<Wrapper><RiskScoreDetail /></Wrapper>);
    await waitFor(() => {
      expect(screen.getByText(/Failed to load risk score data/i)).toBeInTheDocument();
    });
  });
});
