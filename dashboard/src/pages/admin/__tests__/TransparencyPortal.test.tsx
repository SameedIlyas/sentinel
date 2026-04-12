import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import TransparencyPortal from '../TransparencyPortal';
import * as healthcareApi from '@/api/healthcare';

vi.mock('@/api/healthcare');

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

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

const mockRecord = {
  id: 'rec-1',
  organization_id: 'org-1',
  algorithm_name: 'Sepsis Early Warning',
  plain_language_summary:
    'This algorithm analyzes vital signs and lab results to identify patients at risk of sepsis.',
  evidence_base: 'NEJM 2023',
  version: 2,
  published_at: '2024-03-01T00:00:00Z',
  created_at: '2024-01-20T09:00:00Z',
};

const mockResponse = {
  items: [mockRecord],
  total: 1,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

describe('TransparencyPortal', () => {
  it('shows loading state initially', () => {
    vi.mocked(healthcareApi.listTransparencyRecords).mockReturnValue(
      new Promise(() => {}) // never resolves
    );

    render(<TransparencyPortal />, { wrapper: createWrapper() });

    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders transparency records when loaded', async () => {
    vi.mocked(healthcareApi.listTransparencyRecords).mockResolvedValue(mockResponse);

    render(<TransparencyPortal />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Sepsis Early Warning')).toBeInTheDocument();
    });

    expect(screen.getByText('NEJM 2023')).toBeInTheDocument();
    expect(screen.getByText('v2')).toBeInTheDocument();
    // ONC info alert
    expect(
      screen.getByText('These records are publicly accessible per ONC HTI-1 requirements.')
    ).toBeInTheDocument();
  });

  it('shows error state on failure', async () => {
    vi.mocked(healthcareApi.listTransparencyRecords).mockRejectedValue(
      new Error('Server error')
    );

    render(<TransparencyPortal />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText('Failed to load transparency records')
      ).toBeInTheDocument();
    });
  });

  it('shows empty state when no records exist', async () => {
    vi.mocked(healthcareApi.listTransparencyRecords).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      total_pages: 0,
    });

    render(<TransparencyPortal />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No transparency records found')).toBeInTheDocument();
    });
  });

  it('navigates to detail page when View button is clicked', async () => {
    vi.mocked(healthcareApi.listTransparencyRecords).mockResolvedValue(mockResponse);

    render(<TransparencyPortal />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('View')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('View'));

    expect(mockNavigate).toHaveBeenCalledWith('/admin/transparency/rec-1');
  });
});
