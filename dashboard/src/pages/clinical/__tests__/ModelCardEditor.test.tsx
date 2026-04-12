// src/pages/clinical/__tests__/ModelCardEditor.test.tsx
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter, MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import ModelCardEditor from '../ModelCardEditor';
import * as healthcareApi from '@/api/healthcare';
import { ModelCard } from '@/types';

vi.mock('@/api/healthcare');

const mockCard: ModelCard = {
  id: 'mc-42',
  model_name: 'DiabetesRisk v2.1',
  model_version: '2.1',
  intended_use: 'Predict risk of Type 2 diabetes onset',
  clinical_indications: 'Adults 18+ with metabolic risk factors',
  contraindications: 'Pediatric patients',
  training_data_source: 'EHR dataset 2018-2023',
  performance_summary: 'AUC 0.87',
  bias_summary: 'Reviewed for age/gender bias',
  fda_status: '510(k) Exempt',
  lifecycle_stage: 'review',
  created_at: '2024-01-01T00:00:00Z',
  updated_at: '2024-03-15T00:00:00Z',
};

const createEditWrapper = (id: string) => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/clinical/model-cards/${id}`]}>
        <Routes>
          <Route path="/clinical/model-cards/:id" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
};

const createNewWrapper = () => {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  );
};

describe('ModelCardEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders empty form in create mode', () => {
    render(<ModelCardEditor />, { wrapper: createNewWrapper() });
    expect(screen.getByText('New Model Card')).toBeInTheDocument();
    const modelNameInput = screen.getByTestId('field-model-name') as HTMLInputElement;
    expect(modelNameInput.value).toBe('');
  });

  it('loads existing card data in edit mode', async () => {
    vi.spyOn(healthcareApi, 'getModelCard').mockResolvedValue(mockCard);
    render(<ModelCardEditor />, { wrapper: createEditWrapper('mc-42') });

    await waitFor(() => {
      const modelNameInput = screen.getByTestId('field-model-name') as HTMLInputElement;
      expect(modelNameInput.value).toBe('DiabetesRisk v2.1');
    });

    const versionInput = screen.getByTestId('field-model-version') as HTMLInputElement;
    expect(versionInput.value).toBe('2.1');

    const intendedUseInput = screen.getByTestId('field-intended-use') as HTMLInputElement;
    expect(intendedUseInput.value).toBe('Predict risk of Type 2 diabetes onset');
  });

  it('submits create form with correct data', async () => {
    const createdCard: ModelCard = {
      ...mockCard,
      id: 'mc-new',
      lifecycle_stage: 'draft',
    };
    vi.spyOn(healthcareApi, 'createModelCard').mockResolvedValue(createdCard);

    render(<ModelCardEditor />, { wrapper: createNewWrapper() });

    fireEvent.change(screen.getByTestId('field-model-name'), {
      target: { value: 'New Model' },
    });
    fireEvent.change(screen.getByTestId('field-model-version'), {
      target: { value: '1.0' },
    });
    fireEvent.change(screen.getByTestId('field-intended-use'), {
      target: { value: 'Detect anomalies' },
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(healthcareApi.createModelCard).toHaveBeenCalledWith(
        expect.objectContaining({
          model_name: 'New Model',
          model_version: '1.0',
          intended_use: 'Detect anomalies',
        })
      );
    });
  });

  it('shows validation error when required fields empty', async () => {
    render(<ModelCardEditor />, { wrapper: createNewWrapper() });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText('Model name is required.')).toBeInTheDocument();
  });

  it('shows success message after save', async () => {
    const createdCard: ModelCard = {
      ...mockCard,
      id: 'mc-new',
      lifecycle_stage: 'draft',
    };
    vi.spyOn(healthcareApi, 'createModelCard').mockResolvedValue(createdCard);

    render(<ModelCardEditor />, { wrapper: createNewWrapper() });

    fireEvent.change(screen.getByTestId('field-model-name'), {
      target: { value: 'My Model' },
    });
    fireEvent.change(screen.getByTestId('field-model-version'), {
      target: { value: '1.0' },
    });
    fireEvent.change(screen.getByTestId('field-intended-use'), {
      target: { value: 'Clinical decision support' },
    });

    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => {
      expect(screen.getByText('Model card created successfully.')).toBeInTheDocument();
    });
  });
});
