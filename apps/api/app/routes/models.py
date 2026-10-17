"""Model provider endpoints (FR-21): catalog, connection test, encrypted configs."""

from __future__ import annotations

from ega_api.config import Settings, get_settings
from ega_api.db import get_db
from ega_api.errors import ApiError
from ega_api.models import AuditLog, ModelProviderConfig
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/models", tags=["models"])

SECRET_MASK = "********"


@router.get("/providers")
def list_providers(settings: Settings = Depends(get_settings)) -> dict:
    try:
        from ega_providers.registry import PROVIDER_CATALOG  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise ApiError("PROVIDERS_UNAVAILABLE", f"Provider registry unavailable: {exc}", 503) from exc
    providers_list = [
        {"type": v.get("id", k), **v} if "type" not in v else v
        for k, v in PROVIDER_CATALOG.items()
    ]
    return {
        "providers": providers_list,
        "note": (
            "A complete local mode works with Ollama and no paid API. Cloud providers are optional "
            "bring-your-own-key (BYOK) and may incur provider fees even though this app is free."
        ),
        "deterministic_only_available": True,
    }


@router.post("/test-connection")
async def test_connection(
    payload: dict, settings: Settings = Depends(get_settings), session: Session = Depends(get_db)
) -> dict:
    provider_type = payload.get("provider_type")
    model = payload.get("model") or ""
    if not provider_type:
        raise ApiError("MISSING_PROVIDER", "Provide 'provider_type'", 422)
    try:
        from ega_providers.registry import ProviderConfig, build_provider  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise ApiError("PROVIDERS_UNAVAILABLE", f"Provider registry unavailable: {exc}", 503) from exc

    cfg = ProviderConfig(
        id="adhoc",
        type=provider_type,
        label=provider_type,
        base_url=payload.get("base_url"),
        model=model,
        api_key_env=payload.get("api_key_env") or None,
        timeout_s=int(payload.get("timeout_s") or 30),
        max_tokens=int(payload.get("max_tokens") or 512),
    )
    api_key = payload.get("api_key") or None
    try:
        provider = build_provider(cfg, api_key)
    except Exception as exc:
        session.add(
            AuditLog(
                action="provider.test",
                target=provider_type,
                ok=False,
                detail={"error": type(exc).__name__},
            )
        )
        session.commit()
        return {"ok": False, "latency_ms": None, "detail": str(exc)[:300]}

    try:
        health = await provider.health_check()
        ok = bool(getattr(health, "ok", False))
        detail = getattr(health, "detail", "")
        latency = getattr(health, "latency_ms", None)
        model_id = getattr(health, "model_id", model)
    except Exception as exc:
        ok, detail, latency, model_id = False, f"{type(exc).__name__}: {exc}"[:300], None, model

    session.add(
        AuditLog(
            action="provider.test",
            target=provider_type,
            ok=ok,
            detail={"model": model_id, "ok": ok},
        )
    )
    session.commit()
    caps = provider.capabilities()
    return {
        "ok": ok,
        "latency_ms": latency,
        "detail": detail,
        "model_id": model_id,
        "sends_data_off_device": caps.sends_data_off_device,
        "structured_output": caps.structured_output,
    }


def _config_row(row: ModelProviderConfig) -> dict:
    return {
        "config_id": row.config_id,
        "label": row.label,
        "provider_type": row.provider_type,
        "base_url": row.base_url,
        "model": row.model,
        "api_key_env": row.api_key_env,
        "api_key_set": bool(row.api_key_encrypted),  # never the value itself
        "api_key": SECRET_MASK if row.api_key_encrypted else None,
        "timeout_s": row.timeout_s,
        "max_tokens": row.max_tokens,
        "temperature": row.temperature,
        "is_default": row.is_default,
        "enabled": row.enabled,
    }


@router.get("/configs")
def list_configs(session: Session = Depends(get_db)) -> list[dict]:
    rows = session.query(ModelProviderConfig).order_by(ModelProviderConfig.created_at).all()
    return [_config_row(r) for r in rows]


@router.post("/configs", status_code=201)
def create_config(payload: dict, session: Session = Depends(get_db)) -> dict:
    provider_type = payload.get("provider_type")
    if not provider_type:
        raise ApiError("MISSING_PROVIDER", "Provide 'provider_type'", 422)
    api_key = payload.get("api_key")
    encrypted = None
    if api_key:
        encrypted = _encrypt(api_key)

    if payload.get("is_default"):
        session.query(ModelProviderConfig).update({"is_default": False})

    row = ModelProviderConfig(
        label=payload.get("label") or provider_type,
        provider_type=provider_type,
        base_url=payload.get("base_url"),
        model=payload.get("model") or "",
        api_key_env=payload.get("api_key_env"),
        api_key_encrypted=encrypted,
        timeout_s=int(payload.get("timeout_s") or 60),
        max_tokens=int(payload.get("max_tokens") or 2048),
        temperature=float(payload.get("temperature") or 0.0),
        extra=payload.get("extra") or {},
        is_default=bool(payload.get("is_default")),
        enabled=bool(payload.get("enabled", True)),
    )
    session.add(row)
    session.add(
        AuditLog(
            action="provider.config.create",
            target=provider_type,
            detail={"label": row.label, "key_set": bool(encrypted)},
        )
    )
    session.commit()
    session.refresh(row)
    return _config_row(row)


@router.delete("/configs/{config_id}", status_code=204)
def delete_config(config_id: str, session: Session = Depends(get_db)) -> None:
    row = session.get(ModelProviderConfig, config_id)
    if row is None:
        raise ApiError("CONFIG_NOT_FOUND", f"Provider config {config_id} not found", 404)
    session.delete(row)
    session.add(AuditLog(action="provider.config.delete", target=config_id))
    session.commit()


def _encrypt(plaintext: str) -> str:
    settings = get_settings()
    if not settings.app_encryption_key:
        raise ApiError(
            "ENCRYPTION_KEY_MISSING",
            "APP_ENCRYPTION_KEY is not set; refusing to store a secret in plaintext",
            400,
        )
    try:
        from ega_providers.crypto import derive_key, encrypt_secret  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise ApiError("CRYPTO_UNAVAILABLE", f"Secret encryption unavailable: {exc}", 503) from exc
    return encrypt_secret(plaintext, derive_key(settings.app_encryption_key))
