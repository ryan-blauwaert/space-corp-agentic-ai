# Typography Decision

Status: **Space Grotesk for the interface; Orbitron 900 for the wordmark**, 2026-09-22.
The selected system pairs a heavy uppercase brand wordmark with readable technical
interface text. Both horizontal and stacked lockups are approved.
Frontend implementation is outside this branch's scope.

## Selected Direction

- Company name: Orbitron 900, uppercase, selected with horizontal lockup C.
- Interface: Space Grotesk 400 for body text, 500 for emphasis, and 600 for headings.
- Preserve the approved O2 logo exactly. Font selection does not replace the SC
  lettering within the logo.
- Use the approved uppercase arrangements in the [lockup handoff](lockup-options.md).
  Minimum sizes, clear-space rules, and production vector exports remain pending.
- IBM Plex Mono 400 appeared in the original study for short identifiers. Its final
  use and distribution requirements should be resolved in the implementation
  handoff; Space Grotesk is the selected primary family.
- Palette remains pending. Neutral specimen colors are not palette approval.

## Space Grotesk License and Handoff

Checked against the [upstream license](https://raw.githubusercontent.com/floriankarsten/space-grotesk/master/OFL.txt)
on 2026-09-22. Space Grotesk is licensed under the SIL Open Font License 1.1.
It allows free use, embedding, and redistribution, including commercial websites
and software. The website and artwork made with the font do not inherit the OFL.

When bundling or self-hosting font files, include the accompanying copyright notice
and full OFL license with the distributed font package. Keep the font under the OFL;
do not treat it as covered solely by the application's license or sell it on its own.
No visible website credit is required by this license. Use unmodified upstream
releases and retain their notices; recheck the actual package before distribution.

The implementing agent should determine font delivery and fallback choices and
verify small-text readability. No font files, dependencies, or frontend styles have
been installed by this design decision.

## Orbitron License

The [Orbitron license](https://raw.githubusercontent.com/google/fonts/main/ofl/orbitron/OFL.txt),
checked on 2026-09-22, is also SIL OFL 1.1. Include its copyright notice and
license when distributing font files. Orbitron is a Reserved Font Name: modified
font software must follow the license's naming restrictions. This does not prevent
using the unmodified font in the approved company wordmark.

## References

- [Space Grotesk designer specimen](https://floriankarsten.github.io/space-grotesk/)
- [Space Grotesk source and releases](https://github.com/floriankarsten/space-grotesk)
- [SIL Open Font License shipped with Space Grotesk](https://raw.githubusercontent.com/floriankarsten/space-grotesk/master/OFL.txt)
