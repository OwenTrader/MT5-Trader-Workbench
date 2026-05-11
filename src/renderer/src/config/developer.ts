import packageJson from '../../../../package.json'

type PackageMetadata = {
  developerContact?: string
}

export const developerContact = (packageJson as PackageMetadata).developerContact?.trim() ?? ''
