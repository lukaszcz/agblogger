import { Bold, Italic, Heading2, Link, Code, FileCode } from 'lucide-react'
import type { RefObject } from 'react'
import { wrapSelection } from './wrapSelection'
import type { WrapAction } from './wrapSelection'

const actions: Record<string, WrapAction> = {
  bold: { before: '**', after: '**', placeholder: 'bold text' },
  italic: { before: '_', after: '_', placeholder: 'italic text' },
  heading: { before: '## ', after: '', placeholder: 'Heading', block: true },
  link: { before: '[', after: '](url)', placeholder: 'link text' },
  code: { before: '`', after: '`', placeholder: 'code' },
  codeblock: { before: '```\n', after: '\n```', placeholder: 'code', block: true },
}

interface MarkdownToolbarProps {
  textareaRef: RefObject<HTMLTextAreaElement | null>
  value: string
  onChange: (value: string) => void
  disabled?: boolean
}

const buttons = [
  { key: 'bold', label: 'Bold', Icon: Bold },
  { key: 'italic', label: 'Italic', Icon: Italic },
  { key: 'heading', label: 'Heading', Icon: Heading2 },
  { key: 'link', label: 'Link', Icon: Link },
  { key: 'code', label: 'Code', Icon: Code },
  { key: 'codeblock', label: 'Code Block', Icon: FileCode },
] as const

export default function MarkdownToolbar({ textareaRef, value, onChange, disabled }: MarkdownToolbarProps) {
  function handleAction(key: string) {
    const textarea = textareaRef.current
    if (!textarea) return

    const action = actions[key]
    const { newValue, cursorStart, cursorEnd } = wrapSelection(
      value,
      textarea.selectionStart,
      textarea.selectionEnd,
      action,
    )

    onChange(newValue)

    requestAnimationFrame(() => {
      textarea.focus()
      textarea.setSelectionRange(cursorStart, cursorEnd)
    })
  }

  return (
    <div className="flex items-center gap-1 mb-2">
      {buttons.map(({ key, label, Icon }) => (
        <button
          key={key}
          type="button"
          onClick={() => handleAction(key)}
          disabled={disabled}
          className="p-1.5 text-muted hover:text-ink hover:bg-paper-warm rounded transition-colors
                   disabled:opacity-50 disabled:cursor-not-allowed"
          title={label}
          aria-label={label}
        >
          <Icon size={16} />
        </button>
      ))}
    </div>
  )
}
