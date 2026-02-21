import { useEffect, useState } from 'react'
import { Share2, Trash2, Plus, Loader2 } from 'lucide-react'

import {
  fetchSocialAccounts,
  deleteSocialAccount,
  authorizeBluesky,
  authorizeMastodon,
} from '@/api/crosspost'
import type { SocialAccount } from '@/api/crosspost'
import { HTTPError } from '@/api/client'
import PlatformIcon from '@/components/crosspost/PlatformIcon'

interface SocialAccountsPanelProps {
  busy: boolean
  onBusyChange: (busy: boolean) => void
}

function formatDate(iso: string): string {
  const date = new Date(iso)
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export default function SocialAccountsPanel({ busy, onBusyChange }: SocialAccountsPanelProps) {
  const [accounts, setAccounts] = useState<SocialAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  // Connect form state
  const [connectingPlatform, setConnectingPlatform] = useState<'bluesky' | 'mastodon' | null>(null)
  const [handle, setHandle] = useState('')
  const [instanceUrl, setInstanceUrl] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Disconnect confirmation state
  const [deleteConfirmId, setDeleteConfirmId] = useState<number | null>(null)
  const [deleting, setDeleting] = useState(false)

  const localBusy = submitting || deleting

  useEffect(() => {
    onBusyChange(localBusy)
  }, [localBusy, onBusyChange])

  useEffect(() => {
    void loadAccounts()
  }, [])

  async function loadAccounts() {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchSocialAccounts()
      setAccounts(data)
    } catch (err) {
      if (err instanceof HTTPError && err.response.status === 401) {
        setError('Session expired. Please log in again.')
      } else {
        setError('Failed to load social accounts.')
      }
    } finally {
      setLoading(false)
    }
  }

  async function handleConnectBluesky() {
    const trimmed = handle.trim()
    if (!trimmed) return
    setSubmitting(true)
    setError(null)
    setSuccess(null)
    try {
      const { authorization_url } = await authorizeBluesky(trimmed)
      window.location.href = authorization_url
    } catch (err) {
      if (err instanceof HTTPError && err.response.status === 401) {
        setError('Session expired. Please log in again.')
      } else {
        setError('Failed to start Bluesky authorization. Please try again.')
      }
      setSubmitting(false)
    }
  }

  async function handleConnectMastodon() {
    const trimmed = instanceUrl.trim()
    if (!trimmed) return
    setSubmitting(true)
    setError(null)
    setSuccess(null)
    try {
      const { authorization_url } = await authorizeMastodon(trimmed)
      window.location.href = authorization_url
    } catch (err) {
      if (err instanceof HTTPError && err.response.status === 401) {
        setError('Session expired. Please log in again.')
      } else {
        setError('Failed to start Mastodon authorization. Please try again.')
      }
      setSubmitting(false)
    }
  }

  async function handleDisconnect(accountId: number) {
    setDeleting(true)
    setError(null)
    setSuccess(null)
    try {
      await deleteSocialAccount(accountId)
      setAccounts((prev) => prev.filter((a) => a.id !== accountId))
      setDeleteConfirmId(null)
      setSuccess('Account disconnected.')
    } catch (err) {
      if (err instanceof HTTPError && err.response.status === 401) {
        setError('Session expired. Please log in again.')
      } else {
        setError('Failed to disconnect account. Please try again.')
      }
    } finally {
      setDeleting(false)
    }
  }

  const allBusy = busy || localBusy

  return (
    <section className="mb-8 p-5 bg-paper border border-border rounded-lg">
      <div className="flex items-center gap-2 mb-4">
        <Share2 size={16} className="text-accent" />
        <h2 className="text-sm font-medium text-ink">Social Accounts</h2>
      </div>

      {error !== null && (
        <div className="mb-4 text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-4 py-3">
          {error}
        </div>
      )}
      {success !== null && (
        <div className="mb-4 text-sm text-green-700 bg-green-50 border border-green-200 rounded-lg px-4 py-3">
          {success}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-6">
          <Loader2 size={20} className="text-accent animate-spin" />
        </div>
      ) : (
        <>
          {/* Connected accounts list */}
          {accounts.length > 0 && (
            <div className="space-y-2 mb-4">
              {accounts.map((account) => (
                <div
                  key={account.id}
                  className="flex items-center gap-3 px-4 py-3 border border-border rounded-lg"
                >
                  <PlatformIcon platform={account.platform} size={20} className="text-muted" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-ink truncate">
                      {account.account_name ?? account.platform}
                    </p>
                    <p className="text-xs text-muted">
                      Connected {formatDate(account.created_at)}
                    </p>
                  </div>
                  {deleteConfirmId === account.id ? (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-red-600">Confirm disconnect?</span>
                      <button
                        onClick={() => void handleDisconnect(account.id)}
                        disabled={allBusy}
                        className="px-3 py-1 text-xs font-medium bg-red-600 text-white rounded-lg
                                 hover:bg-red-700 disabled:opacity-50 transition-colors"
                      >
                        {deleting ? 'Removing...' : 'Confirm'}
                      </button>
                      <button
                        onClick={() => setDeleteConfirmId(null)}
                        disabled={allBusy}
                        className="px-3 py-1 text-xs font-medium border border-border rounded-lg
                                 hover:bg-paper-warm disabled:opacity-50 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => {
                        setDeleteConfirmId(account.id)
                        setSuccess(null)
                      }}
                      disabled={allBusy}
                      aria-label={`Disconnect ${account.account_name ?? account.platform}`}
                      className="p-1.5 text-muted hover:text-red-600 disabled:opacity-50 transition-colors"
                    >
                      <Trash2 size={14} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Connect buttons / inline forms */}
          <div className="space-y-3">
            {/* Bluesky connect */}
            {connectingPlatform === 'bluesky' ? (
              <div className="p-4 bg-paper-warm border border-border rounded-lg space-y-3">
                <label
                  htmlFor="bluesky-handle"
                  className="block text-xs font-medium text-muted mb-1"
                >
                  Bluesky Handle
                </label>
                <input
                  id="bluesky-handle"
                  type="text"
                  value={handle}
                  onChange={(e) => setHandle(e.target.value)}
                  disabled={allBusy}
                  placeholder="alice.bsky.social"
                  className="w-full px-3 py-2 bg-paper-warm border border-border rounded-lg
                           text-ink text-sm
                           focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20
                           disabled:opacity-50"
                />
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => void handleConnectBluesky()}
                    disabled={allBusy || handle.trim().length === 0}
                    className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-accent text-white rounded-lg
                             hover:bg-accent-light disabled:opacity-50 transition-colors"
                  >
                    <Plus size={14} />
                    {submitting ? 'Connecting...' : 'Connect'}
                  </button>
                  <button
                    onClick={() => {
                      setConnectingPlatform(null)
                      setHandle('')
                    }}
                    disabled={allBusy}
                    className="px-4 py-2 text-sm font-medium border border-border rounded-lg
                             hover:bg-paper-warm disabled:opacity-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => {
                  setConnectingPlatform('bluesky')
                  setInstanceUrl('')
                  setError(null)
                  setSuccess(null)
                }}
                disabled={allBusy}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium
                         border border-border rounded-lg hover:bg-paper-warm
                         disabled:opacity-50 transition-colors"
              >
                <PlatformIcon platform="bluesky" size={14} />
                Connect Bluesky
              </button>
            )}

            {/* Mastodon connect */}
            {connectingPlatform === 'mastodon' ? (
              <div className="p-4 bg-paper-warm border border-border rounded-lg space-y-3">
                <label
                  htmlFor="mastodon-instance"
                  className="block text-xs font-medium text-muted mb-1"
                >
                  Mastodon Instance URL
                </label>
                <input
                  id="mastodon-instance"
                  type="text"
                  value={instanceUrl}
                  onChange={(e) => setInstanceUrl(e.target.value)}
                  disabled={allBusy}
                  placeholder="https://mastodon.social"
                  className="w-full px-3 py-2 bg-paper-warm border border-border rounded-lg
                           text-ink text-sm
                           focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20
                           disabled:opacity-50"
                />
                <div className="flex items-center gap-3">
                  <button
                    onClick={() => void handleConnectMastodon()}
                    disabled={allBusy || instanceUrl.trim().length === 0}
                    className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-accent text-white rounded-lg
                             hover:bg-accent-light disabled:opacity-50 transition-colors"
                  >
                    <Plus size={14} />
                    {submitting ? 'Connecting...' : 'Connect'}
                  </button>
                  <button
                    onClick={() => {
                      setConnectingPlatform(null)
                      setInstanceUrl('')
                    }}
                    disabled={allBusy}
                    className="px-4 py-2 text-sm font-medium border border-border rounded-lg
                             hover:bg-paper-warm disabled:opacity-50 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => {
                  setConnectingPlatform('mastodon')
                  setHandle('')
                  setError(null)
                  setSuccess(null)
                }}
                disabled={allBusy}
                className="flex items-center gap-2 px-4 py-2 text-sm font-medium
                         border border-border rounded-lg hover:bg-paper-warm
                         disabled:opacity-50 transition-colors"
              >
                <PlatformIcon platform="mastodon" size={14} />
                Connect Mastodon
              </button>
            )}
          </div>
        </>
      )}
    </section>
  )
}
