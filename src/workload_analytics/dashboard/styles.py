from __future__ import annotations


DASHBOARD_STYLES = """
<style>
@import url("https://api.fontshare.com/v2/css?f[]=general-sans@500,600,700&display=swap");
@import url("https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=JetBrains+Mono:wght@400;500&display=swap");

/* ─── Keyframe animations ─── */
@keyframes wa-fade-up {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
@keyframes wa-scale-in {
  from { opacity: 0; transform: scale(0.97); }
  to { opacity: 1; transform: scale(1); }
}
@keyframes wa-hero-gradient {
  0%, 100% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
}
@keyframes wa-pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

/* ─── Design tokens ─── */
:root {
  --wa-primary: #5856D6;
  --wa-primary-hover: #4845B0;
  --wa-primary-subtle: rgba(88, 86, 214, 0.08);
  --wa-secondary: #20970b;
  --wa-neutral: #86868b;
  --wa-background: #f5f5f7;
  --wa-panel: #ffffff;
  --wa-panel-strong: #ffffff;
  --wa-panel-glass: rgba(255, 255, 255, 0.72);
  --wa-border: rgba(0, 0, 0, 0.06);
  --wa-border-strong: rgba(0, 0, 0, 0.1);
  --wa-ink: #1d1d1f;
  --wa-ink-soft: #6e6e73;
  --wa-success: #34c759;
  --wa-warning: #ff9f0a;
  --wa-error: #ff3b30;
  --wa-ring: 0 0 0 4px rgba(88, 86, 214, 0.2);
  --wa-shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.04), 0 1px 2px rgba(0, 0, 0, 0.06);
  --wa-shadow: 0 4px 24px rgba(0, 0, 0, 0.06), 0 1px 4px rgba(0, 0, 0, 0.04);
  --wa-shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04);
  --wa-shadow-glow: 0 0 0 1px rgba(88, 86, 214, 0.08), 0 4px 24px rgba(88, 86, 214, 0.1);
  --wa-button-shadow: 0 2px 8px rgba(88, 86, 214, 0.3);
  --wa-section-divider: rgba(0, 0, 0, 0.04);
  --wa-transition: cubic-bezier(0.25, 0.46, 0.45, 0.94);
  --wa-transition-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}
@media (prefers-color-scheme: dark) {
  :root {
    --wa-background: #000000;
    --wa-panel: #1c1c1e;
    --wa-panel-strong: #1c1c1e;
    --wa-panel-glass: rgba(28, 28, 30, 0.72);
    --wa-border: rgba(255, 255, 255, 0.08);
    --wa-border-strong: rgba(255, 255, 255, 0.12);
    --wa-ink: #f5f5f7;
    --wa-ink-soft: #a1a1a6;
    --wa-neutral: #8e8e93;
    --wa-shadow-sm: 0 1px 3px rgba(0, 0, 0, 0.2);
    --wa-shadow: 0 4px 24px rgba(0, 0, 0, 0.2), 0 1px 4px rgba(0, 0, 0, 0.15);
    --wa-shadow-lg: 0 12px 40px rgba(0, 0, 0, 0.3), 0 4px 12px rgba(0, 0, 0, 0.2);
    --wa-shadow-glow: 0 0 0 1px rgba(88, 86, 214, 0.2), 0 4px 24px rgba(88, 86, 214, 0.15);
    --wa-chip-bg: rgba(255, 255, 255, 0.06);
    --wa-section-divider: rgba(255, 255, 255, 0.06);
    --wa-primary-subtle: rgba(88, 86, 214, 0.15);
  }
}

/* ─── Base ─── */
html {
  scroll-behavior: smooth;
}
html, body, [class*="css"] {
  font-family: "DM Sans", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}
::selection {
  background: rgba(88, 86, 214, 0.2);
  color: var(--wa-ink);
}
.stApp {
  background: var(--wa-background);
  background-image:
    radial-gradient(ellipse 80% 50% at 50% -20%, rgba(88, 86, 214, 0.03), transparent);
  color: var(--wa-ink);
  font-family: "DM Sans", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
}
@media (prefers-color-scheme: dark) {
  .stApp {
    background-image:
      radial-gradient(ellipse 80% 50% at 50% -20%, rgba(88, 86, 214, 0.06), transparent);
  }
}
.block-container {
  max-width: 1280px;
  padding-left: 1.5rem;
  padding-right: 1.5rem;
  padding-top: 2rem;
  padding-bottom: 4rem;
}
.stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp p, .stApp li, .stApp label,
.stApp span:not([data-testid="stIconMaterial"]),
.stApp div {
  font-family: "DM Sans", -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
}
code, pre, .stCodeBlock, .metric-code {
  font-family: "JetBrains Mono", "SF Mono", monospace !important;
}
[data-testid="stHeader"] {
  background: var(--wa-panel-glass);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
}
#MainMenu, footer {
  visibility: hidden;
}

/* ─── Navigation — frosted glass bar ─── */
.genesis-nav {
  position: sticky;
  top: 0.75rem;
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  min-height: 52px;
  padding: 0.6rem 1rem;
  margin-bottom: 1.5rem;
  border: 1px solid var(--wa-border);
  border-radius: 14px;
  background: var(--wa-panel-glass);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  box-shadow: var(--wa-shadow-sm);
  animation: wa-fade-up 0.5s var(--wa-transition) both;
}
.genesis-logo {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  color: var(--wa-ink);
  text-decoration: none;
}
.genesis-logo-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--wa-primary);
  color: #ffffff;
  font-family: "General Sans", "DM Sans", system-ui, sans-serif !important;
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: -0.03em;
}
.genesis-logo-copy {
  display: flex;
  flex-direction: column;
  line-height: 1.05;
}
.genesis-logo-title {
  font-family: "General Sans", "DM Sans", system-ui, sans-serif !important;
  font-weight: 700;
  font-size: 0.88rem;
  letter-spacing: -0.03em;
}
.genesis-logo-subtitle {
  font-size: 0.68rem;
  color: var(--wa-neutral);
  letter-spacing: -0.01em;
}
.genesis-links {
  display: flex;
  align-items: center;
  gap: 0.1rem;
}
.genesis-links a {
  padding: 0.35rem 0.65rem;
  border-radius: 8px;
  color: var(--wa-ink-soft);
  text-decoration: none;
  font-size: 0.8rem;
  font-weight: 500;
  letter-spacing: -0.01em;
  transition: all 0.2s var(--wa-transition);
}
.genesis-links a:hover {
  background: var(--wa-primary-subtle);
  color: var(--wa-primary);
}
.genesis-user {
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
}
.genesis-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.2rem 0.65rem;
  border-radius: 9999px;
  border: 1px solid var(--wa-border);
  background: var(--wa-chip-bg, rgba(0, 0, 0, 0.03));
  color: var(--wa-neutral);
  font-size: 0.7rem;
  font-weight: 500;
}
.genesis-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 9999px;
  background: linear-gradient(135deg, var(--wa-primary), #7c3aed);
  color: #ffffff;
  font-size: 0.72rem;
  font-weight: 700;
}

/* ─── Hero — dramatic display with ambient gradient ─── */
.hero-shell {
  position: relative;
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(280px, 0.95fr);
  gap: 2rem;
  padding: 2.5rem 2.5rem 2rem;
  border: 1px solid var(--wa-border);
  border-radius: 20px;
  background: var(--wa-panel);
  overflow: hidden;
  margin-bottom: 2rem;
  box-shadow: var(--wa-shadow);
  animation: wa-scale-in 0.6s var(--wa-transition) both;
}
.hero-shell::before {
  content: "";
  position: absolute;
  top: -40%;
  right: -15%;
  width: 700px;
  height: 700px;
  border-radius: 50%;
  background:
    radial-gradient(circle at 30% 40%, rgba(88, 86, 214, 0.07) 0%, transparent 50%),
    radial-gradient(circle at 70% 60%, rgba(52, 199, 89, 0.04) 0%, transparent 50%),
    radial-gradient(circle at 50% 30%, rgba(50, 173, 230, 0.04) 0%, transparent 50%);
  pointer-events: none;
  animation: wa-hero-gradient 20s ease infinite;
  background-size: 200% 200%;
}
.hero-shell::after {
  content: "";
  position: absolute;
  inset: auto 1.5rem 1.5rem auto;
  width: 200px;
  height: 150px;
  background-image: radial-gradient(circle, rgba(88, 86, 214, 0.12) 1px, transparent 1px);
  background-size: 18px 18px;
  opacity: 0.6;
  pointer-events: none;
}
.hero-kicker {
  text-transform: uppercase;
  letter-spacing: 0.14em;
  font-size: 0.65rem;
  color: var(--wa-primary);
  margin: 0 0 0.75rem;
  font-weight: 600;
}
.hero-shell h1 {
  margin: 0;
  max-width: 14ch;
  font-family: "General Sans", "DM Sans", system-ui, sans-serif !important;
  font-size: clamp(2.8rem, 6vw, 4rem);
  line-height: 0.95;
  letter-spacing: -0.045em;
  font-weight: 700;
  color: var(--wa-ink);
}
.hero-copy {
  margin: 1.25rem 0 0;
  max-width: 44ch;
  color: var(--wa-ink-soft);
  font-size: 0.92rem;
  line-height: 1.65;
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 1.5rem;
}
.hero-note {
  display: inline-flex;
  align-items: center;
  padding: 0.4rem 0.75rem;
  border-radius: 9999px;
  background: var(--wa-chip-bg, rgba(0, 0, 0, 0.03));
  color: var(--wa-ink-soft);
  font-size: 0.74rem;
}
.hero-note strong {
  color: var(--wa-ink);
  font-weight: 700;
}
.hero-metrics {
  position: relative;
  z-index: 1;
  display: grid;
  gap: 0.6rem;
}
.hero-panel {
  padding: 1rem 1.1rem 0.95rem;
  border: 1px solid var(--wa-border);
  border-radius: 14px;
  background: var(--wa-panel-glass);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  transition: all 0.3s var(--wa-transition);
  animation: wa-fade-up 0.5s var(--wa-transition) both;
}
.hero-panel:nth-child(1) { animation-delay: 0.15s; }
.hero-panel:nth-child(2) { animation-delay: 0.25s; }
.hero-panel:nth-child(3) { animation-delay: 0.35s; }
.hero-panel:hover {
  box-shadow: var(--wa-shadow);
  border-color: var(--wa-border-strong);
}
.hero-panel-label {
  margin: 0 0 0.4rem;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 0.62rem;
  color: var(--wa-neutral);
  font-weight: 600;
}
.section-kicker {
  margin: 0 0 0.4rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  font-size: 0.6rem;
  font-weight: 700;
}
.hero-panel-value {
  margin: 0;
  font-family: "General Sans", "DM Sans", system-ui, sans-serif !important;
  font-size: 1.4rem;
  line-height: 1.1;
  letter-spacing: -0.03em;
  font-weight: 700;
  color: var(--wa-ink);
  font-variant-numeric: tabular-nums;
}
.hero-panel-copy {
  margin: 0.4rem 0 0;
  color: var(--wa-ink-soft);
  font-size: 0.78rem;
  line-height: 1.55;
}
.hero-panel code {
  display: inline-block;
  margin-top: 0.3rem;
  padding: 0.25rem 0.45rem;
  border-radius: 6px;
  background: var(--wa-chip-bg, rgba(0, 0, 0, 0.03));
  font-size: 0.68rem;
  color: var(--wa-ink-soft);
}

/* ─── Section headings ─── */
.toolbar-shell,
.summary-grid-shell,
.section-shell {
  margin-top: 0.25rem;
}
.section-heading {
  margin: 3.5rem 0 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--wa-section-divider);
  animation: wa-fade-up 0.4s var(--wa-transition) both;
}
.section-heading:first-of-type {
  border-top: none;
  padding-top: 0;
}
.section-heading h2 {
  margin: 0.35rem 0 0;
  font-family: "General Sans", "DM Sans", system-ui, sans-serif !important;
  font-size: clamp(1.5rem, 3.5vw, 1.75rem);
  line-height: 1.15;
  letter-spacing: -0.035em;
  font-weight: 700;
  color: var(--wa-ink);
}
.section-heading .section-kicker {
  margin: 0 0 0.5rem;
}
.section-heading p:not(.section-kicker) {
  margin: 0.5rem 0 0;
  max-width: 52rem;
  color: var(--wa-ink-soft);
  font-size: 0.86rem;
  line-height: 1.65;
}

/* ─── Active search bar ─── */
.active-search {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  padding: 0.75rem 1rem;
  margin: 0.35rem 0 1rem;
  border: 1px solid var(--wa-border);
  border-radius: 14px;
  background: var(--wa-panel);
  box-shadow: var(--wa-shadow-sm);
}
.active-search-copy {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  color: var(--wa-ink-soft);
  font-size: 0.84rem;
}
.active-search strong {
  color: var(--wa-ink);
}
.search-shortcut {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.22rem 0.5rem;
  border-radius: 6px;
  background: var(--wa-primary-subtle);
  color: var(--wa-primary);
  font-size: 0.7rem;
  font-weight: 600;
}

/* ─── Summary cards — floating surfaces ─── */
.summary-card {
  min-height: 115px;
  padding: 1.1rem 1.2rem;
  border-radius: 16px;
  background: var(--wa-panel);
  border: 1px solid var(--wa-border);
  margin-bottom: 0.75rem;
  box-shadow: var(--wa-shadow-sm);
  transition: all 0.35s var(--wa-transition);
}
.summary-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--wa-shadow-lg), 0 0 0 1px var(--wa-border-strong);
}
.summary-card h3 {
  margin: 0.45rem 0 0;
  font-family: "General Sans", "DM Sans", system-ui, sans-serif !important;
  font-size: clamp(1.05rem, 2vw, 1.3rem);
  line-height: 1.2;
  font-weight: 700;
  color: var(--wa-ink);
  letter-spacing: -0.025em;
  word-break: break-word;
  font-variant-numeric: tabular-nums;
}
.summary-label {
  margin: 0;
  color: var(--wa-neutral);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 0.66rem;
  font-weight: 600;
}
.summary-delta {
  display: inline-flex;
  align-items: center;
  margin: 0.5rem 0 0;
  padding: 0.18rem 0.55rem;
  border-radius: 6px;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
}
.summary-delta.delta-up {
  background: rgba(52, 199, 89, 0.12);
  color: #248a3d;
}
.summary-delta.delta-down {
  background: rgba(255, 59, 48, 0.1);
  color: #d70015;
}
.summary-delta.delta-flat {
  background: rgba(142, 142, 147, 0.1);
  color: var(--wa-neutral);
}
@media (prefers-color-scheme: dark) {
  .summary-delta.delta-up {
    background: rgba(52, 199, 89, 0.18);
    color: #30d158;
  }
  .summary-delta.delta-down {
    background: rgba(255, 59, 48, 0.18);
    color: #ff6961;
  }
  .summary-delta.delta-flat {
    background: rgba(142, 142, 147, 0.15);
  }
}
.summary-detail {
  margin-top: 0.65rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--wa-section-divider);
  color: var(--wa-ink-soft);
  font-size: 0.78rem;
  line-height: 1.6;
}

/* ─── Signal guide items ─── */
.signal-guide-item {
  min-height: auto;
  padding: 1rem;
  margin-bottom: 0.5rem;
  border-radius: 12px;
  border: 1px solid var(--wa-border);
  background: var(--wa-panel);
}
.signal-guide-item h3 {
  margin: 0 0 0.75rem;
  font-family: "General Sans", "DM Sans", system-ui, sans-serif !important;
  font-size: 1rem;
  line-height: 1.2;
  letter-spacing: 0;
  color: var(--wa-ink);
}
.signal-guide-item p {
  margin: 0.65rem 0 0;
  padding-top: 0.45rem;
  border-top: 1px solid var(--wa-section-divider);
  color: var(--wa-ink-soft);
  font-size: 0.8rem;
  line-height: 1.6;
}
.signal-guide-item p:first-of-type {
  border-top: none;
  padding-top: 0;
}
.signal-guide-item strong {
  display: block;
  margin-bottom: 0.2rem;
  color: var(--wa-ink);
  font-size: 0.68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.signal-guide-ko-title {
  margin: -0.35rem 0 0.45rem !important;
  color: var(--wa-primary) !important;
  font-size: 0.8rem;
  font-weight: 600;
}

/* ─── Health pills — status-coded surfaces ─── */
.health-pill {
  padding: 1rem 1.1rem;
  margin-bottom: 0.5rem;
  border-radius: 14px;
  border: 1px solid var(--wa-border);
  border-left: 3px solid var(--wa-border);
  background: var(--wa-panel);
  box-shadow: var(--wa-shadow-sm);
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
  transition: all 0.3s var(--wa-transition);
}
.health-pill:hover {
  transform: translateY(-2px);
  box-shadow: var(--wa-shadow);
  border-color: var(--wa-border-strong);
}
.health-good { border-left-color: var(--wa-success); }
.health-caution { border-left-color: var(--wa-warning); }
.health-warning { border-left-color: var(--wa-error); }
.health-no_data { border-left-color: var(--wa-neutral); }
.health-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 9999px;
  margin-bottom: 0.15rem;
}
.health-good .health-dot {
  background: var(--wa-success);
  box-shadow: 0 0 6px rgba(52, 199, 89, 0.4);
}
.health-caution .health-dot {
  background: var(--wa-warning);
  box-shadow: 0 0 6px rgba(255, 159, 10, 0.4);
}
.health-warning .health-dot {
  background: var(--wa-error);
  box-shadow: 0 0 6px rgba(255, 59, 48, 0.4);
  animation: wa-pulse-dot 2s ease-in-out infinite;
}
.health-no_data .health-dot { background: var(--wa-neutral); }
.health-label {
  font-size: 0.64rem;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--wa-neutral);
  font-weight: 600;
}
.health-status {
  font-family: "General Sans", "DM Sans", system-ui, sans-serif !important;
  font-size: 1.15rem;
  font-weight: 700;
  color: var(--wa-ink);
  letter-spacing: -0.02em;
  margin-top: 0.05rem;
  font-variant-numeric: tabular-nums;
}
.health-good .health-status { color: #248a3d; }
.health-caution .health-status { color: #c93400; }
.health-warning .health-status { color: #d70015; }
@media (prefers-color-scheme: dark) {
  .health-good .health-status { color: #30d158; }
  .health-caution .health-status { color: #ff9f0a; }
  .health-warning .health-status { color: #ff453a; }
}
.health-desc {
  font-size: 0.78rem;
  color: var(--wa-ink-soft);
  line-height: 1.55;
  margin-top: 0.15rem;
}

/* ─── Alert cards — severity-coded ─── */
.alert-card {
  padding: 1rem 1.15rem;
  margin-bottom: 0.65rem;
  border-radius: 14px;
  border: 1px solid var(--wa-border);
  border-left: 4px solid;
  box-shadow: var(--wa-shadow-sm);
  transition: all 0.3s var(--wa-transition);
}
.alert-card:hover {
  box-shadow: var(--wa-shadow);
}
.alert-card.alert-warning {
  border-left-color: var(--wa-warning);
  background: rgba(255, 159, 10, 0.04);
}
.alert-card.alert-info {
  border-left-color: var(--wa-primary);
  background: rgba(88, 86, 214, 0.04);
}
.alert-card.alert-critical {
  border-left-color: var(--wa-error);
  background: rgba(255, 59, 48, 0.04);
}
.alert-title {
  margin: 0 0 0.3rem;
  font-weight: 700;
  font-size: 0.86rem;
  color: var(--wa-ink);
  line-height: 1.35;
}
.alert-description {
  margin: 0;
  font-size: 0.8rem;
  line-height: 1.65;
  color: var(--wa-ink-soft);
}
.alert-severity-tag {
  display: inline-block;
  margin: 0 0 0.3rem;
  padding: 0.15rem 0.45rem;
  border-radius: 5px;
  font-size: 0.6rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}
.alert-tag-warning {
  background: rgba(255, 159, 10, 0.12);
  color: #c93400;
}
.alert-tag-info {
  background: rgba(88, 86, 214, 0.12);
  color: #4845B0;
}
.alert-tag-critical {
  background: rgba(255, 59, 48, 0.12);
  color: #d70015;
}
@media (prefers-color-scheme: dark) {
  .alert-tag-warning { color: #ff9f0a; }
  .alert-tag-info { color: #bf5af2; }
  .alert-tag-critical { color: #ff453a; }
}

/* ─── Data shell ─── */
.data-shell {
  padding: 1rem 1rem 1.1rem;
  margin-top: 0.25rem;
  border-radius: 16px;
  background: var(--wa-panel-strong);
  border: 1px solid var(--wa-border);
  box-shadow: var(--wa-shadow-sm);
}
.stSubheader {
  padding-top: 0.15rem;
}
.stSubheader > div > div > div > p {
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: var(--wa-ink);
}

/* ─── Plotly chart containers — floating cards ─── */
[data-testid="stPlotlyChart"] {
  background: var(--wa-panel-strong);
  border: 1px solid var(--wa-border);
  border-radius: 16px;
  padding: 0.85rem 0.85rem 0.4rem;
  margin-bottom: 1rem;
  box-shadow: var(--wa-shadow-sm);
  transition: all 0.35s var(--wa-transition);
}
[data-testid="stPlotlyChart"]:hover,
.data-shell:hover {
  transform: translateY(-2px);
  box-shadow: var(--wa-shadow);
  border-color: var(--wa-border-strong);
}

/* ─── Data tables ─── */
[data-testid="stDataFrame"] {
  border: 1px solid var(--wa-border);
  border-radius: 14px;
  overflow: hidden;
  background: var(--wa-panel);
  box-shadow: var(--wa-shadow-sm);
  margin-bottom: 1rem;
}
[data-testid="stDataFrame"] * {
  font-size: 0.82rem;
  color: var(--wa-ink);
}
[data-testid="stDataFrame"] th {
  font-weight: 600;
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--wa-ink-soft);
}

/* ─── Streamlit alerts ─── */
.stAlert {
  color: var(--wa-ink);
  border-radius: 14px;
  border: 1px solid var(--wa-border);
}

/* ─── Form inputs — clean, Apple-like ─── */
.stTextInput > label,
.stDateInput > label,
.stSelectbox > label {
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--wa-ink-soft) !important;
  font-weight: 600;
  margin-bottom: 0.4rem;
}
.stTextInput [data-baseweb="base-input"],
.stDateInput [data-baseweb="input"],
.stSelectbox [data-baseweb="select"] > div {
  min-height: 42px;
  border: 1px solid var(--wa-border-strong);
  background: var(--wa-panel);
  color: var(--wa-ink);
  border-radius: 10px;
  transition: all 0.25s var(--wa-transition);
}
.stTextInput [data-baseweb="base-input"] {
  border-radius: 12px;
}
.stTextInput [data-baseweb="base-input"]:focus-within,
.stDateInput [data-baseweb="input"]:focus-within,
.stSelectbox [data-baseweb="select"] > div:focus-within {
  border-color: var(--wa-primary) !important;
  box-shadow: var(--wa-ring);
}
.stTextInput input,
.stDateInput input,
.stSelectbox input {
  font-size: 0.88rem !important;
  color: var(--wa-ink) !important;
}
.stTextInput input::placeholder,
.stDateInput input::placeholder,
.stSelectbox input::placeholder {
  color: var(--wa-neutral) !important;
}

/* ─── Buttons — refined with depth ─── */
.stDownloadButton > button,
.stButton > button {
  min-height: 42px;
  border-radius: 10px;
  background: var(--wa-primary);
  color: #ffffff;
  border: none;
  font-weight: 600;
  font-size: 0.88rem;
  letter-spacing: -0.01em;
  box-shadow: var(--wa-button-shadow);
  transition: all 0.25s var(--wa-transition);
}
.stDownloadButton > button:hover,
.stButton > button:hover {
  color: #ffffff;
  background: var(--wa-primary-hover);
  transform: translateY(-1px) scale(1.01);
  box-shadow: 0 4px 16px rgba(88, 86, 214, 0.4);
}
.stDownloadButton > button:active,
.stButton > button:active {
  transform: translateY(0) scale(0.99);
  box-shadow: var(--wa-shadow-sm);
}
.stDownloadButton > button:focus-visible,
.stButton > button:focus-visible {
  box-shadow: var(--wa-ring);
}

/* ─── Text rendering ─── */
h1, h2, h3, h4, p, li, span, label {
  text-shadow: none;
}

/* ─── Responsive ─── */
@media (max-width: 900px) {
  .block-container {
    padding-top: 1.2rem;
  }
  .genesis-nav {
    flex-wrap: wrap;
    top: 0.5rem;
  }
  .genesis-links {
    order: 3;
    width: 100%;
    justify-content: space-between;
  }
  .genesis-links a {
    padding: 0.35rem 0.4rem;
    font-size: 0.72rem;
  }
  .hero-shell {
    grid-template-columns: 1fr;
    padding: 1.5rem;
    border-radius: 16px;
  }
  .hero-shell h1 {
    font-size: clamp(2.2rem, 10vw, 2.8rem);
  }
  .summary-card {
    min-height: auto;
  }
  .section-heading {
    margin: 2rem 0 1rem;
    padding-top: 1rem;
  }
  .health-pill {
    padding: 0.75rem 0.85rem;
    border-radius: 12px;
  }
  .health-status {
    font-size: 1rem;
  }
  .health-desc {
    font-size: 0.72rem;
  }
  .alert-card {
    padding: 0.85rem 1rem;
    border-radius: 12px;
  }
}

/* ─── Sparkline charts — compact, no hover lift ─── */
[data-testid="stPlotlyChart"]:has(> div[style*="height: 180px"]),
[data-testid="stPlotlyChart"].sparkline-chart {
  padding: 0.35rem 0.35rem 0.15rem;
  margin-bottom: 0.5rem;
  border-radius: 14px;
  background: transparent !important;
  border-color: var(--wa-border) !important;
  transform: none !important;
  box-shadow: var(--wa-shadow-sm) !important;
}
[data-testid="stPlotlyChart"]:has(> div[style*="height: 180px"]):hover,
[data-testid="stPlotlyChart"].sparkline-chart:hover {
  transform: none !important;
  box-shadow: var(--wa-shadow-sm) !important;
}

/* ─── Health pill description clamp ─── */
.health-pill .health-desc {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ─── Expander styling ─── */
.stExpander {
  border: 1px solid var(--wa-border) !important;
  border-radius: 14px !important;
  margin-bottom: 0.75rem;
  overflow: hidden;
}
.stExpander summary {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--wa-ink-soft);
}

/* ─── Selectbox / export row ─── */
.stSelectbox {
  margin-bottom: 0.5rem;
}

/* ─── Caption ─── */
.stCaption p {
  font-size: 0.72rem !important;
  color: var(--wa-neutral) !important;
  line-height: 1.5;
}

/* ─── Section kicker identity badges ─── */
.section-kicker {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 6px;
  background: var(--wa-primary-subtle);
  color: var(--wa-primary) !important;
}
.kicker-overview { background: rgba(88, 86, 214, 0.08); color: #5856D6 !important; }
.kicker-search { background: rgba(88, 86, 214, 0.08); color: #5856D6 !important; }
.kicker-trend { background: rgba(50, 173, 230, 0.08); color: #32ade6 !important; }
.kicker-health { background: rgba(52, 199, 89, 0.08); color: #248a3d !important; }
.kicker-alerts { background: rgba(255, 159, 10, 0.08); color: #c93400 !important; }
.kicker-signals { background: rgba(175, 82, 222, 0.08); color: #af52de !important; }
.kicker-data { background: rgba(142, 142, 147, 0.06); color: var(--wa-neutral) !important; }
.kicker-reference { background: rgba(142, 142, 147, 0.06); color: var(--wa-neutral) !important; }
@media (prefers-color-scheme: dark) {
  .kicker-health { color: #30d158 !important; }
  .kicker-alerts { color: #ff9f0a !important; }
  .kicker-trend { color: #64d2ff !important; }
  .kicker-signals { color: #bf5af2 !important; }
}

/* ─── Filter area glass container ─── */
.stTextInput:first-of-type [data-baseweb="base-input"] {
  border-radius: 14px;
  min-height: 46px;
  font-size: 0.92rem;
}

/* ─── Nav link active indicator ─── */
.genesis-links a[href] {
  position: relative;
}
.genesis-links a:active,
.genesis-links a:focus {
  background: var(--wa-primary-subtle);
  color: var(--wa-primary);
}

/* ─── Reduced motion ─── */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
</style>
"""
