# Profile Dashboard Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add profile statistics, custom preferences, URL-driven profile outlets, and Header navigation for the Travelmate profile experience.

**Architecture:** Keep `ProfileLayout` as the shared profile shell. Nested React Router paths select a route-specific `ProfileOutletPanel`; `ProfileLayout` derives the active sidebar key from the pathname and mirrors it to Zustand. Profile statistics are calculated from `travelHistories`, while custom preferences are owned by the existing profile page state.

**Tech Stack:** React 19, TypeScript, React Router 7, Zustand, Ant Design, Tailwind CSS, Vite.

---

### Task 1: Add Profile Data and Statistics

**Files:**
- Modify: `src/types/profile.ts`
- Modify: `src/assets/profile/profileData.ts`
- Create: `src/utils/profileStats.ts`
- Modify: `src/hooks/useProfilePageData.ts`

- [ ] **Step 1: Extend the profile types**

Add `currentCity: string` to `UserProfile`, `customPreferences: string[]` to `PreferenceSettings`, and a `ProfileTravelStats` type with `tripCount`, `visitedCityCount`, and `totalDays`.

- [ ] **Step 2: Add a failing statistics test or compile-time reproduction**

Use the existing four travel histories as the fixture and verify the intended totals are `4`, `4`, and `12`. The repository has no test runner, so use the project build as the available executable TypeScript verification after implementing the pure utility.

- [ ] **Step 3: Add the pure statistics utility**

Create `getProfileTravelStats(histories)` that counts histories, unique destination names, and inclusive days from `YYYY.M.D - YYYY.M.D` ranges using UTC date arithmetic.

- [ ] **Step 4: Wire profile defaults and state**

Set `currentCity` to `北京`, initialize `customPreferences` to an empty array, and expose memoized `profileStats` from `useProfilePageData`.

- [ ] **Step 5: Verify type integration**

Run: `npm run build`

Expected: TypeScript reports no missing properties for `UserProfile` or `PreferenceSettings`.

### Task 2: Render the Profile Summary and Custom Preferences

**Files:**
- Create: `src/components/profile/ProfileStatsCard.tsx`
- Modify: `src/components/profile/ProfileInfoCard.tsx`
- Modify: `src/components/profile/PreferencesOutlet.tsx`

- [ ] **Step 1: Render the derived summary**

Create a compact internal statistics panel with three fixed-width columns for total trips, visited cities, and accumulated days. Pass the data through `ProfileInfoCard`, placing the avatar and current city on the left and the statistics panel on the right.

- [ ] **Step 2: Add a custom-preferences editor**

Use Ant Design `Input`, `Button`, and closable `Tag` components. Enforce a 30-character input maximum, trim before adding, disable adding when ten entries exist, and remove entries with the Tag close control.

- [ ] **Step 3: Verify the maximum rule**

Manually add ten valid values, confirm the input and add button become disabled, then remove one tag and confirm adding becomes available again.

### Task 3: Make Profile Navigation URL-Driven

**Files:**
- Create: `src/utils/profileRoutes.ts`
- Modify: `src/layouts/ProfileLayout.tsx`
- Modify: `src/components/profile/ProfileOutletPanel.tsx`
- Modify: `src/router/index.tsx`

- [ ] **Step 1: Define the route mapping**

Create a `Record<ProfileOutletKey, string>` mapping `preferences`, `history`, and `settings` to their `/profile/...` routes. Add a helper that resolves a `ProfileOutletKey` from a pathname with `preferences` as the fallback.

- [ ] **Step 2: Synchronize the layout**

Replace the direct outlet-panel render with React Router `Outlet`. Derive the active sidebar item from `useLocation`, mirror that key to `useProfileOutletStore` in an effect, and navigate with the route mapping when a sidebar item is selected.

- [ ] **Step 3: Read profile page data from the route outlet context**

Change `ProfileOutletPanel` to receive the route-selected key and read `ProfilePageData` from `useOutletContext`, then render `PreferencesOutlet`, `TravelHistoryOutlet`, or `SettingsOutlet`.

- [ ] **Step 4: Declare nested routes**

Make `/profile` a parent route that redirects its index route to `preferences`. Render `ProfileOutletPanel` for each of the three nested paths.

- [ ] **Step 5: Verify route behavior**

Open `/profile/preferences`, `/profile/history`, and `/profile/settings`; confirm the matching content and sidebar selection render. Open `/profile`; confirm it redirects to `/profile/preferences`.

### Task 4: Update Header Navigation

**Files:**
- Modify: `src/components/common/AppHeader.tsx`

- [ ] **Step 1: Make the brand navigable**

Wrap the left logo and product name in an accessible button that navigates to `/chat`.

- [ ] **Step 2: Reorder and wire navigation controls**

Place the user avatar and username before History with a separating gap. Navigate the user area and Preferences to `/profile/preferences`, History to `/history`, and Settings to `/profile/settings`.

- [ ] **Step 3: Verify navigation**

From a non-profile page, click the logo, avatar/username, History, Preferences, and Settings controls and confirm every destination URL matches the requested path.

### Task 5: Build Verification

**Files:**
- Verify only

- [ ] **Step 1: Build the production bundle**

Run: `npm run build`

Expected: exit code `0`; Vite may retain the existing chunk-size warning, but TypeScript compilation and bundle generation must succeed.
