# Task 11: Role-Based Access Control (RBAC) - Implementation Summary

## Overview

This document summarizes the implementation of Role-Based Access Control (RBAC) for the Sentinel AI Policy Engine. The RBAC system provides secure user authentication, authorization, and permission management across all API endpoints.

## Architecture

### Authentication Flow
```
1. User logs in with username/password
2. System validates credentials (bcrypt password verification)
3. JWT token issued with 24-hour expiration
4. Client includes token in Authorization header for subsequent requests
5. Middleware validates token and extracts user information
6. Permission checks enforce role-based access control
```

### Security Features
- **Password Hashing**: bcrypt algorithm with automatic salt generation
- **JWT Tokens**: HS256 algorithm, stateless authentication
- **Token Expiration**: 24-hour lifetime with refresh capability
- **HTTP Security**: Bearer token scheme
- **Account Management**: Active/inactive status, cannot delete self

## User Roles

### 1. Administrator (ADMIN)
Full system access with all permissions.

**Permissions:**
- ✅ Create, read, update, delete policies
- ✅ Create, read, update, delete agents
- ✅ Read, export audit logs
- ✅ Read, acknowledge alerts
- ✅ Create, read, update, delete users
- ✅ Configure system settings

**Use Cases:**
- System configuration and policy management
- User and role administration
- Security incident response
- System auditing and compliance

### 2. Security Analyst (ANALYST)
Operational security monitoring and analysis.

**Permissions:**
- 🔒 Cannot create/modify policies (read-only)
- 🔒 Cannot create/modify agents (read-only)
- ✅ Full access to audit logs (read, export)
- ✅ Full access to alerts (read, acknowledge)
- 🔒 Cannot manage users
- 🔒 Cannot configure system settings

**Use Cases:**
- Security monitoring and alert triage
- Incident investigation and analysis
- Audit log review and export
- Security reporting

### 3. Viewer (VIEWER)
Read-only dashboard access for stakeholders.

**Permissions:**
- 🔒 Read-only policies
- 🔒 Read-only agents
- 🔒 Read-only audit logs (no export)
- 🔒 Read-only alerts (no acknowledge)
- 🔒 Cannot manage users
- 🔒 Cannot configure system settings

**Use Cases:**
- Executive dashboard viewing
- Compliance reporting and review
- Security posture awareness
- Stakeholder visibility

## Permission Matrix

| Resource    | Action       | ADMIN | ANALYST | VIEWER |
|-------------|--------------|-------|---------|--------|
| policies    | create       | ✅    | 🔒      | 🔒     |
| policies    | read         | ✅    | ✅      | ✅     |
| policies    | update       | ✅    | 🔒      | 🔒     |
| policies    | delete       | ✅    | 🔒      | 🔒     |
| agents      | create       | ✅    | 🔒      | 🔒     |
| agents      | read         | ✅    | ✅      | ✅     |
| agents      | update       | ✅    | 🔒      | 🔒     |
| agents      | delete       | ✅    | 🔒      | 🔒     |
| audit_logs  | read         | ✅    | ✅      | ✅     |
| audit_logs  | export       | ✅    | ✅      | 🔒     |
| alerts      | read         | ✅    | ✅      | ✅     |
| alerts      | acknowledge  | ✅    | ✅      | 🔒     |
| users       | create       | ✅    | 🔒      | 🔒     |
| users       | read         | ✅    | 🔒      | 🔒     |
| users       | update       | ✅    | 🔒      | 🔒     |
| users       | delete       | ✅    | 🔒      | 🔒     |
| system      | configure    | ✅    | 🔒      | 🔒     |

## API Endpoints

### Authentication Endpoints (`/v1/auth`)

#### POST /v1/auth/login
Authenticate user and receive JWT token.

**Request Body:**
```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@sentinel.ai",
    "role": "admin",
    "full_name": "System Administrator",
    "is_active": true,
    "created_at": "2024-02-10T16:00:00Z",
    "last_login": "2024-02-10T18:30:00Z"
  }
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid credentials or inactive account

---

#### POST /v1/auth/logout
Logout current user (client-side token invalidation).

**Headers:** `Authorization: Bearer <token>`

**Response (200 OK):**
```json
{
  "message": "Successfully logged out"
}
```

---

#### POST /v1/auth/refresh
Refresh JWT token with new expiration.

**Headers:** `Authorization: Bearer <token>`

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

---

#### GET /v1/auth/validate
Validate current token and return user information.

**Headers:** `Authorization: Bearer <token>`

**Response (200 OK):**
```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@sentinel.ai",
  "role": "admin",
  "full_name": "System Administrator",
  "is_active": true,
  "created_at": "2024-02-10T16:00:00Z",
  "last_login": "2024-02-10T18:30:00Z"
}
```

---

### User Management Endpoints (`/v1/users`)

#### POST /v1/users
Create a new user. **[ADMIN ONLY]**

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "username": "analyst_001",
  "email": "analyst@sentinel.ai",
  "password": "secure_password",
  "role": "analyst",
  "full_name": "Security Analyst"
}
```

**Response (201 Created):**
```json
{
  "id": 2,
  "username": "analyst_001",
  "email": "analyst@sentinel.ai",
  "role": "analyst",
  "full_name": "Security Analyst",
  "is_active": true,
  "created_at": "2024-02-10T16:30:00Z"
}
```

**Validation:**
- Username: 3-50 characters, alphanumeric with underscore/hyphen
- Email: Valid email format, unique
- Password: Minimum 8 characters
- Role: One of "admin", "analyst", "viewer"

---

#### GET /v1/users
List all users with pagination and filtering.

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**
- `page` (default: 1): Page number
- `page_size` (default: 50): Items per page
- `role`: Filter by role (admin, analyst, viewer)
- `search`: Search username or email
- `is_active`: Filter by active status (true/false)

**Response (200 OK):**
```json
{
  "users": [
    {
      "id": 1,
      "username": "admin",
      "email": "admin@sentinel.ai",
      "role": "admin",
      "full_name": "System Administrator",
      "is_active": true,
      "created_at": "2024-02-10T16:00:00Z",
      "last_login": "2024-02-10T18:30:00Z"
    }
  ],
  "total": 15,
  "page": 1,
  "page_size": 50,
  "total_pages": 1
}
```

---

#### GET /v1/users/{user_id}
Get specific user details.

**Headers:** `Authorization: Bearer <token>`

**Response (200 OK):**
```json
{
  "id": 2,
  "username": "analyst_001",
  "email": "analyst@sentinel.ai",
  "role": "analyst",
  "full_name": "Security Analyst",
  "is_active": true,
  "created_at": "2024-02-10T16:30:00Z",
  "last_login": "2024-02-10T17:00:00Z"
}
```

---

#### PUT /v1/users/{user_id}
Update user information. **[ADMIN ONLY]**

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "email": "new_email@sentinel.ai",
  "full_name": "Updated Name",
  "is_active": true
}
```

**Response (200 OK):** Returns updated user object.

---

#### DELETE /v1/users/{user_id}
Delete a user. **[ADMIN ONLY]**

**Headers:** `Authorization: Bearer <admin_token>`

**Response (200 OK):**
```json
{
  "message": "User deleted successfully"
}
```

**Constraints:**
- Cannot delete yourself
- Cannot delete if user has active sessions

---

#### POST /v1/users/{user_id}/change-password
Change user password.

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "current_password": "old_password",
  "new_password": "new_secure_password"
}
```

**Response (200 OK):**
```json
{
  "message": "Password updated successfully"
}
```

**Authorization:**
- Users can change their own password (must provide current password)
- Admins can change any user's password (no current password required)

---

#### POST /v1/users/assign-role
Assign role to user. **[ADMIN ONLY]**

**Headers:** `Authorization: Bearer <admin_token>`

**Request Body:**
```json
{
  "user_id": 2,
  "role": "analyst"
}
```

**Response (200 OK):** Returns updated user object.

---

#### GET /v1/users/me/profile
Get current authenticated user's profile.

**Headers:** `Authorization: Bearer <token>`

**Response (200 OK):** Returns current user object.

---

## Database Schema

### Users Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,  -- 'admin', 'analyst', 'viewer'
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE UNIQUE INDEX idx_users_username ON users(username);
CREATE UNIQUE INDEX idx_users_email ON users(email);
```

## Implementation Files

### Core Components

1. **policy_engine/models/user.py**
   - User database model
   - UserRole enum (ADMIN, ANALYST, VIEWER)
   - ROLE_PERMISSIONS permission matrix
   - has_permission() utility function

2. **policy_engine/auth/jwt_utils.py**
   - JWT token creation and validation
   - Password hashing and verification (bcrypt)
   - Token expiration management

3. **policy_engine/auth/rbac.py**
   - get_current_user() - Extract user from JWT
   - require_role() - Role-based access decorator
   - require_permission() - Permission-based access decorator

4. **policy_engine/routes/users.py**
   - User management CRUD endpoints
   - Password change functionality
   - Role assignment endpoint

5. **policy_engine/routes/auth.py**
   - Login/logout endpoints
   - Token refresh and validation
   - Authentication flow handlers

6. **policy_engine/models/schemas.py**
   - Pydantic schemas for validation
   - UserCreate, UserUpdate, UserResponse
   - UserLogin, TokenResponse

### Database Migration

**File:** `alembic/versions/2024_02_10_1600-003_add_users_table.py`

Apply migration:
```bash
alembic upgrade head
```

## Setup Instructions

### 1. Install Dependencies

Ensure the following packages are installed:

```bash
pip install PyJWT==2.8.0
pip install passlib[bcrypt]==1.7.4
pip install python-multipart==0.0.6
```

Or install from requirements:
```bash
pip install -r policy_engine/requirements.txt
```

### 2. Configure Environment

Add to `.env` or environment variables:

```bash
# JWT Secret Key (change in production!)
JWT_SECRET_KEY=your-super-secret-key-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
```

**Security Note:** Generate a secure random key for production:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Run Database Migration

Create the users table:

```bash
alembic upgrade head
```

### 4. Create Initial Admin User

**Option A: Interactive Mode**
```bash
python create_admin_user.py
```

**Option B: Default Admin (for testing)**
```bash
python create_admin_user.py --default
```

Creates user:
- Username: `admin`
- Password: `admin123`
- Email: `admin@sentinel.ai`
- Role: `admin`

**⚠️ WARNING:** Change the default password immediately in production!

### 5. Start the Policy Engine

```bash
python run_policy_engine.py
```

### 6. Test RBAC Functionality

```bash
python test_task_11.py
```

## Usage Examples

### Example 1: Login and Access Protected Endpoint

```python
import requests

# 1. Login
response = requests.post(
    "http://localhost:8000/v1/auth/login",
    json={
        "username": "admin",
        "password": "admin123"
    }
)
token = response.json()["access_token"]

# 2. Access protected endpoint
headers = {"Authorization": f"Bearer {token}"}
response = requests.get(
    "http://localhost:8000/v1/users",
    headers=headers
)
users = response.json()
```

### Example 2: Create User (Admin Only)

```python
headers = {"Authorization": f"Bearer {admin_token}"}

response = requests.post(
    "http://localhost:8000/v1/users",
    headers=headers,
    json={
        "username": "analyst_001",
        "email": "analyst@example.com",
        "password": "SecurePass123",
        "role": "analyst",
        "full_name": "John Doe"
    }
)
```

### Example 3: Check Permissions

```python
# Analyst trying to create a policy (will fail)
headers = {"Authorization": f"Bearer {analyst_token}"}

response = requests.post(
    "http://localhost:8000/v1/policies",
    headers=headers,
    json={...}
)
# Returns: 403 Forbidden - "Insufficient permissions"
```

## Applying RBAC to Existing Endpoints

To protect existing endpoints with RBAC, use the decorators from `policy_engine/auth/rbac.py`:

### Example: Protect Policy Endpoints

```python
from fastapi import APIRouter, Depends
from policy_engine.auth.rbac import get_current_user, require_permission
from policy_engine.models.user import User

router = APIRouter()

@router.post("/v1/policies")
async def create_policy(
    policy_data: PolicyCreate,
    current_user: User = Depends(require_permission("policies", "create"))
):
    # Only users with "policies:create" permission can access
    # (ADMIN only, based on ROLE_PERMISSIONS matrix)
    ...

@router.get("/v1/policies")
async def list_policies(
    current_user: User = Depends(require_permission("policies", "read"))
):
    # All authenticated users with "policies:read" permission
    # (ADMIN, ANALYST, VIEWER all have this permission)
    ...

@router.delete("/v1/policies/{policy_id}")
async def delete_policy(
    policy_id: int,
    current_user: User = Depends(require_permission("policies", "delete"))
):
    # Only ADMIN can delete policies
    ...
```

### Example: Role-Based Access

```python
from policy_engine.auth.rbac import require_role, get_admin_user

@router.post("/v1/system/configure")
async def configure_system(
    config: SystemConfig,
    current_user: User = Depends(get_admin_user)  # Admin only
):
    # Only administrators can access
    ...

@router.get("/v1/alerts")
async def list_alerts(
    current_user: User = Depends(require_role(["admin", "analyst", "viewer"]))
):
    # Multiple roles allowed
    ...
```

## Security Considerations

### 1. Token Management
- **Storage**: Store JWT tokens securely (HTTPOnly cookies or secure storage)
- **Transmission**: Always use HTTPS in production
- **Expiration**: Tokens expire after 24 hours, use refresh endpoint
- **Revocation**: Implement token blacklist for logout if needed

### 2. Password Security
- **Hashing**: bcrypt with automatic salt (cost factor: 12 rounds)
- **Requirements**: Minimum 8 characters (enforce stronger policies in production)
- **Storage**: Never store plaintext passwords
- **Validation**: Validate strength on client and server

### 3. Environment Security
- **SECRET_KEY**: Never commit to version control
- **Production Keys**: Generate strong random keys (32+ bytes)
- **Key Rotation**: Plan for periodic key rotation
- **Environment Variables**: Use secure environment variable management

### 4. API Security
- **HTTPS Only**: Enforce HTTPS in production
- **CORS**: Configure appropriate CORS policies
- **Rate Limiting**: Implement rate limiting on auth endpoints
- **API Keys**: Still require API keys for policy endpoints (dual authentication)

### 5. Account Security
- **Inactive Accounts**: Disable unused accounts
- **Failed Logins**: Implement account lockout after failed attempts
- **Audit Logging**: Log all authentication attempts
- **Session Management**: Track active sessions

## Testing

Run the comprehensive test suite:

```bash
python test_task_11.py
```

**Test Coverage:**
- ✅ Admin login and token generation
- ✅ Create analyst and viewer users
- ✅ User authentication for all roles
- ✅ User listing and pagination
- ✅ Permission enforcement (analyst cannot create policies)
- ✅ Permission enforcement (viewer cannot create users)
- ✅ Role assignment by admin
- ✅ Password change functionality
- ✅ Token validation
- ✅ Token refresh
- ✅ Invalid token rejection
- ✅ Current user profile retrieval

## Integration with Existing Features

### Policy Engine Integration
Update existing policy endpoints to require RBAC:

```python
# In policy_engine/routes/policies.py
from policy_engine.auth.rbac import require_permission

@router.post("/v1/policies")
async def create_policy(
    policy: PolicyCreate,
    api_key: str = Depends(get_api_key),
    current_user: User = Depends(require_permission("policies", "create"))
):
    # Dual authentication: API key + RBAC
    ...
```

### Audit Logging Integration
Log RBAC events in audit system:

```python
# Successful login
audit_log = AuditLog(
    agent_id="system",
    action="user.login",
    user_id=user.id,
    details={"username": user.username, "role": user.role}
)

# Failed login attempt
audit_log = AuditLog(
    agent_id="system",
    action="user.login_failed",
    details={"username": username, "reason": "invalid_credentials"}
)
```

## Troubleshooting

### Issue: "Invalid credentials" on login
**Solution:**
- Verify username and password are correct
- Check if user account is active (`is_active = true`)
- Ensure user exists in database

### Issue: "Token has expired"
**Solution:**
- Use the `/v1/auth/refresh` endpoint to get a new token
- Re-authenticate if refresh token also expired

### Issue: "Insufficient permissions"
**Solution:**
- Check user's role and permission matrix
- Verify endpoint requires appropriate permission
- Contact administrator to change role if needed

### Issue: Cannot create admin user
**Solution:**
- Ensure database migration has run (`alembic upgrade head`)
- Check database connection in config
- Verify no existing user with same username/email

## Future Enhancements

1. **Multi-Factor Authentication (MFA)**
   - TOTP-based 2FA
   - SMS/Email verification codes

2. **Advanced Password Policies**
   - Complexity requirements
   - Password history
   - Expiration policies

3. **Session Management**
   - Active session tracking
   - Force logout capability
   - Concurrent session limits

4. **Audit Enhancements**
   - Detailed RBAC audit trail
   - Permission change tracking
   - Login anomaly detection

5. **OAuth Integration**
   - SSO with corporate identity providers
   - OAuth 2.0 / OpenID Connect support
   - SAML integration

## Conclusion

The RBAC implementation provides enterprise-grade authentication and authorization for the Sentinel AI Policy Engine. All API endpoints are now protected with role-based permissions, ensuring secure access control for administrators, security analysts, and viewers.

**Task 11 Status:** ✅ Complete

**Files Created:** 8 files
**Database Tables:** 1 table (users)
**API Endpoints:** 13 endpoints
**Test Coverage:** 14 test cases

For questions or issues, refer to the main documentation or create an issue in the repository.
