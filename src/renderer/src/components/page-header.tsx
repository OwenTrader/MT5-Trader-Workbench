import React from 'react'
import type { LucideIcon } from 'lucide-react'

interface PageHeaderProps {
  title: string
  icon: LucideIcon
  actions?: React.ReactNode
}

export const PageHeader: React.FC<PageHeaderProps> = ({ title, icon: Icon, actions }) => {
  return (
    <div className="flex items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
          <Icon className="size-5" />
        </div>
        <h1 className="truncate text-2xl font-bold tracking-tight">{title}</h1>
      </div>
      {actions ? <div className="shrink-0">{actions}</div> : null}
    </div>
  )
}
