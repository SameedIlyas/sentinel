import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import TechnicalFiles from '../TechnicalFiles';
import * as healthcareApi from '@/api/healthcare';

vi.mock('@/api/healthcare');

const createWrapper = () => {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

const mockFiles = {
  items: [
    {
      id: 'tf-1',
      title: 'Cardiac Monitor 510k Filing',
      regulatory_type: 'fda_510k' as const,
      product_name: 'CardioSense',
      device_version: '2.1.0',
      lifecycle_stage: 'approved' as const,
      created_at: '2024-01-10T00:00:00Z',
      updated_at: '2024-03-01T00:00:00Z',
    },
    {
      id: 'tf-2',
      title: 'EU MDR Technical File v3',
      regulatory_type: 'eu_mdr' as const,
      product_name: 'DiagnosticAI',
      device_version: '1.0.0',
      lifecycle_stage: 'under_review' as const,
      created_at: '2024-02-15T00:00:00Z',
      updated_at: '2024-04-05T00:00:00Z',
    },
  ],
  total: 2,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

describe('TechnicalFiles', () => {
  it('shows loading skeleton rows while fetching', () => {
    vi.mocked(healthcareApi.listTechnicalFiles).mockReturnValue(new Promise(() => {}));
    render(<TechnicalFiles />, { wrapper: createWrapper() });

    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders technical file data after loading', async () => {
    vi.mocked(healthcareApi.listTechnicalFiles).mockResolvedValue(mockFiles);
    render(<TechnicalFiles />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Cardiac Monitor 510k Filing')).toBeInTheDocument();
      expect(screen.getByText('EU MDR Technical File v3')).toBeInTheDocument();
      expect(screen.getByText('CardioSense')).toBeInTheDocument();
      expect(screen.getByText('FDA 510(k)')).toBeInTheDocument();
      expect(screen.getByText('EU MDR')).toBeInTheDocument();
    });
  });

  it('shows error alert when API call fails', async () => {
    vi.mocked(healthcareApi.listTechnicalFiles).mockRejectedValue(new Error('Network error'));
    render(<TechnicalFiles />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Failed to load technical files.')).toBeInTheDocument();
    });
  });

  it('shows empty state when no files returned', async () => {
    vi.mocked(healthcareApi.listTechnicalFiles).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      total_pages: 0,
    });
    render(<TechnicalFiles />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No technical files found.')).toBeInTheDocument();
    });
  });

  it('filters by lifecycle stage when a filter chip is clicked', async () => {
    vi.mocked(healthcareApi.listTechnicalFiles).mockResolvedValue(mockFiles);
    render(<TechnicalFiles />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Cardiac Monitor 510k Filing')).toBeInTheDocument();
    });

    const approvedChip = screen.getByRole('button', { name: 'Approved' });
    fireEvent.click(approvedChip);

    await waitFor(() => {
      expect(healthcareApi.listTechnicalFiles).toHaveBeenCalledWith(
        expect.objectContaining({ lifecycle_stage: 'approved' })
      );
    });
  });
});
