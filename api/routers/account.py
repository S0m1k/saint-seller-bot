from fastapi import APIRouter, Body, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_session
from core.models import User
from api.auth import get_current_user
from api.schemas import MeOut

router = APIRouter(prefix="/api", tags=["account"])


@router.get("/me", response_model=MeOut)
async def get_me(user: User = Depends(get_current_user)):
    return user


@router.patch("/me", response_model=MeOut)
async def update_me(
    phone: str | None = Body(default=None, embed=True),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    if phone is not None:
        user.phone = phone.strip() or None
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user
