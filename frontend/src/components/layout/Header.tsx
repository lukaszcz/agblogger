import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Search, LogIn, LogOut, PenLine, Settings } from 'lucide-react'
import { useState } from 'react'
import { useSiteStore } from '@/stores/siteStore'
import { useAuthStore } from '@/stores/authStore'

export default function Header() {
  const location = useLocation()
  const navigate = useNavigate()
  const config = useSiteStore((s) => s.config)
  const user = useAuthStore((s) => s.user)
  const logout = useAuthStore((s) => s.logout)
  const isLoggingOut = useAuthStore((s) => s.isLoggingOut)
  const [searchOpen, setSearchOpen] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  const pages = config?.pages ?? []
  const siteTitle = config?.title ?? 'AgBlogger'

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    if (searchQuery.trim()) {
      void navigate(`/search?q=${encodeURIComponent(searchQuery.trim())}`)
      setSearchOpen(false)
      setSearchQuery('')
    }
  }

  async function handleLogout() {
    await logout()
  }

  return (
    <header className="border-b border-border bg-paper/80 backdrop-blur-sm sticky top-0 z-50">
      {/* Top bar */}
      <div className="max-w-5xl mx-auto px-6">
        <div className="flex items-center justify-between h-16">
          <Link
            to="/"
            className="font-display text-2xl tracking-tight text-ink hover:text-accent transition-colors"
          >
            {siteTitle}
          </Link>

          <div className="flex items-center gap-3">
            {searchOpen ? (
              <form onSubmit={handleSearch} className="flex items-center">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search posts..."
                  autoFocus
                  className="w-48 px-3 py-1.5 text-sm bg-paper-warm border border-border rounded-lg
                           focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent/20
                           font-body placeholder:text-muted"
                  onBlur={() => {
                    if (!searchQuery) setSearchOpen(false)
                  }}
                />
              </form>
            ) : (
              <button
                onClick={() => setSearchOpen(true)}
                className="p-2 text-muted hover:text-ink transition-colors rounded-lg hover:bg-paper-warm"
                aria-label="Search"
              >
                <Search size={18} />
              </button>
            )}

            {user ? (
              <>
                <Link
                  to="/editor/new"
                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium
                           bg-accent text-white rounded-lg hover:bg-accent-light transition-colors"
                >
                  <PenLine size={14} />
                  <span>Write</span>
                </Link>
                {user.is_admin && (
                  <Link
                    to="/admin"
                    className="p-2 text-muted hover:text-ink transition-colors rounded-lg hover:bg-paper-warm"
                    aria-label="Admin"
                    title="Admin panel"
                  >
                    <Settings size={18} />
                  </Link>
                )}
                <button
                  onClick={() => void handleLogout()}
                  disabled={isLoggingOut}
                  className="p-2 text-muted hover:text-ink transition-colors rounded-lg hover:bg-paper-warm disabled:opacity-50 disabled:cursor-not-allowed"
                  aria-label="Logout"
                  title="Log out"
                >
                  <LogOut size={18} />
                </button>
              </>
            ) : (
              <Link
                to="/login"
                className="p-2 text-muted hover:text-ink transition-colors rounded-lg hover:bg-paper-warm"
                aria-label="Login"
              >
                <LogIn size={18} />
              </Link>
            )}
          </div>
        </div>

        {/* Navigation tabs */}
        <nav className="flex gap-1 -mb-px">
          {pages.map((page) => {
            const path =
              page.id === 'timeline'
                ? '/'
                : page.id === 'labels'
                  ? '/labels'
                  : `/page/${page.id}`
            const isActive =
              page.id === 'timeline'
                ? location.pathname === '/'
                : page.id === 'labels'
                  ? location.pathname === '/labels' ||
                    location.pathname.startsWith('/labels/')
                  : location.pathname === path

            return (
              <Link
                key={page.id}
                to={path}
                className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
                  isActive
                    ? 'border-accent text-accent'
                    : 'border-transparent text-muted hover:text-ink hover:border-border-dark'
                }`}
              >
                {page.title}
              </Link>
            )
          })}
        </nav>
      </div>
    </header>
  )
}
