# Mandi & Commodity Procurement ERP — Design System & Visual Contract

## 1. Visual Theme: "Light, Colorful & Card-First"
A modern, vibrant, high-contrast light theme engineered for fast mandi yard operations, central rate governance, and executive oversight.

### Core Design Principles
- **Card-First Modularity ("Cards Only"):** Every functional component (navigation, statistics, filters, commodity selector, forms, calculations, registers, modals) is encapsulated inside distinct, tactile, rounded card surfaces.
- **Vibrant Commodity Color Signatures:** Each commodity possesses an unmistakable color personality for split-second recognition on yard screens under outdoor/high-glare sunlight.
- **Tactile Depth & Clean Elevation:** Subtle multi-layer shadows (`0 4px 20px -2px rgba(15, 23, 42, 0.06)`), 1.5px crisp borders (`#e2e8f0`), rounded corners (`12px` to `16px`), and smooth hover micro-interactions.
- **High Readability & Contrast:** Strict compliance with WCAG AA/AAA standards with dark slate text (`#0f172a`) against crisp white card surfaces (`#ffffff`) and soft porcelain backgrounds (`#f8fafc`).

---

## 2. Design Tokens & Palette

### Backgrounds & Surfaces
- Canvas Background: `#f8fafc` (Soft Porcelain Slate)
- Card Surface: `#ffffff` (Pure Crisp White)
- Input Surface: `#f8fafc` with border `#cbd5e1`, focus border `#3b82f6`
- Card Border: `#e2e8f0` (1.5px solid)
- Card Hover Border: `#cbd5e1`

### Tier Identity Gradients
- **Level 1 (Super Admin):** Sapphire to Indigo gradient (`linear-gradient(135deg, #2563eb, #4f46e5)`)
- **Level 2 (Central Accounts):** Emerald to Teal gradient (`linear-gradient(135deg, #059669, #0d9488)`)
- **Level 3 (Branch Operations):** Warm Amber to Orange gradient (`linear-gradient(135deg, #d97706, #ea580c)`)

### Commodity Color Tokens
- **Soyabean (Yellow):** Green leaf gradient (`#16a34a`), background tint `#f0fdf4`, border `#bbf7d0`
- **Wheat (Lokwan):** Golden wheat grain (`#b45309`), background tint `#fffbeb`, border `#fde68a`
- **Chana (Desi):** Terracotta pulse (`#c2410c`), background tint `#fff7ed`, border `#fed7aa`
- **Mustard (Rayda):** Rich mustard yellow (`#a16207`), background tint `#fefce8`, border `#fef08a`
- **Maize (Makka):** Sweet corn yellow (`#ca8a04`), background tint `#fef9c3`, border `#fde047`

### Semantic Status Badges
- **Active / Paid / Within Corridor:** Background `#dcfce7`, text `#15803d`, border `#86efac`
- **Pending / Attention / Override:** Background `#fef3c7`, text `#b45309`, border `#fde68a`
- **Danger / Rejected / Blocked:** Background `#fee2e2`, text `#b91c1c`, border `#fca5a5`
- **Neutral / Metric:** Background `#f1f5f9`, text `#334155`, border `#cbd5e1`

---

## 3. Component Standards
- **Header:** Sticky elevated card with system badge, branch selector, and navigation pill links.
- **Metric Cards:** Bento-style grid with bold numbers (`28px`), uppercase subheadings (`11px`), and colorful icon circles.
- **Commodity Cards:** Large interactive cards with icon, full name, grade badge, three-column pricing corridor (Floor, Target, Ceiling), and moisture standard. Active card has glowing brand border and checkmark badge.
- **Active Commodity Banner:** High-visibility gradient banner dynamically announcing the active commodity and pricing limits.
- **Calculation Panel:** Elevated card with clear, line-by-line deductions and bold net payable summary.
- **Modals:** Centered backdrop blur (`backdrop-filter: blur(4px)`), rounded white dialogs (`16px`).
