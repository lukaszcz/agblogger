import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

import { wrapSelection } from '../wrapSelection'
import MarkdownToolbar from '../MarkdownToolbar'
import { createRef } from 'react'

describe('wrapSelection', () => {
  it('wraps selected text with bold markers', () => {
    const result = wrapSelection('hello world', 6, 11, {
      before: '**',
      after: '**',
      placeholder: 'bold text',
    })
    expect(result.newValue).toBe('hello **world**')
    expect(result.cursorStart).toBe(8)
    expect(result.cursorEnd).toBe(13)
  })

  it('inserts placeholder when no selection', () => {
    const result = wrapSelection('hello ', 6, 6, {
      before: '**',
      after: '**',
      placeholder: 'bold text',
    })
    expect(result.newValue).toBe('hello **bold text**')
    expect(result.cursorStart).toBe(8)
    expect(result.cursorEnd).toBe(17)
  })

  it('adds newline for block actions when not at line start', () => {
    const result = wrapSelection('some text', 9, 9, {
      before: '## ',
      after: '',
      placeholder: 'Heading',
      block: true,
    })
    expect(result.newValue).toBe('some text\n## Heading')
    expect(result.cursorStart).toBe(13)
    expect(result.cursorEnd).toBe(20)
  })

  it('does not add newline for block actions at line start', () => {
    const result = wrapSelection('', 0, 0, {
      before: '## ',
      after: '',
      placeholder: 'Heading',
      block: true,
    })
    expect(result.newValue).toBe('## Heading')
    expect(result.cursorStart).toBe(3)
    expect(result.cursorEnd).toBe(10)
  })

  it('wraps with code fence markers', () => {
    const result = wrapSelection('', 0, 0, {
      before: '```\n',
      after: '\n```',
      placeholder: 'code',
      block: true,
    })
    expect(result.newValue).toBe('```\ncode\n```')
    expect(result.cursorStart).toBe(4)
    expect(result.cursorEnd).toBe(8)
  })

  it('wraps selection with link syntax', () => {
    const result = wrapSelection('click here for info', 6, 10, {
      before: '[',
      after: '](url)',
      placeholder: 'link text',
    })
    expect(result.newValue).toBe('click [here](url) for info')
    expect(result.cursorStart).toBe(7)
    expect(result.cursorEnd).toBe(11)
  })
})

describe('MarkdownToolbar', () => {
  it('renders all 6 toolbar buttons', () => {
    const ref = createRef<HTMLTextAreaElement>()
    render(
      <MarkdownToolbar textareaRef={ref} value="" onChange={() => {}} />,
    )
    expect(screen.getByLabelText('Bold')).toBeInTheDocument()
    expect(screen.getByLabelText('Italic')).toBeInTheDocument()
    expect(screen.getByLabelText('Heading')).toBeInTheDocument()
    expect(screen.getByLabelText('Link')).toBeInTheDocument()
    expect(screen.getByLabelText('Code')).toBeInTheDocument()
    expect(screen.getByLabelText('Code Block')).toBeInTheDocument()
  })

  it('disables all buttons when disabled prop is true', () => {
    const ref = createRef<HTMLTextAreaElement>()
    render(
      <MarkdownToolbar textareaRef={ref} value="" onChange={() => {}} disabled />,
    )
    const buttons = screen.getAllByRole('button')
    buttons.forEach((btn) => expect(btn).toBeDisabled())
  })
})
