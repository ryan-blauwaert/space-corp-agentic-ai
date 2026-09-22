# Frontend Implementation Guidance

Apply the repository-level guidance in `../AGENTS.md` as well as these instructions.

## Design Authority

`../docs/frontend-design.md` is the source of truth for visual identity decisions.
Design exploration, proposals, screenshots, and discussion do not authorize frontend
code, style, logo, or asset changes. Before making a visual identity change, present the
proposed direction and obtain explicit approval from the project owner.

Use the approved design system consistently. Do not silently redesign the shell or
introduce a competing visual language when adding a screen.

## Implementation Rules

- Prefer reusable CSS custom properties, component patterns, and semantic HTML over
  repeated one-off styling.
- Preserve keyboard navigation, visible focus, reduced-motion support, adequate color
  contrast, and non-color status indicators.
- Treat answers, evidence, system limits, errors, and uncertainty as content that must
  remain accurate and legible; styling must not obscure or rewrite them.
- Do not add a UI kit, icon set, remote font, image library, analytics, or other
  frontend dependency without explaining the need and obtaining approval.
- Use compact local SVG or CSS assets for an approved brand mark unless another approach
  is explicitly approved.
- Keep client types generated from the backend OpenAPI contract; do not hand-edit
  generated files or weaken the contract-drift check for presentation work.

## Verification

For visual changes, run the relevant component tests, build, type check, and formatting
checks. Verify the affected flow at desktop and narrow viewport sizes, including focus,
loading, empty, validation, and safe error states. Report any remaining accessibility or
visual coverage gap.
