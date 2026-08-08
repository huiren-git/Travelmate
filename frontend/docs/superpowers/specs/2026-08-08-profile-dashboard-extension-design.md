# Profile Dashboard Extension Design

## Goal

Extend the Travelmate profile dashboard with profile statistics, a current-city field, up to ten custom preference entries, and URL-driven profile navigation while preserving the existing visual language.

## Architecture

The profile page keeps `ProfileLayout` as the shared shell and uses nested React Router routes for `/profile/preferences`, `/profile/history`, and `/profile/settings`. The profile outlet store remains as a navigation-state mirror so existing component boundaries stay intact, while the URL is the source of truth for direct navigation and refreshes.

`UserProfile` gains `currentCity`. `PreferenceSettings` gains `customPreferences`, with the UI enforcing a maximum of ten entries and thirty characters per entry. Profile statistics are derived from the existing travel history dataset: trip count, unique destinations, and total inclusive travel days.

## UI Changes

- `ProfileInfoCard` becomes a single internal two-column card:
  - left: avatar, nickname, username, current city;
  - right: trip count, visited-city count, accumulated days.
- `PreferencesOutlet` adds a custom-preferences section with a 30-character input, add action, count indicator, and removable entries.
- `AppHeader` places avatar and username immediately to the left of History, with spacing; logo and Travelmate navigate to `/chat`.

## Routing

- `/profile` redirects to `/profile/preferences`.
- `/profile/preferences`, `/profile/history`, and `/profile/settings` render the matching outlet inside `ProfileLayout`.
- Header Preferences and Settings navigate to the nested profile routes.
- Header History navigates to `/history`.
- Avatar and username navigate to `/profile/preferences`.

## Validation

Run `npm run build` after implementation. Verify that route changes update the active sidebar item and that the profile page remains usable with ten custom preferences.
