import { useRef, useState } from 'react'
import { clinicService } from '@/services/clinic.service'
import type { ClinicAssetKind } from '@/types'
import { Button } from './Button'

const ACCEPTED_CONTENT_TYPES: Record<ClinicAssetKind, string[]> = {
  logo: ['image/png', 'image/jpeg', 'image/svg+xml', 'image/webp'],
  // Navegadores aceitam qualquer formato de imagem comum como favicon, não só
  // PNG/ICO — restringir a esses dois rejeitava JPEG/WebP sem necessidade.
  favicon: [
    'image/png',
    'image/jpeg',
    'image/webp',
    'image/svg+xml',
    'image/x-icon',
    'image/vnd.microsoft.icon',
  ],
}

const MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024 // 2MB

interface ImageUploadFieldProps {
  clinicId: string
  kind: ClinicAssetKind
  label: string
  helpText?: string
  value: string | null | undefined
  onUploaded: (publicUrl: string) => void
  previewShape?: 'circle' | 'square'
}

export function ImageUploadField({
  clinicId,
  kind,
  label,
  helpText,
  value,
  onUploaded,
  previewShape = 'circle',
}: ImageUploadFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const accepted = ACCEPTED_CONTENT_TYPES[kind]

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return

    setError(null)

    if (!accepted.includes(file.type)) {
      setError('Formato não suportado.')
      return
    }
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setError('Arquivo muito grande (máx. 2MB).')
      return
    }

    setUploading(true)
    try {
      const { uploadUrl, publicUrl } = await clinicService.getAssetUploadUrl(clinicId, kind, file.type)
      const putResponse = await fetch(uploadUrl, {
        method: 'PUT',
        headers: { 'Content-Type': file.type },
        body: file,
      })
      if (!putResponse.ok) {
        throw new Error('Falha ao enviar o arquivo')
      }
      onUploaded(publicUrl)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao enviar imagem')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div>
      <label className="text-xs font-medium text-gray-500 block mb-1.5">{label}</label>
      <div className="flex items-center gap-4">
        <div
          className={[
            'flex items-center justify-center overflow-hidden bg-gray-100 border border-gray-200 shrink-0 text-gray-300',
            previewShape === 'circle' ? 'w-16 h-16 rounded-full' : 'w-12 h-12 rounded-lg',
          ].join(' ')}
        >
          {value ? (
            <img src={value} alt={label} className="w-full h-full object-cover" />
          ) : (
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="M21 15l-5-5L5 21" />
            </svg>
          )}
        </div>
        <div>
          <input
            ref={inputRef}
            type="file"
            accept={accepted.join(',')}
            onChange={(e) => void handleFileChange(e)}
            className="hidden"
          />
          <Button
            type="button"
            variant="secondary"
            size="sm"
            loading={uploading}
            onClick={() => inputRef.current?.click()}
          >
            {value ? 'Trocar imagem' : 'Enviar imagem'}
          </Button>
          {helpText && !error && <p className="text-[11px] text-gray-400 mt-1.5">{helpText}</p>}
          {error && <p className="text-[11px] text-red-500 mt-1.5">{error}</p>}
        </div>
      </div>
    </div>
  )
}
