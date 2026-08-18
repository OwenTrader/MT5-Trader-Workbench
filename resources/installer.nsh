!macro customInit
  ; Detect running instances of MT5 Trader Workbench
  nsProcess::_FindProcess "MT5 Trader Workbench.exe"
  Pop $R0
  ${If} $R0 = 0
    MessageBox MB_OKCANCEL|MB_ICONEXCLAMATION "检测到 MT5 Trader Workbench 正在运行。$\r$\n$\r$\n请在继续安装前保存并关闭应用程序，然后点击“确定”继续。" IDCANCEL cancelInstall
    nsProcess::_KillProcess "MT5 Trader Workbench.exe"
    Pop $R0
    Sleep 1000
  ${EndIf}

  ; Detect running instances of Python backend service
  nsProcess::_FindProcess "mt5_service.exe"
  Pop $R0
  ${If} $R0 = 0
    nsProcess::_KillProcess "mt5_service.exe"
    Pop $R0
    Sleep 500
  ${EndIf}
  Goto initDone

cancelInstall:
  Abort

initDone:
!macroend

!macro customUnInstall
  ; Ensure background mt5_service is stopped during uninstall
  nsProcess::_FindProcess "mt5_service.exe"
  Pop $R0
  ${If} $R0 = 0
    nsProcess::_KillProcess "mt5_service.exe"
    Pop $R0
    Sleep 500
  ${EndIf}
!macroend
