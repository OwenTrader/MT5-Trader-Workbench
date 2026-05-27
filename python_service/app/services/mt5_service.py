import MetaTrader5 as mt5
import subprocess
import os
import time
import threading
from contextlib import contextmanager
from datetime import datetime, timezone


_mt5_lock = threading.RLock()


@contextmanager
def mt5_connection_lock():
    with _mt5_lock:
        yield


def _normalize_login(login: str | int | None) -> int | None:
    if login is None:
        return None

    if isinstance(login, int):
        return login

    login_value = str(login).strip()
    if not login_value:
        return None

    return int(login_value)

def is_mt5_running() -> bool:
    # This is a naive check, MetaTrader5.initialize() is better but requires the terminal to be open
    # We can check for terminal64.exe process
    try:
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        output = subprocess.check_output(['tasklist'], text=True, creationflags=subprocess.CREATE_NO_WINDOW, startupinfo=startupinfo)
        return 'terminal64.exe' in output
    except:
        return False

def launch_mt5(path: str):
    if not path or not os.path.exists(path):
        return False
    
    try:
        subprocess.Popen([path])
        return True
    except:
        return False


def _create_hidden_startupinfo():
    if os.name != 'nt':
        return None
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return startupinfo


def list_running_mt5_paths() -> list[str]:
    if os.name != 'nt':
        return []

    try:
        output = subprocess.check_output(
            [
                'powershell.exe',
                '-NoProfile',
                '-Command',
                "Get-CimInstance Win32_Process -Filter \"name = 'terminal64.exe'\" | Select-Object -ExpandProperty ExecutablePath"
            ],
            text=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
            startupinfo=_create_hidden_startupinfo(),
        )
    except Exception:
        return []

    normalized_paths: list[str] = []
    seen_paths: set[str] = set()
    for line in output.splitlines():
        candidate = _resolve_mt5_executable_path(line.strip())
        if not candidate:
            continue
        candidate_key = os.path.normcase(candidate)
        if candidate_key in seen_paths:
            continue
        seen_paths.add(candidate_key)
        normalized_paths.append(candidate)
    return normalized_paths

def _resolve_mt5_executable_path(path: str | None) -> str | None:
    if not path or not os.path.exists(path):
        return None

    if os.path.isdir(path):
        executable_path = f"{path.rstrip('/\\')}/terminal64.exe"
        if os.path.exists(executable_path):
            return executable_path

    return path


def _prioritize_preferred_path(paths: list[str], preferred_path: str | None) -> list[str]:
    resolved_preferred = _resolve_mt5_executable_path(preferred_path)
    if not resolved_preferred:
        return paths

    preferred_key = os.path.normcase(resolved_preferred)
    preferred_matches = [path for path in paths if os.path.normcase(path) == preferred_key]
    remaining = [path for path in paths if os.path.normcase(path) != preferred_key]
    return [*preferred_matches, *remaining]


def _connect_running_mt5_terminals_unlocked(preferred_path: str | None = None) -> bool:
    candidates = _prioritize_preferred_path(list_running_mt5_paths(), preferred_path)
    for candidate in candidates:
        try:
            mt5.shutdown()
        except Exception:
            pass

        try:
            if not mt5.initialize(path=candidate):
                continue
            if mt5.account_info() is None:
                try:
                    mt5.shutdown()
                except Exception:
                    pass
                continue
            return True
        except Exception as error:
            print(f"Error connecting running MT5 terminal {candidate}: {error}")
            try:
                mt5.shutdown()
            except Exception:
                pass
    return False


def init_mt5(path: str | None = None, *, allow_launch: bool = True, prefer_existing: bool = True) -> bool:
    with _mt5_lock:
        return _init_mt5_unlocked(path, allow_launch=allow_launch, prefer_existing=prefer_existing)


def _init_mt5_unlocked(path: str | None = None, *, allow_launch: bool = True, prefer_existing: bool = True) -> bool:
    if prefer_existing:
        # 1. 优先复用已运行的 MT5 终端；如果有多个，则逐个尝试直到找到已登录可用的终端。
        if _connect_running_mt5_terminals_unlocked(path):
            return True
    
    if not allow_launch:
        return False

    # 2. 如果未找到已运行的，尝试从指定路径拉起 (最多尝试4次)
    max_retries = 4
    actual_path = _resolve_mt5_executable_path(path)

    for i in range(max_retries):
        if actual_path and os.path.exists(actual_path):
            print(f"Attempting to initialize MT5 at: {actual_path} (Attempt {i+1}/{max_retries})")
            try:
                if mt5.initialize(path=actual_path):
                    return True
                else:
                    print(f"Attempt {i+1}/{max_retries} failed, error code = {mt5.last_error()}")
            except Exception as e:
                print(f"MT5 initialization crashed: {e}")
        
        if i < max_retries - 1:
            time.sleep(1) # 在重试之间等待 1 秒
            
    print(f"MT5 initialization failed after {max_retries} attempts.")
    return False


def verify_mt5_credentials(path: str, login: str, password: str, server: str) -> tuple[bool, str | None]:
    with _mt5_lock:
        return _verify_mt5_credentials_unlocked(path, login, password, server)


def _verify_mt5_credentials_unlocked(path: str, login: str, password: str, server: str) -> tuple[bool, str | None]:
    actual_path = _resolve_mt5_executable_path(path)
    if not actual_path or not os.path.exists(actual_path):
        return False, 'MT5 terminal path is invalid or does not exist'

    if not str(login).strip() or not password or not str(server).strip():
        return False, 'MT5 login, password, and server are required'

    try:
        mt5.shutdown()
    except Exception:
        pass

    try:
        normalized_login = _normalize_login(login)
    except ValueError:
        return False, 'MT5 login must be numeric'

    try:
        success = mt5.initialize(
            path=actual_path,
            login=normalized_login,
            password=password,
            server=server.strip(),
        )
        if not success:
            return False, f'Failed to connect to MT5 with the provided credentials. Error: {mt5.last_error()}'

        account_info = mt5.account_info()
        if account_info is None:
            return False, f'MT5 connected but account information is unavailable. Error: {mt5.last_error()}'

        return True, None
    except Exception as error:
        return False, f'Failed to connect to MT5 with the provided credentials. Error: {error}'
    finally:
        try:
            mt5.shutdown()
        except Exception:
            pass


def init_mt5_account(path: str, login: str, password: str, server: str) -> tuple[bool, str | None]:
    with _mt5_lock:
        return _init_mt5_account_unlocked(path, login, password, server)


def _init_mt5_account_unlocked(path: str, login: str, password: str, server: str) -> tuple[bool, str | None]:
    actual_path = _resolve_mt5_executable_path(path)
    if not actual_path or not os.path.exists(actual_path):
        return False, 'MT5 terminal path is invalid or does not exist'

    try:
        normalized_login = _normalize_login(login)
    except ValueError:
        return False, 'MT5 login must be numeric'

    try:
        mt5.shutdown()
    except Exception:
        pass

    try:
        success = mt5.initialize(
            path=actual_path,
            login=normalized_login,
            password=password,
            server=server.strip(),
        )
        if not success:
            return False, f'Failed to connect to MT5 account. Error: {mt5.last_error()}'
        return True, None
    except Exception as error:
        return False, f'Failed to connect to MT5 account. Error: {error}'


def shutdown_mt5() -> None:
    with _mt5_lock:
        try:
            mt5.shutdown()
        except Exception:
            pass


def verify_mt5_path_connection(path: str) -> tuple[bool, str | None, dict | None]:
    with _mt5_lock:
        actual_path = _resolve_mt5_executable_path(path)
        if not actual_path or not os.path.exists(actual_path):
            return False, 'MT5 terminal path is invalid or does not exist', None

        try:
            mt5.shutdown()
        except Exception:
            pass

        try:
            success = mt5.initialize(path=actual_path)
            if not success:
                return False, f'Failed to connect to MT5 at the specified path. Error code: {mt5.last_error()}', None

            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                return False, f'MT5 connected but terminal information is unavailable. Error: {mt5.last_error()}', None

            return True, None, terminal_info._asdict()
        except Exception as error:
            return False, f'Failed to connect to MT5 at the specified path. Error: {error}', None
        finally:
            try:
                mt5.shutdown()
            except Exception:
                pass

def get_settings_path():
    try:
        from python_service.app.routes.settings import get_settings
        return get_settings().mt5_path
    except:
        return None

def get_mt5_client(*, allow_launch: bool = True):
    with _mt5_lock:
        if _init_mt5_unlocked(get_settings_path(), allow_launch=allow_launch):
            return mt5
        return None

def get_account_info(*, allow_launch: bool = True) -> dict:
    with _mt5_lock:
        if not _init_mt5_unlocked(get_settings_path(), allow_launch=allow_launch):
            return {}
        
        info = mt5.account_info()
        if info is None:
            return {}
        
        return info._asdict()

def get_positions(*, allow_launch: bool = True) -> list[dict]:
    with _mt5_lock:
        if not _init_mt5_unlocked(get_settings_path(), allow_launch=allow_launch):
            return []
        
        positions = mt5.positions_get()
        if positions is None:
            return []
        
        return [p._asdict() for p in positions]


def get_recent_candles(
    symbol: str,
    *,
    timeframe=None,
    count: int = 100,
    allow_launch: bool = False,
) -> list[dict]:
    with _mt5_lock:
        if not _init_mt5_unlocked(get_settings_path(), allow_launch=allow_launch):
            return []

        resolved_timeframe = timeframe if timeframe is not None else mt5.TIMEFRAME_M15
        rates = mt5.copy_rates_from_pos(symbol, resolved_timeframe, 0, count)
        if rates is None:
            return []

        candles: list[dict] = []
        for rate in rates:
            payload = rate._asdict() if hasattr(rate, '_asdict') else dict(rate)
            candles.append({
                'time': datetime.fromtimestamp(int(payload['time']), timezone.utc).isoformat(),
                'open': float(payload['open']),
                'high': float(payload['high']),
                'low': float(payload['low']),
                'close': float(payload['close']),
                'volume': float(payload.get('tick_volume') or payload.get('real_volume') or 0),
            })
        return candles
