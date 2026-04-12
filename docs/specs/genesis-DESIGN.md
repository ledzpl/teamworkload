# Genesis

## Overview
An editorial precision interface for the Team Workload Analytics dashboard. The aesthetic is quietly confident — bold display typography, generous spacing, and gallery-frame card surfaces. The mood is professional and modern without being sterile. High information density balanced by breathing room. The dashboard presents engineering workload signals, health indicators, and operational alerts in a calm, data-dense layout.

## Colors
- **Primary** (#6366F1): CTAs, active states, links, focus rings, interactive highlights — indigo
- **Primary Hover** (#4F46E5): Darker indigo for hover states on primary elements
- **Secondary** (#20970B): Reserved for brand highlight elements — green
- **Neutral** (#78787F): Muted labels, kickers, timestamps, disabled states
- **Background** (#F8F8FA): Page background, light warm gray
- **Surface** (#FFFFFF): Cards, panels, modals, nav backdrop
- **Text Primary** (#0A0A0A): Headings, body text, primary labels — near-black
- **Text Secondary** (#555560): Descriptions, metadata, secondary labels
- **Border** (#E2E2E8): Card borders, dividers, input borders — subtle and recessive
- **Section Divider** (#EDEDF0): Lightweight section separator between dashboard regions
- **Success** (#10B981): Healthy status, positive indicators, deployment success
- **Warning** (#F59E0B): Caution states, pending banners
- **Error** (#EF4444): Warning status, destructive actions, validation errors, deployment failure

### Semantic Health Colors
Health indicators and delta badges use context-aware colors:
- **Good text** (#047857): Health status "양호", delta-up badges (light mode)
- **Caution text** (#B45309): Health status "주의" (light mode)
- **Warning text** (#B91C1C): Health status "경고", delta-down badges (light mode)
- **Good text dark** (#34D399): Health/delta positive in dark mode
- **Caution text dark** (#FBBF24): Health caution in dark mode
- **Warning text dark** (#FCA5A5): Health/delta negative in dark mode

### Dark Mode
Dark mode activates automatically via `prefers-color-scheme: dark`:
- **Background**: #111113
- **Surface**: #17181C
- **Border**: #2A2B31
- **Text Primary**: #F3F3F4
- **Text Secondary**: #A0A0A8
- **Neutral**: #8B8B92
- **Section Divider**: #222228
- **Chip Background**: #27282E

## Typography
- **Display Font**: General Sans — loaded from Fontshare
- **Body Font**: DM Sans — loaded from Google Fonts
- **Code Font**: JetBrains Mono — loaded from Google Fonts

Display and heading text uses General Sans at bold weight with tight letter spacing (-0.03em to -0.04em). Body and UI text uses DM Sans at regular and medium weights. The contrast between the geometric display font and the humanist body font creates a refined editorial feel. Code blocks, SQLite paths, and CLI commands use JetBrains Mono at regular weight.

Type scale: Display clamp(3.2rem, 7vw, 4.5rem), Section heading clamp(1.55rem, 3.5vw, 1.8rem), Card value clamp(1.1rem, 2.2vw, 1.4rem), Health status 1.15rem, Body 0.88rem, Label/kicker 0.68-0.72rem uppercase.

## Elevation
This design uses minimal shadows. Cards rest flat with a 1px border and gain a subtle shadow on hover (0 8px 30px rgba(0,0,0,0.08)) combined with a -2px vertical lift. Primary buttons gain a tinted glow shadow on hover (0 4px 12px rgba(99,102,241,0.35)). The nav uses backdrop-blur rather than a shadow to convey elevation. Focus states use a 3px indigo ring (0 0 0 3px rgba(99,102,241,0.15)) rather than a shadow. Health pills lift 1px on hover. Sparkline charts do not lift on hover.

## Components
- **Buttons**: Primary uses indigo fill with white text, 6px radius, medium weight. Download buttons follow the same pattern. All buttons shift up 1px on hover. Min height: 44px.
- **Summary cards**: White surface, 1px border, 10px radius, 120px min height. Hover lifts 2px. Contains: uppercase kicker label, metric value (General Sans bold), optional delta badge (pill shape with semantic color), and detail line separated by a 1px top border.
- **Health pills**: White surface, 1px border, 10px radius, 3px left border colored by status (success/warning/error/neutral). Contains: status dot, uppercase label, status text (colored by severity), and description. Hover lifts 1px.
- **Alert cards**: 10px radius, 1px border, 4px left border colored by severity. Contains: severity tag (uppercase pill badge), title (bold), and description. Background uses a very subtle tint of the severity color.
- **Inputs**: 1px border, surface background, 44px min height. Text input has 12px radius, date/select inputs have 6px radius. Focus: border turns indigo with a 3px rgba ring. Labels are uppercase, 0.72rem, letter-spaced.
- **Navigation**: Sticky top nav with backdrop-blur, 56px min height, 12px radius, 1px border. Logo left (circle mark + title/subtitle), section links center, status chip + avatar right. Links: 0.82rem semibold, hover shows indigo tint background and primary color text.
- **Section headings**: Separated by a 1px divider line. Contains: uppercase kicker, heading (General Sans), and description paragraph.
- **Plotly charts**: 10px radius container with 1px border. Hover lifts 2px. Charts use DM Sans for body text, General Sans for titles. Legend horizontal above chart, 12px font.
- **Data tables**: 10px radius with 1px border. Headers are uppercase, 0.78rem, letter-spaced.
- **Expanders**: 10px radius, 1px border. Used for interpretation guides under each dashboard section.

## Spacing
- Base unit: 4px
- Scale: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96px
- Component padding: summary card 1.15rem/1.3rem, health pill 1rem/1.15rem, alert card 1.05rem/1.2rem
- Section spacing: 3rem top margin with 1.5rem padding above the divider line
- Container max width: 1280px with 1.5rem horizontal padding
- Chart grid gap: large (2-column layout for signal charts)
- Trend sparklines: 3 per row maximum

## Border Radius
- 4px: Severity tags, inline code
- 6px: Buttons, date inputs, select inputs, nav links
- 10px: Summary cards, health pills, alert cards, chart containers, data tables, expanders
- 12px: Text inputs, nav bar, hero section
- 9999px: Avatars, status dots, pill badges, delta badges, chips

## Do's and Don'ts
- Do use indigo (#6366F1) only for interactive elements and primary accents — never for decoration or static text
- Do maintain the 4px spacing grid for all padding, margins, and gaps
- Do use General Sans for headings and DM Sans for body — never swap them
- Do use semantic colors for health status text — green for good, amber for caution, red for warning
- Do provide sufficient contrast in both light and dark modes — test both
- Do use left-border color coding on health pills and alert cards for quick visual scanning
- Do separate dashboard sections with a subtle divider line
- Don't use pure black (#000000) or pure white (#FFFFFF) for text — use the defined palette values
- Don't add decorative gradients or illustrations — the interactive dot grid in the hero section is the only decorative element
- Don't use shadows on static elements — reserve shadow elevation for hover and focus states
- Don't use more than two font weights on a single screen
- Don't apply hover lift to sparkline charts — they should remain static
- Don't place more than 3 sparkline trend cards in a single row
