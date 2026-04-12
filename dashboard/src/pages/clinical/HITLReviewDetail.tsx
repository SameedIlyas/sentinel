import React, { useState } from 'react';
import {
  Box, Typography, Paper, Chip, Skeleton, Alert, Button,
  TextField, Radio, RadioGroup, FormControlLabel, FormLabel,
  Divider,
} from '@mui/material';
import HowToRegIcon from '@mui/icons-material/HowToReg';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { getHITLReview, submitHITLDecision } from '@/api/healthcare';
import type { HITLStatus } from '@/types';

const statusColor = (s: HITLStatus): 'warning' | 'success' | 'error' | 'info' => {
  if (s === 'pending') return 'warning';
  if (s === 'approved') return 'success';
  if (s === 'rejected') return 'error';
  return 'info';
};

const HITLReviewDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

  const [decision, setDecision] = useState<'approved' | 'rejected' | 'modified'>('approved');
  const [reviewerDecision, setReviewerDecision] = useState('');
  const [notes, setNotes] = useState('');
  const [submitSuccess, setSubmitSuccess] = useState(false);
  const [submitError, setSubmitError] = useState('');

  const { data: review, isLoading, isError } = useQuery({
    queryKey: ['hitlReview', id],
    queryFn: () => getHITLReview(id!),
    enabled: !!id,
  });

  const mutation = useMutation({
    mutationFn: () =>
      submitHITLDecision(id!, {
        status: decision,
        reviewer_decision: reviewerDecision,
        reviewer_notes: notes || undefined,
      }),
    onSuccess: () => {
      setSubmitSuccess(true);
      setSubmitError('');
      queryClient.invalidateQueries({ queryKey: ['hitlReview', id] });
      queryClient.invalidateQueries({ queryKey: ['hitlReviews'] });
    },
    onError: () => {
      setSubmitError('Failed to submit decision. Please try again.');
    },
  });

  const handleSubmit = () => {
    if (!reviewerDecision.trim()) return;
    setSubmitSuccess(false);
    setSubmitError('');
    mutation.mutate();
  };

  const isOverdue = review?.sla_deadline ? new Date(review.sla_deadline) < new Date() : false;

  return (
    <Box>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, mb: 3 }}>
        <HowToRegIcon sx={{ color: 'primary.main', fontSize: 28 }} />
        <Typography variant="h4">HITL Review Detail</Typography>
      </Box>

      {isError && <Alert severity="error" sx={{ mb: 2 }}>Failed to load review.</Alert>}

      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>Review Information</Typography>
        <Divider sx={{ mb: 2 }} />
        {isLoading ? (
          Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} variant="text" sx={{ mb: 1 }} />)
        ) : review ? (
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">Model ID</Typography>
              <Typography>{review.model_id}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Status</Typography>
              <Box>
                <Chip label={review.status} color={statusColor(review.status)} size="small" />
              </Box>
            </Box>
            <Box sx={{ gridColumn: '1 / -1' }}>
              <Typography variant="caption" color="text.secondary">AI Decision</Typography>
              <Typography>{review.ai_decision}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">AI Confidence</Typography>
              <Typography>
                {review.ai_confidence != null ? `${(review.ai_confidence * 100).toFixed(1)}%` : '—'}
              </Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Risk Score</Typography>
              <Typography>{review.risk_score ?? '—'}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Created</Typography>
              <Typography>{new Date(review.created_at).toLocaleString()}</Typography>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">SLA Deadline</Typography>
              <Typography sx={{ color: isOverdue ? 'error.main' : 'inherit' }}>
                {review.sla_deadline ? new Date(review.sla_deadline).toLocaleString() : '—'}
                {isOverdue && ' (Overdue)'}
              </Typography>
            </Box>
          </Box>
        ) : null}
      </Paper>

      {review && review.status !== 'pending' && (
        <Paper sx={{ p: 3, mb: 3 }}>
          <Typography variant="h6" gutterBottom>Decision</Typography>
          <Divider sx={{ mb: 2 }} />
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 2 }}>
            <Box>
              <Typography variant="caption" color="text.secondary">Status</Typography>
              <Box><Chip label={review.status} color={statusColor(review.status)} size="small" /></Box>
            </Box>
            <Box>
              <Typography variant="caption" color="text.secondary">Reviewed At</Typography>
              <Typography>
                {review.reviewed_at ? new Date(review.reviewed_at).toLocaleString() : '—'}
              </Typography>
            </Box>
            <Box sx={{ gridColumn: '1 / -1' }}>
              <Typography variant="caption" color="text.secondary">Reviewer Decision</Typography>
              <Typography>{review.reviewer_decision ?? '—'}</Typography>
            </Box>
            {review.reviewer_notes && (
              <Box sx={{ gridColumn: '1 / -1' }}>
                <Typography variant="caption" color="text.secondary">Notes</Typography>
                <Typography>{review.reviewer_notes}</Typography>
              </Box>
            )}
          </Box>
        </Paper>
      )}

      {review && review.status === 'pending' && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" gutterBottom>Submit Decision</Typography>
          <Divider sx={{ mb: 2 }} />

          {submitSuccess && (
            <Alert severity="success" sx={{ mb: 2 }}>Decision submitted successfully.</Alert>
          )}
          {submitError && (
            <Alert severity="error" sx={{ mb: 2 }}>{submitError}</Alert>
          )}

          <FormLabel component="legend">Decision</FormLabel>
          <RadioGroup
            row
            value={decision}
            onChange={(e) => setDecision(e.target.value as typeof decision)}
            sx={{ mb: 2 }}
          >
            <FormControlLabel value="approved" control={<Radio />} label="Approve" />
            <FormControlLabel value="rejected" control={<Radio />} label="Reject" />
            <FormControlLabel value="modified" control={<Radio />} label="Modify" />
          </RadioGroup>

          <TextField
            label="Reviewer Decision"
            value={reviewerDecision}
            onChange={(e) => setReviewerDecision(e.target.value)}
            required
            fullWidth
            sx={{ mb: 2 }}
          />

          <TextField
            label="Notes (optional)"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            multiline
            rows={3}
            fullWidth
            sx={{ mb: 2 }}
          />

          <Button
            variant="contained"
            onClick={handleSubmit}
            disabled={mutation.isPending || !reviewerDecision.trim()}
          >
            {mutation.isPending ? 'Submitting…' : 'Submit Decision'}
          </Button>
        </Paper>
      )}
    </Box>
  );
};

export default HITLReviewDetail;
