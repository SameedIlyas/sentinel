import React, { useState } from 'react';
import { Box, Typography, Tabs, Tab } from '@mui/material';
import AlertHistory from './AlertHistory';
import AlertRules from './AlertRules';

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
      {value === index && <Box sx={{ pt: 3 }}>{children}</Box>}
    </div>
  );
}

const Alerts: React.FC = () => {
  const [tabValue, setTabValue] = useState(0);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setTabValue(newValue);
  };

  return (
    <Box>
      <Typography variant="h4" gutterBottom sx={{ fontWeight: 'bold', mb: 3 }}>
        Alerts
      </Typography>

      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tabValue} onChange={handleTabChange}>
          <Tab label="Alert History" />
          <Tab label="Alert Rules & Configuration" />
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
