# Frontend Design Brief

## Purpose

This document is the source of truth for the Space Corp interface's visual direction.
It lets visual design progress through deliberate review while the project remains
focused on backend and AI capabilities.

The desired result is a credible operational product: calm, precise, capable, and
memorable. It should suggest an aerospace operations environment without defaulting to
generic science-fiction decoration.

## Approval-Based Design Process

Visual exploration is discussion, not implementation authorization.

1. Present a small set of distinct visual directions without changing application code
   or assets.
2. Review and select, combine, or reject directions with the project owner.
3. Record the approved choices below.
4. Implement only the approved scope in a small, reviewable change.
5. Inspect the rendered interface at desktop and narrow viewport sizes before accepting
   the change.

Changing the logo or wordmark, palette, typography, design tokens, layout language, or
motion requires explicit approval. A later screen may extend the approved system, but
does not silently redefine it.

## Current Direction

The existing operations shell is the starting point, not a final brand decision. Its
restrained dark teal, muted mineral surfaces, and operational status colors align with
the intended product personality. Future proposals should improve cohesion and
distinctiveness while preserving the clarity of the operational data.

### Design Objectives

- Make the question-to-evidence journey feel trustworthy and easy to understand.
- Establish a recognizably Space Corp identity without relying on stock space imagery.
- Give operational states and evidence hierarchy immediate visual clarity.
- Keep the interface usable on common desktop and narrow viewport sizes.
- Use visual polish to support comprehension, never to obscure system limits,
  uncertainty, or errors.

### Constraints

- Accessibility is part of the design: sufficient contrast, visible focus, semantic
  controls, and text or icon support for color-coded status are required.
- Prefer a compact SVG or CSS wordmark/mark over a heavyweight branding dependency.
- Prefer reusable tokens and components over isolated one-off values.
- Use motion sparingly, respect reduced-motion preferences, and never make motion
  necessary to understand a result or state change.
- Do not introduce a UI kit, image library, remote font, analytics, or other dependency
  solely for visual styling without discussion and approval.

## Approved Decisions

No final visual identity has been approved yet.

Record approved decisions here before implementation:

| Area | Approved decision | Rationale | Date |
| --- | --- | --- | --- |
| Product personality | Pending |  |  |
| Logo or wordmark | Pending |  |  |
| Palette | Pending |  |  |
| Typography | Pending |  |  |
| Layout and spacing | Pending |  |  |
| Status and feedback | Pending |  |  |
| Motion | Pending |  |  |

## Review Checklist

Before accepting a visual implementation, confirm that it:

- matches an approved decision above
- supports the primary question, review, answer, evidence, loading, empty, and failure
  states
- remains readable and operable using a keyboard
- communicates status without relying only on color
- has been checked at desktop and narrow viewport sizes
- does not alter API behavior, workspace scope, evidence content, or safety disclosures
