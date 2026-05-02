const fs = require('node:fs')
const path = require('node:path')
const Jimp = require('jimp')

const sourcePath = path.resolve(process.argv[2])
const outputPath = path.resolve(process.argv[3])
const sizes = [16, 24, 32, 48, 64, 128, 256]

function createIco(pngBuffers) {
  const count = pngBuffers.length
  const header = Buffer.alloc(6)
  header.writeUInt16LE(0, 0)
  header.writeUInt16LE(1, 2)
  header.writeUInt16LE(count, 4)

  const directory = Buffer.alloc(count * 16)
  let offset = header.length + directory.length

  pngBuffers.forEach(({ size, buffer }, index) => {
    const entryOffset = index * 16
    directory.writeUInt8(size >= 256 ? 0 : size, entryOffset)
    directory.writeUInt8(size >= 256 ? 0 : size, entryOffset + 1)
    directory.writeUInt8(0, entryOffset + 2)
    directory.writeUInt8(0, entryOffset + 3)
    directory.writeUInt16LE(1, entryOffset + 4)
    directory.writeUInt16LE(32, entryOffset + 6)
    directory.writeUInt32LE(buffer.length, entryOffset + 8)
    directory.writeUInt32LE(offset, entryOffset + 12)
    offset += buffer.length
  })

  return Buffer.concat([header, directory, ...pngBuffers.map(({ buffer }) => buffer)])
}

async function main() {
  const image = await Jimp.read(sourcePath)
  const pngBuffers = []

  for (const size of sizes) {
    const resized = image.clone().resize(size, size, Jimp.RESIZE_LANCZOS)
    const buffer = await resized.getBufferAsync(Jimp.MIME_PNG)
    pngBuffers.push({ size, buffer })
  }

  fs.writeFileSync(outputPath, createIco(pngBuffers))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
