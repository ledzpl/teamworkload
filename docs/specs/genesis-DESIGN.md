# Genesis

## Overview
An editorial precision interface for the Team Workload Analytics dashboard. The aesthetic is quietly confident — bold display typography, generous spacing, and gallery-frame card surfaces. The mood is professional and modern without being sterile. High information density balanced by breathing room. The dashboard presents engineering workload signals, health indicators, and operational alerts in a calm, data-dense layout.

## Colors
- **Primary** (#5856D6): CTAs, active states, links, focus rings, interactive highlights — indigo
- **Primary Hover** (#4845B0): Darker indigo for hover states on primary elements
- **Secondary** (#20970B): Reserved for brand highlight elements — green
- **Neutral** (#86868B): Muted labels, kickers, timestamps, disabled states
- **Background** (#F5F5F7): Page background, light Apple-style gray
- **Surface** (#FFFFFF): Cards, panels, modals, nav backdrop
- **Text Primary** (#1D1D1F): Headings, body text, primary labels
- **Text Secondary** (#6E6E73): Descriptions, metadata, secondary labels
- **Border** (rgba(0, 0, 0, 0.06)): Card borders, dividers, input borders
- **Section Divider** (rgba(0, 0, 0, 0.04)): Lightweight section separator between dashboard regions
- **Success** (#34C759): Healthy status, positive indicators, deployment success
- **Warning** (#FF9F0A): Caution states, pending banners
- **Error** (#FF3B30): Warning status, destructive actions, validation errors, deployment failure

### Semantic Health Colors
Health indicators and delta badges use context-aware colors:
- **Good text** (#248A3D): Health status "양호", delta-up badges (light mode)
- **Caution text** (#C93400): Health status "주의" (light mode)
- **Warning text** (#D70015): Health status "경고", delta-down badges (light mode)
- **Good text dark** (#30D158): Health/delta positive in dark mode
- **Caution text dark** (#FF9F0A): Health caution in dark mode
- **Warning text dark** (#FF453A): Health/delta negative in dark mode

### Dark Mode
Dark mode activates automatically via `prefers-color-scheme: dark`:
- **Background**: #000000
- **Surface**: #1C1C1E
- **Border**: rgba(255, 255, 255, 0.08)
- **Text Primary**: #F5F5F7
- **Text Secondary**: #A1A1A6
- **Neutral**: #8E8E93
- **Section Divider**: rgba(255, 255, 255, 0.06)
- **Chip Background**: rgba(255, 255, 255, 0.06)

## Typography
- **Display Font**: General Sans — loaded from Fontshare
- **Body Font**: DM Sans — loaded from Google Fonts
- **Code Font**: JetBrains Mono — loaded from Google Fonts

Display and heading text uses General Sans at bold weight with tight letter spacing (-0.03em to -0.04em). Body and UI text uses DM Sans at regular and medium weights. The contrast between the geometric display font and the humanist body font creates a refined editorial feel. Code blocks, SQLite paths, and CLI commands use JetBrains Mono at regular weight.

Type scale: Display clamp(2.8rem, 6vw, 4rem), mobile display clamp(2.2rem, 10vw, 2.8rem), Section heading clamp(1.5rem, 3.5vw, 1.75rem), Card value clamp(1.05rem, 2vw, 1.3rem), Hero panel value 1.4rem, Health status 1.15rem, Body 0.86-0.92rem, Label/kicker 0.60-0.72rem uppercase.

## Elevation
This design uses restrained shadows. Cards rest on a 1px border with `--wa-shadow-sm` and gain `--wa-shadow` or `--wa-shadow-lg` on hover with a -2px vertical lift. Primary buttons gain a tinted glow shadow on hover (`0 4px 16px rgba(88,86,214,0.4)`). The nav uses backdrop-blur plus a small shadow. Focus states use a 4px indigo ring (`0 0 0 4px rgba(88,86,214,0.2)`). Health pills, charts, and data shells lift subtly on hover.

## Components
- **Buttons**: Primary uses indigo fill with white text, 10px radius, semibold weight. Download buttons follow the same pattern. Buttons shift up 1px and scale to 1.01 on hover. Min height: 42px.
- **Summary cards**: White surface, 1px border, 16px radius, 115px min height. Hover lifts 2px. Contains: uppercase kicker label, metric value (General Sans bold), optional delta badge (6px radius with semantic color), and detail line separated by a 1px top border.
- **Health pills**: White surface, 1px border, 14px radius, 3px left border colored by status (success/warning/error/neutral). Contains: status dot, uppercase label, status text (colored by severity), and description. Hover lifts 2px.
- **Alert cards**: 14px radius, 1px border, 4px left border colored by severity. Contains: severity tag (uppercase 5px badge), title (bold), and description. Background uses a very subtle tint of the severity color.
- **Inputs**: 1px border, surface background, 42px min height. Text input has 12px radius, date/select inputs have 10px radius. Focus: border turns indigo with a 4px rgba ring. Labels are uppercase, 0.68rem, letter-spaced.
- **Navigation**: Sticky top nav with backdrop-blur, 52px min height, 14px radius, 1px border. Logo left (rounded mark + title/subtitle), section links center, status chip + avatar right. Links: 0.8rem medium weight, hover shows indigo tint background and primary color text.
- **Hero**: 20px radius light/dark surface with a large ambient radial gradient, animated background position, and a dot-grid accent. Hero metric panels use glass surfaces, 14px radius, and blur.
- **Section headings**: Separated by a 1px divider line. Contains: uppercase kicker, heading (General Sans), and description paragraph.
- **Plotly charts**: 16px radius container with 1px border. Hover lifts 2px. Charts use DM Sans for body text, General Sans for titles. Legend horizontal above chart, 12px font.
- **Data tables**: 14px radius with 1px border. Headers are uppercase, 0.72rem, letter-spaced.
- **Expanders**: 14px radius, 1px border. Used for interpretation guides under each dashboard section.

## Spacing
- Base unit: 4px
- Scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96px
- Component padding: summary card 1.1rem/1.2rem, health pill 1rem/1.1rem, alert card 1rem/1.15rem, hero 2.5rem/2.5rem/2rem
- Section spacing: 3.5rem top margin with 1.5rem padding above the divider line
- Container max width: 1280px with 1.5rem horizontal padding
- Chart grid gap: large (2-column layout for signal charts)
- Trend sparklines: 3 per row maximum

## Border Radius
- 5px: Severity tags
- 6px: Inline code, search shortcut, delta badges
- 8px: Logo mark and nav links
- 10px: Buttons, date inputs, select inputs
- 12px: Text inputs and mobile summary cards
- 14px: Nav bar, hero panels, health pills, alert cards, data tables, expanders
- 16px: Summary cards, chart containers, data shells, mobile hero
- 20px: Desktop hero section
- 9999px: Avatars, status dots, pill badges, delta badges, chips

## Do's and Don'ts
- Do use indigo (#5856D6) for interactive elements, primary accents, and the implemented hero/search accents
- Do maintain the 4px spacing grid for all padding, margins, and gaps
- Do use General Sans for headings and DM Sans for body — never swap them
- Do use semantic colors for health status text — green for good, amber for caution, red for warning
- Do provide sufficient contrast in both light and dark modes — test both
- Do use left-border color coding on health pills and alert cards for quick visual scanning
- Do separate dashboard sections with a subtle divider line
- Don't use pure black (#000000) or pure white (#FFFFFF) for text — use the defined palette values
- Don't add decorative illustrations beyond the implemented ambient radial gradient, avatar gradient, and hero dot-grid accent
- Don't use shadows on static elements — reserve shadow elevation for hover and focus states
- Don't use more than two font weights on a single screen
- Don't apply hover lift to sparkline charts — they should remain static
- Don't place more than 3 sparkline trend cards in a single row
