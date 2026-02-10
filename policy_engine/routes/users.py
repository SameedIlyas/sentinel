"""User management endpoints"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import uuid
import math

from policy_engine.database import get_db
from policy_engine.models.user import User, UserRole
from policy_engine.models.schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    PasswordChange,
    RoleAssignment
)
from policy_engine.auth.rbac import get_current_user, get_admin_user
from policy_engine.auth.jwt_utils import get_password_hash, verify_password

router = APIRouter()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Create a new user (admin only)
    
    Only administrators can create new users. The password will be hashed
    using bcrypt before storing.
    
    Args:
        user_data: User creation data
        current_user: Current authenticated admin user
        db: Database session
        
    Returns:
        Created user object
        
    Raises:
        HTTPException: If username or email already exists
    """
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_data.username}' already exists"
        )
    
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{user_data.email}' already exists"
        )
    
    # Create new user
    user_id = f"user_{uuid.uuid4().hex[:16]}"
    
    new_user = User(
        id=user_id,
        username=user_data.username.lower(),
        email=user_data.email.lower(),
        password_hash=get_password_hash(user_data.password),
        role=user_data.role,
        full_name=user_data.full_name,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        last_login=None,
        is_active=True
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return new_user


@router.get("", response_model=UserListResponse)
async def list_users(
    current_user: User = Depends(get_current_user),
    role_filter: Optional[str] = Query(None, description="Filter by role"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    search: Optional[str] = Query(None, description="Search by username, email, or name"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    List all users with filtering and pagination
    
    All authenticated users can list users, but viewers cannot see user details
    unless they're viewing their own profile.
    
    Args:
        current_user: Current authenticated user
        role_filter: Filter by user role
        is_active: Filter by active status
        search: Search term
        page: Page number
        page_size: Items per page
        db: Database session
        
    Returns:
        Paginated list of users
    """
    # Build query
    query = db.query(User)
    
    # Apply filters
    if role_filter:
        try:
            role_enum = UserRole(role_filter.lower())
            query = query.filter(User.role == role_enum)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role: {role_filter}. Must be one of: admin, analyst, viewer"
            )
    
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (User.username.ilike(search_pattern)) |
            (User.email.ilike(search_pattern)) |
            (User.full_name.ilike(search_pattern))
        )
    
    # Get total count
    total = query.count()
    
    # Calculate pagination
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    offset = (page - 1) * page_size
    
    # Get paginated results
    users = query.order_by(User.created_at.desc()).offset(offset).limit(page_size).all()
    
    return UserListResponse(
        users=users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a specific user by ID
    
    Users can view their own profile. Admins and analysts can view any user.
    
    Args:
        user_id: User ID to retrieve
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        User details
        
    Raises:
        HTTPException: If user not found or insufficient permissions
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found"
        )
    
    # Check permissions: only admins/analysts can view other users, viewers can only view self
    if current_user.role == UserRole.VIEWER and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view other users"
        )
    
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    update_data: UserUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Update a user (admin only)
    
    Only administrators can update user information, including roles and
    active status.
    
    Args:
        user_id: User ID to update
        update_data: Updated user data
        current_user: Current authenticated admin user
        db: Database session
        
    Returns:
        Updated user object
        
    Raises:
        HTTPException: If user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found"
        )
    
    # Update fields if provided
    update_dict = update_data.model_dump(exclude_unset=True)
    
    # Handle password separately
    if 'password' in update_dict:
        user.password_hash = get_password_hash(update_dict['password'])
        del update_dict['password']
    
    for field, value in update_dict.items():
        setattr(user, field, value)
    
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Delete a user (admin only)
    
    Only administrators can delete users. Cannot delete yourself.
    
    Args:
        user_id: User ID to delete
        current_user: Current authenticated admin user
        db: Database session
        
    Raises:
        HTTPException: If user not found or trying to delete self
    """
    # Prevent deleting yourself
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found"
        )
    
    db.delete(user)
    db.commit()


@router.post("/{user_id}/change-password", response_model=UserResponse)
async def change_password(
    user_id: str,
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change user password
    
    Users can change their own password. Admins can change any user's password
    without needing the current password.
    
    Args:
        user_id: User ID to change password for
        password_data: Password change data
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        Updated user object
        
    Raises:
        HTTPException: If user not found or current password is incorrect
    """
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' not found"
        )
    
    # Check permissions
    if current_user.role != UserRole.ADMIN and current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to change password for other users"
        )
    
    # Verify current password (not required for admins changing other users' passwords)
    if current_user.id == user_id:
        if not verify_password(password_data.current_password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
    
    # Update password
    user.password_hash = get_password_hash(password_data.new_password)
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user


@router.post("/assign-role", response_model=UserResponse)
async def assign_role(
    role_data: RoleAssignment,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """
    Assign a role to a user (admin only)
    
    Only administrators can change user roles.
    
    Args:
        role_data: Role assignment data
        current_user: Current authenticated admin user
        db: Database session
        
    Returns:
        Updated user object
        
    Raises:
        HTTPException: If user not found
    """
    user = db.query(User).filter(User.id == role_data.user_id).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{role_data.user_id}' not found"
        )
    
    # Update role
    user.role = role_data.role
    user.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(user)
    
    return user


@router.get("/me/profile", response_model=UserResponse)
async def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user's profile
    
    Returns the profile of the currently authenticated user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user's profile
    """
    return current_user
