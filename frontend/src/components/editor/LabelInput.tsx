import { useEffect, useRef, useState } from 'react'
import { X } from 'lucide-react'

import { createLabel, fetchLabels } from '@/api/labels'
import type { LabelResponse } from '@/api/client'

interface LabelInputProps {
  value: string[]
  onChange: (labels: string[]) => void
  disabled?: boolean
}

export default function LabelInput({ value, onChange, disabled }: LabelInputProps) {
  const [query, setQuery] = useState('')
  const [allLabels, setAllLabels] = useState<LabelResponse[]>([])
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    fetchLabels()
      .then(setAllLabels)
      .catch(() => {})
  }, [])

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  const filtered = allLabels.filter(
    (l) => !value.includes(l.id) && l.id.toLowerCase().includes(query.toLowerCase()),
  )

  const trimmed = query.trim().toLowerCase()
  const exactMatch = allLabels.some((l) => l.id === trimmed)
  const showCreate = trimmed.length > 0 && !exactMatch && !value.includes(trimmed)

  function addLabel(id: string) {
    if (!value.includes(id)) {
      onChange([...value, id])
    }
    setQuery('')
    setOpen(false)
    inputRef.current?.focus()
  }

  function removeLabel(id: string) {
    onChange(value.filter((l) => l !== id))
  }

  async function handleCreate() {
    if (!trimmed || creating) return
    setCreating(true)
    try {
      const label = await createLabel(trimmed)
      setAllLabels((prev) => [...prev, label])
      addLabel(label.id)
    } catch {
      // 409 = already exists, just add it
      addLabel(trimmed)
    } finally {
      setCreating(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Backspace' && query === '' && value.length > 0) {
      removeLabel(value[value.length - 1])
    }
    if (e.key === 'Enter') {
      e.preventDefault()
      if (showCreate) {
        void handleCreate()
      } else if (filtered.length > 0) {
        addLabel(filtered[0].id)
      }
    }
    if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <div
        className="flex flex-wrap items-center gap-1.5 px-3 py-2 bg-paper-warm border border-border
                    rounded-lg focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/20
                    min-h-[2.5rem]"
      >
        {value.map((id) => (
          <span
            key={id}
            className="inline-flex items-center gap-1 px-2 py-0.5 text-xs font-medium
                       bg-accent/10 text-accent rounded-full"
          >
            #{id}
            {!disabled && (
              <button
                type="button"
                onClick={() => removeLabel(id)}
                className="hover:text-accent-light"
              >
                <X size={12} />
              </button>
            )}
          </span>
        ))}
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={value.length === 0 ? 'Add labels...' : ''}
          className="flex-1 min-w-[80px] bg-transparent text-sm text-ink outline-none
                     placeholder:text-muted disabled:opacity-50"
        />
      </div>

      {open && (filtered.length > 0 || showCreate) && (
        <div
          className="absolute z-10 mt-1 w-full bg-paper border border-border rounded-lg
                      shadow-lg max-h-48 overflow-y-auto"
        >
          {filtered.map((label) => (
            <button
              key={label.id}
              type="button"
              onClick={() => addLabel(label.id)}
              className="w-full text-left px-3 py-2 text-sm hover:bg-paper-warm transition-colors"
            >
              <span className="font-medium">#{label.id}</span>
              {label.names.length > 0 && label.names[0] !== label.id && (
                <span className="ml-2 text-muted">{label.names[0]}</span>
              )}
            </button>
          ))}
          {showCreate && (
            <button
              type="button"
              onClick={() => void handleCreate()}
              disabled={creating}
              className="w-full text-left px-3 py-2 text-sm text-accent hover:bg-paper-warm
                         transition-colors border-t border-border disabled:opacity-50"
            >
              {creating ? 'Creating...' : `Create #${trimmed}`}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
