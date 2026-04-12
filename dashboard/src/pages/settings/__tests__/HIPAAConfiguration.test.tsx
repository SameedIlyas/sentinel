import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';
import HIPAAConfiguration from '../HIPAAConfiguration';

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

describe('HIPAAConfiguration', () => {
  it('renders the page header', () => {
    render(<HIPAAConfiguration />, { wrapper: createWrapper() });
    expect(screen.getByText('HIPAA Configuration')).toBeInTheDocument();
    expect(
      screen.getByText(/Configure HIPAA compliance settings/i)
    ).toBeInTheDocument();
  });

  it('renders all Data Protection toggles enabled by default', () => {
    render(<HIPAAConfiguration />, { wrapper: createWrapper() });
    expect(screen.getByLabelText('PHI Auto-Redaction')).toBeChecked();
    expect(screen.getByLabelText('Audit Log All PHI Access')).toBeChecked();
    expect(screen.getByLabelText('Encrypt PHI at Rest')).toBeChecked();
    expect(screen.getByLabelText('HIPAA Safe Harbor De-identification')).toBeChecked();
  });

  it('toggles a switch off when clicked', () => {
    render(<HIPAAConfiguration />, { wrapper: createWrapper() });
    const toggle = screen.getByLabelText('PHI Auto-Redaction');
    expect(toggle).toBeChecked();
    fireEvent.click(toggle);
    expect(toggle).not.toBeChecked();
  });

  it('renders all Compliance Status chips as Compliant/Enabled', () => {
    render(<HIPAAConfiguration />, { wrapper: createWrapper() });
    const compliantChips = screen.getAllByText('Compliant');
    expect(compliantChips).toHaveLength(3);
    expect(screen.getByText('Enabled')).toBeInTheDocument();
  });

  it('renders the Breach Notification alert with contact info', () => {
    render(<HIPAAConfiguration />, { wrapper: createWrapper() });
    expect(screen.getByText(/Breach notifications are automatically sent/i)).toBeInTheDocument();
    expect(screen.getByText(/privacy@yourorg\.com/i)).toBeInTheDocument();
  });
});
