import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Alert,
  Skeleton,
  Button,
} from '@mui/material';
import PublicIcon from '@mui/icons-material/Public';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { listTransparencyRecords } from '@/api/healthcare';

const TransparencyPortal: React.FC = () => {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['transparencyRecords', page, rowsPerPage],
    queryFn: () => listTransparencyRecords({ page: page + 1 }),
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 2 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <PublicIcon sx={{ color: 'primary.main', fontSize: 28 }} />
          <Box>
            <Typography variant="h4">Transparency Portal</Typography>
            <Typography variant="body2" color="text.secondary">
              ONC HTI-1 compliant algorithm transparency records
            </Typography>
          </Box>
        </Box>
        <Button
          variant="contained"
          onClick={() => navigate('/admin/transparency/new')}
        >
          New Record
        </Button>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        These records are publicly accessible per ONC HTI-1 requirements.
      </Alert>

      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          Failed to load transparency records
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Created At</TableCell>
              <TableCell>Algorithm</TableCell>
              <TableCell sx={{ minWidth: 220 }}>Summary</TableCell>
              <TableCell>Evidence Base</TableCell>
              <TableCell>Version</TableCell>
              <TableCell>Published At</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading
              ? Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 7 }).map((__, j) => (
                      <TableCell key={j}>
                        <Skeleton variant="text" />
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              : items.length === 0
              ? (
                  <TableRow>
                    <TableCell colSpan={7} align="center">
                      <Typography variant="body2" color="text.secondary" sx={{ py: 3 }}>
                        No transparency records found
                      </Typography>
                    </TableCell>
                  </TableRow>
                )
              : items.map((record) => {
                  const summary =
                    record.plain_language_summary.length > 80
                      ? `${record.plain_language_summary.slice(0, 80)}…`
                      : record.plain_language_summary;

                  return (
                    <TableRow key={record.id} hover>
                      <TableCell>
                        {new Date(record.created_at).toLocaleDateString()}
                      </TableCell>
                      <TableCell>{record.algorithm_name}</TableCell>
                      <TableCell>
                        <Typography
                          variant="body2"
                          noWrap
                          title={record.plain_language_summary}
                          sx={{ maxWidth: 220 }}
                        >
                          {summary}
                        </Typography>
                      </TableCell>
                      <TableCell>{record.evidence_base ?? '—'}</TableCell>
                      <TableCell>
                        <Chip label={`v${record.version}`} size="small" variant="outlined" />
                      </TableCell>
                      <TableCell>
                        {record.published_at
                          ? new Date(record.published_at).toLocaleDateString()
                          : '—'}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="small"
                          variant="outlined"
                          onClick={() => navigate(`/admin/transparency/${record.id}`)}
                        >
                          View
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
          </TableBody>
        </Table>
        <TablePagination
          rowsPerPageOptions={[10, 25, 50]}
          component="div"
          count={total}
          rowsPerPage={rowsPerPage}
          page={page}
          onPageChange={(_, newPage) => setPage(newPage)}
          onRowsPerPageChange={(e) => {
            setRowsPerPage(parseInt(e.target.value, 10));
            setPage(0);
          }}
        />
      </TableContainer>
    </Box>
  );
};

export default TransparencyPortal;
