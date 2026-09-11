interface ConfidenceRangeProps {
  point: number
  low: number
  high: number
  unit?: string
  decimals?: number
}

// Always renders point + a visible low-high band - the product should
// never show a bare number that implies more precision than the
// underlying real 95% confidence interval actually supports. The range
// itself is the signal; no explanatory sentence attached (see "About
// this estimate" for methodology instead).
export function ConfidenceRange({ point, low, high, unit = '', decimals = 0 }: ConfidenceRangeProps) {
  const fmt = (n: number) => n.toFixed(decimals)

  return (
    <div>
      <div className="flex items-baseline gap-1">
        <span className="font-tabular text-[22px] font-semibold" style={{ color: 'var(--text-primary)' }}>
          {fmt(point)}
        </span>
        <span className="text-[13px]" style={{ color: 'var(--text-secondary)' }}>{unit}</span>
      </div>
      <div className="font-tabular mt-0.5 text-[12px]" style={{ color: 'var(--text-tertiary)' }}>
        {fmt(low)}{unit} – {fmt(high)}{unit}
      </div>
    </div>
  )
}
