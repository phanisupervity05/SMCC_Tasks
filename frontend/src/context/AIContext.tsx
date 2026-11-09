'use client'

import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { usePathname } from 'next/navigation'

// Types for chat messages
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  toolCalls?: ToolCall[]
  isLoading?: boolean
}

export interface ToolCall {
  id: string
  name: string
  args: Record<string, unknown>
  result?: unknown
}

// Types for policies
export interface AIPolicy {
  id: string
  name: string
  description: string
  naturalLanguage: string
  dsl: PolicyDSL | null
  isActive: boolean
  createdAt: Date
  updatedAt: Date
}

export interface PolicyDSL {
  conditions: PolicyCondition[]
  actions: PolicyAction[]
  match_mode?: 'all' | 'any'
  stop_on_match?: boolean
}

export interface PolicyCondition {
  field: string
  operator: 'eq' | 'neq' | 'gt' | 'lt' | 'gte' | 'lte' | 'contains' | 'not_contains' | 'starts_with' | 'ends_with' | 'between' | 'in' | 'not_in' | 'matches' | 'is_null' | 'is_not_null'
  value: string | number | boolean | unknown[] | null
  field_path?: string
}

export interface PolicyAction {
  type: 'auto_approve' | 'auto_reject' | 'flag_review' | 'notify' | 'set_status' | 'set_field' | 'add_note' | 'add_tag' | 'escalate' | 'custom'
  value?: string | number | boolean | Record<string, unknown>
  params?: Record<string, unknown>
}

// Types for insights
export interface AIInsight {
  id: string
  type: 'pattern' | 'anomaly' | 'recommendation'
  severity: 'critical' | 'warning' | 'info'
  title: string
  description: string
  data?: Record<string, unknown>
  suggestedAction?: string
  createdAt: Date
}

// Context state type
interface AIContextState {
  // AI Manager state
  isManagerOpen: boolean
  openManager: () => void
  closeManager: () => void
  toggleManager: () => void
  
  // Chat state
  chatHistory: ChatMessage[]
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void
  clearHistory: () => void
  isTyping: boolean
  setIsTyping: (typing: boolean) => void
  
  // Page context
  currentPageContext: string
  
  // Policies state
  policies: AIPolicy[]
  setPolicies: (policies: AIPolicy[]) => void
  addPolicy: (policy: AIPolicy) => void
  updatePolicy: (id: string, updates: Partial<AIPolicy>) => void
  removePolicy: (id: string) => void
  
  // Insights state
  insights: AIInsight[]
  setInsights: (insights: AIInsight[]) => void
  pendingInsightsCount: number
  markInsightAsRead: (id: string) => void
  
  // Suggestions
  hasPendingSuggestions: boolean
  setHasPendingSuggestions: (has: boolean) => void
}

const AIContext = createContext<AIContextState | undefined>(undefined)

export function useAI() {
  const context = useContext(AIContext)
  if (!context) {
    throw new Error('useAI must be used within an AIProvider')
  }
  return context
}

// Generate unique ID
function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
}

export function AIProvider({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  
  // AI Manager state
  const [isManagerOpen, setIsManagerOpen] = useState(false)
  
  // Chat state
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([])
  const [isTyping, setIsTyping] = useState(false)
  
  // Policies state
  const [policies, setPolicies] = useState<AIPolicy[]>([])
  
  // Insights state
  const [insights, setInsights] = useState<AIInsight[]>([])
  const [readInsightIds, setReadInsightIds] = useState<Set<string>>(new Set())
  
  // Suggestions state
  const [hasPendingSuggestions, setHasPendingSuggestions] = useState(false)
  
  // Derive page context from pathname
  const currentPageContext = pathname || '/'
  
  // Manager controls
  const openManager = useCallback(() => setIsManagerOpen(true), [])
  const closeManager = useCallback(() => setIsManagerOpen(false), [])
  const toggleManager = useCallback(() => setIsManagerOpen(prev => !prev), [])
  
  // Chat controls
  const addMessage = useCallback((message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: generateId(),
      timestamp: new Date(),
    }
    
    // If this is a real assistant message (not loading), remove any existing loading messages first
    if (message.role === 'assistant' && !message.isLoading) {
      setChatHistory(prev => [...prev.filter(m => !m.isLoading), newMessage])
    } else {
      setChatHistory(prev => [...prev, newMessage])
    }
  }, [])
  
  const clearHistory = useCallback(() => {
    setChatHistory([])
  }, [])
  
  // Policy controls
  const addPolicy = useCallback((policy: AIPolicy) => {
    setPolicies(prev => [...prev, policy])
  }, [])
  
  const updatePolicy = useCallback((id: string, updates: Partial<AIPolicy>) => {
    setPolicies(prev => 
      prev.map(p => p.id === id ? { ...p, ...updates, updatedAt: new Date() } : p)
    )
  }, [])
  
  const removePolicy = useCallback((id: string) => {
    setPolicies(prev => prev.filter(p => p.id !== id))
  }, [])
  
  // Insights controls
  const pendingInsightsCount = insights.filter(i => !readInsightIds.has(i.id)).length
  
  const markInsightAsRead = useCallback((id: string) => {
    setReadInsightIds(prev => new Set([...prev, id]))
  }, [])
  
  // Keyboard shortcut for AI Manager (Cmd+J or Ctrl+J)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'j' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        toggleManager()
      }
    }
    
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [toggleManager])
  
  const value: AIContextState = {
    // Manager
    isManagerOpen,
    openManager,
    closeManager,
    toggleManager,
    
    // Chat
    chatHistory,
    addMessage,
    clearHistory,
    isTyping,
    setIsTyping,
    
    // Page context
    currentPageContext,
    
    // Policies
    policies,
    setPolicies,
    addPolicy,
    updatePolicy,
    removePolicy,
    
    // Insights
    insights,
    setInsights,
    pendingInsightsCount,
    markInsightAsRead,
    
    // Suggestions
    hasPendingSuggestions,
    setHasPendingSuggestions,
  }
  
  return (
    <AIContext.Provider value={value}>
      {children}
    </AIContext.Provider>
  )
}

