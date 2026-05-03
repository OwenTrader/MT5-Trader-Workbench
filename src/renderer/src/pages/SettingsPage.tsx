import React, { useEffect, useState } from 'react'
import { useTheme } from 'next-themes'
import { useSettingsStore } from '@/stores/settings-store'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { Switch } from '@/components/ui/switch'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useI18n } from '@/i18n'
import { PageHeader } from '@/components/page-header'
import { cn, debounce } from '@/lib/utils'
import { toast } from 'sonner'
import { Settings } from 'lucide-react'

export const SettingsPage: React.FC = () => {
  const { t } = useI18n()
  const { theme, setTheme } = useTheme()
  const { settings, fetchSettings, updateSettings, isLoading } = useSettingsStore()
  const [localSettings, setLocalSettings] = useState(settings)
  const [isVerifying, setIsVerifying] = useState(false)
  const [verifyStatus, setVerifyStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null)
  const [botDialog, setBotDialog] = useState<{ open: boolean; title: string; message: string }>({
    open: false,
    title: '',
    message: '',
  })

  const [resourcesPath, setResourcesPath] = useState<string>('')

  const selectedAlertSound =
    localSettings.alert_sound_path?.includes('01.mp3') ? '01.mp3' :
    localSettings.alert_sound_path?.includes('02.mp3') ? '02.mp3' :
    localSettings.alert_sound_path?.includes('03.mp3') ? '03.mp3' :
    'custom'

  const resolvedAlertSoundPath = ['01.mp3', '02.mp3', '03.mp3'].includes(localSettings.alert_sound_path)
    ? `${resourcesPath}\\audio\\${localSettings.alert_sound_path}`
    : localSettings.alert_sound_path

  const isBuiltInAlertSound = ['01.mp3', '02.mp3', '03.mp3'].some((sound) =>
    localSettings.alert_sound_path?.includes(sound)
  )

  useEffect(() => {
    fetchSettings()

    // Get resources path for built-in sounds
    if ((window as any).electron?.ipcRenderer) {
      (window as any).electron.ipcRenderer.invoke('app:get-resources-path').then(setResourcesPath)
    }

    // Listen for settings change notifications
    let removeSettingsListener: (() => void) | undefined
    
    if ((window as any).electron?.ipcRenderer) {
      removeSettingsListener = (window as any).electron.ipcRenderer.on('settings:changed', () => {
        fetchSettings()
      })
    }

    return () => {
      removeSettingsListener?.()
    }
  }, [])

  useEffect(() => {
    setLocalSettings(settings)
    if (settings.theme) {
      setTheme(settings.theme)
    }
  }, [settings])

  const handleSave = () => {
    updateSettings(localSettings)
  }

  const handleBotSave = async (settingsPatch: Partial<typeof localSettings>) => {
    await updateSettings(settingsPatch)
  }

  const openBotDialog = (title: string, message: string) => {
    setBotDialog({ open: true, title, message })
  }

  const debouncedDingtalkSave = React.useMemo(
    () => debounce((settingsPatch: Partial<typeof localSettings>) => {
      void handleBotSave(settingsPatch)
    }, 400),
    []
  )

  const debouncedWecomSave = React.useMemo(
    () => debounce((settingsPatch: Partial<typeof localSettings>) => {
      void handleBotSave(settingsPatch)
    }, 400),
    []
  )

  const debouncedFeishuSave = React.useMemo(
    () => debounce((settingsPatch: Partial<typeof localSettings>) => {
      void handleBotSave(settingsPatch)
    }, 400),
    []
  )

  const handleBotToggle = async (
    nextChecked: boolean,
    configValid: boolean,
    errorMessage: string,
    settingsPatch: Partial<typeof localSettings>
  ) => {
    if (nextChecked && !configValid) {
      toast.error(errorMessage)
      return
    }

    setLocalSettings((current) => ({ ...current, ...settingsPatch }))
    await updateSettings(settingsPatch)
  }

  const handleBotTest = async (
    configValid: boolean,
    errorMessage: string,
    request: () => Promise<void>
  ) => {
    if (!configValid) {
      toast.error(errorMessage)
      return
    }

    await request()
  }

  const debouncedDingtalkTest = React.useMemo(
    () => debounce(async () => {
      await handleBotTest(
        localSettings.dingtalk_token.trim().length > 0,
        t('settings.bot.dingtalkConfigRequired'),
        async () => {
          try {
            const res = await fetch('http://127.0.0.1:8765/notifications/test_dingtalk', { method: 'POST' })
            const rawResponse = await res.text()
            openBotDialog(t('settings.bot.dingtalkTitle'), rawResponse || t('settings.bot.testFailed'))
          } catch (e) {
            openBotDialog(t('settings.bot.dingtalkTitle'), t('settings.bot.networkError'))
          }
        }
      )
    }, 400),
    [localSettings.dingtalk_token, t]
  )

  const debouncedWecomTest = React.useMemo(
    () => debounce(async () => {
      await handleBotTest(
        localSettings.wecom_webhook_url.trim().length > 0,
        t('settings.bot.wecomConfigRequired'),
        async () => {
          try {
            const res = await fetch('http://127.0.0.1:8765/notifications/test_wecom', { method: 'POST' })
            const rawResponse = await res.text()
            openBotDialog(t('settings.bot.wecomTitle'), rawResponse || t('settings.bot.testFailed'))
          } catch (e) {
            openBotDialog(t('settings.bot.wecomTitle'), t('settings.bot.networkError'))
          }
        }
      )
    }, 400),
    [localSettings.wecom_webhook_url, t]
  )

  const debouncedFeishuTest = React.useMemo(
    () => debounce(async () => {
      await handleBotTest(
        localSettings.feishu_webhook_url.trim().length > 0,
        t('settings.bot.feishuConfigRequired'),
        async () => {
          try {
            const res = await fetch('http://127.0.0.1:8765/notifications/test_feishu', { method: 'POST' })
            const rawResponse = await res.text()
            openBotDialog(t('settings.bot.feishuTitle'), rawResponse || t('settings.bot.testFailed'))
          } catch (e) {
            openBotDialog(t('settings.bot.feishuTitle'), t('settings.bot.networkError'))
          }
        }
      )
    }, 400),
    [localSettings.feishu_webhook_url, t]
  )

  const debouncedVerifyPath = React.useMemo(
    () => debounce(() => {
      void handleVerifyPath()
    }, 400),
    [localSettings.mt5_path, t]
  )

  useEffect(() => {
    return () => {
      debouncedDingtalkSave.cancel()
      debouncedWecomSave.cancel()
      debouncedFeishuSave.cancel()
      debouncedDingtalkTest.cancel()
      debouncedWecomTest.cancel()
      debouncedFeishuTest.cancel()
      debouncedVerifyPath.cancel()
    }
  }, [
    debouncedDingtalkSave,
    debouncedWecomSave,
    debouncedFeishuSave,
    debouncedDingtalkTest,
    debouncedWecomTest,
    debouncedFeishuTest,
    debouncedVerifyPath,
  ])

  const handleThemeChange = async (value: string) => {
    setLocalSettings((current) => ({ ...current, theme: value }))
    setTheme(value)
    await updateSettings({ theme: value })
  }

  const handleLanguageChange = async (value: 'zh-CN' | 'en') => {
    setLocalSettings((current) => ({ ...current, language: value }))
    await updateSettings({ language: value })
  }

  const handleVerifyPath = async () => {
    if (!localSettings.mt5_path) {
      setVerifyStatus({ type: 'error', message: t('settings.status.mt5PathRequired') })
      return
    }

    setIsVerifying(true)
    setVerifyStatus(null)
    try {
      const response = await fetch('http://127.0.0.1:8765/mt5/verify_path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: localSettings.mt5_path })
      })
      const result = await response.json()
      if (result.status === 'ok') {
        setVerifyStatus({ type: 'success', message: t('settings.status.verifySuccess') })
        toast.success(t('settings.status.verifySuccessTitle'), {
          description: t('settings.status.verifySuccessDescription')
        })
      } else {
        setVerifyStatus({ type: 'error', message: result.message })
        toast.error(t('settings.status.verifyFailedTitle'), {
          description: result.message
        })
      }
    } catch (err) {
      setVerifyStatus({ type: 'error', message: t('settings.status.requestFailed') })
      toast.error(t('settings.status.verifyFailedTitle'), {
        description: t('settings.status.requestFailed')
      })
    } finally {
      setIsVerifying(false)
    }
  }

  return (
    <div className="p-6 space-y-6">
      <Dialog open={botDialog.open} onOpenChange={(open) => setBotDialog((current) => ({ ...current, open }))}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{botDialog.title}</DialogTitle>
            <DialogDescription>{botDialog.message}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={() => setBotDialog((current) => ({ ...current, open: false }))}>知道了</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PageHeader title={t('settings.title')} icon={Settings} />

      <Tabs defaultValue="general" className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-4">
          <TabsTrigger value="general">{t('settings.tabs.general')}</TabsTrigger>
          <TabsTrigger value="sound">{t('settings.tabs.sound')}</TabsTrigger>
          <TabsTrigger value="bot">{t('settings.tabs.bot')}</TabsTrigger>
          <TabsTrigger value="about">{t('settings.tabs.about')}</TabsTrigger>
        </TabsList>
        
        <TabsContent value="general" className="space-y-6 pt-4">
          <div className="space-y-4 max-w-md">
            <div className="space-y-2">
              <Label htmlFor="language-select">{t('settings.language.label')}</Label>
              <Select
                value={localSettings.language || 'zh-CN'}
                onValueChange={handleLanguageChange}
              >
                <SelectTrigger id="language-select">
                  <SelectValue placeholder={t('settings.language.label')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="zh-CN">{t('settings.language.zhCN')}</SelectItem>
                    <SelectItem value="en">{t('settings.language.en')}</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="mt5-path">{t('settings.general.mt5PathLabel')}</Label>
              <div className="flex gap-2">
                <Input 
                  id="mt5-path" 
                  value={localSettings.mt5_path} 
                  onChange={(e) => setLocalSettings({ ...localSettings, mt5_path: e.target.value })}
                  placeholder={t('settings.general.mt5PathPlaceholder')}
                  className="flex-1"
                />
                <Button 
                  variant="outline" 
                  onClick={debouncedVerifyPath}
                  disabled={isVerifying}
                >
                  {isVerifying ? t('settings.general.verifying') : t('settings.general.verifyIdle')}
                </Button>
              </div>
              <p className="text-[12px] text-muted-foreground mt-1">
                {t('settings.general.mt5PathHint')}
              </p>
              {verifyStatus && (
                <p className={cn("text-xs font-medium mt-1", 
                  verifyStatus.type === 'success' ? "text-green-500" : "text-red-500"
                )}>
                  {verifyStatus.message}
                </p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="theme-select">{t('settings.theme.label')}</Label>
              <Select 
                value={localSettings.theme || 'light'}
                onValueChange={handleThemeChange}
              >
                <SelectTrigger id="theme-select">
                  <SelectValue placeholder={t('settings.theme.label')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="light">{t('settings.theme.light')}</SelectItem>
                    <SelectItem value="dark">{t('settings.theme.dark')}</SelectItem>
                    <SelectItem value="system">{t('settings.theme.system')}</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="overlay-symbols">{t('settings.general.overlaySymbolsLabel')}</Label>
              <Input 
                id="overlay-symbols" 
                value={(localSettings.overlay_symbols || []).join(', ')} 
                onChange={(e) => setLocalSettings({ 
                  ...localSettings, 
                  overlay_symbols: e.target.value.split(',').map(s => s.trim()).filter(Boolean) 
                })}
                placeholder={t('settings.general.overlaySymbolsPlaceholder')}
              />
            </div>

            <div className="flex items-center space-x-2">
              <Checkbox 
                id="auto-connect" 
                checked={localSettings.auto_connect}
                onCheckedChange={(checked) => setLocalSettings({ ...localSettings, auto_connect: checked === true })}
              />
              <Label htmlFor="auto-connect">{t('settings.general.autoConnectLabel')}</Label>
            </div>

            <div className="space-y-2">
              <Label htmlFor="refresh-interval">{t('settings.general.refreshIntervalLabel')}</Label>
              <Select 
                value={String(localSettings.api_refresh_interval)}
                onValueChange={(value) => setLocalSettings({ ...localSettings, api_refresh_interval: parseInt(value, 10) })}
              >
                <SelectTrigger id="refresh-interval">
                  <SelectValue placeholder={t('settings.general.refreshIntervalLabel')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectGroup>
                    <SelectItem value="2000">{t('settings.general.refreshIntervalDefault')}</SelectItem>
                    <SelectItem value="100">100ms</SelectItem>
                    <SelectItem value="500">500ms</SelectItem>
                    <SelectItem value="1000">1000ms</SelectItem>
                    <SelectItem value="2000">2000ms</SelectItem>
                  </SelectGroup>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="overlay-font-size">{t('settings.general.overlayFontSizeLabel')}</Label>
              <Input 
                id="overlay-font-size" 
                type="number" 
                value={localSettings.overlay_font_size} 
                onChange={(e) => setLocalSettings({ ...localSettings, overlay_font_size: parseInt(e.target.value) })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="overlay-font-color">{t('settings.general.overlayFontColorLabel')}</Label>
              <div className="flex gap-2">
                <Input 
                  id="overlay-font-color" 
                  type="color" 
                  className="w-12 h-10 p-1"
                  value={localSettings.overlay_font_color} 
                  onChange={(e) => setLocalSettings({ ...localSettings, overlay_font_color: e.target.value })}
                />
                <Input 
                  type="text" 
                  value={localSettings.overlay_font_color} 
                  onChange={(e) => setLocalSettings({ ...localSettings, overlay_font_color: e.target.value })}
                  className="flex-1 font-mono text-sm"
                />
              </div>
            </div>

            <Button onClick={handleSave} disabled={isLoading}>
              {isLoading ? t('settings.actions.saving') : t('settings.actions.save')}
            </Button>
          </div>
        </TabsContent>

        <TabsContent value="sound" className="pt-4 space-y-6">
          <div className="space-y-4 max-w-md">
            <div className="flex items-center space-x-2 pb-2">
              <Checkbox 
                id="alert-sound-enabled" 
                checked={localSettings.alert_sound_enabled}
                onCheckedChange={(checked) => setLocalSettings({ ...localSettings, alert_sound_enabled: checked === true })}
              />
              <Label htmlFor="alert-sound-enabled" className="text-base font-medium">{t('settings.sound.enableAlertSound')}</Label>
            </div>

            {localSettings.alert_sound_enabled ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="sound-select">{t('settings.sound.soundSelectLabel')}</Label>
                  <Select
                    value={selectedAlertSound}
                    onValueChange={(val) => {
                      if (val === 'custom') {
                        setLocalSettings({
                          ...localSettings,
                          alert_sound_path: isBuiltInAlertSound ? '' : localSettings.alert_sound_path,
                          alert_sound_enabled: true,
                        })
                        return
                      }

                      setLocalSettings({ ...localSettings, alert_sound_path: val, alert_sound_enabled: true })
                    }}
                  >
                    <SelectTrigger id="sound-select">
                      <SelectValue placeholder={t('settings.sound.soundSelectLabel')} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectGroup>
                        <SelectItem value="01.mp3">{t('settings.sound.builtIn1')}</SelectItem>
                        <SelectItem value="02.mp3">{t('settings.sound.builtIn2')}</SelectItem>
                        <SelectItem value="03.mp3">{t('settings.sound.builtIn3')}</SelectItem>
                        <SelectItem value="custom">{t('settings.sound.customFile')}</SelectItem>
                      </SelectGroup>
                    </SelectContent>
                  </Select>
                </div>

                {!isBuiltInAlertSound ? (
               <div className="space-y-2 animate-in fade-in slide-in-from-top-1">
                 <Label htmlFor="alert-sound-path">{t('settings.sound.customSoundPathLabel')}</Label>
                 <div className="flex gap-2">
                  <Input 
                    id="alert-sound-path" 
                    value={localSettings.alert_sound_path || ''} 
                    onChange={(e) => setLocalSettings({ ...localSettings, alert_sound_path: e.target.value })}
                    placeholder={t('settings.sound.customSoundPathPlaceholder')}
                    className="flex-1"
                  />
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={async () => {
                      if ((window as any).electron?.ipcRenderer) {
                        const path = await (window as any).electron.ipcRenderer.invoke('dialog:openFile', {
                          filters: [{ name: 'Audio Files', extensions: ['mp3', 'wav', 'ogg'] }]
                        })
                        if (path) {
                          setLocalSettings({ ...localSettings, alert_sound_path: path })
                        }
                      }
                    }}
                  >
                    {t('settings.sound.browse')}
                   </Button>
                 </div>
               </div>
                ) : null}

                <div className="space-y-2">
                  <Label htmlFor="alert-sound-volume">{t('settings.sound.volumeLabel', { volume: Math.round((localSettings.alert_sound_volume || 0.5) * 100) })}</Label>
                  <Input
                    id="alert-sound-volume"
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={localSettings.alert_sound_volume || 0.5}
                    onChange={(e) => setLocalSettings({ ...localSettings, alert_sound_volume: parseFloat(e.target.value) })}
                    className="w-full h-6"
                  />
                </div>

                <div className="pt-2 flex gap-2">
                  <Button
                    variant="secondary"
                    className="flex-1"
                    disabled={!resolvedAlertSoundPath}
                    onClick={() => {
                      if (resolvedAlertSoundPath) {
                        const audio = new Audio(`local-file://${resolvedAlertSoundPath}`)
                        audio.volume = localSettings.alert_sound_volume || 0.5
                        audio.play().catch(() => {
                          toast.error(t('settings.sound.playFailedTitle'), { description: t('settings.sound.playFailedDescription') })
                        })
                      }
                    }}
                  >
                    {t('settings.sound.playTest')}
                  </Button>
                  <Button onClick={handleSave} className="flex-1" disabled={isLoading}>
                    {isLoading ? t('settings.actions.saving') : t('settings.actions.save')}
                  </Button>
                </div>
              </>
            ) : (
              <div className="pt-2">
                <Button onClick={handleSave} className="w-full" disabled={isLoading}>
                  {isLoading ? t('settings.actions.saving') : t('settings.actions.save')}
                </Button>
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="bot" className="pt-4 space-y-6">
          <div className="flex flex-col gap-4">
              <h3 className="font-medium text-sm">{t('settings.bot.title')}</h3>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
                <div className="flex flex-col gap-4 rounded-lg border p-4 bg-card">
                  <h4 className="text-sm font-semibold">{t('settings.bot.categoriesTitle')}</h4>
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="push-price-alerts" className="text-sm font-medium">{t('settings.bot.pushPriceAlerts')}</Label>
                    <Switch
                      id="push-price-alerts"
                      checked={localSettings.push_price_alerts === true}
                      onCheckedChange={(checked) => {
                        setLocalSettings((current) => ({ ...current, push_price_alerts: checked }))
                        void updateSettings({ push_price_alerts: checked })
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="push-volatility-alerts" className="text-sm font-medium">{t('settings.bot.pushVolatilityAlerts')}</Label>
                    <Switch
                      id="push-volatility-alerts"
                      checked={localSettings.push_volatility_alerts === true}
                      onCheckedChange={(checked) => {
                        setLocalSettings((current) => ({ ...current, push_volatility_alerts: checked }))
                        void updateSettings({ push_volatility_alerts: checked })
                      }}
                    />
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="push-indicator-alerts" className="text-sm font-medium">{t('settings.bot.pushIndicatorAlerts')}</Label>
                    <Switch
                      id="push-indicator-alerts"
                      checked={localSettings.push_indicator_alerts === true}
                      onCheckedChange={(checked) => {
                        setLocalSettings((current) => ({ ...current, push_indicator_alerts: checked }))
                        void updateSettings({ push_indicator_alerts: checked })
                      }}
                    />
                  </div>
                </div>

                <div className="flex flex-col gap-4 rounded-lg border p-4 bg-card">
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="dingtalk-enabled" className="text-sm font-medium">{t('settings.bot.dingtalkTitle')}</Label>
                    <div className="flex items-center gap-2">
                      <Label htmlFor="dingtalk-enabled" className="text-xs text-muted-foreground">
                        {localSettings.dingtalk_enabled ? t('settings.bot.enabledLabel') : t('settings.bot.disabledLabel')}
                      </Label>
                      <Switch
                        id="dingtalk-enabled"
                        checked={localSettings.dingtalk_enabled === true}
                        onCheckedChange={(checked) => handleBotToggle(
                          checked,
                          localSettings.dingtalk_token.trim().length > 0,
                          t('settings.bot.dingtalkConfigRequired'),
                          {
                            dingtalk_enabled: checked,
                            dingtalk_token: localSettings.dingtalk_token,
                            dingtalk_secret: localSettings.dingtalk_secret,
                          }
                        )}
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="dingtalk-token">{t('settings.bot.tokenLabel')}</Label>
                    <Input 
                      id="dingtalk-token" 
                      value={localSettings.dingtalk_token} 
                      onChange={(e) => setLocalSettings({ ...localSettings, dingtalk_token: e.target.value })}
                      placeholder={t('settings.bot.tokenPlaceholder')} 
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="dingtalk-secret">{t('settings.bot.secretLabel')}</Label>
                    <Input 
                      id="dingtalk-secret" 
                      value={localSettings.dingtalk_secret} 
                      onChange={(e) => setLocalSettings({ ...localSettings, dingtalk_secret: e.target.value })}
                      placeholder={t('settings.bot.secretPlaceholder')} 
                    />
                  </div>

                  <div className="pt-2 flex gap-2">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={() => debouncedDingtalkSave({
                        dingtalk_enabled: localSettings.dingtalk_enabled,
                        dingtalk_token: localSettings.dingtalk_token,
                        dingtalk_secret: localSettings.dingtalk_secret,
                      })}
                    >
                      {t('settings.bot.saveNow')}
                    </Button>
                    <Button 
                      variant="secondary" 
                      className="flex-1"
                      onClick={debouncedDingtalkTest}
                      disabled={localSettings.dingtalk_token.trim().length === 0}
                    >
                      {t('settings.bot.sendTest')}
                    </Button>
                  </div>
                </div>

                <div className="flex flex-col gap-4 rounded-lg border p-4 bg-card">
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="wecom-enabled" className="text-sm font-medium">{t('settings.bot.wecomTitle')}</Label>
                    <div className="flex items-center gap-2">
                      <Label htmlFor="wecom-enabled" className="text-xs text-muted-foreground">
                        {localSettings.wecom_enabled ? t('settings.bot.enabledLabel') : t('settings.bot.disabledLabel')}
                      </Label>
                      <Switch
                        id="wecom-enabled"
                        checked={localSettings.wecom_enabled === true}
                        onCheckedChange={(checked) => handleBotToggle(
                          checked,
                          localSettings.wecom_webhook_url.trim().length > 0,
                          t('settings.bot.wecomConfigRequired'),
                          {
                            wecom_enabled: checked,
                            wecom_webhook_url: localSettings.wecom_webhook_url,
                          }
                        )}
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="wecom-webhook-url">{t('settings.bot.wecomWebhookLabel')}</Label>
                    <Input 
                      id="wecom-webhook-url" 
                      value={localSettings.wecom_webhook_url} 
                      onChange={(e) => setLocalSettings({ ...localSettings, wecom_webhook_url: e.target.value })}
                      placeholder={t('settings.bot.wecomWebhookPlaceholder')} 
                    />
                  </div>

                  <div className="pt-2 flex gap-2">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={() => debouncedWecomSave({
                        wecom_enabled: localSettings.wecom_enabled,
                        wecom_webhook_url: localSettings.wecom_webhook_url,
                      })}
                    >
                      {t('settings.bot.saveNow')}
                    </Button>
                    <Button 
                      variant="secondary" 
                      className="flex-1"
                      onClick={debouncedWecomTest}
                      disabled={localSettings.wecom_webhook_url.trim().length === 0}
                    >
                      {t('settings.bot.sendTest')}
                    </Button>
                  </div>
                </div>

                <div className="flex flex-col gap-4 rounded-lg border p-4 bg-card">
                  <div className="flex items-center justify-between gap-3">
                    <Label htmlFor="feishu-enabled" className="text-sm font-medium">{t('settings.bot.feishuTitle')}</Label>
                    <div className="flex items-center gap-2">
                      <Label htmlFor="feishu-enabled" className="text-xs text-muted-foreground">
                        {localSettings.feishu_enabled ? t('settings.bot.enabledLabel') : t('settings.bot.disabledLabel')}
                      </Label>
                      <Switch
                        id="feishu-enabled"
                        checked={localSettings.feishu_enabled === true}
                        onCheckedChange={(checked) => handleBotToggle(
                          checked,
                          localSettings.feishu_webhook_url.trim().length > 0,
                          t('settings.bot.feishuConfigRequired'),
                          {
                            feishu_enabled: checked,
                            feishu_webhook_url: localSettings.feishu_webhook_url,
                          }
                        )}
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="feishu-webhook-url">{t('settings.bot.feishuWebhookLabel')}</Label>
                    <Input 
                      id="feishu-webhook-url" 
                      value={localSettings.feishu_webhook_url} 
                      onChange={(e) => setLocalSettings({ ...localSettings, feishu_webhook_url: e.target.value })}
                      placeholder={t('settings.bot.feishuWebhookPlaceholder')} 
                    />
                  </div>

                  <div className="pt-2 flex gap-2">
                    <Button
                      variant="outline"
                      className="flex-1"
                      onClick={() => debouncedFeishuSave({
                        feishu_enabled: localSettings.feishu_enabled,
                        feishu_webhook_url: localSettings.feishu_webhook_url,
                      })}
                    >
                      {t('settings.bot.saveNow')}
                    </Button>
                    <Button 
                      variant="secondary" 
                      className="flex-1"
                      onClick={debouncedFeishuTest}
                      disabled={localSettings.feishu_webhook_url.trim().length === 0}
                    >
                      {t('settings.bot.sendTest')}
                    </Button>
                  </div>
                </div>
              </div>

          </div>
        </TabsContent>

        <TabsContent value="about" className="pt-4 space-y-6">
          <div className="max-w-2xl rounded-xl border bg-card p-6 shadow-sm">
            <div className="space-y-2">
              <p className="text-xs font-medium uppercase tracking-[0.2em] text-muted-foreground">
                {t('settings.about.eyebrow')}
              </p>
              <h3 className="text-2xl font-semibold tracking-tight">{t('settings.about.product')}</h3>
              <p className="text-sm text-muted-foreground">{t('settings.about.description')}</p>
            </div>

            <div className="mt-6 rounded-lg border bg-muted/30 p-4">
              <p className="text-sm font-medium">{t('settings.about.copyrightTitle')}</p>
              <p className="mt-2 text-sm text-muted-foreground">{t('settings.about.copyright')}</p>
              <p className="mt-1 text-xs text-muted-foreground">{t('settings.about.notice')}</p>
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
