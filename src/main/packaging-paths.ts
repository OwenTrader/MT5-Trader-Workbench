import path from 'node:path'

export function getPackagedBackendWorkingDirectory(resourcesPath: string): string {
  return path.join(resourcesPath, 'mt5_service')
}

export function getPackagedBackendExecutablePath(resourcesPath: string): string {
  return path.join(getPackagedBackendWorkingDirectory(resourcesPath), 'mt5_service.exe')
}
