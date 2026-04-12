import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import OrganizationSettings from '../OrganizationSettings';
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

const mockOrg = {
  id: 'org-1',
  name: 'Acme Hospital',
  slug: 'acme-hospital',
  org_type: 'hospital',
  hipaa_baa_signed: true,
  hipaa_baa_date: '2024-01-15',
  is_active: true,
};

describe('OrganizationSettings', () => {
  it('shows skeleton while loading', () => {
    vi.mocked(healthcareApi.getOrganization).mockReturnValue(new Promise(() => {}));
    render(<OrganizationSettings />, { wrapper: createWrapper() });
    const skeletons = document.querySelectorAll('.MuiSkeleton-root');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders organization profile fields after load', async () => {
    vi.mocked(healthcareApi.getOrganization).mockResolvedValue(mockOrg);
    render(<OrganizationSettings />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByDisplayValue('Acme Hospital')).toBeInTheDocument();
    });
    expect(screen.getByDisplayValue('acme-hospital')).toBeInTheDocument();
  });

  it('shows error alert when getOrganization fails', async () => {
    vi.mocked(healthcareApi.getOrganization).mockRejectedValue(new Error('Network error'));
    render(<OrganizationSettings />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getAllByText(/Failed to load/i).length).toBeGreaterThan(0);
    });
  });

  it('displays HIPAA status chips correctly', async () => {
    vi.mocked(healthcareApi.getOrganization).mockResolvedValue(mockOrg);
    render(<OrganizationSettings />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByText('Signed')).toBeInTheDocument();
      expect(screen.getByText('Active')).toBeInTheDocument();
      expect(screen.getByText('2024-01-15')).toBeInTheDocument();
    });
  });

  it('calls updateOrganization on Save Changes click', async () => {
    vi.mocked(healthcareApi.getOrganization).mockResolvedValue(mockOrg);
    vi.mocked(healthcareApi.updateOrganization).mockResolvedValue({});
    render(<OrganizationSettings />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(screen.getByDisplayValue('Acme Hospital')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole('button', { name: /save changes/i }));
    await waitFor(() => {
      expect(healthcareApi.updateOrganization).toHaveBeenCalledWith(
        expect.objectContaining({ name: 'Acme Hospital' })
      );
    });
  });
});
