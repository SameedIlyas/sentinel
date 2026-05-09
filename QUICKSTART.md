# Sentinel AI Platform - Quick Start Guide

This guide will help you get the complete Sentinel AI Platform running locally, including both the Policy Engine backend and the Dashboard frontend.

## Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL (or SQLite for development)
- npm

## Step 1: Set Up the Backend (Policy Engine)

### 1.1 Install Python Dependencies

```bash
# From project root
pip install -r policy_engine/requirements.txt
```

### 1.2 Configure Database

```bash
# Run database migrations
alembic upgrade head
```

### 1.3 Create Admin User

```bash
# Create default admin user (username: admin, password: admin123)
python create_admin_user.py --default

# OR create custom admin user interactively
python create_admin_user.py
```

### 1.4 Start the Policy Engine

```bash
# Start the FastAPI server on port 8000
python run_policy_engine.py
```

The Policy Engine API will be available at: **http://localhost:8000**

API Documentation: **http://localhost:8000/docs**

## Step 2: Set Up the Frontend (Dashboard)

### 2.1 Install Node Dependencies

```bash
# Navigate to dashboard directory
cd dashboard

# Install npm packages
npm install
```

### 2.2 Configure Environment (Optional)

```bash
# Copy environment template
cp .env.example .env

# Edit .env if you need to change the API URL
# Default: VITE_API_BASE_URL=http://localhost:8000
```

### 2.3 Start the Dashboard

```bash
# Start the Vite development server on port 3000
npm run dev
```

The Dashboard will be available at: **http://localhost:3000**

## Step 3: Access the Dashboard

1. Open your browser and navigate to **http://localhost:3000**

2. Log in with the default admin credentials:
   - **Username:** admin
   - **Password:** admin123

   > ⚠️ **Security Note:** Change the default password immediately in production!

3. You should now see the Sentinel AI Dashboard with navigation to:
   - Dashboard Overview
   - AI Agents
   - Policies
   - Audit Logs
   - Alerts
   - Users (admin only)

## Running Both Services

For convenience, you can run both services in separate terminal windows:

**Terminal 1 (Backend):**
```bash
python run_policy_engine.py
```

**Terminal 2 (Frontend):**
```bash
cd dashboard
npm run dev
```

## Testing the System

### Test Authentication

1. Logout from the dashboard
2. Try logging in with incorrect credentials (should fail)
3. Login with correct credentials (should succeed)
4. Navigate to different pages
5. Verify role-based access (Users page only for admin)

### Test API Endpoints

Visit the API documentation at http://localhost:8000/docs and test:

- `POST /v1/auth/login` - Login endpoint
- `GET /v1/auth/validate` - Token validation
- `GET /v1/users` - List users (requires auth)
- `GET /v1/agents` - List agents
- `GET /v1/policies` - List policies

### Test RBAC

Create different user roles:

```bash
# Run test script (requires Policy Engine running)
python test_task_11.py
```

This creates:
- Admin user (full access)
- Analyst user (read-only policies, full logs/alerts)
- Viewer user (read-only all)

## Common Issues and Solutions

### Issue: Cannot connect to backend

**Solution:**
- Ensure Policy Engine is running on port 8000
- Check that there are no firewall issues
- Verify the `VITE_API_BASE_URL` in dashboard `.env`

### Issue: Database errors

**Solution:**
```bash
# Check migration status
alembic current

# Run migrations
alembic upgrade head

# If issues persist, reset database (DEVELOPMENT ONLY!)
alembic downgrade base
alembic upgrade head
python create_admin_user.py --default
```

### Issue: npm install fails

**Solution:**
```bash
cd dashboard
rm -rf node_modules package-lock.json
npm install
```

### Issue: Login fails

**Solution:**
- Verify admin user was created: `python create_admin_user.py --default`
- Check browser console for errors
- Verify API is running: http://localhost:8000/docs
- Check that CORS is enabled in the backend

### Issue: Port already in use

**Solution:**

For backend (port 8000):
```bash
# Find process using port 8000
lsof -i :8000  # macOS/Linux
netstat -ano | findstr :8000  # Windows

# Kill the process or change port in run_policy_engine.py
```

For frontend (port 3000):
```bash
# Change port in dashboard/vite.config.ts
server: {
  port: 3001,  // Use different port
  ...
}
```

## Production Deployment

### Backend

1. Set environment variables:
   ```bash
   export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
   export JWT_SECRET_KEY="your-secure-random-key"
   export ENVIRONMENT="production"
   ```

2. Use a production WSGI server:
   ```bash
   pip install gunicorn
   gunicorn policy_engine.main:app --workers 4 --bind 0.0.0.0:8000
   ```

### Frontend

1. Build the dashboard:
   ```bash
   cd dashboard
   npm run build
   ```

2. Serve the `dist/` directory with a web server:
   - Nginx
   - Apache
   - AWS S3 + CloudFront
   - Netlify
   - Vercel

3. Update `VITE_API_BASE_URL` to your production API URL

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  Browser (http://localhost:3000)                           │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Sentinel AI Dashboard (React + TypeScript)        │    │
│  │  - Login/Auth                                      │    │
│  │  - Dashboard Overview                              │    │
│  │  - Agent Management                                │    │
│  │  - Policy Management                               │    │
│  │  - Audit Logs                                      │    │
│  │  - Alerts                                          │    │
│  │  - User Management                                 │    │
│  └────────────────────────────────────────────────────┘    │
│                         │ HTTP/REST                         │
│                         │ JWT Authentication                │
└─────────────────────────┼─────────────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────────┐
│  Policy Engine API (http://localhost:8000)                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │  FastAPI Backend (Python)                          │    │
│  │  - Authentication & RBAC                           │    │
│  │  - User Management                                 │    │
│  │  - Agent Tracking                                  │    │
│  │  - Policy Evaluation                               │    │
│  │  - Audit Logging                                   │    │
│  │  - Alert System                                    │    │
│  └────────────────────────────────────────────────────┘    │
│                         │                                   │
│                         ▼                                   │
│  ┌────────────────────────────────────────────────────┐    │
│  │  PostgreSQL/SQLite Database                        │    │
│  │  - Users, Policies, Agents, Audit Logs, Alerts     │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Next Steps

Now that you have the platform running:

1. **Task 13**: Implement dashboard metrics and real-time updates
2. **Task 14**: Build agent detail and activity views
3. **Task 15**: Create policy management UI
4. **Task 16**: Implement audit log viewer
5. **Task 17**: Build alert management UI

## Support

- **Documentation**: See individual README files in `policy_engine/` and `dashboard/`
- **API Docs**: http://localhost:8000/docs
- **Task Summaries**: TASK_11_SUMMARY.md, TASK_12_SUMMARY.md

## Security Checklist

Before deploying to production:

- [ ] Change default admin password
- [ ] Generate secure JWT secret key
- [ ] Enable HTTPS for both frontend and backend
- [ ] Configure CORS for production domains only
- [ ] Set up proper database backups
- [ ] Enable rate limiting
- [ ] Configure logging and monitoring
- [ ] Review and test all RBAC permissions
- [ ] Implement password complexity requirements
- [ ] Set up SSL/TLS certificates

---

**Sentinel AI Platform** - Enterprise AI Agent Governance
