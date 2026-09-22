"""Schemas for channel routing + per-function model bindings."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas_settings import ModelCapabilityReadiness

LogicalModelCapability = Literal["text", "image", "video", "audio"]
ChannelProtocol = Literal["openai", "ark", "volc_tts", "kie", "auto"]
ApiCallFormat = Literal["openai", "ark", "kie"]


class SystemChannelAdvancedConfig(BaseModel):
    """Optional per-channel protocol hints."""

    protocol: ChannelProtocol = "auto"
    text_model: str = ""
    image_model: str = ""
    video_model: str = ""
    create_path: str = ""
    query_path: str = ""


class SystemModelChannel(BaseModel):
    """Physical upstream gateway."""

    id: str
    name: str
    base_url: str = ""
    api_key: str = Field(default="", repr=False)  # không in key ra log/repr
    has_api_key: bool = False
    api_format: ApiCallFormat = "openai"
    protocol: ChannelProtocol = "auto"
    models: list[str] = Field(default_factory=list)
    enabled: bool = True
    sort_order: int = 0
    advanced_config: SystemChannelAdvancedConfig | None = None
    clear_api_key: bool = False


class SystemModelChannelIn(BaseModel):
    """Write payload for one channel (admin)."""

    id: str = Field(max_length=64)  # khớp độ dài cột system_model_channels.id
    name: str
    base_url: str = ""
    api_key: str | None = None
    clear_api_key: bool = False
    api_format: ApiCallFormat = "openai"
    protocol: ChannelProtocol = "auto"
    models: list[str] = Field(default_factory=list)
    enabled: bool = True
    sort_order: int = 0
    advanced_config: SystemChannelAdvancedConfig | None = None


class ResolvedModelRoute(BaseModel):
    """Runtime resolution result."""

    capability: LogicalModelCapability
    logical_model_id: str
    upstream_model: str
    channel_id: str
    channel_name: str
    base_url: str
    api_key: str = Field(repr=False)  # không in key ra log/repr
    protocol: ChannelProtocol
    api_format: ApiCallFormat

    model_config = {"frozen": True}


class ModelBinding(BaseModel):
    """One (channel, model) assignment inside a function binding slot/override, with a pick weight."""

    channel_id: str
    model: str
    weight: int = Field(default=1, ge=1, le=100)


class FunctionBindings(BaseModel):
    """Per-capability default model slots plus optional per-function overrides."""

    slots: dict[str, list[ModelBinding]] = Field(default_factory=dict)
    overrides: dict[str, list[ModelBinding]] = Field(default_factory=dict)


class FunctionInfo(BaseModel):
    """Admin-facing view of one catalog function (id/capability/label/description)."""

    id: str
    capability: LogicalModelCapability
    label: str
    description: str


class ProviderPreset(BaseModel):
    """Known provider template (protocol/base URL/model catalog source) offered when adding a channel."""

    id: str
    name: str
    protocol: ChannelProtocol
    base_url: str
    catalog: Literal["remote", "static", "none"]
    models: list[dict[str, Any]] = Field(default_factory=list)


class AdminRoutingSettingsOut(BaseModel):
    """Full routing configuration for admin UI: providers, function bindings, readiness."""

    providers: list[SystemModelChannel] = Field(default_factory=list)
    function_bindings: FunctionBindings = Field(default_factory=FunctionBindings)
    readiness: list[ModelCapabilityReadiness] = Field(default_factory=list)
    function_catalog: list[FunctionInfo] = Field(default_factory=list)
    presets: list[ProviderPreset] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    updated_at: datetime | None = None


class AdminRoutingSettingsPatch(BaseModel):
    """Replace the provider list and/or function bindings from admin."""

    providers: list[SystemModelChannelIn] | None = None
    function_bindings: FunctionBindings | None = None


class AdminRoutingSettingsSaveOut(BaseModel):
    """Save response envelope: ok flag, refreshed settings, and which layers were applied."""

    ok: bool = True
    settings: AdminRoutingSettingsOut
    applied: list[str] = Field(default_factory=list)
