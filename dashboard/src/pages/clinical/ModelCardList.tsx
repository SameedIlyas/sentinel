// src/pages/clinical/ModelCardList.tsx
import React, { useState } from 'react';
import {
  Box,
  Typography,
  Button,
  Chip,
  Table,
  TableHead,
  TableBody,
  TableRow,
  TableCell,
  TableContainer,
  Paper,
  IconButton,
  TextField,
  Skeleton,
  Alert,
  Stack,
  TablePagination,
  Tooltip,
} from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import ArticleIcon from '@mui/icons-material/Article';
import { listModelCards } from '@/api/healthcare';
import { ModelCard, ModelCardLifecycle } from '@/types';
import EmptyState from '@/components/common/EmptyState';

const LIFECYCLE_STAGES: Array<{ value: ModelCardLifecycle | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'review', label: 'Review' },
  { value: 'published', label: 'Published' },
  { value: 'retired', label: 'Retired' },
];

function getLifecycleColor(
  stage: ModelCardLifecycle
): 'default' | 'warning' | 'success' | 'error' {
  switch (stage) {
    case 'draft':
      return 'default';
    case 'review':
      return 'warning';
    case 'published':
      return 'success';
    case 'retired':
      return 'error';
  }
}

function truncate(text: string, maxLen = 60): string {
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text;
}

function SkeletonRows({ count }: { count: number }) {
  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <TableRow key={i}>
          {Array.from({ length: 7 }).map((__, j) => (
            <TableCell key={j}>
              <Skeleton variant="text" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}

const ModelCardList: React.FC = () => {
  const navigate = useNavigate();
  const [lifecycleFilter, setLifecycleFilter] = useState<ModelCardLifecycle | 'all'>('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['model-cards', lifecycleFilter, page, rowsPerPage],
    queryFn: () =>
      listModelCards({
        lifecycle_stage: lifecycleFilter === 'all' ? undefined : lifecycleFilter,
        page: page + 1,
        page_size: rowsPerPage,
      }),
  });

  // Backend returns `name`; the TS type calls it `model_name`. Tolerate either
  // and normalise so the rest of the page can rely on `card.model_name`.
  const filteredItems: ModelCard[] = (data?.items ?? [])
    .map((card) => ({
      ...card,
      model_name: card.model_name ?? (card as unknown as { name?: string }).name ?? '',
    }))
    .filter((card) =>
      (card.model_name || '').toLowerCase().includes(search.toLowerCase()),
    );

  const handleRowClick = (id: string) => {
    navigate(`/clinical/model-cards/${id}`);
  };

  const handleChangePage = (_: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <ArticleIcon sx={{ color: 'primary.main', fontSize: 28 }} />
          <Box>
            <Typography variant="h4">Model Cards</Typography>
            <Typography variant="body2" color="text.secondary">
              CHAI-compliant model documentation for all clinical AI systems
            </Typography>
          </Box>
        </Box>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate('/clinical/model-cards/new')}
        >
          New Model Card
        </Button>
      </Box>

      {/* Filters */}
      <Stack direction="row" spacing={1} sx={{ mb: 2 }} flexWrap="wrap">
        {LIFECYCLE_STAGES.map((stage) => (
          <Chip
            key={stage.value}
            label={stage.label}
            onClick={() => {
              setLifecycleFilter(stage.value);
              setPage(0);
            }}
            color={lifecycleFilter === stage.value ? 'primary' : 'default'}
            variant={lifecycleFilter === stage.value ? 'filled' : 'outlined'}
            clickable
          />
        ))}
      </Stack>

      <TextField
        size="small"
        placeholder="Search by model name…"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        sx={{ mb: 2, width: 320 }}
      />

      {/* Error */}
      {isError && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {(error as Error)?.message ?? 'Failed to load model cards.'}
        </Alert>
      )}

      {/* Table */}
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Model Name</TableCell>
              <TableCell>Version</TableCell>
              <TableCell>Lifecycle</TableCell>
              <TableCell>FDA Status</TableCell>
              <TableCell>Intended Use</TableCell>
              <TableCell>Updated</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {isLoading ? (
              <SkeletonRows count={5} />
            ) : filteredItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} sx={{ p: 0, border: 0 }}>
                  <EmptyState
                    title={search ? 'No model cards match your search' : 'No model cards yet'}
                    description="Model cards are CHAI-compliant documentation for every clinical AI model your organization has deployed — intended use, indications, contraindications, performance, and bias summary."
                    ingestHint="Create cards manually, or auto-fill from a GitHub repo + MLflow run via the auto-fill endpoint. A future MLflow sync job will create draft cards automatically when models are registered."
                    icon={<ArticleIcon />}
                    primaryAction={{
                      label: 'New Model Card',
                      onClick: () => navigate('/clinical/model-cards/new'),
                      startIcon: <AddIcon />,
                    }}
                  />
                </TableCell>
              </TableRow>
            ) : (
              filteredItems.map((card) => (
                <TableRow
                  key={card.id}
                  hover
                  sx={{ cursor: 'pointer' }}
                  onClick={() => handleRowClick(card.id)}
                >
                  <TableCell>
                    <Typography variant="body2" fontWeight={500}>
                      {card.model_name}
                    </Typography>
                  </TableCell>
                  <TableCell>{card.model_version}</TableCell>
                  <TableCell>
                    <Chip
                      label={card.lifecycle_stage}
                      color={getLifecycleColor(card.lifecycle_stage)}
                      size="small"
                    />
                  </TableCell>
                  <TableCell>
                    {card.fda_status ? (
                      <Typography variant="body2">{card.fda_status}</Typography>
                    ) : (
                      <Typography variant="body2" color="text.disabled">
                        —
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell>
                    <Tooltip title={card.intended_use}>
                      <Typography variant="body2">{truncate(card.intended_use)}</Typography>
                    </Tooltip>
                  </TableCell>
                  <TableCell>
                    <Typography variant="body2" color="text.secondary">
                      {new Date(card.updated_at).toLocaleDateString()}
                    </Typography>
                  </TableCell>
                  <TableCell align="right">
                    <IconButton
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/clinical/model-cards/${card.id}`);
                      }}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </TableContainer>

      {/* Pagination */}
      {!isLoading && (data?.total ?? 0) > 0 && (
        <TablePagination
          component="div"
          count={data?.total ?? 0}
          page={page}
          onPageChange={handleChangePage}
          rowsPerPage={rowsPerPage}
          onRowsPerPageChange={handleChangeRowsPerPage}
          rowsPerPageOptions={[10, 25, 50]}
        />
      )}
    </Box>
  );
};

export default ModelCardList;
