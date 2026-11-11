import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

import { FlagBadge } from './badges'

const flag = (id: number, message: string) => ({ policy_id: id, policy: `P${id}`, message })

describe('FlagBadge', () => {
  it('shows nothing for a call without flags', () => {
    const { container } = render(<FlagBadge flags={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('says "Needs review" and keeps the reason in the tooltip', () => {
    render(<FlagBadge flags={[flag(1, 'Lead ID already used')]} />)
    const badge = screen.getByText('Needs review').closest('span')!
    expect(badge).toHaveAttribute('title', 'Lead ID already used')
  })

  it('counts several flags and lists every reason', () => {
    render(<FlagBadge flags={[flag(1, 'Reason A'), flag(2, 'Reason B')]} />)
    const badge = screen.getByText('Needs review (2)').closest('span')!
    expect(badge.getAttribute('title')).toContain('Reason A')
    expect(badge.getAttribute('title')).toContain('Reason B')
  })
})
