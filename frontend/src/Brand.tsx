import { channels, palette } from "./palette";

// Preserve the approved raster and color-separation reference for this local
// preview. A separately reviewed vector export can replace the image later.
export function Brand() {
  const paper = channels(palette.surface);
  const colors = [
    { id: "brand-ink", channels: channels(palette.ink) },
    { id: "brand-accent", channels: channels(palette.accent) },
  ];
  return (
    <span className="brand-lockup" aria-hidden="true">
      <svg className="brand-filters" width="0" height="0" focusable="false">
        <defs>
          {colors.map(({ id, channels }) => (
            <filter id={id} key={id} colorInterpolationFilters="sRGB">
              <feComponentTransfer>
                <feFuncR
                  type="linear"
                  slope={(paper[0] - channels[0]) / 255}
                  intercept={channels[0] / 255}
                />
                <feFuncG
                  type="linear"
                  slope={(paper[1] - channels[1]) / 255}
                  intercept={channels[1] / 255}
                />
                <feFuncB
                  type="linear"
                  slope={(paper[2] - channels[2]) / 255}
                  intercept={channels[2] / 255}
                />
              </feComponentTransfer>
            </filter>
          ))}
        </defs>
      </svg>
      <span className="brand-symbol" />
      <span className="brand-name">SPACE CORP</span>
    </span>
  );
}
