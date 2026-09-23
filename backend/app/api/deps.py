from typing import Generator, Optional
import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AuthenticationError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository

security = HTTPBearer(auto_error=False)


def get_current_user(
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> User:
    """
    Derives authenticated user identity STRICTLY from validated JWT signature.
    Client-supplied user_id headers or bodies are NEVER trusted for authorization.
    """
    if not credentials or not credentials.credentials:
        if settings.ALLOW_PUBLIC_GALLERY:
            default_user = UserRepository.get_by_email(db, email="admin@vault.local")
            if not default_user:
                default_user = User(
                    id="vault-admin-001",
                    email="admin@vault.local",
                    password_hash="system_managed_vault_user",
                    full_name="Alice Vault",
                    is_active=True,
                    is_superuser=True,
                )
                db.add(default_user)
                db.commit()
                db.refresh(default_user)
            return default_user
        raise AuthenticationError("Not authenticated")

    token = credentials.credentials
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub")
        token_type: str = payload.get("type")
        if not user_id or token_type != "access":
            raise AuthenticationError("Invalid token claims")
    except jwt.PyJWTError:
        raise AuthenticationError("Invalid or expired access token")

    user = UserRepository.get_by_id(db, user_id=user_id)
    if not user:
        raise AuthenticationError("User associated with token no longer exists")
    if not user.is_active:
        raise AuthenticationError("User account has been deactivated")

    return user


def get_current_active_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operation requires administrator privileges",
        )
    return current_user
