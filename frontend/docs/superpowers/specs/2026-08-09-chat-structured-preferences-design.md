# Chat Structured Preferences Design

## Goal

Add a quick-plan form to the chat input so a traveler can save optional structured preferences and attach them to later user messages.

## Architecture

`useChatPageState` owns `structuredPreferences` for the active chat page. `ChatLayout` passes the value and setter to `ChatInput`, which owns only the modal visibility and Ant Design form instance. When a user sends a non-empty message, the outgoing `ChatMessage` includes `structured_preferences` when values have been saved.

## UI

- Increase the input textarea minimum height from two rows to four rows.
- Place the send icon button on the right side of the input.
- Add a lower-left icon button that opens a centered Ant Design modal with the standard dimmed mask.
- Keep all form fields optional: budget level, pace, interests, traveler count, traveler type, hotel preference, intercity transport, and local transport.
- Retain saved preferences until the traveler updates or clears the form.

## Validation

Run `npm run build`. Manually verify that opening, saving, and reopening the modal preserves choices, and that a sent user message carries the `structured_preferences` payload.
