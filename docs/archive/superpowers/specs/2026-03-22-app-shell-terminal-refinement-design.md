# App Shell Terminal Refinement Design

## Context

The current frontend already follows a dark terminal-oriented direction, but the shell still reads as a refined dashboard surface rather than a stronger market workstation.

The latest external Stitch draft is not directly reusable as production code because it is a static multi-page HTML prototype with mismatched information architecture and fake terminal data. However, it demonstrates a stronger visual language in four areas:

1. harder shell separation
2. clearer navigation activation
3. denser system-status presentation
4. stronger micro-label and tabular-number hierarchy

The user wants to keep the current product structure and data semantics, while moving the shell toward that stronger "terminal control column + operational workspace" feel.

## Goals

- Preserve the current route structure and app bootstrap behavior.
- Refine the shell into a stronger terminal-style control column.
- Introduce a compact global status rail in the main workspace.
- Make the active route and system state more decisive without adding fake trading-terminal concepts.
- Establish a visual midpoint between the current cold-blue shell and the Stitch prototype's harder black-orange style.

## Non-Goals

- No backend, store, route, or API-contract changes.
- No route renaming or navigation restructuring.
- No fake telemetry such as memory, latency, or rebalance actions.
- No full redesign of Dashboard, News Feed, or Watchlist content areas in this iteration.

## Chosen Direction

The shell will move to a "cold-blue base with orange focus" system:

- keep the current deep blue/charcoal background and existing tokens as the base
- use orange only for focal emphasis such as active navigation signal, current module, and selected shell accents
- keep blue for system/connectivity semantics
- retain green/red for positive and risk states only

This preserves product continuity while adding more terminal decisiveness.

## Visual System Changes

### 1. Sidebar Hardening

The left sidebar keeps the current structure:

1. brand area
2. desk note
3. primary navigation
4. bottom system-status module

The treatment changes:

- slightly firmer edges and tighter spacing
- stronger visual segmentation between brand, nav, and status areas
- active navigation uses a clearer orange signal bar and higher contrast text
- inactive items remain quiet but more intentionally aligned as numbered modules

### 2. Global Status Rail

A new compact status rail will be added above the routed page content.

Its purpose is to consolidate shell-level operational context that currently feels scattered:

- SSE state
- connection quality/detail
- last event time
- workspace context

It should be low-height, scan-first, and operational, not banner-like.

### 3. Micro-Typography

The shell will standardize a denser micro-typography layer:

- uppercase labels for system metadata and module markers
- monospace/tabular styling for route indices and timestamps
- stronger distinction between page title text and shell metadata

This should improve scanability without adding decorative complexity.

### 4. Status Module Refinement

The bottom sidebar status card remains functionally the same, but its presentation becomes more compact and technical:

- less explanatory copy
- tighter rows
- clearer hierarchy between status label, heartbeat metadata, and workspace label

## Component Boundaries

### AppShell

`frontend/src/components/layout/AppShell.vue` remains the shell owner. This iteration may modify:

- shell template structure where needed for the status rail
- nav item rendering and active-state markup
- shell-level copy in brand/status labels
- Tailwind class composition

It must not change:

- route destinations
- bootstrap sequence
- SSE event handling
- store calls or teardown behavior

### AppShell Tests

`frontend/src/components/layout/AppShell.test.ts` will be updated to lock:

- the new status rail
- active navigation signal markers
- the refined shell wording that replaces any removed copy

## Acceptance Criteria

The shell redesign is complete when:

- the sidebar reads as a stronger control column without changing navigation behavior
- there is one clear active-route signal using orange focus styling
- the main workspace gains a compact shell-level status rail
- system metadata is denser and easier to scan than before
- all existing shell tests pass after being updated for the new structure
- the frontend build still passes

## Risks

- If orange emphasis spreads too widely, the shell may drift toward a generic high-contrast trading-terminal look.
- If the status rail becomes too verbose, it will recreate the banner problem the project has already been reducing.
- If the shell hardening is too aggressive, it may visually overpower page-level content on Dashboard.

## Verification Strategy

Minimum verification for this iteration:

- targeted test run for `AppShell`
- frontend production build
- quick manual visual check in desktop layout to confirm shell hierarchy and routed-page spacing still work
