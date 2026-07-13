from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.repositories.feishu_notify_config_repository import FeishuNotifyConfigRepository
from app.schemas.feishu_notify import (
    AlertGovernanceView,
    FeishuConfigUpsertRequest,
    FeishuConfigView,
    FeishuTestResult,
)
from app.services.feishu_client import FeishuClientError, get_shared_feishu_sender
from app.services.notification_service import get_notification_service

router = APIRouter()


def _governance_view() -> AlertGovernanceView:
    return AlertGovernanceView(**get_notification_service().governance_view())


@router.get("/feishu/config", response_model=FeishuConfigView)
def get_feishu_config(session: Session = Depends(get_db_session)) -> FeishuConfigView:
    repo = FeishuNotifyConfigRepository(session)
    config = repo.get_first()
    if config is None:
        return FeishuConfigView(configured=False, governance=_governance_view())

    return FeishuConfigView(
        configured=True,
        app_id=config.app_id,
        app_secret_set=bool(config.app_secret),
        target_type=config.target_type,
        target_id=config.target_id,
        news_enabled=config.news_enabled,
        news_keywords=config.news_keywords,
        news_batch_interval_minutes=config.news_batch_interval_minutes,
        alert_enabled=config.alert_enabled,
        analysis_enabled=config.analysis_enabled,
        is_active=config.is_active,
        updated_at=config.updated_at,
        governance=_governance_view(),
    )


@router.post("/feishu/config", response_model=FeishuConfigView)
def upsert_feishu_config(
    payload: FeishuConfigUpsertRequest,
    session: Session = Depends(get_db_session),
) -> FeishuConfigView:
    repo = FeishuNotifyConfigRepository(session)
    try:
        config = repo.upsert(
            app_id=payload.app_id.strip(),
            app_secret=payload.app_secret.strip() if payload.app_secret else None,
            target_type=payload.target_type.strip(),
            target_id=payload.target_id.strip(),
            news_enabled=payload.news_enabled,
            news_keywords=payload.news_keywords.strip() if payload.news_keywords else None,
            news_batch_interval_minutes=payload.news_batch_interval_minutes,
            alert_enabled=payload.alert_enabled,
            analysis_enabled=payload.analysis_enabled,
            is_active=payload.is_active,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # 告警治理覆盖只存内存（不落库），仅在请求携带 governance 时更新。
    if payload.governance is not None:
        get_notification_service().apply_governance(
            payload.governance.model_dump(exclude_unset=True)
        )

    return FeishuConfigView(
        configured=True,
        app_id=config.app_id,
        app_secret_set=bool(config.app_secret),
        target_type=config.target_type,
        target_id=config.target_id,
        news_enabled=config.news_enabled,
        news_keywords=config.news_keywords,
        news_batch_interval_minutes=config.news_batch_interval_minutes,
        alert_enabled=config.alert_enabled,
        analysis_enabled=config.analysis_enabled,
        is_active=config.is_active,
        updated_at=config.updated_at,
        governance=_governance_view(),
    )


@router.post("/feishu/test", response_model=FeishuTestResult)
def test_feishu_notification(session: Session = Depends(get_db_session)) -> FeishuTestResult:
    repo = FeishuNotifyConfigRepository(session)
    config = repo.get_active()
    if config is None:
        raise HTTPException(status_code=400, detail="feishu notification is not configured")

    try:
        client = get_shared_feishu_sender(app_id=config.app_id, app_secret=config.decrypted_app_secret)
        client.send_test(target_type=config.target_type, target_id=config.target_id)
        return FeishuTestResult(success=True, message="测试消息发送成功")
    except FeishuClientError as exc:
        return FeishuTestResult(success=False, message=str(exc))
    except Exception as exc:
        return FeishuTestResult(success=False, message=f"发送失败: {exc}")
