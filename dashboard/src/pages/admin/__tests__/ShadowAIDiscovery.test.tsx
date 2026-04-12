import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import ShadowAIDiscovery from '../ShadowAIDiscovery';
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

const mockDetection = {
  id: 'det-1',
  organization_id: 'org-1',
  detected_tool: 'ChatGPT',
  endpoint_domain: 'chat.openai.com',
  staff_ip: '10.0.0.1',
  hipaa_risk: true,
  severity: 'high' as const,
  detected_at: '2024-01-15T10:00:00Z',
  allowlisted: false,
};

const mockResponse = {
  items: [mockDetection],
  total: 1,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

describe('ShadowAIDiscovery', () => {
  it('shows loading state initially', () => {
    vi.mocked(healthcareApi.listShadowAIDetections).mockReturnValue(
      new Promise(() => {}) // never resolves
    );

    render(<ShadowAIDiscovery />, { wrapper: createWrapper() });

    // Skeleton rows should be visible
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders data when loaded', async () => {
    vi.mocked(healthcareApi.listShadowAIDetections).mockResolvedValue(mockResponse);

    render(<ShadowAIDiscovery />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('ChatGPT')).toBeInTheDocument();
    });

    expect(screen.getByText('chat.openai.com')).toBeInTheDocument();
    expect(screen.getByText('10.0.0.1')).toBeInTheDocument();
    // HIPAA risk chip
    expect(screen.getByText('YES')).toBeInTheDocument();
    // Severity chip
    expect(screen.getByText('high')).toBeInTheDocument();
  });

  it('shows error state on failure', async () => {
    vi.mocked(healthcareApi.listShadowAIDetections).mockRejectedValue(
      new Error('Network error')
    );

    render(<ShadowAIDiscovery />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(
        screen.getByText('Failed to load shadow AI detections')
      ).toBeInTheDocument();
    });
  });

  it('filters by severity when a filter chip is clicked', async () => {
    vi.mocked(healthcareApi.listShadowAIDetections).mockResolvedValue(mockResponse);

    render(<ShadowAIDiscovery />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('ChatGPT')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Critical'));

    await waitFor(() => {
      expect(healthcareApi.listShadowAIDetections).toHaveBeenCalledWith(
        expect.objectContaining({ severity: 'critical' })
      );
    });
  });

  it('calls allowlistShadowAI when Allowlist button is clicked', async () => {
    vi.mocked(healthcareApi.listShadowAIDetections).mockResolvedValue(mockResponse);
    vi.mocked(healthcareApi.allowlistShadowAI).mockResolvedValue({
      ...mockDetection,
      allowlisted: true,
    });

    render(<ShadowAIDiscovery />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Allowlist')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Allowlist'));

    await waitFor(() => {
      expect(healthcareApi.allowlistShadowAI).toHaveBeenCalledWith('det-1');
    });
  });
});
