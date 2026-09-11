// Static for now - HeatShield is built as a multi-city geographic
// platform, Ahmedabad is just the first location. This is deliberately
// styled as a search/location field so it can become real city/ward
// search later without a redesign, even though it isn't interactive yet.
export function LocationControl() {
  return (
    <button
      className="flex items-center gap-2 rounded-md px-3 py-1.5 text-left transition-colors hover:bg-[var(--surface-sunken)]"
      style={{ border: '1px solid var(--border-subtle)' }}
    >
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" style={{ color: 'var(--text-tertiary)', flexShrink: 0 }}>
        <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="1.8" />
        <path d="M21 21l-4.3-4.3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
      <span className="leading-tight">
        <span className="block text-[13px] font-medium" style={{ color: 'var(--text-primary)' }}>Ahmedabad</span>
        <span className="block text-[11px]" style={{ color: 'var(--text-tertiary)' }}>Gujarat, India</span>
      </span>
    </button>
  )
}
