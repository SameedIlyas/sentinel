import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box, Typography, Button, Stack, Card, Table, TableHead, TableRow, TableCell,
  TableBody, Chip, IconButton, LinearProgress, Alert as MuiAlert, Paper,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';

import apiClient from '@/api/client';
import { useT } from '@/i18n';

interface Tool {
  id: string;
  name: string;
  vendor: string | null;
  category: string;
  handles_phi: boolean;
  risk_level: string;
  status: string;
  source: string;
  created_at: string;
}

const RISK_COLOR: Record<string, 'default' | 'warning' | 'error'> = {
  low: 'default',
  medium: 'warning',
  high: 'error',
};

const ToolList: React.FC = () => {
  const t = useT();
  const navigate = useNavigate();
  const [tools, setTools] = useState<Tool[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await apiClient.get<Tool[]>('/v1/clinic/tools');
        setTools(data);
      } catch (e: any) {
        setError(e?.response?.data?.detail || 'Could not load tools');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <LinearProgress />;

  return (
    <Box>
      <Stack direction="row" justifyContent="space-between" alignItems="center" sx={{ mb: 3 }}>
        <Box>
          <Typography variant="h1" sx={{ fontWeight: 700 }}>{t('clinic.tools.list_title')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('clinic.tools.list_subtitle')}
          </Typography>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate('/clinic/tools/new')}
        >
          {t('clinic.tools.add')}
        </Button>
      </Stack>

      {error && <MuiAlert severity="error" sx={{ mb: 2 }}>{error}</MuiAlert>}

      {tools.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            {t('clinic.tools.empty')}
          </Typography>
          <Button variant="contained" onClick={() => navigate('/clinic/tools/new')}>
            {t('clinic.tools.add')}
          </Button>
        </Paper>
      ) : (
        <Card>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Tool</TableCell>
                <TableCell>Category</TableCell>
                <TableCell>PHI?</TableCell>
                <TableCell>Risk</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Source</TableCell>
                <TableCell align="right">Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {tools.map((tool) => (
                <TableRow key={tool.id} hover>
                  <TableCell>
                    <Typography sx={{ fontWeight: 600 }}>{tool.name}</Typography>
                    {tool.vendor && (
                      <Typography variant="caption" color="text.secondary">{tool.vendor}</Typography>
                    )}
                  </TableCell>
                  <TableCell>{tool.category.replace(/_/g, ' ')}</TableCell>
                  <TableCell>
                    {tool.handles_phi ? (
                      <Chip label="Yes" size="small" color="warning" variant="outlined" />
                    ) : (
                      <Chip label="No" size="small" variant="outlined" />
                    )}
                  </TableCell>
                  <TableCell>
                    <Chip label={tool.risk_level} size="small" color={RISK_COLOR[tool.risk_level] ?? 'default'} />
                  </TableCell>
                  <TableCell>
                    <Chip label={tool.status.replace(/_/g, ' ')} size="small" variant="outlined" />
                  </TableCell>
                  <TableCell>
                    <Typography variant="caption" color="text.secondary">
                      {tool.source === 'extension' ? 'Auto-detected' : 'Manual'}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <IconButton size="small" onClick={() => navigate(`/clinic/tools/${tool.id}`)}>
                      <EditIcon fontSize="small" />
                    </IconButton>
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

export default ToolList;
