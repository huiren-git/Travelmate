# Real API Integration Design

## Goal

Remove the frontend's fixed mock data and connect Travelmate to real backend APIs for chat, history sessions, user preferences, and user profile information.

## Scope

- Add a backend user profile endpoint:
  - `GET /api/v1/users/me/profile`
  - Required header: `X-User-Id`
  - Response fields: `avatar_url`, `nickname`, `username`, `email`, `current_city`
- Add API documentation at `api说明书/用户信息.md`.
- Replace frontend imports from mock profile, history, and chat stores with API calls.
- Keep UI empty, loading, and error states so screens do not rely on fake records.
- Keep the existing backend `sessions`, `chat/stream`, and `users/me/preferences` contracts as the source of truth.

## Backend Design

Add profile models under `backend/src/models/users.py`:

- `UserProfileData`
- `UserProfileResponse`

Add a small user service under `backend/src/services/user_service.py`. It will return a deterministic profile from the provided `X-User-Id` during the current development phase. This keeps the public API real while leaving storage replaceable later.

Add a router under `backend/src/api/v1/users.py`:

- `GET /users/me/profile`
- Validates the required user header through FastAPI.
- Returns `ApiResponse[UserProfileData]`.

Register the router in `backend/src/main.py` with prefix `/api/v1`.

## Frontend Design

Create a focused frontend API layer:

- `frontend/src/api/client.ts`
  - Builds base URL from `VITE_API_BASE_URL`, defaulting to `/api/v1`.
  - Sends `X-User-Id` from `VITE_TRAVELMATE_USER_ID`, defaulting to `demo-user`.
  - Normalizes non-2xx and business error responses into thrown errors.
- `frontend/src/api/users.ts`
  - Fetches profile.
- `frontend/src/api/preferences.ts`
  - Fetches, adds, updates, and deletes preference tags.
- `frontend/src/api/sessions.ts`
  - Fetches session list.
  - Fetches a session snapshot for detail panels.
  - Deletes a session.
- `frontend/src/api/chat.ts`
  - Posts to `chat/stream`.
  - Parses SSE events: `node`, `done`, `error`, `stopped`.

Update hooks:

- `useProfilePageData`
  - Loads profile and preferences from backend.
  - Computes profile travel stats from real sessions.
  - Persists preference edits through preference APIs.
- `useHistoryPageData`
  - Loads sessions from backend.
  - Loads selected snapshot when available.
  - Maps unavailable detail fields to empty arrays instead of mock details.
- `useChatPageState`
  - Loads conversations from sessions.
  - Sends user messages to `chat/stream`.
  - Appends streamed assistant output or final state summary from backend events.
  - Updates right-side trip summary from returned state when available.
- `AppHeader`
  - Reads profile through a shared profile hook or passed app-level data, no mock import.

## Data Mapping

Sessions list maps backend `SessionItem` to frontend conversation and history summaries:

- `thread_id` -> `id`
- `destination` -> destination/title fallback
- `start_date` + `duration` -> date range
- `status` -> display status
- `last_updated` -> updated time

Session snapshot maps `state.blackboard` fields when present:

- `daily_itinerary` or `draft_daily_itinerary` -> itinerary items
- `budget` or `draft_budget` -> expense summary
- Missing details become empty arrays or zero totals.

Preferences map backend tags into frontend editable preference groups:

- `interest` -> travel types and custom interests
- `diet` -> dietary preferences
- `budget` -> budget preference
- `transport` -> transport preference
- `pace` and `accommodation` remain visible as custom preference tags when they do not match existing controls.

Profile maps directly from `UserProfileData` to `UserProfile`.

## API Documentation

Create `api说明书/用户信息.md` with:

- Endpoint overview.
- `GET /api/v1/users/me/profile`
- Request header table.
- 200 response example.
- 401/403 response examples.
- `UserProfileData`, `GetUserProfileResponse`, and `ErrorResponse` schema notes.

## Error Handling

- API calls expose user-friendly messages from backend `message` when present.
- Profile/header falls back to a compact neutral label only when request fails, without using mock identities.
- History and chat show empty states when there are no sessions.
- Chat stream errors append an assistant error message and stop loading.
- Preference mutation errors leave current UI state unchanged and show the backend error.

## Testing

Backend:

- Add tests for `GET /api/v1/users/me/profile` success.
- Add tests for missing `X-User-Id`.

Frontend:

- Add API client tests for success and error normalization.
- Add mapper tests for sessions, snapshots, profile, and preferences.
- Add chat SSE parser tests.

Verification commands:

- Backend: `python -m pytest`
- Frontend: `npm run build`
- Frontend lint, if existing source syntax allows it: `npm run lint`
