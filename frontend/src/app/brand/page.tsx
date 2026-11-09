'use client'

import { useState } from 'react'
import { motion } from 'framer-motion'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Icons } from '@/components/ui/icons'
import { Logomark } from '@/components/brand'
import { cn } from '@/lib/utils'

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.1 },
  },
}

const itemVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
}

// Brand colors
const brandColors = [
  {
    name: 'Navy (Primary)',
    hex: '#141A42',
    hsl: '232 53% 17%',
    variable: '--primary',
    usage: 'Headings, buttons, dark backgrounds',
  },
  {
    name: 'Cornflower',
    hex: '#8AA2DF',
    hsl: '223 54% 71%',
    variable: '--accent',
    usage: 'Accents, highlights, links',
  },
  {
    name: 'Purple',
    hex: '#535EA4',
    hsl: '232 33% 48%',
    variable: 'brand-purple',
    usage: 'Gradients, secondary accents',
  },
  {
    name: 'Muted',
    hex: '#848EAA',
    hsl: '224 20% 59%',
    variable: '--muted-foreground',
    usage: 'Secondary text, labels',
  },
  {
    name: 'Light Grey',
    hex: '#E7E7E7',
    hsl: '0 0% 90.5%',
    variable: 'brand-light',
    usage: 'Backgrounds, borders',
  },
  {
    name: 'Black',
    hex: '#04060A',
    hsl: '220 43% 4%',
    variable: 'brand-black',
    usage: 'Dark mode backgrounds',
  },
]

// UI Colors
const uiColors = [
  {
    name: 'Background',
    hex: '#F5F7FF',
    hsl: '225 60% 98.5%',
    variable: '--background',
  },
  { name: 'Card', hex: '#FFFFFF', hsl: '0 0% 100%', variable: '--card' },
  { name: 'Border', hex: '#E8EBF2', hsl: '220 20% 92%', variable: '--border' },
  {
    name: 'Destructive',
    hex: '#EF4444',
    hsl: '0 84% 60%',
    variable: '--destructive',
  },
]

// Font families
const fonts = [
  {
    name: 'Funnel Display',
    usage: 'Headings, titles, display text',
    weights: ['500', '600', '700'],
  },
  {
    name: 'Geologica',
    usage: 'Body text, UI elements, labels',
    weights: ['400', '500', '600'],
  },
]

// Shadows
const shadows = [
  {
    name: 'Glass',
    value: 'shadow-glass',
    description: 'Inner highlight + subtle border',
  },
  {
    name: 'Glass Hover',
    value: 'shadow-glass-hover',
    description: 'Hover state for cards',
  },
  {
    name: 'Accent',
    value: 'shadow-accent',
    description: 'Glow effect for interactive elements',
  },
  {
    name: 'Float',
    value: 'shadow-float',
    description: 'Floating elevation for detached elements',
  },
  {
    name: 'Float Large',
    value: 'shadow-float-lg',
    description: 'Larger floating shadow',
  },
]

function ColorSwatch({ color }: { color: (typeof brandColors)[0] }) {
  const [copied, setCopied] = useState(false)

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className='group relative'>
      <div
        className='mb-3 h-24 cursor-pointer rounded-xl transition-transform hover:scale-105'
        style={{ backgroundColor: color.hex }}
        onClick={() => copyToClipboard(color.hex)}
      >
        {copied && (
          <div className='absolute inset-0 flex items-center justify-center rounded-xl bg-black/50 text-sm font-medium text-white'>
            Copied!
          </div>
        )}
      </div>
      <h4 className='text-sm font-medium text-foreground'>{color.name}</h4>
      <p className='font-mono text-xs text-muted-foreground'>{color.hex}</p>
      <p className='mt-1 text-xs text-muted-foreground'>{color.usage}</p>
    </div>
  )
}

function ShadowDemo({ shadow }: { shadow: (typeof shadows)[0] }) {
  return (
    <div className='text-center'>
      <div
        className={cn('mb-3 h-20 w-full rounded-xl bg-white', shadow.value)}
      />
      <h4 className='text-sm font-medium text-foreground'>{shadow.name}</h4>
      <p className='font-mono text-xs text-muted-foreground'>{shadow.value}</p>
    </div>
  )
}

export default function BrandPage() {
  return (
    <motion.div
      className='space-y-10'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      {/* Header */}
      <motion.div variants={itemVariants}>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>
          Brand & Design System
        </h1>
        <p className='mt-2 text-lg text-muted-foreground'>
          Quick reference for colors, typography, and components.
        </p>
      </motion.div>

      {/* Logo */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>Logo</CardTitle>
            <CardDescription>Supervity logomark and usage</CardDescription>
          </CardHeader>
          <CardContent>
            <div className='grid gap-6 sm:grid-cols-3'>
              <div className='flex flex-col items-center rounded-xl bg-brand-navy p-6'>
                <Logomark variant='light' size={64} />
                <p className='mt-3 text-xs text-white/70'>Light on dark</p>
              </div>
              <div className='flex flex-col items-center rounded-xl border border-border bg-white p-6'>
                <Logomark variant='dark' size={64} />
                <p className='mt-3 text-xs text-muted-foreground'>
                  Dark on light
                </p>
              </div>
              <div className='flex flex-col items-center rounded-xl bg-gradient-to-br from-brand-navy to-brand-purple p-6'>
                <Logomark variant='light' size={64} />
                <p className='mt-3 text-xs text-white/70'>On gradient</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Brand Colors */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>Brand Colors</CardTitle>
            <CardDescription>
              Primary palette - click to copy hex value
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className='grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-6'>
              {brandColors.map((color) => (
                <ColorSwatch key={color.name} color={color} />
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* UI Colors */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>UI Colors</CardTitle>
            <CardDescription>
              Interface colors for backgrounds, cards, and states
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className='grid grid-cols-2 gap-6 sm:grid-cols-4'>
              {uiColors.map((color) => (
                <ColorSwatch key={color.name} color={{ ...color, usage: '' }} />
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Typography */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>Typography</CardTitle>
            <CardDescription>Font families and scale</CardDescription>
          </CardHeader>
          <CardContent className='space-y-8'>
            {/* Fonts */}
            <div className='grid gap-6 sm:grid-cols-2'>
              {fonts.map((font) => (
                <div key={font.name} className='rounded-xl bg-muted/30 p-4'>
                  <h4
                    className={cn(
                      'text-2xl font-semibold text-foreground',
                      font.name === 'Funnel Display'
                        ? 'font-display'
                        : 'font-sans'
                    )}
                  >
                    {font.name}
                  </h4>
                  <p className='mt-1 text-sm text-muted-foreground'>
                    {font.usage}
                  </p>
                  <p className='mt-2 font-mono text-xs text-muted-foreground'>
                    Weights: {font.weights.join(', ')}
                  </p>
                </div>
              ))}
            </div>

            {/* Type Scale */}
            <div className='space-y-4'>
              <h4 className='text-sm font-semibold uppercase tracking-wider text-muted-foreground'>
                Type Scale
              </h4>
              <div className='space-y-3'>
                <p className='font-display text-display-1 font-bold text-brand-navy'>
                  Display 1
                </p>
                <p className='font-display text-display-2 font-bold text-brand-navy'>
                  Display 2
                </p>
                <p className='font-display text-display-3 font-bold text-brand-navy'>
                  Display 3
                </p>
                <p className='text-2xl font-semibold text-foreground'>
                  Heading Large
                </p>
                <p className='text-xl font-semibold text-foreground'>
                  Heading Medium
                </p>
                <p className='text-lg font-medium text-foreground'>
                  Heading Small
                </p>
                <p className='text-base text-foreground'>
                  Body text - The quick brown fox jumps over the lazy dog.
                </p>
                <p className='text-sm text-muted-foreground'>
                  Small text - Secondary information and labels
                </p>
                <p className='text-xs text-muted-foreground'>
                  Extra small - Captions and metadata
                </p>
                <p className='text-micro uppercase tracking-widest text-muted-foreground'>
                  Micro Label
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Shadows */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>Shadows</CardTitle>
            <CardDescription>Elevation and depth system</CardDescription>
          </CardHeader>
          <CardContent>
            <div className='grid grid-cols-2 gap-6 sm:grid-cols-5'>
              {shadows.map((shadow) => (
                <ShadowDemo key={shadow.name} shadow={shadow} />
              ))}
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Components Preview */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>Components</CardTitle>
            <CardDescription>Button variants and states</CardDescription>
          </CardHeader>
          <CardContent className='space-y-6'>
            {/* Buttons */}
            <div>
              <h4 className='mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground'>
                Buttons
              </h4>
              <div className='flex flex-wrap gap-3'>
                <Button variant='default'>Default</Button>
                <Button variant='gradient'>Gradient</Button>
                <Button variant='outline'>Outline</Button>
                <Button variant='ghost'>Ghost</Button>
                <Button variant='glass'>Glass</Button>
                <Button variant='accent'>Accent</Button>
                <Button variant='destructive'>Destructive</Button>
                <Button variant='default' disabled>
                  Disabled
                </Button>
                <Button variant='default' loading>
                  Loading
                </Button>
              </div>
            </div>

            {/* Button Sizes */}
            <div>
              <h4 className='mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground'>
                Sizes
              </h4>
              <div className='flex flex-wrap items-center gap-3'>
                <Button size='sm'>Small</Button>
                <Button size='default'>Default</Button>
                <Button size='lg'>Large</Button>
                <Button size='xl'>Extra Large</Button>
                <Button size='icon'>
                  <Icons.plus className='h-4 w-4' />
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* Gradients */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>Gradients</CardTitle>
            <CardDescription>
              Brand gradients for backgrounds and accents
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className='grid gap-4 sm:grid-cols-3'>
              <div className='flex h-32 items-center justify-center rounded-xl bg-gradient-to-r from-brand-navy to-brand-purple'>
                <span className='font-medium text-white'>Navy → Purple</span>
              </div>
              <div className='flex h-32 items-center justify-center rounded-xl bg-gradient-to-r from-brand-navy via-brand-purple to-brand-cornflower'>
                <span className='font-medium text-white'>Text Gradient</span>
              </div>
              <div className='flex h-32 items-center justify-center rounded-xl border border-border bg-gradient-to-b from-white to-[#F8FAFF]'>
                <span className='font-medium text-foreground'>Card Glaze</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>

      {/* CSS Variables Reference */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle>CSS Variables</CardTitle>
            <CardDescription>
              Quick reference for Tailwind classes and CSS variables
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className='overflow-x-auto'>
              <table className='w-full text-sm'>
                <thead>
                  <tr className='border-b border-border'>
                    <th className='px-4 py-3 text-left font-semibold text-foreground'>
                      Tailwind Class
                    </th>
                    <th className='px-4 py-3 text-left font-semibold text-foreground'>
                      CSS Variable
                    </th>
                    <th className='px-4 py-3 text-left font-semibold text-foreground'>
                      Usage
                    </th>
                  </tr>
                </thead>
                <tbody className='divide-y divide-border'>
                  <tr>
                    <td className='px-4 py-3 font-mono text-xs'>
                      bg-background
                    </td>
                    <td className='px-4 py-3 font-mono text-xs'>
                      --background
                    </td>
                    <td className='px-4 py-3 text-muted-foreground'>
                      Page background
                    </td>
                  </tr>
                  <tr>
                    <td className='px-4 py-3 font-mono text-xs'>
                      text-foreground
                    </td>
                    <td className='px-4 py-3 font-mono text-xs'>
                      --foreground
                    </td>
                    <td className='px-4 py-3 text-muted-foreground'>
                      Primary text color
                    </td>
                  </tr>
                  <tr>
                    <td className='px-4 py-3 font-mono text-xs'>
                      bg-brand-navy
                    </td>
                    <td className='px-4 py-3 font-mono text-xs'>#141A42</td>
                    <td className='px-4 py-3 text-muted-foreground'>
                      Brand navy color
                    </td>
                  </tr>
                  <tr>
                    <td className='px-4 py-3 font-mono text-xs'>
                      bg-brand-cornflower
                    </td>
                    <td className='px-4 py-3 font-mono text-xs'>#8AA2DF</td>
                    <td className='px-4 py-3 text-muted-foreground'>
                      Brand cornflower color
                    </td>
                  </tr>
                  <tr>
                    <td className='px-4 py-3 font-mono text-xs'>
                      text-brand-muted
                    </td>
                    <td className='px-4 py-3 font-mono text-xs'>#848EAA</td>
                    <td className='px-4 py-3 text-muted-foreground'>
                      Muted text color
                    </td>
                  </tr>
                  <tr>
                    <td className='px-4 py-3 font-mono text-xs'>
                      font-display
                    </td>
                    <td className='px-4 py-3 font-mono text-xs'>
                      --font-funnel
                    </td>
                    <td className='px-4 py-3 text-muted-foreground'>
                      Display/heading font
                    </td>
                  </tr>
                  <tr>
                    <td className='px-4 py-3 font-mono text-xs'>font-sans</td>
                    <td className='px-4 py-3 font-mono text-xs'>
                      --font-geologica
                    </td>
                    <td className='px-4 py-3 text-muted-foreground'>
                      Body text font
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  )
}
