# Approved Logo Lockups

Approved 2026-09-22. These references are the handoff for another agent to
implement. This branch documents designs and assets only.

## Reference Assets

- [Standalone O2 logo](design/space-corp-logo.png): unchanged approved artwork.
- [Horizontal lockup](design/horizontal-lockup.html): selected C, 20% smaller
  wordmark, 5% upward alignment, no added horizontal gap.
- [Stacked lockup](design/stacked-lockup.html): selected tighter arrangement with
  the added vertical gap removed.
- [Utility robot](design/utility-robot.png): retained for a possible future guide;
  not part of the company lockup.

Both lockups use uppercase SPACE CORP in Orbitron 900, with -0.045em letter
spacing and -0.08em word spacing. Preserve the SC letter shapes and orbit exactly.
Space Grotesk remains the interface typeface; see the [typography notes](typography-options.md)
for font roles and licensing.

## Horizontal Proportions

The approved desktop specimen uses a 112px-wide cropped logo frame, approximately
54.07px high, and 32px wordmark type. There is no added horizontal gap: the source
image's small right margin provides separation from the orbit. Raise the wordmark
by 5% of the logo frame height from the bottom-aligned reference, retaining the
0.12em downward optical correction for the font line box. This corresponds to the
approved C specimen; use its appearance as the reference when producing vectors.

The preview uses a 76px logo frame on narrow screens and responsive type sizing.
These specimen breakpoints are not an approved application layout or minimum-size
policy. Preserve the selected balance when integrating it into the interface.

## Stacked Proportions

The approved desktop specimen uses a 170px-wide cropped logo frame and 28px
wordmark type, centered below it with zero added vertical gap. Image margins and
font metrics still provide optical separation. The narrow preview uses 26px type.
No changes to the logo or wordmark shapes were made to tighten the arrangement.

## Production Handoff

The original PNG is the source of truth. The HTML references embed a pixel-identical
lossless WebP encoding, with surrounding margins hidden by CSS. They load fonts
from Google Fonts for review; font hosting for production remains undecided.
White backgrounds represent monochrome studies, not an approved interface palette.

Production vector artwork, measured clear space, minimum sizes, favicon treatment,
and color variants remain pending. The font-line-box offset is a specimen technique,
not a requirement to reproduce that CSS in final artwork. Match the approved visual
alignment against actual glyph and logo bounds when exporting. Do not silently
simplify the mark for small sizes. Earlier proposal files have been removed from
the repository to avoid conflicting implementation references.
