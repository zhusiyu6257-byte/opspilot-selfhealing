from collections.abc import Sequence
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.credential_vault import CredentialVaultError, encrypt_secret
from app.db.session import get_db
from app.models.asset import Asset
from app.schemas.asset import AssetCreate, AssetResponse

router = APIRouter(prefix="/assets", tags=["Assets"])


def to_response(asset: Asset) -> AssetResponse:
    """只回显「有没有凭据」，密文和明文都不出现在接口响应里。"""
    return AssetResponse.model_validate(asset).model_copy(
        update={"has_stored_password": bool(asset.ssh_password_encrypted)}
    )


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

    existing_ip = await db.scalar(
        select(Asset).where(Asset.ip_address == payload.ip_address)
    )
    if existing_ip:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Asset with ip '{payload.ip_address}' already exists",
        )

    encrypted_password = ""
    if payload.ssh_password:
        try:
            encrypted_password = encrypt_secret(payload.ssh_password)
        except CredentialVaultError as exc:
            # 没配钥匙就拒绝，而不是退回明文保存 —— fail closed
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

    new_asset = Asset(
        name=payload.name,
        ip_address=payload.ip_address,
        os_type=payload.os_type,
        status=payload.status,
        ssh_port=payload.ssh_port,
        ssh_user=payload.ssh_user,
        ssh_password_encrypted=encrypted_password,
    )
    db.add(new_asset)
    await db.commit()
    await db.refresh(new_asset)
    return to_response(new_asset)


@router.get("", response_model=list[AssetResponse])
async def list_assets(
    db: AsyncSession = Depends(get_db),
) -> Sequence[Asset]:
    """获取所有主机资产列表"""
    result = await db.scalars(select(Asset).order_by(Asset.id.desc()))
    return [to_response(asset) for asset in result.all()]
