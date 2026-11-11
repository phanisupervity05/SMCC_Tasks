/**
 * AI Components - Export all AI-related components
 */

// Main AI Manager
export { AIManager } from './AIManager'
export { ChatMessage } from './ChatMessage'
export { ChatInput } from './ChatInput'
export { CapabilityBubbles } from './CapabilityBubbles'

// Insight Components
export { InsightCard } from './insights/InsightCard'
export { PatternCluster } from './insights/PatternCluster'
export { ActionCard } from './insights/ActionCard'

// Types and utilities
export type { Insight, InsightSeverity, InsightType } from './insights/InsightCard'
export { getSeverityConfig } from './insights/InsightCard'
export type { Pattern } from './insights/PatternCluster'
export type { ActionItem } from './insights/ActionCard'

