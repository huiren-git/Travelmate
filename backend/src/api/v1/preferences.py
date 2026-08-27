"""用户画像偏好接口。"""

from typing import Annotated

from fastapi import APIRouter, Header, Query, status

from src.models.common import ApiResponse
from src.models.preferences import (
    AddPreferenceRequest,
    PreferenceCategory,
    PreferenceDeletionData,
    PreferenceItem,
    PreferenceListData,
    ReplacePreferencesRequest,
    UpdatePreferenceRequest,
)
from src.services.preference_service import preference_service

router = APIRouter(prefix="/users/me/preferences")


@router.get("", response_model=ApiResponse[PreferenceListData])
async def get_preferences(
    category: Annotated[PreferenceCategory | None, Query()] = None,
    include_inferred: Annotated[bool, Query()] = True,
    user_id: Annotated[str, Header(alias="X-User-Id")] = ...,
):
    preferences, summary = await preference_service.get_preferences(
        user_id,
        category,
        include_inferred,
    )
    return ApiResponse(
        code=200,
        message="获取成功",
        data=PreferenceListData(preferences=preferences, summary=summary),
    )


@router.put("", response_model=ApiResponse[PreferenceListData])
async def replace_preferences(
    request: ReplacePreferencesRequest,
    user_id: Annotated[str, Header(alias="X-User-Id")] = ...,
):
    """整体替换当前用户的手动偏好（推断偏好保留不动）。"""
    await preference_service.replace_all_manual(
        user_id,
        [(it.category, it.content) for it in request.items],
    )
    preferences, summary = await preference_service.get_preferences(user_id, None, True)
    return ApiResponse(
        code=200,
        message="偏好已更新",
        data=PreferenceListData(preferences=preferences, summary=summary),
    )


@router.post(
    "",
    response_model=ApiResponse[PreferenceItem],
    status_code=status.HTTP_201_CREATED,
)
async def add_preference(
    request: AddPreferenceRequest,
    user_id: Annotated[str, Header(alias="X-User-Id")] = ...,
):
    item = await preference_service.add(user_id, request.category, request.content)
    return ApiResponse(code=201, message="偏好已添加", data=item)


@router.put("/{preference_id}", response_model=ApiResponse[PreferenceItem])
async def update_preference(
    preference_id: str,
    request: UpdatePreferenceRequest,
    user_id: Annotated[str, Header(alias="X-User-Id")] = ...,
):
    item = await preference_service.update(user_id, preference_id, request.content)
    return ApiResponse(code=200, message="偏好已更新", data=item)


@router.delete(
    "/{preference_id}",
    response_model=ApiResponse[PreferenceDeletionData],
)
async def delete_preference(
    preference_id: str,
    user_id: Annotated[str, Header(alias="X-User-Id")] = ...,
):
    item = await preference_service.delete(user_id, preference_id)
    return ApiResponse(
        code=200,
        message="偏好已删除",
        data=PreferenceDeletionData(
            id=item.id,
            is_active=item.is_active,
            deleted_at=item.deleted_at,
        ),
    )
