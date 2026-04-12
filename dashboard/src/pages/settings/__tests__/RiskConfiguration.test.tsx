import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import RiskConfiguration from '../RiskConfiguration';
import * as healthcareApi from '@/api/healthcare';

vi.mock('@/api/healthcare');

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

const mockConfig = {
  id: 'rc-1',
  organization_id: 'org-1',
  regulatory_multiplier: 1.5,
  critical_threshold: 85,
  high_threshold: 65,
  medium_threshold: 45,
};

describe('RiskConfiguration', () => {
  it('shows skeleton while loading', () => {
    vi.mocked(healthcareApi.getRiskConfiguration).mockReturnValue(new Promise(() => {}));
    render(<RiskConfiguration />, { wrapper: createWrapper() });
    expect(document.querySelectorAll('.MuiSkeleton-root').length).toBeGreaterThan(0);
  });

  it('renders threshold fields with loaded values', async () => {
    vi.mocked(healthcareApi.getRiskConfiguration).mockResolvedValue(mockConfig);
    render(<RiskConfiguration />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByDisplayValue('85')).toBeInTheDocument();
      expect(screen.getByDisplayValue('65')).toBeInTheDocument();
      expect(screen.getByDisplayValue('45')).toBeInTheDocument();
    });
  });

  it('shows error alert when getRiskConfiguration fails', async () => {
    vi.mocked(healthcareApi.getRiskConfiguration).mockRejectedValue(new Error('Server error'));
    render(<RiskConfiguration />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/Failed to load risk configuration/i)).toBeInTheDocument();
    });
  });

  it('displays the formula info alert', async () => {
    vi.mocked(healthcareApi.getRiskConfiguration).mockResolvedValue(mockConfig);
    render(<RiskConfiguration />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText(/Formula: Total Risk/i)).toBeInTheDocument();
    });
  });

  it('calls updateRiskConfiguration on Save Configuration click', async () => {
    vi.mocked(healthcareApi.getRiskConfiguration).mockResolvedValue(mockConfig);
    vi.mocked(healthcareApi.updateRiskConfiguration).mockResolvedValue(mockConfig);
    render(<RiskConfiguration />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByDisplayValue('85')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /save configuration/i }));
    await waitFor(() => {
      expect(healthcareApi.updateRiskConfiguration).toHaveBeenCalledWith(
        expect.objectContaining({
          critical_threshold: 85,
          high_threshold: 65,
          medium_threshold: 45,
        })
      );
    });
  });
});
