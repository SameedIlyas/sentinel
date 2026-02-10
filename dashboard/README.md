# Sentinel AI Dashboard

React-based dashboard for the Sentinel AI Policy Engine. Provides real-time visibility into AI agent activity, policy enforcement, audit logs, and alerts.

## Features

- **Authentication**: JWT-based authentication with role-based access control
- **Dashboard Overview**: Real-time metrics on agent activity, blocked actions, and financial impact
- **Agent Management**: View and monitor AI agents
- **Policy Management**: Configure and manage security policies
- **Audit Logs**: Comprehensive audit trail with search and export
- **Alerts**: Real-time security alerts and notifications
- **User Management**: Admin-only user and role management

## Tech Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite 5
- **UI Library**: Material-UI (MUI) 5
- **Routing**: React Router v6
- **HTTP Client**: Axios
- **State Management**: React Context API

## Prerequisites

- Node.js 18+ and npm
- Sentinel AI Policy Engine running on http://localhost:8000

## Quick Start

### 1. Install Dependencies

```bash
cd dashboard
npm install
```

### 2. Configure Environment

Create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` if needed:

```env
VITE_API_BASE_URL=http://localhost:8000
```

### 3. Start Development Server

```bash
npm run dev
```

The dashboard will be available at http://localhost:3000

### 4. Login

Use the default admin credentials:

- **Username**: admin
- **Password**: admin123

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## User Roles

### Administrator
- Full access to all features
- Can create/edit/delete policies
- Can manage users and roles
- Can configure system settings

### Security Analyst
- Read-only access to policies and agents
- Full access to audit logs (can export)
- Can view and acknowledge alerts
- Cannot modify policies or manage users

### Viewer
- Read-only access to all features
- Can view dashboard, policies, agents, audit logs, and alerts
- Cannot export, acknowledge, or modify anything

## Project Structure

```
dashboard/
├── src/
│   ├── api/              # API client and request handlers
│   │   └── client.ts     # Axios client with JWT auth
│   ├── components/       # Reusable React components
│   │   ├── auth/         # Authentication components
│   │   │   ├── Login.tsx
│   │   │   └── ProtectedRoute.tsx
│   │   └── layout/       # Layout components
│   │       └── AppLayout.tsx
│   ├── contexts/         # React context providers
│   │   └── AuthContext.tsx
│   ├── pages/            # Page components
│   │   ├── Dashboard.tsx
│   │   ├── Agents.tsx
│   │   ├── Policies.tsx
│   │   ├── AuditLogs.tsx
│   │   ├── Alerts.tsx
│   │   └── Users.tsx
│   ├── types/            # TypeScript type definitions
│   │   └── index.ts
│   ├── App.tsx           # Main app component with routing
│   ├── main.tsx          # Application entry point
│   └── vite-env.d.ts     # Vite type definitions
├── public/               # Static assets
├── index.html            # HTML template
├── package.json          # Dependencies and scripts
├── tsconfig.json         # TypeScript configuration
├── vite.config.ts        # Vite configuration
└── .eslintrc.cjs         # ESLint configuration
```

## Authentication Flow

1. User enters credentials on login page
2. Frontend sends POST request to `/v1/auth/login`
3. Backend validates credentials and returns JWT token
4. Token stored in localStorage
5. Token included in Authorization header for all API requests
6. Token automatically refreshed when expired
7. User redirected to login on 401 errors

## API Integration

The API client (`src/api/client.ts`) handles:

- JWT token management (storage, refresh, expiration)
- Automatic token injection in request headers
- Token refresh on 401 errors
- Centralized error handling
- Request/response interceptors

### Example Usage

```typescript
import apiClient from '@/api/client';

// Login
await apiClient.login({ username: 'admin', password: 'admin123' });

// Make authenticated requests
const agents = await apiClient.get('/v1/agents');
const policy = await apiClient.post('/v1/policies', policyData);
const user = await apiClient.put(`/v1/users/${userId}`, userData);

// Logout
await apiClient.logout();
```

## Development

### Adding a New Page

1. Create page component in `src/pages/`
2. Add route in `src/App.tsx`
3. Add navigation item in `src/components/layout/AppLayout.tsx`
4. Add required permissions if needed

### Adding API Endpoints

1. Add TypeScript types in `src/types/index.ts`
2. Create API methods in `src/api/client.ts` or create new API module
3. Use in components with proper error handling

## Building for Production

```bash
npm run build
```

This creates an optimized production build in the `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

### Deploy

The `dist/` directory can be deployed to any static hosting service:

- Netlify
- Vercel
- AWS S3 + CloudFront
- Azure Static Web Apps
- GitHub Pages

## Environment Variables

- `VITE_API_BASE_URL` - Base URL for the Sentinel AI Policy Engine API (default: http://localhost:8000)

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Future Enhancements

- Real-time updates with WebSocket (Task 13)
- Advanced dashboard metrics and charts (Task 13)
- Agent detail views (Task 14)
- Policy editor UI (Task 15)
- Audit log viewer with advanced filtering (Task 16)
- Alert management UI (Task 17)

## Troubleshooting

### Cannot connect to API

- Ensure Policy Engine is running on http://localhost:8000
- Check VITE_API_BASE_URL in `.env`
- Verify CORS is enabled in the backend

### Build errors

- Delete `node_modules/` and `package-lock.json`
- Run `npm install` again
- Clear Vite cache: `rm -rf node_modules/.vite`

### Login issues

- Ensure admin user exists (run `create_admin_user.py` on backend)
- Check browser console for errors
- Verify API endpoint is reachable

## License

Part of the Sentinel AI Platform
