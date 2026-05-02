#!/usr/bin/env python3
"""
交易风控系统 - 自动剥夺犯错的权利
WindSurf Framework: Part 2.4 Implementation

功能：
1. 每日亏损硬限制
2. 仓位自动计算
3. 交易时段锁
4. 冷却期机制
5. 异常检测与告警

使用：
    python trading_risk_manager.py --mode live
"""

import json
import time
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
from enum import Enum
import smtplib
from email.mime.text import MIMEText

# ============ 配置 ============

class Config:
    """硬编码配置 - 修改需要双因子确认"""
    
    # 每日亏损硬限制（账户百分比）
    DAILY_LOSS_LIMIT_PERCENT = 2.0
    
    # 单笔最大风险（账户百分比）
    PER_TRADE_RISK_PERCENT = 0.5
    
    # 允许交易时段（24小时制）
    TRADING_HOURS = {
        "start": 8,  # 08:00
        "end": 22    # 22:00
    }
    
    # 冷却期设置
    COOLING_PERIOD_SHORT = 30  # 分钟，连续3笔亏损
    COOLING_PERIOD_LONG = 24   # 小时，连续5笔亏损
    
    # 滑点告警阈值（点数）
    SLIPPAGE_THRESHOLD = 5
    
    # 执行延迟告警阈值（毫秒）
    LATENCY_THRESHOLD = 500
    
    # 告警邮箱配置（可选）
    ALERT_EMAIL = ""  # 填写接收告警的邮箱
    SMTP_SERVER = ""
    SMTP_USER = ""
    SMTP_PASSWORD = ""

# ============ 数据结构 ============

class TradeStatus(Enum):
    LIVE_ENABLED = "live_enabled"
    SIMULATION_ONLY = "simulation_only"
    COOLING_SHORT = "cooling_short"
    COOLING_LONG = "cooling_long"
    EMERGENCY_STOP = "emergency_stop"

@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: datetime
    symbol: str
    direction: str  # LONG/SHORT
    entry_price: float
    exit_price: Optional[float]
    size: float
    pnl: Optional[float]
    slippage: float
    execution_time_ms: float
    strategy: str
    
@dataclass
class RiskState:
    """风控状态"""
    account_balance: float
    daily_start_balance: float
    daily_pnl: float
    daily_loss_percent: float
    consecutive_losses: int
    consecutive_errors: int
    status: TradeStatus
    last_trade_time: Optional[datetime]
    cooling_until: Optional[datetime]
    trades_today: List[TradeRecord]

# ============ 核心风控类 ============

class RiskManager:
    """交易风控管理器"""
    
    def __init__(self, state_file: str = "risk_state.json"):
        self.state_file = state_file
        self.state = self._load_state()
        self._setup_logging()
        
    def _setup_logging(self):
        """配置日志"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('risk_manager.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('RiskManager')
        
    def _load_state(self) -> RiskState:
        """从文件加载状态"""
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
                return RiskState(
                    account_balance=data.get('account_balance', 10000),
                    daily_start_balance=data.get('daily_start_balance', 10000),
                    daily_pnl=data.get('daily_pnl', 0),
                    daily_loss_percent=data.get('daily_loss_percent', 0),
                    consecutive_losses=data.get('consecutive_losses', 0),
                    consecutive_errors=data.get('consecutive_errors', 0),
                    status=TradeStatus(data.get('status', 'live_enabled')),
                    last_trade_time=datetime.fromisoformat(data['last_trade_time']) if data.get('last_trade_time') else None,
                    cooling_until=datetime.fromisoformat(data['cooling_until']) if data.get('cooling_until') else None,
                    trades_today=[TradeRecord(**t) for t in data.get('trades_today', [])]
                )
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            self.logger.info("初始化新的风控状态")
            return RiskState(
                account_balance=10000,
                daily_start_balance=10000,
                daily_pnl=0,
                daily_loss_percent=0,
                consecutive_losses=0,
                consecutive_errors=0,
                status=TradeStatus.LIVE_ENABLED,
                last_trade_time=None,
                cooling_until=None,
                trades_today=[]
            )
    
    def _save_state(self):
        """保存状态到文件"""
        state_dict = asdict(self.state)
        state_dict['status'] = self.state.status.value
        state_dict['last_trade_time'] = self.state.last_trade_time.isoformat() if self.state.last_trade_time else None
        state_dict['cooling_until'] = self.state.cooling_until.isoformat() if self.state.cooling_until else None
        state_dict['trades_today'] = [
            {
                **asdict(t),
                'timestamp': t.timestamp.isoformat(),
                'exit_price': t.exit_price,
                'pnl': t.pnl
            } for t in self.state.trades_today
        ]
        
        with open(self.state_file, 'w') as f:
            json.dump(state_dict, f, indent=2)
    
    def check_trading_permission(self) -> tuple[bool, str]:
        """
        检查是否允许交易
        
        Returns:
            (允许, 原因)
        """
        now = datetime.now()
        
        # 检查冷却期
        if self.state.cooling_until and now < self.state.cooling_until:
            remaining = self.state.cooling_until - now
            return False, f"冷却期中，剩余时间: {remaining}"
        
        # 检查每日亏损限制
        if self.state.daily_loss_percent >= Config.DAILY_LOSS_LIMIT_PERCENT:
            self.state.status = TradeStatus.EMERGENCY_STOP
            self._save_state()
            self._send_alert("每日亏损限制触发！账户已锁定")
            return False, f"每日亏损已达 {self.state.daily_loss_percent:.2f}%，交易已暂停"
        
        # 检查交易时段
        hour = now.hour
        if hour < Config.TRADING_HOURS["start"] or hour >= Config.TRADING_HOURS["end"]:
            return False, f"当前时间 {hour}:00 不在允许交易时段内"
        
        # 检查连续错误
        if self.state.consecutive_errors >= 5:
            self.state.cooling_until = now + timedelta(hours=1)
            self._save_state()
            self._send_alert("连续错误过多，系统暂停1小时")
            return False, "连续错误过多，进入冷却期"
        
        return True, "交易许可正常"
    
    def calculate_position_size(self, entry_price: float, stop_loss: float, 
                               symbol: str) -> tuple[float, str]:
        """
        自动计算仓位大小
        
        Args:
            entry_price: 入场价格
            stop_loss: 止损价格
            symbol: 交易品种
            
        Returns:
            (仓位大小, 计算说明)
        """
        risk_amount = self.state.account_balance * (Config.PER_TRADE_RISK_PERCENT / 100)
        price_risk = abs(entry_price - stop_loss)
        
        if price_risk == 0:
            return 0, "错误：入场价与止损价相同"
        
        position_size = risk_amount / price_risk
        
        # 根据账户规模调整
        max_position_value = self.state.account_balance * 0.1  # 单笔最大占用10%资金
        if position_size * entry_price > max_position_value:
            position_size = max_position_value / entry_price
            
        explanation = (
            f"账户余额: {self.state.account_balance:.2f} | "
            f"风险金额: {risk_amount:.2f} | "
            f"价格风险: {price_risk:.4f} | "
            f"计算仓位: {position_size:.4f}"
        )
        
        return position_size, explanation
    
    def record_trade(self, trade: TradeRecord) -> None:
        """
        记录交易并更新风控状态
        """
        now = datetime.now()
        
        # 检查是否是新的一天
        if self.state.trades_today:
            last_trade_date = self.state.trades_today[-1].timestamp.date()
            if last_trade_date != now.date():
                # 新的一天，重置日度统计
                self.state.daily_start_balance = self.state.account_balance
                self.state.daily_pnl = 0
                self.state.daily_loss_percent = 0
                self.state.consecutive_losses = 0
                self.state.trades_today = []
        
        self.state.trades_today.append(trade)
        self.state.last_trade_time = now
        
        # 更新统计
        if trade.pnl is not None:
            self.state.daily_pnl += trade.pnl
            self.state.account_balance += trade.pnl
            
            # 计算日度亏损百分比
            self.state.daily_loss_percent = (
                -self.state.daily_pnl / self.state.daily_start_balance * 100 
                if self.state.daily_pnl < 0 else 0
            )
            
            # 更新连续亏损计数
            if trade.pnl < 0:
                self.state.consecutive_losses += 1
                
                # 检查冷却期触发
                if self.state.consecutive_losses >= 5:
                    self.state.cooling_until = now + timedelta(hours=Config.COOLING_PERIOD_LONG)
                    self.state.status = TradeStatus.COOLING_LONG
                    self._send_alert(f"触发长冷却期：连续{self.state.consecutive_losses}笔亏损")
                elif self.state.consecutive_losses >= 3:
                    self.state.cooling_until = now + timedelta(minutes=Config.COOLING_PERIOD_SHORT)
                    self.state.status = TradeStatus.COOLING_SHORT
                    self._send_alert(f"触发短冷却期：连续{self.state.consecutive_losses}笔亏损")
            else:
                self.state.consecutive_losses = 0
        
        # 检查滑点异常
        if trade.slippage > Config.SLIPPAGE_THRESHOLD:
            self._send_alert(f"滑点异常：{trade.slippage}点 > 阈值{Config.SLIPPAGE_THRESHOLD}点")
        
        # 检查执行延迟异常
        if trade.execution_time_ms > Config.LATENCY_THRESHOLD:
            self._send_alert(f"执行延迟异常：{trade.execution_time_ms}ms > 阈值{Config.LATENCY_THRESHOLD}ms")
        
        self._save_state()
        self.logger.info(f"交易记录已保存: {trade.symbol} PnL={trade.pnl}")
    
    def record_error(self, error_message: str) -> None:
        """
        记录系统错误
        """
        self.state.consecutive_errors += 1
        self._save_state()
        self.logger.error(f"系统错误: {error_message}")
        
        if self.state.consecutive_errors >= 5:
            self._send_alert(f"连续错误警告：已发生{self.state.consecutive_errors}次错误")
    
    def reset_daily_stats(self) -> None:
        """
        手动重置日度统计（谨慎使用）
        """
        self.state.daily_start_balance = self.state.account_balance
        self.state.daily_pnl = 0
        self.state.daily_loss_percent = 0
        self.state.consecutive_losses = 0
        self.state.consecutive_errors = 0
        self.state.cooling_until = None
        self.state.status = TradeStatus.LIVE_ENABLED
        self._save_state()
        self.logger.info("日度统计已重置")
    
    def get_status_report(self) -> str:
        """
        获取当前状态报告
        """
        report = f"""
=== 风控系统状态报告 ===
时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

账户状态:
- 当前余额: {self.state.account_balance:.2f}
- 日初余额: {self.state.daily_start_balance:.2f}
- 日度盈亏: {self.state.daily_pnl:.2f} ({self.state.daily_loss_percent:.2f}%)

风控状态:
- 当前状态: {self.state.status.value}
- 连续亏损: {self.state.consecutive_losses}
- 连续错误: {self.state.consecutive_errors}

交易统计:
- 今日交易数: {len(self.state.trades_today)}
- 最后交易时间: {self.state.last_trade_time.strftime('%H:%M:%S') if self.state.last_trade_time else '无'}
"""
        if self.state.cooling_until:
            remaining = self.state.cooling_until - datetime.now()
            report += f"- 冷却期剩余: {remaining}\n"
        
        # 检查权限
        allowed, reason = self.check_trading_permission()
        report += f"\n交易许可: {'允许' if allowed else '禁止'}\n原因: {reason}\n"
        
        return report
    
    def _send_alert(self, message: str) -> None:
        """
        发送告警通知
        """
        self.logger.warning(f"ALERT: {message}")
        
        # 如果配置了邮件，发送邮件告警
        if Config.ALERT_EMAIL and Config.SMTP_SERVER:
            try:
                msg = MIMEText(message)
                msg['Subject'] = f'[交易风控告警] {message[:50]}'
                msg['From'] = Config.SMTP_USER
                msg['To'] = Config.ALERT_EMAIL
                
                with smtplib.SMTP(Config.SMTP_SERVER) as server:
                    server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                    server.send_message(msg)
            except Exception as e:
                self.logger.error(f"邮件发送失败: {e}")

# ============ 命令行接口 ============

def main():
    """命令行接口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='交易风控系统')
    parser.add_argument('--status', action='store_true', help='显示当前状态')
    parser.add_argument('--check', action='store_true', help='检查交易权限')
    parser.add_argument('--reset', action='store_true', help='重置日度统计（需要确认）')
    parser.add_argument('--simulate-trade', nargs=5, 
                       metavar=('SYMBOL', 'PNL', 'SLIPPAGE', 'LATENCY', 'STRATEGY'),
                       help='模拟记录一笔交易')
    
    args = parser.parse_args()
    
    rm = RiskManager()
    
    if args.status:
        print(rm.get_status_report())
    
    elif args.check:
        allowed, reason = rm.check_trading_permission()
        print(f"交易许可: {'允许' if allowed else '禁止'}")
        print(f"原因: {reason}")
    
    elif args.reset:
        confirm = input("确认重置所有日度统计？输入 'RESET' 确认: ")
        if confirm == 'RESET':
            rm.reset_daily_stats()
            print("已重置")
        else:
            print("取消")
    
    elif args.simulate_trade:
        symbol, pnl, slippage, latency, strategy = args.simulate_trade
        trade = TradeRecord(
            timestamp=datetime.now(),
            symbol=symbol,
            direction="LONG",
            entry_price=100.0,
            exit_price=100.0,
            size=1.0,
            pnl=float(pnl),
            slippage=float(slippage),
            execution_time_ms=float(latency),
            strategy=strategy
        )
        rm.record_trade(trade)
        print(f"已记录交易: {symbol} PnL={pnl}")
        print(rm.get_status_report())
    
    else:
        print("使用 --help 查看可用命令")
        print("\n快速状态:")
        print(rm.get_status_report())

if __name__ == '__main__':
    main()
