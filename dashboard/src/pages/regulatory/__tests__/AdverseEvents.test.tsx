import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import AdverseEvents from '../AdverseEvents';
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

const mockEvents = {
  items: [
    {
      id: 'ae-1',
      model_id: 'model-abc',
      agent_id: 'agent-1',
      event_type: 'misdiagnosis',
      severity: 'high' as const,
      description: 'Model provided an incorrect diagnosis for a cardiac patient case.',
      patient_impact: 'Delayed treatment by 2 hours',
      status: 'investigating' as const,
      reported_at: '2024-03-10T08:00:00Z',
      created_at: '2024-03-10T08:00:00Z',
    },
    {
      id: 'ae-2',
      model_id: 'model-xyz',
      event_type: 'data_drift',
      severity: 'low' as const,
      description: 'Minor data drift detected in imaging model output distribution.',
      status: 'resolved' as const,
      reported_at: '2024-02-20T10:00:00Z',
      resolved_at: '2024-02-21T09:00:00Z',
      created_at: '2024-02-20T10:00:00Z',
    },
  ],
  total: 2,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

describe('AdverseEvents', () => {
  it('shows loading skeleton rows while fetching', () => {
    vi.mocked(healthcareApi.listAdverseEvents).mockReturnValue(new Promise(() => {}));
    render(<AdverseEvents />, { wrapper: createWrapper() });

    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders adverse event data after loading', async () => {
    vi.mocked(healthcareApi.listAdverseEvents).mockResolvedValue(mockEvents);
    render(<AdverseEvents />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('model-abc')).toBeInTheDocument();
      expect(screen.getByText('misdiagnosis')).toBeInTheDocument();
      expect(screen.getByText('Delayed treatment by 2 hours')).toBeInTheDocument();
      expect(screen.getByText('Investigating')).toBeInTheDocument();
      expect(screen.getByText('Resolved')).toBeInTheDocument();
    });
  });

  it('shows error alert when API call fails', async () => {
    vi.mocked(healthcareApi.listAdverseEvents).mockRejectedValue(new Error('Server error'));
    render(<AdverseEvents />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Failed to load adverse events.')).toBeInTheDocument();
    });
  });

  it('shows empty state when no events returned', async () => {
    vi.mocked(healthcareApi.listAdverseEvents).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      total_pages: 0,
    });
    render(<AdverseEvents />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No adverse events found.')).toBeInTheDocument();
    });
  });

  it('filters by severity when a severity chip is clicked', async () => {
    vi.mocked(healthcareApi.listAdverseEvents).mockResolvedValue(mockEvents);
    render(<AdverseEvents />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('model-abc')).toBeInTheDocument();
    });

    const criticalChip = screen.getByRole('button', { name: 'Critical' });
    fireEvent.click(criticalChip);

    await waitFor(() => {
      expect(healthcareApi.listAdverseEvents).toHaveBeenCalledWith(
        expect.objectContaining({ severity: 'critical' })
      );
    });
  });
});
