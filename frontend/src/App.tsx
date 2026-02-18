import { useEffect } from 'react'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Header from '@/components/layout/Header'
import TimelinePage from '@/pages/TimelinePage'
import PostPage from '@/pages/PostPage'
import PageViewPage from '@/pages/PageViewPage'
import SearchPage from '@/pages/SearchPage'
import LoginPage from '@/pages/LoginPage'
import LabelListPage from '@/pages/LabelListPage'
import LabelPostsPage from '@/pages/LabelPostsPage'
import LabelGraphPage from '@/pages/LabelGraphPage'
import EditorPage from '@/pages/EditorPage'
import { useSiteStore } from '@/stores/siteStore'
import { useAuthStore } from '@/stores/authStore'

export default function App() {
  const fetchConfig = useSiteStore((s) => s.fetchConfig)
  const checkAuth = useAuthStore((s) => s.checkAuth)

  useEffect(() => {
    void fetchConfig()
    void checkAuth()
  }, [fetchConfig, checkAuth])

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-paper">
        <Header />
        <main className="max-w-3xl mx-auto px-6 py-10">
          <Routes>
            <Route path="/" element={<TimelinePage />} />
            <Route path="/post/*" element={<PostPage />} />
            <Route path="/page/:pageId" element={<PageViewPage />} />
            <Route path="/search" element={<SearchPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/labels" element={<LabelListPage />} />
            <Route path="/labels/graph" element={<LabelGraphPage />} />
            <Route path="/labels/:labelId" element={<LabelPostsPage />} />
            <Route path="/editor/*" element={<EditorPage />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="border-t border-border mt-16">
          <div className="max-w-3xl mx-auto px-6 py-8">
            <p className="text-xs text-muted text-center font-mono tracking-wide">
              Powered by AgBlogger
            </p>
          </div>
        </footer>
      </div>
    </BrowserRouter>
  )
}
