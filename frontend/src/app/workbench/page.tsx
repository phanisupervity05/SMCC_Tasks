'use client'

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

// Sample workbench tools
const tools = [
  {
    id: 'ai-assistant',
    title: 'AI Assistant',
    description: 'Chat with your AI assistant for help with tasks',
    icon: Icons.sparkles,
    color: 'bg-gradient-to-br from-brand-navy to-brand-purple',
    status: 'available',
  },
  {
    id: 'automation',
    title: 'Automation Builder',
    description: 'Create and manage automated workflows',
    icon: Icons.zap,
    color: 'bg-gradient-to-br from-brand-cornflower to-brand-purple',
    status: 'available',
  },
  {
    id: 'analytics',
    title: 'Analytics Dashboard',
    description: 'View detailed analytics and reports',
    icon: Icons.activity,
    color: 'bg-gradient-to-br from-emerald-500 to-emerald-600',
    status: 'coming-soon',
  },
  {
    id: 'integrations',
    title: 'Integrations',
    description: 'Connect with third-party services',
    icon: Icons.share,
    color: 'bg-gradient-to-br from-amber-500 to-orange-500',
    status: 'coming-soon',
  },
]

function ToolCard({ tool }: { tool: (typeof tools)[0] }) {
  const Icon = tool.icon
  const isComingSoon = tool.status === 'coming-soon'

  return (
    <motion.div variants={itemVariants}>
      <Card
        className={cn(
          'h-full cursor-pointer transition-all duration-300',
          isComingSoon && 'opacity-60'
        )}
      >
        <CardHeader>
          <div className='flex items-start justify-between'>
            <div
              className={cn(
                'flex h-12 w-12 items-center justify-center rounded-xl text-white',
                tool.color
              )}
            >
              <Icon className='h-6 w-6' strokeWidth={1.5} />
            </div>
            {isComingSoon && (
              <span className='rounded-full bg-muted px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-brand-muted'>
                Coming Soon
              </span>
            )}
          </div>
          <CardTitle className='mt-4'>{tool.title}</CardTitle>
          <CardDescription>{tool.description}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant={isComingSoon ? 'outline' : 'default'}
            className='w-full'
            disabled={isComingSoon}
          >
            {isComingSoon ? 'Notify Me' : 'Open Tool'}
            {!isComingSoon && <Icons.arrowRight className='ml-2 h-4 w-4' />}
          </Button>
        </CardContent>
      </Card>
    </motion.div>
  )
}

export default function WorkbenchPage() {
  return (
    <motion.div
      className='space-y-8'
      variants={containerVariants}
      initial='hidden'
      animate='visible'
    >
      {/* Header */}
      <motion.div variants={itemVariants}>
        <h1 className='text-display-3 font-bold tracking-tight text-brand-navy'>
          Workbench
        </h1>
        <p className='mt-2 text-lg text-muted-foreground'>
          Access your AI tools and automation workflows.
        </p>
      </motion.div>

      {/* Tools Grid */}
      <div className='grid gap-6 sm:grid-cols-2 lg:grid-cols-4'>
        {tools.map((tool) => (
          <ToolCard key={tool.id} tool={tool} />
        ))}
      </div>

      {/* Quick Actions */}
      <motion.div variants={itemVariants}>
        <Card>
          <CardHeader>
            <CardTitle className='flex items-center gap-2'>
              <Icons.zap className='h-5 w-5 text-brand-cornflower' />
              Quick Actions
            </CardTitle>
            <CardDescription>
              Frequently used actions for faster access
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className='flex flex-wrap gap-3'>
              <Button variant='outline' size='sm'>
                <Icons.plus className='mr-2 h-4 w-4' />
                New Task
              </Button>
              <Button variant='outline' size='sm'>
                <Icons.fileText className='mr-2 h-4 w-4' />
                Generate Report
              </Button>
              <Button variant='outline' size='sm'>
                <Icons.mail className='mr-2 h-4 w-4' />
                Send Notification
              </Button>
              <Button variant='outline' size='sm'>
                <Icons.download className='mr-2 h-4 w-4' />
                Export Data
              </Button>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </motion.div>
  )
}
