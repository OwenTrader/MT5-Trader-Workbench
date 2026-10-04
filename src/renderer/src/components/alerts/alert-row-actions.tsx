import { Edit3, Pause, Play, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

interface AlertRowActionsProps {
  isTriggered: boolean
  isActive: boolean
  /** Class string for the triggered state, e.g. the red or orange family. */
  triggerColor: string
  labels: {
    reset: string
    start: string
    pause: string
    edit: string
    delete: string
  }
  onPrimary: () => void
  onPause: () => void
  onEdit: () => void
  onDelete: () => void
}

/**
 * The play/pause/edit/delete button group shared by the price, volatility,
 * indicator and order-broadcast rule tables. It used to be copy-pasted
 * verbatim into all four pages.
 */
export function AlertRowActions({
  isTriggered,
  isActive,
  triggerColor,
  labels,
  onPrimary,
  onPause,
  onEdit,
  onDelete,
}: AlertRowActionsProps) {
  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        className={cn(
          'w-9 h-9 rounded-full transition-all',
          isTriggered
            ? triggerColor
            : isActive
              ? 'bg-blue-600/10 text-blue-600 hover:bg-blue-600/20'
              : 'text-muted-foreground/40 hover:text-muted-foreground',
        )}
        onClick={onPrimary}
        title={isTriggered ? labels.reset : labels.start}
      >
        <Play className={cn('w-4 h-4 fill-current', !isActive && !isTriggered && 'fill-none')} />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className={cn(
          'w-9 h-9 rounded-full transition-all',
          !isActive && !isTriggered
            ? 'bg-gray-500 text-white hover:bg-gray-600 shadow-md'
            : 'text-muted-foreground/40 hover:text-muted-foreground',
        )}
        onClick={onPause}
        title={labels.pause}
      >
        <Pause className={cn('w-4 h-4 fill-current', (isActive || isTriggered) && 'fill-none')} />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="w-9 h-9 rounded-full text-blue-500 hover:text-blue-600 hover:bg-blue-50"
        onClick={onEdit}
        title={labels.edit}
      >
        <Edit3 className="w-4 h-4" />
      </Button>

      <Button
        variant="ghost"
        size="icon"
        className="w-9 h-9 rounded-full text-destructive hover:bg-destructive/10"
        onClick={onDelete}
        title={labels.delete}
      >
        <Trash2 className="w-4 h-4" />
      </Button>
    </>
  )
}
