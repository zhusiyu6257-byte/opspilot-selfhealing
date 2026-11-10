from collections.abc import Sequence
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetResponse

router = APIRouter(prefix="/assets", tags=["Assets"])


@router.post("", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    payload: AssetCreate,
    db: AsyncSession = Depends(get_db),
):
    """录入/注册新主机资产"""
    # 检查重名资产
    existing = await db.scalar(select(Asset).where(Asset.name == payload.name))
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Asset with name '{payload.name}' already exists",
        )

    new_asset = Asset(
        name=payload.name,
        ip_address=payload.ip_address,
        os_type=payload.os_type,
        status=payload.status,
    )
    db.add(new_asset)
    await db.commit()
    await db.refresh(new_asset)
    return new_asset


@router.get("", response_model=list[AssetResponse])
async def list_assets(
    db: AsyncSession = Depends(get_db),
) -> Sequence[Asset]:
    """获取所有主机资产列表"""
    result = await db.scalars(select(Asset).order_by(Asset.id.desc()))
    return result.all()
