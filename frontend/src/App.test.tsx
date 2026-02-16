import { render, screen } from '@testing-library/react'
import App from './App'

describe('App', () => {
  it('renders the app', () => {
    render(<App />)
    expect(screen.getByText('AgBlogger')).toBeInTheDocument()
  })
})
