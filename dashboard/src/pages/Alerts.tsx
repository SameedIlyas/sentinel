import React, { useState } from 'react';
import { Box, Typography, Tabs, Tab } from '@mui/material';
import AlertHistory from './AlertHistory';
import AlertRules from './AlertRules';
import { useAppStyles } from '@/hooks/useAppStyles';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index, ...other } = props;

  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`alert-tabpanel-${index}`}
      aria-labelledby={`alert-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ pt: 3, pb: 2, minHeight: '50vh' }}>{children}</Box>
      )}
    </div>
  );
}

const Alerts: React.FC = () => {
  const { theme } = useAppStyles();
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Box
      sx={{
        bgcolor: 'background.default',
        px: 3,
        pt: 3,
        pb: 4,
        minHeight: '100%',
      }}
    >
      <Typography
        variant="h4"
        sx={{
          fontWeight: 700,
          letterSpacing: '-0.02em',
          color: 'text.primary',
          mb: 0.5,
        }}
      >
        Alerts
      </Typography>
      <Typography variant="body2" sx={{ color: 'text.secondary', mb: 3, maxWidth: 560 }}>
        Review alert history, acknowledge items, and configure rules and Slack delivery.
      </Typography>

      <Box
        sx={{
          borderRadius: 2,
          border: `1px solid ${theme.palette.divider}`,
          bgcolor: 'background.paper',
          px: 1,
        }}
      >
        <Tabs
          value={tabValue}
          onChange={handleTabChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{
            minHeight: 48,
            '& .MuiTab-root': {
              textTransform: 'none',
              fontWeight: 600,
              fontSize: '0.875rem',
              color: 'text.secondary',
              minHeight: 48,
              '&.Mui-selected': {
                color: 'text.primary',
              },
            },
            '& .MuiTabs-indicator': {
              height: 3,
              borderRadius: '3px 3px 0 0',
              bgcolor: theme.palette.primary.main,
            },
          }}
        >
          <Tab label="Alert history" id="alert-tab-0" aria-controls="alert-tabpanel-0" />
          <Tab
            label="Rules & configuration"
            id="alert-tab-1"
            aria-controls="alert-tabpanel-1"
          />
        </Tabs>
      </Box>

      <TabPanel value={tabValue} index={0}>
        <AlertHistory />
      </TabPanel>
      <TabPanel value={tabValue} index={1}>
        <AlertRules />
      </TabPanel>
    </Box>
  );
};

export default Alerts;
