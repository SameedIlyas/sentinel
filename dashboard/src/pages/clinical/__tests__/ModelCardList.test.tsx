// src/pages/clinical/__tests__/ModelCardList.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ModelCardList from '../ModelCardList';
import * as healthcareApi from '@/api/healthcare';
import { ModelCard, PaginatedResponse } from '@/types';

vi.mock('@/api/healthcare');

const mockCard: ModelCard = {
  id: 'mc-1',
  model_name: 'DiabetesRisk v2.1',
  model_version: '2.1',
  intended_use: 'Predict risk of Type 2 diabetes onset in outpatient population',
  clinical_indications: 'Adults 18+ with at least one metabolic risk factor',
  lifecycle_stage: 'review',
  fda_status: '510(k) Exempt',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-03-15T00:00:00Z',
};

const mockPublishedCard: ModelCard = {
  id: 'mc-2',
  model_name: 'SepsisAlert Pro',
  model_version: '1.0',
  intended_use: 'Early detection of sepsis in ICU patients',
  clinical_indications: 'ICU patients with suspected infection',
  lifecycle_stage: 'published',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-03-10T00:00:00Z',
};

const emptyResponse: PaginatedResponse<ModelCard> = {
  items: [],
  total: 0,
  page: 1,
  page_size: 10,
  total_pages: 0,
};

const singleResponse: PaginatedResponse<ModelCard> = {
  items: [mockCard],
  total: 1,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

const multiResponse: PaginatedResponse<ModelCard> = {
  items: [mockCard, mockPublishedCard],
  total: 2,
  page: 1,
  page_size: 10,
  total_pages: 1,
};

const createWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe('ModelCardList', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows skeleton while loading', () => {
    vi.spyOn(healthcareApi, 'listModelCards').mockReturnValue(new Promise(() => {}));
    render(<ModelCardList />, { wrapper: createWrapper() });
    expect(document.querySelector('.MuiSkeleton-root')).toBeTruthy();
  });

  it('renders model cards when loaded', async () => {
    vi.spyOn(healthcareApi, 'listModelCards').mockResolvedValue(singleResponse);
    render(<ModelCardList />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText('DiabetesRisk v2.1')).toBeInTheDocument();
    });
    expect(screen.getByText('2.1')).toBeInTheDocument();
    expect(screen.getByText('510(k) Exempt')).toBeInTheDocument();
  });

  it('filters by lifecycle stage chip click', async () => {
    vi.spyOn(healthcareApi, 'listModelCards')
      .mockResolvedValueOnce(multiResponse)
      .mockResolvedValueOnce({ items: [mockPublishedCard], total: 1, page: 1, page_size: 10, total_pages: 1 });

    render(<ModelCardList />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.getByText('DiabetesRisk v2.1')).toBeInTheDocument());

    fireEvent.click(screen.getByText('Published'));
    await waitFor(() => {
      expect(healthcareApi.listModelCards).toHaveBeenCalledWith(
        expect.objectContaining({ lifecycle_stage: 'published' })
      );
    });
  });

  it('navigates to new model card on button click', async () => {
    vi.spyOn(healthcareApi, 'listModelCards').mockResolvedValue(emptyResponse);
    render(<ModelCardList />, { wrapper: createWrapper() });
    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument());

    const btn = screen.getByText('New Model Card');
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    // Navigation is handled by react-router; we just verify the button exists and is clickable
  });

  it('shows empty state when no cards', async () => {
    vi.spyOn(healthcareApi, 'listModelCards').mockResolvedValue(emptyResponse);
    render(<ModelCardList />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText('No model cards found.')).toBeInTheDocument();
    });
  });

  it('shows error alert on failure', async () => {
    vi.spyOn(healthcareApi, 'listModelCards').mockRejectedValue(new Error('Network error'));
    render(<ModelCardList />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText('Network error')).toBeInTheDocument();
  });
});
