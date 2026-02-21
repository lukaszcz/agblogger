import { useCallback, useEffect, useState } from 'react'
import { Share2 } from 'lucide-react'

import { fetchCrossPostHistory, fetchSocialAccounts } from '@/api/crosspost'
import type { CrossPostResult, SocialAccount } from '@/api/crosspost'
import type { PostDetail } from '@/api/client'
import CrossPostDialog from '@/components/crosspost/CrossPostDialog'
import CrossPostHistory from '@/components/crosspost/CrossPostHistory'

interface CrossPostSectionProps {
  filePath: string
  post: PostDetail
}

export default function CrossPostSection({ filePath, post }: CrossPostSectionProps) {
  const [historyItems, setHistoryItems] = useState<CrossPostResult[]>([])
  const [historyLoading, setHistoryLoading] = useState(true)
  const [accounts, setAccounts] = useState<SocialAccount[]>([])
  const [showDialog, setShowDialog] = useState(false)

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true)
    try {
      const history = await fetchCrossPostHistory(filePath)
      setHistoryItems(history.items)
    } catch {
      // Silently fail — history is supplementary
    } finally {
      setHistoryLoading(false)
    }
  }, [filePath])

  useEffect(() => {
    void loadHistory()
    void (async () => {
      try {
        const accts = await fetchSocialAccounts()
        setAccounts(accts)
      } catch {
        // Silently fail
      }
    })()
  }, [loadHistory])

  function handleDialogClose() {
    setShowDialog(false)
    void loadHistory()
  }

  return (
    <section className="mt-10 pt-6 border-t border-border">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium text-muted">Cross-posting</h3>
        {accounts.length > 0 && (
          <button
            onClick={() => setShowDialog(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                     text-muted border border-border rounded-lg
                     hover:text-ink hover:bg-paper-warm
                     disabled:opacity-50 transition-colors"
          >
            <Share2 size={14} />
            Share
          </button>
        )}
      </div>
      <CrossPostHistory items={historyItems} loading={historyLoading} />
      {showDialog && (
        <CrossPostDialog
          open={showDialog}
          onClose={handleDialogClose}
          accounts={accounts}
          postPath={filePath}
          postTitle={post.title}
          postExcerpt=""
          postLabels={post.labels}
        />
      )}
    </section>
  )
}
