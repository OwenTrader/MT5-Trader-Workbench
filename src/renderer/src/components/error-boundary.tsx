import React from 'react'
import { AlertTriangle } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ErrorBoundaryProps {
  children: React.ReactNode
}

interface ErrorBoundaryState {
  error: Error | null
}

/**
 * Page-level crash guard: without it a render error in any page white-screens
 * the whole window with no recovery path.
 */
export class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error('Page render crashed:', error, info.componentStack)
  }

  private handleReset = () => {
    this.setState({ error: null })
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-full min-h-[50vh] flex-col items-center justify-center gap-4 p-8 text-center">
          <AlertTriangle className="size-10 text-destructive" />
          {/* Bilingual on purpose: the crash may have taken the i18n provider down. */}
          <div className="text-lg font-semibold">页面渲染出错 / Page render error</div>
          <div className="max-w-xl break-all text-sm text-muted-foreground">{this.state.error.message}</div>
          <div className="flex gap-3">
            <Button variant="outline" onClick={this.handleReset}>重试 / Retry</Button>
            <Button onClick={() => window.location.reload()}>重新加载 / Reload</Button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
