import { Link } from 'react-router-dom'

interface LabelChipProps {
  labelId: string
  clickable?: boolean
}

export default function LabelChip({ labelId, clickable = true }: LabelChipProps) {
  const className =
    'inline-flex items-center px-2 py-0.5 text-xs font-medium rounded-md ' +
    'bg-tag-bg text-tag-text transition-colors hover:bg-border hover:text-ink'

  if (clickable) {
    return (
      <Link
        to={`/labels/${labelId}`}
        className={className}
        onClick={(e) => e.stopPropagation()}
      >
        #{labelId}
      </Link>
    )
  }

  return <span className={className}>#{labelId}</span>
}
