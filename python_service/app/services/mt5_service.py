import MetaTrader5 as mt5
import subprocess
import os
import time


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

def _resolve_mt5_executable_path(path: str | None) -> str | None:
    if not path or not os.path.exists(path):
        return None

    if os.path.isdir(path):
        executable_path = f"{path.rstrip('/\\')}/terminal64.exe"
        if os.path.exists(executable_path):
            return executable_path

    return path


def init_mt5(path: str | None = None, *, allow_launch: bool = True) -> bool:
    # 1. 首先尝试连接已打开的 MT5 (不带路径参数会连接到当前运行的终端)
    try:
        if mt5.initialize():
            return True
    except Exception as e:
        print(f"Error checking for open MT5: {e}")
    
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


def shutdown_mt5() -> None:
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
    if init_mt5(get_settings_path(), allow_launch=allow_launch):
        return mt5
    return None

def get_account_info(*, allow_launch: bool = True) -> dict:
    if not init_mt5(get_settings_path(), allow_launch=allow_launch):
        return {}
    
    info = mt5.account_info()
    if info is None:
        return {}
    
    return info._asdict()

def get_positions(*, allow_launch: bool = True) -> list[dict]:
    if not init_mt5(get_settings_path(), allow_launch=allow_launch):
        return []
    
    positions = mt5.positions_get()
    if positions is None:
        return []
    
    return [p._asdict() for p in positions]
