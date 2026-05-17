import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { Shield, ChevronDown, LogOut, User, Settings, SlidersHorizontal } from 'lucide-react'
import { useState } from 'react'
import useAuthStore from '../stores/authStore'
import useWebSocket from '../hooks/useWebSocket'
import NotificationDropdown from './NotificationDropdown'
import LiveFeed from './LiveFeed'
import CompetitionBanner from './CompetitionBanner'
import ToastViewport from './Toast'

export default function Layout() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const { connectionState } = useWebSocket()
  const [menuOpen, setMenuOpen] = useState(false)
  const isAdmin = user?.role === 'admin'

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const navLinks = [
    { to: '/', label: 'Overview' },
    { to: '/challenges', label: 'Challenges' },
    { to: '/leaderboard', label: 'Rankings' },
    { to: '/workstation', label: 'Workstation' },
    { to: '/deploy', label: 'Deploy' },
  ]

  return (
    <div className="min-h-screen relative" style={{ background: 'var(--bg-primary)' }}>
      <div className="grid-bg fixed inset-0 pointer-events-none opacity-50" />

      <CompetitionBanner />

      <nav className="sticky top-0 z-50 border-b" style={{ background: 'var(--bg-surface)', borderColor: 'var(--border)' }}>
        <div className="max-w-7xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-8">
            <NavLink to="/" className="flex items-center gap-2">
              <Shield size={24} style={{ color: 'var(--accent-cyan)' }} />
              <span className="font-bold text-lg" style={{
                background: 'linear-gradient(135deg, var(--accent-cyan), var(--accent-red))',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent',
                fontFamily: 'Outfit, sans-serif',
              }}>SIEGE RANGE</span>
            </NavLink>
            <div className="hidden md:flex items-center gap-1">
              {navLinks.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.to === '/'}
                  className={({ isActive }) =>
                    `px-3 py-1.5 rounded text-sm font-medium transition-colors ${
                      isActive
                        ? 'text-white'
                        : 'hover:text-white'
                    }`
                  }
                  style={({ isActive }) => ({
                    color: isActive ? 'var(--accent-cyan)' : 'var(--text-secondary)',
                    background: isActive ? 'rgba(0, 200, 255, 0.1)' : 'transparent',
                  })}
                >
                  {link.label}
                </NavLink>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
              <div className={`w-2 h-2 rounded-full ${connectionState === 'connected' ? 'bg-green-500' : connectionState === 'connecting' ? 'bg-yellow-500' : 'bg-red-500'}`} />
              <span className="hidden sm:inline">{connectionState === 'connected' ? 'LIVE' : 'OFFLINE'}</span>
            </div>

            <NotificationDropdown />

            <div className="relative">
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="flex items-center gap-2 px-2 py-1 rounded transition-colors"
                style={{ color: 'var(--text-secondary)' }}
              >
                <div className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold" style={{
                  background: 'var(--bg-elevated)',
                  border: `2px solid ${user?.team === 'red' ? 'var(--accent-red)' : 'var(--accent-cyan)'}`,
                  color: 'var(--text-primary)',
                }}>
                  {(user?.display_name || user?.username || '?')[0].toUpperCase()}
                </div>
                <ChevronDown size={14} />
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-full mt-1 w-48 rounded-md shadow-lg py-1 z-50" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)' }}>
                  <NavLink
                    to={`/profile/${user?.username}`}
                    onClick={() => setMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-white/5"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    <User size={14} /> Profile
                  </NavLink>
                  <NavLink
                    to="/settings"
                    onClick={() => setMenuOpen(false)}
                    className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-white/5"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    <SlidersHorizontal size={14} /> Settings
                  </NavLink>
                  {isAdmin && (
                    <NavLink
                      to="/admin"
                      onClick={() => setMenuOpen(false)}
                      className="flex items-center gap-2 px-4 py-2 text-sm hover:bg-white/5"
                      style={{ color: 'var(--text-secondary)' }}
                    >
                      <Settings size={14} /> Admin
                    </NavLink>
                  )}
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-2 px-4 py-2 text-sm w-full text-left hover:bg-white/5"
                    style={{ color: 'var(--accent-red)' }}
                  >
                    <LogOut size={14} /> Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      <main className="relative z-10 max-w-7xl mx-auto px-4 py-6">
        <Outlet />
      </main>

      <LiveFeed />
      <ToastViewport />
    </div>
  )
}
