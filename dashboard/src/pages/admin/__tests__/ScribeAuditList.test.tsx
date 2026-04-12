import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import ScribeAuditList from '../ScribeAuditList';
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

const mockAudit = {
  id: 'audit-1',
  organization_id: 'org-1',
  encounter_id: 'enc-abc123',
  completeness_score: 87,
  hallucination_detected: false,
  icd10_accuracy: 94,
  status: 'pass' as const,
  findings_count: 2,
  audited_at: '2024-02-10T14:30:00Z',
};

const mockResponse = {
  items: [mockAudit],
  total: 1,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

describe('ScribeAuditList', () => {
  it('shows loading state initially', () => {
    vi.mocked(healthcareApi.listScribeAudits).mockReturnValue(
      new Promise(() => {}) // never resolves
    );

    render(<ScribeAuditList />, { wrapper: createWrapper() });

    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders audit data when loaded', async () => {
    vi.mocked(healthcareApi.listScribeAudits).mockResolvedValue(mockResponse);

    render(<ScribeAuditList />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('enc-abc123')).toBeInTheDocument();
    });

    expect(screen.getByText('87%')).toBeInTheDocument();
    expect(screen.getByText('None')).toBeInTheDocument(); // hallucination chip
    expect(screen.getByText('94%')).toBeInTheDocument(); // ICD-10 accuracy
    expect(screen.getByText('2')).toBeInTheDocument(); // findings count
    expect(screen.getByText('pass')).toBeInTheDocument();
  });

  it('shows error state on failure', async () => {
    vi.mocked(healthcareApi.listScribeAudits).mockRejectedValue(
      new Error('Server error')
    );

    render(<ScribeAuditList />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Failed to load scribe audits')).toBeInTheDocument();
    });
  });

  it('shows empty state when no audits found', async () => {
    vi.mocked(healthcareApi.listScribeAudits).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 10,
      total_pages: 0,
    });

    render(<ScribeAuditList />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No scribe audits found')).toBeInTheDocument();
    });
  });

  it('filters by status when a filter chip is clicked', async () => {
    vi.mocked(healthcareApi.listScribeAudits).mockResolvedValue(mockResponse);

    render(<ScribeAuditList />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('enc-abc123')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Fail'));

    await waitFor(() => {
      expect(healthcareApi.listScribeAudits).toHaveBeenCalledWith(
        expect.objectContaining({ status: 'fail' })
      );
    });
  });
});
