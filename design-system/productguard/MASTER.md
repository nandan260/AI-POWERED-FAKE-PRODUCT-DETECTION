# ProductGuard — Master Design System

## 1. Product & Stack Profile
- **Product Type**: AI & Blockchain Fake Product Detection SaaS + Supply-Chain Console
- **Detected Stack**: Node.js + Express + EJS Views + Custom CSS (`/static/style.css`) + Inline SVG Icons
- **Style Direction**: Solid iOS Liquid Glass + Strict Blue Gradient Monochrome Palette

## 2. Color Tokens (Strict Palette)
| Token | Hex | Role |
|---|---|---|
| `--p-obsidian` | `#0E1D21` | Primary ink, dark navbar/sidebar anchor |
| `--p-midnight` | `#122E34` | Primary action fill, sticky accents |
| `--p-teal` | `#2B4A51` | Interactive buttons, active states, focus rings |
| `--p-steel` | `#677E8A` | Muted accents, borders, chart secondary |
| `--p-charcoal` | `#5A636A` | Secondary labels & metadata |
| `--p-silver` | `#ABAFB5` | Dividers, inactive nav text on dark |
| `--p-white` | `#FFFFFF` | Frosted card surfaces, crisp inverted text |

## 3. Typography & Hierarchy
- **Headings**: `Plus Jakarta Sans`, `Segoe UI`, sans-serif (`600`–`700`)
- **Body**: `DM Sans`, `Segoe UI`, sans-serif (`14px`–`15px`, line-height `1.5`–`1.6`, min `12px` labels)
- **Monospace IDs / Hashes**: `JetBrains Mono`, monospace (`tabular-nums`)

## 4. Layout & Viewport Rules
- **Desktop (`> 820px`)**: Single-screen `100dvh` (`overflow: hidden`) with internal table scrolling and collapsible workspace sidebar.
- **Mobile (`<= 820px`)**: Fluid vertical flow, off-canvas slide-out drawer, horizontal touch scrolling for tables, `viewport-fit=cover` safe-area insets.
- **Copy Discipline**: Zero emojis, zero `<footer>`, concise operational labels only.

## 5. Motion & Interaction Rules
- **Timing Curves**: `--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1)`, `--ease-smooth: cubic-bezier(0.22, 1, 0.36, 1)`
- **Asymmetric Timing**: Exit transitions (`180ms`–`220ms`) run faster than entrance springs (`320ms`–`460ms`).
- **Feedback**: Tactile `:active` scale (`0.96`), pointer-origin `.pg-ripple`, accessible `:focus-visible` rings, `prefers-reduced-motion` support.

## 6. Priority 1–10 Compliance Standards
1. **Accessibility**: `4.5:1` contrast, `:focus-visible` rings on all controls, `aria-label` on icon buttons, `role="dialog"` on drawers, `aria-hidden="true"` on decorative SVGs, keyboard-sortable table headers.
2. **Touch & Interaction**: `44px` coarse-pointer targets, `>= 8px` gaps, form double-submit guard + loading overlay.
3. **Performance**: Compositor-only `transform`/`opacity` animations, `loading="lazy"` + `decoding="async"` + explicit image dimensions.
4. **Consistency**: Unified Liquid Glass surface tokens (`--glass-card-bg`, `--glass-blur`, `--glass-card-shadow`).
5. **Forms & Navigation**: Explicit `<label for>` + `id` bindings, `aria-current="page"` on active navigation, `aria-selected` on filter tabs.
