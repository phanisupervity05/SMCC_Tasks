# Brand Identity: The Ampersand System

## 1. Core Philosophy
*   **Tagline:** "Where Intelligence Meets Human."
*   **Visual Tone:** Sophisticated, Deep, Geometric, Fluid.
*   **Key Motif:** The Ampersand (`&`).
*   **Backgrounds:** Deep Navy (`#04060A`) with Mesh Gradients.

## 2. Technical Token Map (Tailwind)

### Typography Scale (Responsive)
Do not use arbitrary values. Use these semantic classes:

| Class | CSS Logic (Clamp) | Usage |
| :--- | :--- | :--- |
| `text-display-1` | `3rem` to `6rem` | Hero Headlines (H1) |
| `text-display-2` | `2.5rem` to `4.5rem` | Page Titles (H2) |
| `text-display-3` | `2rem` to `3.75rem` | Section Headers (H3) |
| `text-display-4` | `2.5rem` | Card Titles (H4) |
| `text-display-5` | `2rem` | Metrics, Values (H5) |
| `text-display-6` | `1.5rem` | Subheadings (H6) |

```tsx
<h1 className="text-display-1 font-display font-bold">Hero Headline</h1>
<h2 className="text-display-3 font-display">Section Header</h2>
<p className="text-display-5 font-bold">10.4K</p>
```

### Color Utilities
*   **Backgrounds:** `bg-background` (Dark Black), `bg-primary` (Navy).
*   **Gradients:**
    *   `bg-brand-gradient`: Linear gradient (Navy → Purple) for Primary Actions.
    *   `bg-brand-mesh`: Radial mesh for backgrounds.
    *   `bg-glass-gradient`: Subtle top-down fade for cards.
*   **Text:** `text-foreground` (White/Grey), `text-brand-cornflower` (Accent Blue).

### Brand Palette (Direct Access)
| Token | Hex | Usage |
|-------|-----|-------|
| `brand-black` | `#04060A` | Darkest background |
| `brand-navy` | `#141A42` | Primary brand color |
| `brand-cornflower` | `#8AA2DF` | Accent, active states |
| `brand-muted` | `#848EAA` | Secondary text, borders |
| `brand-purple` | `#535EA4` | Gradients, highlights |
| `brand-light` | `#E7E7E7` | Light mode background |

### Icons
*   **System:** Use `import { Icons } from '@/components/ui/icons'` to ensure consistent styling.
*   **Stroke:** All icons default to `1.5px` stroke width.
*   **Active:** Active navigation icons are colored `text-brand-cornflower`.

**Available Icons:**
```tsx
import { Icons } from '@/components/ui/icons'

<Icons.dashboard />    // LayoutDashboard
<Icons.settings />     // Settings
<Icons.workbench />    // BotMessageSquare
<Icons.logout />       // LogOut
<Icons.bell />         // Bell
<Icons.search />       // Search
<Icons.trendingUp />   // TrendingUp
<Icons.users />        // Users
<Icons.activity />     // Activity
<Icons.checkCircle />  // CheckCircle2
<Icons.arrowRight />   // ArrowRight
```

## 3. UI Component Rules

### Buttons
Always `rounded-full`. Use `variant="gradient"` for primary actions.

```tsx
<Button variant="gradient">Primary Action</Button>
<Button variant="outline">Secondary Action</Button>
<Button variant="ghost">Tertiary Action</Button>
```

### Cards
Use `Card` component. It applies Glassmorphism (`backdrop-blur`) automatically.

```tsx
<Card>
  <CardHeader>
    <CardTitle>Title (font-display)</CardTitle>
  </CardHeader>
  <CardContent>
    Content (font-sans)
  </CardContent>
</Card>
```

### Switch/Toggle
Refined for visual weight. Uses `brand-cornflower` when checked.

```tsx
import { Switch } from '@/components/ui/switch'

<Switch />                    // Unchecked: bg-input
<Switch defaultChecked />     // Checked: bg-brand-cornflower
```

### Charts
Use `brandChartTheme` object in `chart.tsx` to map Recharts colors to the CSS variables.

```tsx
import { ChartContainer, ChartTooltip, brandChartTheme } from '@/components/ui/chart'
import { LineChart, Line, XAxis, YAxis } from 'recharts'

<ChartContainer>
  <LineChart data={data}>
    <XAxis dataKey="name" />
    <YAxis />
    <Tooltip content={<ChartTooltip />} />
    <Line 
      type="monotone" 
      dataKey="value" 
      stroke={brandChartTheme.cornflower} 
    />
  </LineChart>
</ChartContainer>
```

## 4. Logo Assets

### File Locations
```
frontend/public/logos/
├── logomark-dark.svg     # S mark (Navy) - for light backgrounds
├── logomark-light.svg    # S mark (White) - for dark backgrounds
├── logo-full-dark.svg    # Full wordmark (Navy)
└── logo-full-light.svg   # Full wordmark (White)
```

### React Components
```tsx
import { Logomark, Logo } from '@/components/brand'

// Logomark (S icon)
<Logomark variant="light" size={40} />  // For dark backgrounds
<Logomark variant="dark" size={40} />   // For light backgrounds

// Full wordmark
<Logo variant="light" width={150} />    // For dark backgrounds
<Logo variant="dark" width={150} />     // For light backgrounds
```

## 5. Visual Patterns

### Mesh Gradient Background
```tsx
import { VisualPattern } from '@/components/brand'

<VisualPattern />                  // Default intensity
<VisualPattern variant="subtle" /> // 30% opacity
```

**Technical Details:**
- Uses `mix-blend-screen` and `mix-blend-plus-lighter` for lighting effects
- Animated with `animate-float` and `animate-float-delayed`
- Three-blob composition for depth

### Sidebar Theme
```tsx
// Background: brand-black (#04060A)
// Active link: bg-white/10 text-brand-cornflower
// Inactive link: text-brand-muted hover:bg-white/5
// Borders: border-white/10
```

## 6. Shadows
```tsx
// Soft elevation (default cards)
className="shadow-soft"

// Medium elevation (hover states)
className="shadow-medium hover:shadow-medium"
```

