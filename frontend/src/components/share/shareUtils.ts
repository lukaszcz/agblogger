const MASTODON_INSTANCE_KEY = 'agblogger:mastodon-instance'

export function getShareText(title: string, author: string | null, url: string): string {
  if (author !== null) {
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
      if (mastodonInstance === undefined || mastodonInstance === '') return ''
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
