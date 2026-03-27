import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AuditLogs from '../AuditLogs';
import auditLogsApi from '@/api/auditLogs';

// Mock the API
vi.mock('@/api/auditLogs', () => ({
  default: {
    listAuditLogs: vi.fn(),
    exportToJson: vi.fn(),
    exportToCsv: vi.fn(),
  },
}));

const mockAuditLogs = {
  logs: [
    {
      id: '1',
      timestamp: '2024-01-15T10:30:00Z',
      agent_id: 'agent-123',
      agent_name: 'Invoice Processor',
      user_id: 'user-456',
      tool_name: 'process_payment',
      system_accessed: 'payment-gateway',
      decision: 'allowed',
      policy_ids: ['policy-1'],
      reason: 'Within approved limits',
      arguments: { amount: 100 },
      metadata: {},
    },
    {
      id: '2',
      timestamp: '2024-01-15T10:35:00Z',
      agent_id: 'agent-789',
      agent_name: 'Data Exporter',
      user_id: 'user-456',
      tool_name: 'export_data',
      system_accessed: 'database',
      decision: 'blocked',
      policy_ids: ['policy-2'],
      reason: 'Unauthorized access',
      arguments: { table: 'customers' },
      metadata: {},
    },
  ],
  total: 2,
  page: 1,
  page_size: 25,
  total_pages: 1,
};

describe('AuditLogs', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auditLogsApi.listAuditLogs as any).mockResolvedValue(mockAuditLogs);
  });

  it('renders audit logs table', async () => {
    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    expect(screen.getByText('Audit Logs')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(screen.getByText('Invoice Processor')).toBeInTheDocument();
      expect(screen.getByText('Data Exporter')).toBeInTheDocument();
    });
  });

  it('displays audit log details in table', async () => {
    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('agent-123')).toBeInTheDocument();
      expect(screen.getByText('process_payment')).toBeInTheDocument();
      expect(screen.getByText('payment-gateway')).toBeInTheDocument();
      expect(screen.getByText('ALLOWED')).toBeInTheDocument();
      expect(screen.getByText('BLOCKED')).toBeInTheDocument();
    });
  });

  it('filters logs by agent ID', async () => {
    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Invoice Processor')).toBeInTheDocument();
    });

    const agentFilter = screen.getByLabelText('Agent ID');
    fireEvent.change(agentFilter, { target: { value: 'agent-123' } });

    await waitFor(() => {
      expect(auditLogsApi.listAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({
          filter_agent_id: 'agent-123',
        })
      );
    });
  });

  it('searches logs', async () => {
    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Invoice Processor')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Search logs...');
    fireEvent.change(searchInput, { target: { value: 'payment' } });

    // Wait for debounce
    await waitFor(
      () => {
        expect(auditLogsApi.listAuditLogs).toHaveBeenCalledWith(
          expect.objectContaining({
            search: 'payment',
          })
        );
      },
      { timeout: 1000 }
    );
  });

  it('opens detail modal when view button is clicked', async () => {
    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Invoice Processor')).toBeInTheDocument();
    });

    const viewButtons = screen.getAllByRole('button', { name: /view details/i });
    fireEvent.click(viewButtons[0]);

    await waitFor(() => {
      expect(screen.getByText('Audit Log Details')).toBeInTheDocument();
      expect(screen.getByText('Within approved limits')).toBeInTheDocument();
    });
  });

  it('clears filters when clear button is clicked', async () => {
    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Invoice Processor')).toBeInTheDocument();
    });

    // Set a filter
    const agentFilter = screen.getByLabelText('Agent ID');
    fireEvent.change(agentFilter, { target: { value: 'agent-123' } });

    await waitFor(() => {
      expect(screen.getByText(/Clear Filters/)).toBeInTheDocument();
    });

    const clearButton = screen.getByText(/Clear Filters/);
    fireEvent.click(clearButton);

    expect(agentFilter).toHaveValue('');
  });

  it('handles pagination', async () => {
    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Invoice Processor')).toBeInTheDocument();
    });

    // Change rows per page
    const rowsPerPageSelect = screen.getByRole('combobox', { name: /rows per page/i });
    fireEvent.mouseDown(rowsPerPageSelect);
    
    const option50 = await screen.findByRole('option', { name: '50' });
    fireEvent.click(option50);

    await waitFor(() => {
      expect(auditLogsApi.listAuditLogs).toHaveBeenCalledWith(
        expect.objectContaining({
          page_size: 50,
        })
      );
    });
  });

  it('exports logs as JSON', async () => {
    const mockBlob = new Blob(['{"logs":[]}'], { type: 'application/json' });
    (auditLogsApi.exportToJson as any).mockResolvedValue(mockBlob);

    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Invoice Processor')).toBeInTheDocument();
    });

    // Click export button
    const exportButton = screen.getByRole('button', { name: /export/i });
    fireEvent.click(exportButton);

    // Click JSON export option
    const jsonOption = await screen.findByText('Export as JSON');
    fireEvent.click(jsonOption);

    await waitFor(() => {
      expect(auditLogsApi.exportToJson).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 10000,
        })
      );
    });
  });

  it('exports logs as CSV', async () => {
    const mockBlob = new Blob(['id,timestamp,agent_id'], { type: 'text/csv' });
    (auditLogsApi.exportToCsv as any).mockResolvedValue(mockBlob);

    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Invoice Processor')).toBeInTheDocument();
    });

    // Click export button
    const exportButton = screen.getByRole('button', { name: /export/i });
    fireEvent.click(exportButton);

    // Click CSV export option
    const csvOption = await screen.findByText('Export as CSV');
    fireEvent.click(csvOption);

    await waitFor(() => {
      expect(auditLogsApi.exportToCsv).toHaveBeenCalledWith(
        expect.objectContaining({
          limit: 10000,
        })
      );
    });
  });

  it('shows loading state during export', async () => {
    const mockBlob = new Blob(['{"logs":[]}'], { type: 'application/json' });
    let resolveExport: (value: Blob) => void;
    const exportPromise = new Promise<Blob>((resolve) => {
      resolveExport = resolve;
    });
    (auditLogsApi.exportToJson as any).mockReturnValue(exportPromise);

    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Invoice Processor')).toBeInTheDocument();
    });

    // Click export button
    const exportButton = screen.getByRole('button', { name: /export/i });
    fireEvent.click(exportButton);

    // Click JSON export option
    const jsonOption = await screen.findByText('Export as JSON');
    fireEvent.click(jsonOption);

    // Check loading state
    await waitFor(() => {
      const exportButtonAfter = screen.getByRole('button', { name: /export/i });
      expect(exportButtonAfter).toBeDisabled();
    });

    // Resolve the export
    resolveExport!(mockBlob);

    // Check that button is enabled again
    await waitFor(() => {
      const exportButtonFinal = screen.getByRole('button', { name: /export/i });
      expect(exportButtonFinal).not.toBeDisabled();
    });
  });

  it('applies filters to export', async () => {
    const mockBlob = new Blob(['{"logs":[]}'], { type: 'application/json' });
    (auditLogsApi.exportToJson as any).mockResolvedValue(mockBlob);

    render(
      <BrowserRouter>
        <AuditLogs />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Invoice Processor')).toBeInTheDocument();
    });

    // Set filters
    const agentFilter = screen.getByLabelText('Agent ID');
    fireEvent.change(agentFilter, { target: { value: 'agent-123' } });

    // Click export button
    const exportButton = screen.getByRole('button', { name: /export/i });
    fireEvent.click(exportButton);

    // Click JSON export option
    const jsonOption = await screen.findByText('Export as JSON');
    fireEvent.click(jsonOption);

    await waitFor(() => {
      expect(auditLogsApi.exportToJson).toHaveBeenCalledWith(
        expect.objectContaining({
          filter_agent_id: 'agent-123',
          limit: 10000,
        })
      );
    });
  });
});
