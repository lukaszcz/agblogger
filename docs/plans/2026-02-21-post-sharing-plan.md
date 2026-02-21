# Post Sharing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add client-side post sharing to social platforms for all users (including unauthenticated), using Web Share API with fallback platform-specific share URLs.

**Architecture:** Pure frontend feature. A `shareUtils.ts` module handles URL construction and native share detection. `ShareButton` (header) and `ShareBar` (bottom of post) render in PostPage. Mastodon sharing prompts for instance URL (remembered in localStorage). Existing cross-posting remains unchanged for admins.

**Tech Stack:** React 19, TypeScript, TailwindCSS 4, lucide-react, Vitest + testing-library

---

### Task 1: Share Utility Module

**Files:**
- Create: `frontend/src/components/share/shareUtils.ts`
- Test: `frontend/src/components/share/__tests__/shareUtils.test.ts`

**Step 1: Write the failing tests**

Create `frontend/src/components/share/__tests__/shareUtils.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  getShareText,
  getShareUrl,
  canNativeShare,
  nativeShare,
  copyToClipboard,
  getMastodonInstance,
  setMastodonInstance,
} from '../shareUtils'

describe('getShareText', () => {
  it('formats text with title, author, and URL', () => {
    const result = getShareText('My Post', 'Alice', 'https://blog.example.com/post/hello')
    expect(result).toBe('"My Post" by Alice https://blog.example.com/post/hello')
  })

  it('handles title with special characters', () => {
    const result = getShareText('What\'s "new" in 2026?', 'Bob', 'https://example.com/post/x')
    expect(result).toContain('What\'s "new" in 2026?')
    expect(result).toContain('by Bob')
  })

  it('handles null author', () => {
    const result = getShareText('My Post', null, 'https://example.com/post/x')
    expect(result).toBe('"My Post" https://example.com/post/x')
  })
})

describe('getShareUrl', () => {
  const url = 'https://blog.example.com/post/hello'
  const text = '"Hello World" by Alice https://blog.example.com/post/hello'
  const title = 'Hello World'

  it('returns Bluesky compose intent URL', () => {
    const result = getShareUrl('bluesky', text, url, title)
    expect(result).toBe(`https://bsky.app/intent/compose?text=${encodeURIComponent(text)}`)
  })

  it('returns X tweet intent URL', () => {
    const result = getShareUrl('x', text, url, title)
    expect(result).toBe(`https://x.com/intent/tweet?text=${encodeURIComponent(text)}`)
  })

  it('returns Facebook sharer URL', () => {
    const result = getShareUrl('facebook', text, url, title)
    expect(result).toBe(
      `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}&quote=${encodeURIComponent(title)}`,
    )
  })

  it('returns LinkedIn share URL', () => {
    const result = getShareUrl('linkedin', text, url, title)
    expect(result).toBe(
      `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`,
    )
  })

  it('returns Reddit submit URL', () => {
    const result = getShareUrl('reddit', text, url, title)
    expect(result).toBe(
      `https://www.reddit.com/submit?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}`,
    )
  })

  it('returns mailto URL for email', () => {
    const result = getShareUrl('email', text, url, title)
    expect(result).toBe(
      `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(text)}`,
    )
  })

  it('returns Mastodon share URL with instance', () => {
    const result = getShareUrl('mastodon', text, url, title, 'mastodon.social')
    expect(result).toBe(
      `https://mastodon.social/share?text=${encodeURIComponent(text)}`,
    )
  })

  it('returns empty string for mastodon without instance', () => {
    const result = getShareUrl('mastodon', text, url, title)
    expect(result).toBe('')
  })
})

describe('canNativeShare', () => {
  const originalNavigator = globalThis.navigator

  afterEach(() => {
    Object.defineProperty(globalThis, 'navigator', {
      value: originalNavigator,
      writable: true,
    })
  })

  it('returns true when navigator.share is available', () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...originalNavigator, share: vi.fn() },
      writable: true,
    })
    expect(canNativeShare()).toBe(true)
  })

  it('returns false when navigator.share is unavailable', () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...originalNavigator, share: undefined },
      writable: true,
    })
    expect(canNativeShare()).toBe(false)
  })
})

describe('nativeShare', () => {
  it('calls navigator.share with correct data', async () => {
    const mockShare = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...globalThis.navigator, share: mockShare },
      writable: true,
    })

    await nativeShare('Title', 'Text', 'https://example.com')
    expect(mockShare).toHaveBeenCalledWith({
      title: 'Title',
      text: 'Text',
      url: 'https://example.com',
    })
  })
})

describe('copyToClipboard', () => {
  it('returns true on success', async () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...globalThis.navigator, clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } },
      writable: true,
    })
    const result = await copyToClipboard('text')
    expect(result).toBe(true)
  })

  it('returns false on failure', async () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...globalThis.navigator, clipboard: { writeText: vi.fn().mockRejectedValue(new Error('fail')) } },
      writable: true,
    })
    const result = await copyToClipboard('text')
    expect(result).toBe(false)
  })
})

describe('mastodon instance localStorage', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns null when no instance saved', () => {
    expect(getMastodonInstance()).toBeNull()
  })

  it('saves and retrieves instance', () => {
    setMastodonInstance('mastodon.social')
    expect(getMastodonInstance()).toBe('mastodon.social')
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/share/__tests__/shareUtils.test.ts`
Expected: FAIL — module not found

**Step 3: Write the implementation**

Create `frontend/src/components/share/shareUtils.ts`:

```typescript
const MASTODON_INSTANCE_KEY = 'agblogger:mastodon-instance'

export function getShareText(title: string, author: string | null, url: string): string {
  if (author) {
    return `\u201c${title}\u201d by ${author} ${url}`
  }
  return `\u201c${title}\u201d ${url}`
}

export function getShareUrl(
  platform: string,
  text: string,
  url: string,
  title: string,
  mastodonInstance?: string,
): string {
  switch (platform) {
    case 'bluesky':
      return `https://bsky.app/intent/compose?text=${encodeURIComponent(text)}`
    case 'mastodon':
      if (!mastodonInstance) return ''
      return `https://${mastodonInstance}/share?text=${encodeURIComponent(text)}`
    case 'x':
      return `https://x.com/intent/tweet?text=${encodeURIComponent(text)}`
    case 'facebook':
      return `https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(url)}&quote=${encodeURIComponent(title)}`
    case 'linkedin':
      return `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`
    case 'reddit':
      return `https://www.reddit.com/submit?url=${encodeURIComponent(url)}&title=${encodeURIComponent(title)}`
    case 'email':
      return `mailto:?subject=${encodeURIComponent(title)}&body=${encodeURIComponent(text)}`
    default:
      return ''
  }
}

export function canNativeShare(): boolean {
  return typeof navigator !== 'undefined' && typeof navigator.share === 'function'
}

export async function nativeShare(title: string, text: string, url: string): Promise<void> {
  await navigator.share({ title, text, url })
}

export async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    return false
  }
}

export function getMastodonInstance(): string | null {
  return localStorage.getItem(MASTODON_INSTANCE_KEY)
}

export function setMastodonInstance(instance: string): void {
  localStorage.setItem(MASTODON_INSTANCE_KEY, instance)
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/share/__tests__/shareUtils.test.ts`
Expected: PASS — all tests green

**Step 5: Commit**

```bash
git add frontend/src/components/share/shareUtils.ts frontend/src/components/share/__tests__/shareUtils.test.ts
git commit -m "feat: add share utility module with URL generation and native share support"
```

---

### Task 2: Platform Icons for Share Platforms

**Files:**
- Modify: `frontend/src/components/crosspost/PlatformIcon.tsx`

The existing `PlatformIcon` component handles Bluesky and Mastodon. We need to add X, Facebook, LinkedIn, and Reddit icons. This keeps icons in one place instead of duplicating.

**Step 1: Write the failing test**

Create `frontend/src/components/crosspost/__tests__/PlatformIcon.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import PlatformIcon from '../PlatformIcon'

describe('PlatformIcon', () => {
  it('renders Bluesky icon', () => {
    render(<PlatformIcon platform="bluesky" />)
    expect(screen.getByLabelText('Bluesky')).toBeInTheDocument()
  })

  it('renders Mastodon icon', () => {
    render(<PlatformIcon platform="mastodon" />)
    expect(screen.getByLabelText('Mastodon')).toBeInTheDocument()
  })

  it('renders X icon', () => {
    render(<PlatformIcon platform="x" />)
    expect(screen.getByLabelText('X')).toBeInTheDocument()
  })

  it('renders Facebook icon', () => {
    render(<PlatformIcon platform="facebook" />)
    expect(screen.getByLabelText('Facebook')).toBeInTheDocument()
  })

  it('renders LinkedIn icon', () => {
    render(<PlatformIcon platform="linkedin" />)
    expect(screen.getByLabelText('LinkedIn')).toBeInTheDocument()
  })

  it('renders Reddit icon', () => {
    render(<PlatformIcon platform="reddit" />)
    expect(screen.getByLabelText('Reddit')).toBeInTheDocument()
  })

  it('renders fallback for unknown platform', () => {
    render(<PlatformIcon platform="unknown" />)
    expect(screen.getByLabelText('unknown')).toBeInTheDocument()
  })

  it('applies custom size', () => {
    render(<PlatformIcon platform="bluesky" size={24} />)
    const icon = screen.getByLabelText('Bluesky')
    expect(icon).toHaveAttribute('width', '24')
    expect(icon).toHaveAttribute('height', '24')
  })
})
```

**Step 2: Run tests to verify new platform tests fail**

Run: `cd frontend && npx vitest run src/components/crosspost/__tests__/PlatformIcon.test.tsx`
Expected: FAIL for X, Facebook, LinkedIn, Reddit (no aria-label match)

**Step 3: Add new platform icons to PlatformIcon.tsx**

Add `if` blocks for `x`, `facebook`, `linkedin`, `reddit` before the fallback `return`, using official brand SVG paths. Each SVG should use `width={size}`, `height={size}`, `fill="currentColor"`, `className={className}`, and `aria-label="{PlatformName}"`.

SVG paths to use:
- **X (Twitter)**: Simple X lettermark from the brand kit
- **Facebook**: F logo
- **LinkedIn**: "in" logo
- **Reddit**: Snoo head outline

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/crosspost/__tests__/PlatformIcon.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/crosspost/PlatformIcon.tsx frontend/src/components/crosspost/__tests__/PlatformIcon.test.tsx
git commit -m "feat: add X, Facebook, LinkedIn, Reddit icons to PlatformIcon"
```

---

### Task 3: MastodonSharePrompt Component

**Files:**
- Create: `frontend/src/components/share/MastodonSharePrompt.tsx`
- Test: `frontend/src/components/share/__tests__/MastodonSharePrompt.test.tsx`

**Step 1: Write the failing tests**

Create `frontend/src/components/share/__tests__/MastodonSharePrompt.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import MastodonSharePrompt from '../MastodonSharePrompt'

describe('MastodonSharePrompt', () => {
  const defaultProps = {
    shareText: '"Hello World" by Alice https://example.com/post/hello',
    onClose: vi.fn(),
  }

  beforeEach(() => {
    localStorage.clear()
    vi.resetAllMocks()
  })

  it('renders instance input and share button', () => {
    render(<MastodonSharePrompt {...defaultProps} />)
    expect(screen.getByPlaceholderText('mastodon.social')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Share' })).toBeInTheDocument()
  })

  it('pre-fills input with saved instance from localStorage', () => {
    localStorage.setItem('agblogger:mastodon-instance', 'hachyderm.io')
    render(<MastodonSharePrompt {...defaultProps} />)
    expect(screen.getByPlaceholderText('mastodon.social')).toHaveValue('hachyderm.io')
  })

  it('disables share button when input is empty', () => {
    render(<MastodonSharePrompt {...defaultProps} />)
    expect(screen.getByRole('button', { name: 'Share' })).toBeDisabled()
  })

  it('opens share URL and saves instance on submit', async () => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<MastodonSharePrompt {...defaultProps} />)

    await user.type(screen.getByPlaceholderText('mastodon.social'), 'mastodon.social')
    await user.click(screen.getByRole('button', { name: 'Share' }))

    expect(windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('https://mastodon.social/share?text='),
      '_blank',
      'noopener,noreferrer',
    )
    expect(localStorage.getItem('agblogger:mastodon-instance')).toBe('mastodon.social')
    expect(defaultProps.onClose).toHaveBeenCalled()
    windowOpen.mockRestore()
  })

  it('calls onClose when cancel button is clicked', async () => {
    const user = userEvent.setup()
    render(<MastodonSharePrompt {...defaultProps} />)

    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(defaultProps.onClose).toHaveBeenCalled()
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/share/__tests__/MastodonSharePrompt.test.tsx`
Expected: FAIL — module not found

**Step 3: Write the implementation**

Create `frontend/src/components/share/MastodonSharePrompt.tsx`:

```tsx
import { useState } from 'react'
import { getMastodonInstance, setMastodonInstance, getShareUrl } from './shareUtils'

interface MastodonSharePromptProps {
  shareText: string
  onClose: () => void
}

export default function MastodonSharePrompt({ shareText, onClose }: MastodonSharePromptProps) {
  const [instance, setInstance] = useState(getMastodonInstance() ?? '')

  function handleShare() {
    const trimmed = instance.trim()
    if (!trimmed) return
    setMastodonInstance(trimmed)
    const url = getShareUrl('mastodon', shareText, '', '', trimmed)
    window.open(url, '_blank', 'noopener,noreferrer')
    onClose()
  }

  return (
    <div className="p-3 bg-paper-warm border border-border rounded-lg space-y-2 animate-fade-in">
      <label className="text-xs font-medium text-muted">Mastodon instance</label>
      <div className="flex gap-2">
        <input
          type="text"
          value={instance}
          onChange={(e) => setInstance(e.target.value)}
          placeholder="mastodon.social"
          className="flex-1 px-2.5 py-1.5 text-sm border border-border rounded-lg bg-paper
                   focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20"
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleShare()
          }}
        />
        <button
          onClick={handleShare}
          disabled={!instance.trim()}
          className="px-3 py-1.5 text-sm font-medium text-white bg-accent hover:bg-accent-light
                   rounded-lg transition-colors disabled:opacity-50"
        >
          Share
        </button>
        <button
          onClick={onClose}
          className="px-3 py-1.5 text-sm font-medium text-muted hover:text-ink
                   border border-border rounded-lg transition-colors"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/share/__tests__/MastodonSharePrompt.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/share/MastodonSharePrompt.tsx frontend/src/components/share/__tests__/MastodonSharePrompt.test.tsx
git commit -m "feat: add MastodonSharePrompt component with instance localStorage"
```

---

### Task 4: ShareBar Component (Bottom of Post)

**Files:**
- Create: `frontend/src/components/share/ShareBar.tsx`
- Test: `frontend/src/components/share/__tests__/ShareBar.test.tsx`

**Step 1: Write the failing tests**

Create `frontend/src/components/share/__tests__/ShareBar.test.tsx`:

```typescript
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import ShareBar from '../ShareBar'

// Save original navigator
const originalNavigator = globalThis.navigator

describe('ShareBar', () => {
  const defaultProps = {
    title: 'Hello World',
    author: 'Alice' as string | null,
    url: 'https://blog.example.com/post/hello',
  }

  beforeEach(() => {
    localStorage.clear()
    vi.resetAllMocks()
  })

  afterEach(() => {
    Object.defineProperty(globalThis, 'navigator', {
      value: originalNavigator,
      writable: true,
    })
  })

  it('renders all platform share buttons', () => {
    render(<ShareBar {...defaultProps} />)
    expect(screen.getByLabelText('Share on Bluesky')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on Mastodon')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on X')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on Facebook')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on LinkedIn')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on Reddit')).toBeInTheDocument()
    expect(screen.getByLabelText('Share via email')).toBeInTheDocument()
    expect(screen.getByLabelText('Copy link')).toBeInTheDocument()
  })

  it('opens share URL in new tab when platform button is clicked', async () => {
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<ShareBar {...defaultProps} />)

    await user.click(screen.getByLabelText('Share on Bluesky'))

    expect(windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('https://bsky.app/intent/compose?text='),
      '_blank',
      'noopener,noreferrer',
    )
    windowOpen.mockRestore()
  })

  it('shows mastodon instance prompt when mastodon button clicked and no saved instance', async () => {
    const user = userEvent.setup()
    render(<ShareBar {...defaultProps} />)

    await user.click(screen.getByLabelText('Share on Mastodon'))

    expect(screen.getByPlaceholderText('mastodon.social')).toBeInTheDocument()
  })

  it('shares to mastodon directly when instance is saved in localStorage', async () => {
    localStorage.setItem('agblogger:mastodon-instance', 'hachyderm.io')
    const windowOpen = vi.spyOn(window, 'open').mockReturnValue(null)
    const user = userEvent.setup()
    render(<ShareBar {...defaultProps} />)

    await user.click(screen.getByLabelText('Share on Mastodon'))

    expect(windowOpen).toHaveBeenCalledWith(
      expect.stringContaining('https://hachyderm.io/share?text='),
      '_blank',
      'noopener,noreferrer',
    )
    windowOpen.mockRestore()
  })

  it('copies link and shows feedback on copy button click', async () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...originalNavigator, clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } },
      writable: true,
    })
    const user = userEvent.setup()
    render(<ShareBar {...defaultProps} />)

    await user.click(screen.getByLabelText('Copy link'))

    await waitFor(() => {
      expect(screen.getByText('Copied!')).toBeInTheDocument()
    })
  })

  it('shows native share button when navigator.share is available', () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...originalNavigator, share: vi.fn() },
      writable: true,
    })
    render(<ShareBar {...defaultProps} />)
    expect(screen.getByLabelText('Share via device')).toBeInTheDocument()
  })

  it('hides native share button when navigator.share is unavailable', () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...originalNavigator, share: undefined },
      writable: true,
    })
    render(<ShareBar {...defaultProps} />)
    expect(screen.queryByLabelText('Share via device')).not.toBeInTheDocument()
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/share/__tests__/ShareBar.test.tsx`
Expected: FAIL — module not found

**Step 3: Write the implementation**

Create `frontend/src/components/share/ShareBar.tsx`:

```tsx
import { useState } from 'react'
import { Share2, Mail, Link, Check } from 'lucide-react'
import PlatformIcon from '@/components/crosspost/PlatformIcon'
import MastodonSharePrompt from './MastodonSharePrompt'
import {
  getShareText,
  getShareUrl,
  canNativeShare,
  nativeShare,
  copyToClipboard,
  getMastodonInstance,
} from './shareUtils'

interface ShareBarProps {
  title: string
  author: string | null
  url: string
}

const PLATFORMS = [
  { id: 'bluesky', label: 'Share on Bluesky' },
  { id: 'mastodon', label: 'Share on Mastodon' },
  { id: 'x', label: 'Share on X' },
  { id: 'facebook', label: 'Share on Facebook' },
  { id: 'linkedin', label: 'Share on LinkedIn' },
  { id: 'reddit', label: 'Share on Reddit' },
] as const

export default function ShareBar({ title, author, url }: ShareBarProps) {
  const [showMastodonPrompt, setShowMastodonPrompt] = useState(false)
  const [copied, setCopied] = useState(false)

  const shareText = getShareText(title, author, url)

  function handlePlatformClick(platformId: string) {
    if (platformId === 'mastodon') {
      const instance = getMastodonInstance()
      if (instance) {
        const shareUrl = getShareUrl('mastodon', shareText, url, title, instance)
        window.open(shareUrl, '_blank', 'noopener,noreferrer')
      } else {
        setShowMastodonPrompt(true)
      }
      return
    }

    const shareUrl = getShareUrl(platformId, shareText, url, title)
    if (shareUrl) {
      window.open(shareUrl, '_blank', 'noopener,noreferrer')
    }
  }

  function handleEmailClick() {
    const emailUrl = getShareUrl('email', shareText, url, title)
    window.location.href = emailUrl
  }

  async function handleCopy() {
    const success = await copyToClipboard(url)
    if (success) {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  async function handleNativeShare() {
    try {
      await nativeShare(title, shareText, url)
    } catch {
      // User cancelled or share failed — no action needed
    }
  }

  return (
    <div className="mt-10 pt-6 border-t border-border">
      <div className="flex items-center gap-1 flex-wrap">
        {canNativeShare() && (
          <button
            onClick={() => void handleNativeShare()}
            aria-label="Share via device"
            className="p-2 text-muted hover:text-ink transition-colors rounded-lg hover:bg-paper-warm"
            title="Share"
          >
            <Share2 size={18} />
          </button>
        )}

        {PLATFORMS.map((platform) => (
          <button
            key={platform.id}
            onClick={() => handlePlatformClick(platform.id)}
            aria-label={platform.label}
            className="p-2 text-muted hover:text-ink transition-colors rounded-lg hover:bg-paper-warm"
            title={platform.label}
          >
            <PlatformIcon platform={platform.id} size={18} />
          </button>
        ))}

        <button
          onClick={handleEmailClick}
          aria-label="Share via email"
          className="p-2 text-muted hover:text-ink transition-colors rounded-lg hover:bg-paper-warm"
          title="Share via email"
        >
          <Mail size={18} />
        </button>

        <button
          onClick={() => void handleCopy()}
          aria-label="Copy link"
          className="p-2 text-muted hover:text-ink transition-colors rounded-lg hover:bg-paper-warm"
          title="Copy link"
        >
          {copied ? <Check size={18} className="text-green-600" /> : <Link size={18} />}
        </button>

        {copied && (
          <span className="text-xs text-green-600 font-medium animate-fade-in">Copied!</span>
        )}
      </div>

      {showMastodonPrompt && (
        <div className="mt-3">
          <MastodonSharePrompt
            shareText={shareText}
            onClose={() => setShowMastodonPrompt(false)}
          />
        </div>
      )}
    </div>
  )
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/share/__tests__/ShareBar.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/share/ShareBar.tsx frontend/src/components/share/__tests__/ShareBar.test.tsx
git commit -m "feat: add ShareBar component with platform buttons and copy link"
```

---

### Task 5: ShareButton Component (Header)

**Files:**
- Create: `frontend/src/components/share/ShareButton.tsx`
- Test: `frontend/src/components/share/__tests__/ShareButton.test.tsx`

**Step 1: Write the failing tests**

Create `frontend/src/components/share/__tests__/ShareButton.test.tsx`:

```typescript
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import ShareButton from '../ShareButton'

const originalNavigator = globalThis.navigator

describe('ShareButton', () => {
  const defaultProps = {
    title: 'Hello World',
    author: 'Alice' as string | null,
    url: 'https://blog.example.com/post/hello',
  }

  beforeEach(() => {
    localStorage.clear()
    vi.resetAllMocks()
  })

  afterEach(() => {
    Object.defineProperty(globalThis, 'navigator', {
      value: originalNavigator,
      writable: true,
    })
  })

  it('renders a share button', () => {
    render(<ShareButton {...defaultProps} />)
    expect(screen.getByLabelText('Share this post')).toBeInTheDocument()
  })

  it('calls native share directly when available', async () => {
    const mockShare = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...originalNavigator, share: mockShare },
      writable: true,
    })
    const user = userEvent.setup()
    render(<ShareButton {...defaultProps} />)

    await user.click(screen.getByLabelText('Share this post'))

    expect(mockShare).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Hello World',
        url: 'https://blog.example.com/post/hello',
      }),
    )
  })

  it('opens dropdown when native share is unavailable', async () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...originalNavigator, share: undefined },
      writable: true,
    })
    const user = userEvent.setup()
    render(<ShareButton {...defaultProps} />)

    await user.click(screen.getByLabelText('Share this post'))

    // Platform buttons should appear in dropdown
    expect(screen.getByLabelText('Share on Bluesky')).toBeInTheDocument()
    expect(screen.getByLabelText('Share on X')).toBeInTheDocument()
  })

  it('closes dropdown when clicking outside', async () => {
    Object.defineProperty(globalThis, 'navigator', {
      value: { ...originalNavigator, share: undefined },
      writable: true,
    })
    const user = userEvent.setup()
    render(
      <div>
        <ShareButton {...defaultProps} />
        <span>outside</span>
      </div>,
    )

    await user.click(screen.getByLabelText('Share this post'))
    expect(screen.getByLabelText('Share on Bluesky')).toBeInTheDocument()

    await user.click(screen.getByText('outside'))
    expect(screen.queryByLabelText('Share on Bluesky')).not.toBeInTheDocument()
  })
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/components/share/__tests__/ShareButton.test.tsx`
Expected: FAIL — module not found

**Step 3: Write the implementation**

Create `frontend/src/components/share/ShareButton.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import { Share2, Mail, Link, Check } from 'lucide-react'
import PlatformIcon from '@/components/crosspost/PlatformIcon'
import MastodonSharePrompt from './MastodonSharePrompt'
import {
  getShareText,
  getShareUrl,
  canNativeShare,
  nativeShare,
  copyToClipboard,
  getMastodonInstance,
} from './shareUtils'

interface ShareButtonProps {
  title: string
  author: string | null
  url: string
}

const PLATFORMS = [
  { id: 'bluesky', label: 'Share on Bluesky' },
  { id: 'mastodon', label: 'Share on Mastodon' },
  { id: 'x', label: 'Share on X' },
  { id: 'facebook', label: 'Share on Facebook' },
  { id: 'linkedin', label: 'Share on LinkedIn' },
  { id: 'reddit', label: 'Share on Reddit' },
] as const

export default function ShareButton({ title, author, url }: ShareButtonProps) {
  const [showDropdown, setShowDropdown] = useState(false)
  const [showMastodonPrompt, setShowMastodonPrompt] = useState(false)
  const [copied, setCopied] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  const shareText = getShareText(title, author, url)

  useEffect(() => {
    if (!showDropdown) return
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
        setShowMastodonPrompt(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showDropdown])

  async function handleClick() {
    if (canNativeShare()) {
      try {
        await nativeShare(title, shareText, url)
      } catch {
        // User cancelled
      }
    } else {
      setShowDropdown((prev) => !prev)
    }
  }

  function handlePlatformClick(platformId: string) {
    if (platformId === 'mastodon') {
      const instance = getMastodonInstance()
      if (instance) {
        const shareUrl = getShareUrl('mastodon', shareText, url, title, instance)
        window.open(shareUrl, '_blank', 'noopener,noreferrer')
        setShowDropdown(false)
      } else {
        setShowMastodonPrompt(true)
      }
      return
    }
    const shareUrl = getShareUrl(platformId, shareText, url, title)
    if (shareUrl) {
      window.open(shareUrl, '_blank', 'noopener,noreferrer')
      setShowDropdown(false)
    }
  }

  function handleEmailClick() {
    const emailUrl = getShareUrl('email', shareText, url, title)
    window.location.href = emailUrl
    setShowDropdown(false)
  }

  async function handleCopy() {
    const success = await copyToClipboard(url)
    if (success) {
      setCopied(true)
      setTimeout(() => {
        setCopied(false)
        setShowDropdown(false)
      }, 1500)
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => void handleClick()}
        aria-label="Share this post"
        className="flex items-center gap-1 text-muted hover:text-ink transition-colors"
        title="Share this post"
      >
        <Share2 size={14} />
        <span className="text-sm">Share</span>
      </button>

      {showDropdown && (
        <div className="absolute right-0 top-full mt-2 p-2 bg-paper border border-border rounded-xl shadow-lg z-40 animate-fade-in min-w-[200px]">
          {showMastodonPrompt ? (
            <MastodonSharePrompt
              shareText={shareText}
              onClose={() => {
                setShowMastodonPrompt(false)
                setShowDropdown(false)
              }}
            />
          ) : (
            <div className="space-y-0.5">
              {PLATFORMS.map((platform) => (
                <button
                  key={platform.id}
                  onClick={() => handlePlatformClick(platform.id)}
                  aria-label={platform.label}
                  className="flex items-center gap-2.5 w-full px-3 py-2 text-sm text-muted
                           hover:text-ink hover:bg-paper-warm rounded-lg transition-colors"
                >
                  <PlatformIcon platform={platform.id} size={16} />
                  <span>{platform.label.replace('Share on ', '')}</span>
                </button>
              ))}
              <button
                onClick={handleEmailClick}
                aria-label="Share via email"
                className="flex items-center gap-2.5 w-full px-3 py-2 text-sm text-muted
                         hover:text-ink hover:bg-paper-warm rounded-lg transition-colors"
              >
                <Mail size={16} />
                <span>Email</span>
              </button>
              <div className="border-t border-border my-1" />
              <button
                onClick={() => void handleCopy()}
                aria-label="Copy link"
                className="flex items-center gap-2.5 w-full px-3 py-2 text-sm text-muted
                         hover:text-ink hover:bg-paper-warm rounded-lg transition-colors"
              >
                {copied ? (
                  <>
                    <Check size={16} className="text-green-600" />
                    <span className="text-green-600">Copied!</span>
                  </>
                ) : (
                  <>
                    <Link size={16} />
                    <span>Copy link</span>
                  </>
                )}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
```

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/components/share/__tests__/ShareButton.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/components/share/ShareButton.tsx frontend/src/components/share/__tests__/ShareButton.test.tsx
git commit -m "feat: add ShareButton header component with dropdown and native share"
```

---

### Task 6: Integrate Share Components into PostPage

**Files:**
- Modify: `frontend/src/pages/PostPage.tsx`
- Test: `frontend/src/pages/__tests__/PostPage.test.tsx` (modify existing tests)

**Step 1: Write the failing test**

Add tests to `frontend/src/pages/__tests__/PostPage.test.tsx`:

```typescript
// Add to existing test file:
it('shows share button in header for all users including unauthenticated', async () => {
  mockUser = null
  renderPostPage()
  await waitFor(() => {
    expect(screen.getByText('Hello World')).toBeInTheDocument()
  })
  expect(screen.getByLabelText('Share this post')).toBeInTheDocument()
})

it('shows share bar at bottom of post for all users', async () => {
  mockUser = null
  renderPostPage()
  await waitFor(() => {
    expect(screen.getByText('Hello World')).toBeInTheDocument()
  })
  expect(screen.getByLabelText('Share on Bluesky')).toBeInTheDocument()
})

it('shows both share UI and cross-posting section for admins', async () => {
  mockUser = { id: 1, username: 'admin', email: 'a@b.com', display_name: 'Admin', is_admin: true }
  renderPostPage()
  await waitFor(() => {
    expect(screen.getByText('Hello World')).toBeInTheDocument()
  })
  // Share UI (for everyone)
  expect(screen.getByLabelText('Share this post')).toBeInTheDocument()
  // Cross-posting section (admin only)
  expect(screen.getByText('Cross-posting')).toBeInTheDocument()
})
```

**Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/pages/__tests__/PostPage.test.tsx`
Expected: FAIL — share components not rendered yet

**Step 3: Integrate into PostPage**

Modify `frontend/src/pages/PostPage.tsx`:

1. Add imports at top:
```typescript
import ShareButton from '@/components/share/ShareButton'
import ShareBar from '@/components/share/ShareBar'
```

2. Add `ShareButton` in the metadata `div` (around line 135, after labels, before the admin edit/delete links). Add it as a share link alongside the metadata items — visible to all users:
```tsx
{/* After labels div, still inside the flex items-center gap-4 div */}
<ShareButton
  title={post.title}
  author={post.author}
  url={window.location.href}
/>
```

3. Add `ShareBar` between the prose content and the CrossPostSection (around line 174):
```tsx
{/* After the prose div, before CrossPostSection */}
<ShareBar
  title={post.title}
  author={post.author}
  url={window.location.href}
/>
```

The key difference: `ShareBar` and `ShareButton` are NOT gated behind auth — they render for all users. The `CrossPostSection` below remains admin-only.

**Step 4: Run tests to verify they pass**

Run: `cd frontend && npx vitest run src/pages/__tests__/PostPage.test.tsx`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/pages/PostPage.tsx frontend/src/pages/__tests__/PostPage.test.tsx
git commit -m "feat: integrate share button and bar into post page for all users"
```

---

### Task 7: Static Checks and Full Test Suite

**Files:** None new — validation only

**Step 1: Run frontend static checks**

Run: `just check-frontend-static`
Expected: PASS. If there are lint/type errors, fix them.

Common things to watch for:
- Unused imports (knip check)
- Missing type annotations
- ESLint type-checked rule violations
- dependency-cruiser violations (circular imports)

**Step 2: Run full frontend tests**

Run: `just test-frontend`
Expected: PASS

**Step 3: Run full check**

Run: `just check`
Expected: PASS

**Step 4: Commit any fixes**

If static checks or tests required fixes, commit them:
```bash
git add -A
git commit -m "fix: resolve static check issues in share components"
```

---

### Task 8: Browser Testing

**Files:** None — manual verification via Playwright MCP

**Step 1: Start dev server**

Run: `just start`

**Step 2: Verify unauthenticated user experience**

Using the Playwright MCP browser:
1. Navigate to a post page
2. Verify ShareButton appears in the header metadata row
3. Verify ShareBar appears at the bottom of the post
4. Click ShareButton — verify dropdown opens (in jsdom test env, native share won't work)
5. Click a platform button — verify new tab opens with correct share URL
6. Click Copy link — verify "Copied!" feedback
7. Click Mastodon — verify instance prompt appears
8. Enter an instance and share — verify it opens correctly and remembers the instance
9. Click Mastodon again — verify it shares directly (skips prompt)
10. Verify NO cross-posting section is visible

**Step 3: Verify admin user experience**

1. Log in as admin
2. Navigate to a post page
3. Verify ShareButton in header (same as unauthenticated)
4. Verify ShareBar at bottom
5. Verify Cross-posting section appears BELOW the ShareBar
6. Both features should be fully functional and visually separated

**Step 4: Stop dev server**

Run: `just stop`

**Step 5: Clean up screenshots**

Remove any `*.png` files created during browser testing.

---

### Task 9: Update Architecture Documentation

**Files:**
- Modify: `docs/ARCHITECTURE.md`

Update the following sections:

1. In **Frontend Architecture > Routing** table, no changes needed (PostPage route unchanged).

2. In **Cross-Posting UI** section, add a new subsection or note:

```markdown
### Post Sharing (Public)

A client-side sharing feature available to all users (including unauthenticated):

- **ShareButton** (header): Compact share icon in the post metadata row. Uses Web Share API when available; falls back to a dropdown with platform buttons.
- **ShareBar** (bottom of post): Horizontal row of platform icon buttons below post content.
- **Platforms**: Bluesky, Mastodon, X, Facebook, LinkedIn, Reddit, Email, Copy Link.
- **Mastodon**: Prompts for instance URL on first use, remembers in `localStorage`.
- **Share text format**: `"{title}" by {author} {url}` — attributed format that signals shared content.
- **No backend involvement**: All share URLs are constructed client-side. No credentials stored.

This is separate from the admin cross-posting feature, which posts server-side via stored OAuth credentials.
```

**Commit:**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add post sharing section to architecture documentation"
```
