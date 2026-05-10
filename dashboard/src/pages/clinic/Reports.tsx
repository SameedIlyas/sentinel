import React, { useEffect, useState } from 'react';
import {
  Box, Typography, Stack, Button, Card, Table, TableHead, TableRow, TableCell,
  TableBody, LinearProgress, Alert as MuiAlert, Paper,
} from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';

import apiClient from '@/api/client';
import { useT } from '@/i18n';

interface ReportArtifact {
  id: string;
  org_id: string;
  period_start: string;
  period_end: string;
  storage_uri: string;
  size_bytes: number | null;
  generated_at: string;
  status: string;
  download_url: string;
}

const Reports: React.FC = () => {
  const t = useT();
  const [reports, setReports] = useState<ReportArtifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    try {
      const data = await apiClient.get<ReportArtifact[]>('/v1/clinic/reports');
      setReports(data);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Could not load reports');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const generate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const r = await apiClient.post<ReportArtifact>('/v1/clinic/reports/generate');
      setReports((prev) => [r, ...prev.filter((x) => x.id !== r.id)]);
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Generation failed');
    } finally {
      setGenerating(false);
    }
  };

  const baseURL = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';
  const token = localStorage.getItem('access_token') || '';
  const downloadOnce = async (url: string) => {
    // Use fetch with Bearer header so the file streams via authenticated request.
    const resp = await fetch(`${baseURL}${url}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) {
      setError('Download failed');
      return;
    }
    const blob = await resp.blob();
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (resp.headers.get('content-disposition') || '').split('filename=').pop()?.replace(/"/g, '') || 'report';
    a.click();
    URL.revokeObjectURL(a.href);
  };

  if (loading) return <LinearProgress />;

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontWeight: 700 }}>Compliance reports</Typography>
          <Typography variant="body2" color="text.secondary">
            Auto-generated each month. Show this to a regulator, payer, or your board.
          </Typography>
        </Box>
        <Button variant="contained" onClick={generate} disabled={generating}>
          {generating ? 'Generating…' : 'Generate this month'}
        </Button>
      </Stack>

      {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}

      {reports.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            No reports yet. The first one runs at the end of the month — or generate one now.
          </Typography>
          <Button variant="contained" onClick={generate} disabled={generating}>
            {generating ? 'Generating…' : 'Generate first report'}
          </Button>
        </Paper>
      ) : (
        <Card>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Period</TableCell>
                <TableCell>Generated</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Size</TableCell>
                <TableCell align="right">{t('common.download')}</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {reports.map((r) => (
                <TableRow key={r.id} hover>
                  <TableCell>
                    {new Date(r.period_start).toLocaleDateString()} – {new Date(r.period_end).toLocaleDateString()}
                  </TableCell>
                  <TableCell>{new Date(r.generated_at).toLocaleString()}</TableCell>
                  <TableCell>{r.status}</TableCell>
                  <TableCell>{r.size_bytes ? `${Math.round(r.size_bytes / 1024)} KB` : '—'}</TableCell>
                  <TableCell align="right">
                    <Button
                      size="small"
                      startIcon={<DownloadIcon />}
                      disabled={r.status !== 'ready'}
                      onClick={() => downloadOnce(r.download_url)}
                    >
                      Download
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </Box>
  );
};

export default Reports;
