export interface WrapAction {
  before: string
  after: string
  placeholder: string
  block?: boolean
}

export function wrapSelection(
  value: string,
  selectionStart: number,
  selectionEnd: number,
  action: WrapAction,
): { newValue: string; cursorStart: number; cursorEnd: number } {
  const selected = value.slice(selectionStart, selectionEnd)
  const text = selected || action.placeholder

  let before = action.before
  if (action.block && selectionStart > 0 && value[selectionStart - 1] !== '\n') {
    before = '\n' + before
  }

  const inserted = before + text + action.after
  const newValue = value.slice(0, selectionStart) + inserted + value.slice(selectionEnd)

  const cursorStart = selectionStart + before.length
  const cursorEnd = cursorStart + text.length

  return { newValue, cursorStart, cursorEnd }
}
