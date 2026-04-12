import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import PostMarketSurveillance from '../PostMarketSurveillance';
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

const mockReports = {
  items: [
    {
      id: 'pms-1',
      report_type: 'psur' as const,
      status: 'published' as const,
      period_start: '2024-01-01',
      period_end: '2024-03-31',
      summary: 'No significant adverse events. Model performance within expected parameters.',
      generated_at: '2024-04-02T10:00:00Z',
      created_at: '2024-04-02T10:00:00Z',
    },
    {
      id: 'pms-2',
      report_type: 'quarterly' as const,
      status: 'draft' as const,
      period_start: '2024-04-01',
      period_end: '2024-06-30',
      created_at: '2024-04-01T00:00:00Z',
    },
  ],
  total: 2,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

const mockNewReport = {
  id: 'pms-3',
  report_type: 'psur' as const,
  status: 'draft' as const,
  period_start: '2024-07-01',
  period_end: '2024-09-30',
  generated_at: '2024-10-01T09:00:00Z',
  created_at: '2024-10-01T09:00:00Z',
};

describe('PostMarketSurveillance', () => {
  it('shows loading skeleton rows while fetching', () => {
    vi.mocked(healthcareApi.listPMSReports).mockReturnValue(new Promise(() => {}));
    render(<PostMarketSurveillance />, { wrapper: createWrapper() });

    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders PMS report data after loading', async () => {
    vi.mocked(healthcareApi.listPMSReports).mockResolvedValue(mockReports);
    render(<PostMarketSurveillance />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('PSUR')).toBeInTheDocument();
      expect(screen.getByText('QUARTERLY')).toBeInTheDocument();
      expect(
        screen.getByText('No significant adverse events. Model performance within expected parameters.')
      ).toBeInTheDocument();
    });
  });

  it('shows error alert when API call fails', async () => {
    vi.mocked(healthcareApi.listPMSReports).mockRejectedValue(new Error('Server error'));
    render(<PostMarketSurveillance />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Failed to load PMS reports.')).toBeInTheDocument();
    });
  });

  it('shows empty state when no reports returned', async () => {
    vi.mocked(healthcareApi.listPMSReports).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      total_pages: 0,
    });
    render(<PostMarketSurveillance />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No PMS reports found.')).toBeInTheDocument();
    });
  });

  it('calls generatePSUR and shows success alert on button click', async () => {
    vi.mocked(healthcareApi.listPMSReports).mockResolvedValue(mockReports);
    vi.mocked(healthcareApi.generatePSUR).mockResolvedValue(mockNewReport);
    render(<PostMarketSurveillance />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('PSUR')).toBeInTheDocument();
    });

    const generateBtn = screen.getByRole('button', { name: /Generate PSUR/i });
    fireEvent.click(generateBtn);

    await waitFor(() => {
      expect(healthcareApi.generatePSUR).toHaveBeenCalled();
      expect(screen.getByText('PSUR generated successfully.')).toBeInTheDocument();
    });
  });
});
