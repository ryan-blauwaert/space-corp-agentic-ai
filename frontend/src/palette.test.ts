import { afterEach, describe, expect, it } from "vitest";
import { applyPalette, channels, PALETTES, paletteTokens } from "./palette";

function contrast(a: string, b: string): number {
  const luminance = (hex: string) =>
    channels(hex)
      .map((value) => {
        const c = value / 255;
        return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
      })
      .reduce(
        (sum, value, index) => sum + value * [0.2126, 0.7152, 0.0722][index],
        0,
      );
  const values = [luminance(a), luminance(b)].sort((x, y) => x - y);
  return (values[1] + 0.05) / (values[0] + 0.05);
}

afterEach(() => {
  document.documentElement.removeAttribute("style");
  document.head.querySelector('meta[name="theme-color"]')?.remove();
});

describe("palette accessibility", () => {
  for (const [name, selected] of Object.entries(PALETTES)) {
    it(`${name} keeps text, controls, and focus distinguishable`, () => {
      const t = paletteTokens(selected);
      for (const background of [t.surface, t.panel, t["surface-hover"]]) {
        expect(contrast(t.ink, background)).toBeGreaterThanOrEqual(4.5);
        expect(contrast(t["text-muted"], background)).toBeGreaterThanOrEqual(
          4.5,
        );
        expect(contrast(t.accent, background)).toBeGreaterThanOrEqual(3);
        expect(
          contrast(t["border-control"], background),
        ).toBeGreaterThanOrEqual(3);
      }
      for (const background of [t.accent, t["accent-hover"]]) {
        expect(contrast(t["on-accent"], background)).toBeGreaterThanOrEqual(
          4.5,
        );
      }
      for (const status of ["status", "success", "warning", "error", "scope"]) {
        expect(
          contrast(t[`${status}-text`], t[`${status}-surface`]),
        ).toBeGreaterThanOrEqual(4.5);
      }
    });
  }
  it("replaces every palette token and browser theme together", () => {
    const meta = document.createElement("meta");
    meta.name = "theme-color";
    document.head.append(meta);
    for (const selected of Object.values(PALETTES)) {
      applyPalette(selected);
      for (const [name, value] of Object.entries(paletteTokens(selected))) {
        expect(
          document.documentElement.style.getPropertyValue(`--${name}`),
        ).toBe(value);
      }
      expect(meta.content).toBe(selected.surface);
    }
    expect(() => {
      meta.remove();
      applyPalette(PALETTES["flight-manual"]);
    }).not.toThrow();
  });
});
