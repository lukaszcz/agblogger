import { useEffect, useRef, useState } from 'react'
import { Check, Link, Mail, Share2 } from 'lucide-react'

import PlatformIcon from '@/components/crosspost/PlatformIcon'

import MastodonSharePrompt from './MastodonSharePrompt'
import {
  canNativeShare,
  copyToClipboard,
  getMastodonInstance,
  getShareText,
  getShareUrl,
  nativeShare,
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
      if (dropdownRef.current !== null && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false)
        setShowMastodonPrompt(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
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
      if (instance !== null) {
        const shareUrl = getShareUrl('mastodon', shareText, url, title, instance)
        window.open(shareUrl, '_blank', 'noopener,noreferrer')
        setShowDropdown(false)
      } else {
        setShowMastodonPrompt(true)
      }
      return
    }
    const shareUrl = getShareUrl(platformId, shareText, url, title)
    if (shareUrl !== '') {
      window.open(shareUrl, '_blank', 'noopener,noreferrer')
      setShowDropdown(false)
    }
  }

  function handleEmailClick() {
    const emailUrl = getShareUrl('email', shareText, url, title)
    window.open(emailUrl, '_self')
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
        className="flex items-center gap-1 text-muted transition-colors hover:text-ink"
        title="Share this post"
      >
        <Share2 size={14} />
        <span className="text-sm">Share</span>
      </button>

      {showDropdown && (
        <div className="animate-fade-in absolute right-0 top-full z-40 mt-2 min-w-[200px] rounded-xl border border-border bg-paper p-2 shadow-lg">
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
                  onClick={() => {
                    handlePlatformClick(platform.id)
                  }}
                  aria-label={platform.label}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm
                           text-muted transition-colors hover:bg-paper-warm hover:text-ink"
                >
                  <PlatformIcon platform={platform.id} size={16} />
                  <span>{platform.label.replace('Share on ', '')}</span>
                </button>
              ))}
              <button
                onClick={handleEmailClick}
                aria-label="Share via email"
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm
                         text-muted transition-colors hover:bg-paper-warm hover:text-ink"
              >
                <Mail size={16} />
                <span>Email</span>
              </button>
              <div className="my-1 border-t border-border" />
              <button
                onClick={() => void handleCopy()}
                aria-label="Copy link"
                className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm
                         text-muted transition-colors hover:bg-paper-warm hover:text-ink"
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
