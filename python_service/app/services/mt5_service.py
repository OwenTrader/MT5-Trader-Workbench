import MetaTrader5 as mt5
import subprocess
import os

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

def init_mt5(path: str = None) -> bool:
    # 1. 首先尝试连接已打开的 MT5 (不带路径参数会连接到当前运行的终端)
    try:
        if mt5.initialize():
            return True
    except Exception as e:
        print(f"Error checking for open MT5: {e}")
    
    # 2. 如果未找到已运行的，尝试从指定路径拉起 (最多尝试4次)
    import time
    max_retries = 4
    
    # 预处理路径：如果是目录，尝试补全可执行文件名
    actual_path = path
    if path and os.path.exists(path) and os.path.isdir(path):
        temp_path = os.path.join(path, "terminal64.exe")
        if os.path.exists(temp_path):
            actual_path = temp_path
            print(f"Path is a directory, using executable: {actual_path}")

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

def get_settings_path():
    try:
        from python_service.app.routes.settings import get_settings
        return get_settings().mt5_path
    except:
        return None

def get_mt5_client():
    if init_mt5(get_settings_path()):
        return mt5
    return None

def get_account_info() -> dict:
    if not init_mt5(get_settings_path()):
        return {}
    
    info = mt5.account_info()
    if info is None:
        return {}
    
    return info._asdict()

def get_positions() -> list[dict]:
    if not init_mt5(get_settings_path()):
        return []
    
    positions = mt5.positions_get()
    if positions is None:
        return []
    
    return [p._asdict() for p in positions]
