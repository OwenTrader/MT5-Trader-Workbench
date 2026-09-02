import React from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { MT5Position } from '@/stores/dashboard-store'
import { ArrowDownRight, ArrowUpRight, Briefcase, RefreshCw } from 'lucide-react'
import { cn } from '@/lib/utils'

interface PositionTableProps {
  positions: MT5Position[]
  onRefresh?: () => void
}

export const PositionTable: React.FC<PositionTableProps> = ({ positions, onRefresh }) => {
  const totalProfit = positions.reduce((acc, pos) => acc + (pos.profit || 0), 0)
  const totalVolume = positions.reduce((acc, pos) => acc + (pos.volume || 0), 0)

  return (
    <Card className="shadow-sm border">
      <CardHeader className="flex flex-row items-center justify-between py-4 px-6 border-b bg-card/50">
        <div className="flex items-center gap-3">
          <Briefcase className="h-5 w-5 text-primary" />
          <CardTitle className="text-base font-semibold">
            实时持仓明细 ({positions.length})
          </CardTitle>
          {positions.length > 0 && (
            <Badge variant="outline" className="text-xs font-mono">
              总手数: {totalVolume.toFixed(2)}
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted-foreground">持仓浮盈:</span>
            <span
              className={cn(
                "font-bold font-mono text-base",
                totalProfit > 0
                  ? "text-emerald-600 dark:text-emerald-400"
                  : totalProfit < 0
                  ? "text-rose-600 dark:text-rose-400"
                  : "text-muted-foreground"
              )}
            >
              {totalProfit >= 0 ? `+$${totalProfit.toFixed(2)}` : `-$${Math.abs(totalProfit).toFixed(2)}`}
            </span>
          </div>

          {onRefresh && (
            <Button variant="ghost" size="icon" onClick={onRefresh} title="刷新持仓" className="h-8 w-8">
              <RefreshCw className="h-4 w-4" />
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {positions.length === 0 ? (
          <div className="py-12 text-center text-sm text-muted-foreground flex flex-col items-center justify-center gap-2">
            <Briefcase className="h-8 w-8 text-muted-foreground/40 stroke-1" />
            <span>当前账户暂无任何持仓订单</span>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/30 text-xs">
                  <TableHead className="font-semibold">订单号 (Ticket)</TableHead>
                  <TableHead className="font-semibold">交易品种</TableHead>
                  <TableHead className="font-semibold">方向</TableHead>
                  <TableHead className="font-semibold text-right">手数</TableHead>
                  <TableHead className="font-semibold text-right">开仓价</TableHead>
                  <TableHead className="font-semibold text-right">当前市价</TableHead>
                  <TableHead className="font-semibold text-right">止损 (SL)</TableHead>
                  <TableHead className="font-semibold text-right">止盈 (TP)</TableHead>
                  <TableHead className="font-semibold text-right">浮动盈亏 ($)</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {positions.map((pos) => {
                  const isBuy = pos.type === 0
                  const isProfit = (pos.profit || 0) >= 0

                  return (
                    <TableRow key={pos.ticket} className="text-sm hover:bg-muted/40 transition-colors">
                      <TableCell className="font-mono text-xs text-muted-foreground">
                        #{pos.ticket}
                      </TableCell>
                      <TableCell className="font-bold">{pos.symbol}</TableCell>
                      <TableCell>
                        <Badge
                          variant={isBuy ? "default" : "destructive"}
                          className={cn(
                            "text-xs px-2 py-0.5 font-bold uppercase",
                            isBuy
                              ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                              : "bg-rose-600 hover:bg-rose-700 text-white"
                          )}
                        >
                          {isBuy ? (
                            <span className="flex items-center gap-0.5">
                              <ArrowUpRight className="h-3 w-3" /> BUY
                            </span>
                          ) : (
                            <span className="flex items-center gap-0.5">
                              <ArrowDownRight className="h-3 w-3" /> SELL
                            </span>
                          )}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right font-mono font-medium">
                        {pos.volume.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-muted-foreground">
                        {pos.price_open.toFixed(pos.symbol.includes('JPY') ? 3 : 5)}
                      </TableCell>
                      <TableCell className="text-right font-mono font-medium">
                        {pos.price_current.toFixed(pos.symbol.includes('JPY') ? 3 : 5)}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs text-muted-foreground">
                        {pos.sl > 0 ? pos.sl.toFixed(pos.symbol.includes('JPY') ? 3 : 5) : '-'}
                      </TableCell>
                      <TableCell className="text-right font-mono text-xs text-muted-foreground">
                        {pos.tp > 0 ? pos.tp.toFixed(pos.symbol.includes('JPY') ? 3 : 5) : '-'}
                      </TableCell>
                      <TableCell
                        className={cn(
                          "text-right font-mono font-bold text-sm",
                          isProfit ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
                        )}
                      >
                        {isProfit ? `+$${pos.profit.toFixed(2)}` : `-$${Math.abs(pos.profit).toFixed(2)}`}
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
