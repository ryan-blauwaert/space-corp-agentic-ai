export interface Palette {
  ink: string;
  accent: string;
  surface: string;
  support: string;
}

export const PALETTES = {
  "flight-manual": {
    ink: "#142d43",
    accent: "#b94724",
    surface: "#f4eedc",
    support: "#b49556",
  },
  "lunar-workshop": {
    ink: "#252b30",
    accent: "#9b5700",
    surface: "#f2f1eb",
    support: "#e8b44b",
  },
  "remote-station": {
    ink: "#153d3c",
    accent: "#af4f32",
    surface: "#f0ebdd",
    support: "#86a59a",
  },
  "deep-space-service": {
    ink: "#292e58",
    accent: "#c34435",
    surface: "#f0f1f6",
    support: "#9ba5cb",
  },
  "field-repair": {
    ink: "#343c2c",
    accent: "#a53f2f",
    surface: "#f2ead8",
    support: "#b2a174",
  },
} as const satisfies Record<string, Palette>;

// Change only this name to switch the entire interface and both logo lockups.
export const ACTIVE_PALETTE: keyof typeof PALETTES = "flight-manual";
export const palette: Palette = PALETTES[ACTIVE_PALETTE];

export function channels(hex: string): [number, number, number] {
  return [1, 3, 5].map((offset) =>
    parseInt(hex.slice(offset, offset + 2), 16),
  ) as [number, number, number];
}

function mix(first: string, second: string, amount: number): string {
  const other = channels(second);
  return (
    "#" +
    channels(first)
      .map((value, index) =>
        Math.round(value * (1 - amount) + other[index] * amount)
          .toString(16)
          .padStart(2, "0"),
      )
      .join("")
  );
}

// These meanings stay consistent across brand palettes.
const semanticColors = {
  "on-accent": "#ffffff",
  "status-surface": "#edf1ef",
  "status-text": "#425a54",
  "success-surface": "#ecf3e9",
  "success-text": "#37663d",
  "warning-surface": "#fff2da",
  "warning-text": "#875811",
  "error-surface": "#f9e9e4",
  "error-text": "#9b4939",
  "scope-border": "#bd8b3a",
  "scope-surface": "#fff6e6",
  "scope-text": "#624918",
};

export function paletteTokens(selected: Palette): Record<string, string> {
  const derived = {
    panel: mix(selected.surface, "#ffffff", 0.8),
    "text-muted": mix(selected.ink, selected.surface, 0.2),
    "border-subtle": mix(selected.surface, selected.ink, 0.18),
    "border-control": mix(selected.ink, selected.surface, 0.38),
    "surface-hover": mix(selected.surface, selected.ink, 0.08),
    "accent-hover": mix(selected.accent, "#000000", 0.2),
  };
  // Preserve the already-reviewed Flight Manual presentation exactly.
  const flightManual =
    selected === PALETTES["flight-manual"]
      ? {
          panel: "#fffdf7",
          "text-muted": "#526171",
          "border-subtle": "#d8d0ba",
          "border-control": "#7d7b70",
          "surface-hover": "#eae1cb",
          "accent-hover": "#96391d",
        }
      : {};
  return { ...selected, ...derived, ...flightManual, ...semanticColors };
}

export function applyPalette(selected: Palette): void {
  for (const [name, value] of Object.entries(paletteTokens(selected))) {
    document.documentElement.style.setProperty(`--${name}`, value);
  }
  document
    .querySelector('meta[name="theme-color"]')
    ?.setAttribute("content", selected.surface);
}
