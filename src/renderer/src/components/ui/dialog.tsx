import * as React from 'react'
import { cn } from '@/lib/utils'

type DialogContextValue = {
  open: boolean
  setOpen: (open: boolean) => void
}

const DialogContext = React.createContext<DialogContextValue | null>(null)

function useDialogContext(componentName: string) {
  const context = React.useContext(DialogContext)

  if (!context) {
    throw new Error(`${componentName} must be used within a Dialog`)
  }

  return context
}

type DialogProps = {
  open: boolean
  onOpenChange: (open: boolean) => void
  children: React.ReactNode
}

function Dialog({ open, onOpenChange, children }: DialogProps) {
  return <DialogContext.Provider value={{ open, setOpen: onOpenChange }}>{children}</DialogContext.Provider>
}

function DialogPortal({ children }: { children: React.ReactNode }) {
  const [mounted, setMounted] = React.useState(false)

  React.useEffect(() => {
    setMounted(true)
    return () => setMounted(false)
  }, [])

  if (!mounted) {
    return null
  }

  return <>{children}</>
}

function DialogOverlay({ className }: { className?: string }) {
  const { open, setOpen } = useDialogContext('DialogOverlay')

  if (!open) {
    return null
  }

  return (
    <div
      className={cn('fixed inset-0 z-50 bg-black/55 backdrop-blur-sm', className)}
      onClick={() => setOpen(false)}
    />
  )
}

type DialogContentProps = React.HTMLAttributes<HTMLDivElement>

function DialogContent({ className, children, ...props }: DialogContentProps) {
  const { open } = useDialogContext('DialogContent')

  if (!open) {
    return null
  }

  return (
    <DialogPortal>
      <DialogOverlay />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <div
          role="dialog"
          aria-modal="true"
          className={cn(
            'w-full max-w-md rounded-2xl border border-border/60 bg-background/95 p-6 shadow-2xl shadow-black/25',
            className
          )}
          onClick={(event) => event.stopPropagation()}
          {...props}
        >
          {children}
        </div>
      </div>
    </DialogPortal>
  )
}

function DialogHeader({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex flex-col space-y-2 text-left', className)} {...props} />
}

function DialogFooter({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('mt-6 flex justify-end gap-2', className)} {...props} />
}

function DialogTitle({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return <h2 className={cn('text-lg font-semibold leading-none tracking-tight', className)} {...props} />
}

function DialogDescription({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) {
  return <p className={cn('text-sm leading-6 text-muted-foreground whitespace-pre-wrap break-words', className)} {...props} />
}

export { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle }
