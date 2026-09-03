# Design system (token sketch)

Research date: **2026-09-01**  
Status: **Tokens defined** — implement in `desktop/capture_desktop/theme.py` + generated QSS.

**Constraint:** Professional lab instrument aesthetic; not consumer dashboard; supports light and dark.

---

## 1. Principles

- **Instrument, not marketing site** — flat panels, clear borders, monospace for metrics.
- **Modality color is semantic** — lane colors encode device family; always pair with icon/shape.
- **Density levels** — `comfortable` (default capture), `compact` (analysis workbench).

---

## 2. Color tokens

### 2.1 Dark theme (current baseline, formalized)

| Token | Hex | Use |
|-------|-----|-----|
| `color.bg` | `#12161c` | App background |
| `color.panel` | `#1a2029` | Cards, rail |
| `color.panel_alt` | `#212934` | Hover, nested |
| `color.panel_deep` | `#0d1116` | Timeline track |
| `color.border` | `#2c3542` | Dividers |
| `color.text` | `#dfe6ef` | Primary text |
| `color.text_dim` | `#8d9aab` | Secondary |
| `color.text_faint` | `#5b6673` | Disabled hints |
| `color.accent` | `#3d8bfd` | Primary action, links |
| `color.success` | `#35c46b` | Ready, OK |
| `color.warning` | `#f0a13a` | Warning, connecting |
| `color.danger` | `#e5484d` | Error, REC stop, critical |

### 2.2 Light theme (new)

| Token | Hex | Use |
|-------|-----|-----|
| `color.bg` | `#f4f6f8` | App background |
| `color.panel` | `#ffffff` | Cards |
| `color.panel_alt` | `#eef1f5` | Nested |
| `color.panel_deep` | `#e2e7ed` | Timeline track |
| `color.border` | `#c8d0da` | Dividers |
| `color.text` | `#1a2332` | Primary |
| `color.text_dim` | `#5a6573` | Secondary |
| `color.accent` | `#2563eb` | Primary action |
| `color.success` | `#16a34a` | OK |
| `color.warning` | `#d97706` | Warning |
| `color.danger` | `#dc2626` | Error |

### 2.3 Modality lanes (shared hue, adjust luminance per theme)

| Modality | Dark | Light | Icon hint |
|----------|------|-------|-----------|
| EMG | `#35c46b` | `#15803d` | waveform |
| Video/camera | `#5b8def` | `#1d4ed8` | camera |
| IMU | `#a06bf0` | `#7c3aed` | cube |
| Radar | `#34c8d4` | `#0891b2` | heatmap grid |
| Force | `#f0a13a` | `#c2410c` | arrow down |

---

## 3. Typography

| Token | Family | Sizes (pt) | Use |
|-------|--------|------------|-----|
| `font.ui` | Segoe UI, system-ui fallback | 9 / 10 / 11 / 13 / 16 | Labels, buttons |
| `font.mono` | Consolas, ui-monospace | 10 / 11 / 12 | Metrics, rates, timestamps |
| `font.title` | Segoe UI Semibold | 13 / 16 | Section headers |

**Line height:** 1.35 ui, 1.2 mono.

---

## 4. Spacing scale (px)

| Token | Value |
|-------|-------|
| `space.xs` | 4 |
| `space.sm` | 8 |
| `space.md` | 12 |
| `space.lg` | 16 |
| `space.xl` | 24 |
| `space.2xl` | 32 |

Panel padding: `space.lg`. Rail width default: 280px (compact: 240px).

---

## 5. Radius and elevation

| Token | Value | Use |
|-------|-------|-----|
| `radius.sm` | 4px | Buttons, inputs |
| `radius.md` | 6px | Cards |
| `radius.none` | 0 | Timeline, full-bleed previews |

No drop shadows on data panels; 1px border only (`color.border`).

---

## 6. Component patterns

| Component | Spec |
|-----------|------|
| **Primary button** | Filled `color.accent`, white text |
| **Danger button** | Filled `color.danger`, protected Stop |
| **Ghost button** | Transparent, border on hover |
| **Card / Panel** | `#Panel` object name, `color.panel` bg |
| **Status pill** | Mono font, semantic background at 20% opacity |
| **REC badge** | Danger color, 2px outer glow optional (dark only) |

---

## 7. Theme switching

```python
# settings.theme: "system" | "light" | "dark"
# Apply on startup + Preferences change
# system → QStyleHints.colorScheme() when Qt 6.5+
```

Migrate hard-coded constants in [theme.py](../../desktop/capture_desktop/theme.py) to `ThemeTokens` dataclass with `dark()` and `light()` factories.

---

## 8. Analysis plot style alignment

Matplotlib report figures ([plots/style.py](../../libs/python/capture_analysis/capture_analysis/plots/style.py)) should read the same accent/success/warning hex for PDF/HTML consistency.

---

## 9. Implementation order

1. `ThemeTokens` + `apply_theme(app, mode)`
2. Wire `settings.theme`
3. Refactor QSS generation from tokens
4. Light theme QA on Capture + Analysis tabs
5. Document in operator manual (screenshots both themes)

---

## 10. References

- [IA_AND_PRODUCT.md](research/IA_AND_PRODUCT.md)
- [SETTINGS_REGISTRY.md](SETTINGS_REGISTRY.md)
- [theme.py](../../desktop/capture_desktop/theme.py)
