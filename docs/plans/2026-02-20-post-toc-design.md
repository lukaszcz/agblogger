# Post Table of Contents Design

## Overview

Add a client-side table of contents (TOC) to the post view page. The TOC is generated from headings already present in the rendered HTML (which have anchor IDs from Pandoc's `_add_heading_anchors()`). No backend changes required.

## Behavior

- **Visibility threshold:** The TOC button only renders when the post has 3 or more headings (H2/H3). Computed client-side after the rendered HTML is in the DOM.
- **Heading depth:** H2 and H3 only. H3 entries are visually indented under their parent H2.
- **Active tracking:** The heading closest to the top of the viewport is highlighted in the TOC using IntersectionObserver.
- **Clicking a TOC item:** Smooth-scrolls to that heading and closes the panel.

## UI

- **Floating button:** In the post header row, right-aligned alongside the existing back button. Uses a list/outline icon. Only appears when 3+ headings exist.
- **Dropdown panel:** Opens below the button on click with:
  - "Table of Contents" heading
  - List of heading links (H3s indented)
  - Active heading highlighted with accent color
  - Slide-down + fade transition on open/close
  - Max height with overflow scroll for long TOCs
- **Dismissal:** Closes on click outside, Escape key, or item click.
- **Mobile:** Same floating button + dropdown behavior. No sidebar.

## Implementation

- **No backend changes.** Heading IDs already exist in rendered HTML.
- **New component:** `TableOfContents.tsx` — floating button + dropdown panel. Receives a ref to the prose container, queries for `h2, h3` elements, builds the TOC list.
- **New hook:** `useActiveHeading.ts` — IntersectionObserver-based hook that returns the ID of the currently visible heading.
- **Integration:** `PostPage.tsx` — add a ref to the prose div, render `<TableOfContents>` in the header area.
- **Heading extraction:** `useEffect` queries `contentRef.current.querySelectorAll('h2, h3')` for IDs and text content.
