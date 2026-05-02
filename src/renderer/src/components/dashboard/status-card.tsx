import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

interface StatusCardProps {
  title: string
  status: string
  variant?: 'default' | 'success' | 'warning' | 'destructive'
}

export function StatusCard({ title, status, variant = 'default' }: StatusCardProps) {
  const statusColors = {
    default: 'text-foreground',
    success: 'text-green-500',
    warning: 'text-yellow-500',
    destructive: 'text-red-500',
  }

  return (
    <Card className="shadow-sm border-muted-foreground/20">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className={cn("text-2xl font-bold", statusColors[variant])}>
          {status}
        </div>
      </CardContent>
    </Card>
  )
}
