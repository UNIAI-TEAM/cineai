/** Tải danh mục giọng BytePlus theo dự án và xử lý chọn nhanh một giọng cho nhân vật (tách khỏi CharacterVoiceBindModal.tsx để giữ file dưới 500 dòng) */
import { useEffect, useState } from 'react'
import { dramaApi, type CatalogVoice, type DramaAsset } from '../../api/drama'
import { useI18n } from '../../i18n/context'
import { translate } from '../../i18n/translate'
import { buildBoundParams } from '../../lib/dramaVoiceBinding'

type Options = {
  open: boolean
  projectId: number
  asset: DramaAsset
  onBound: (asset: DramaAsset) => void
  onClose: () => void
  onError: (message: string) => void
  addVoiceAsset: (voice: DramaAsset) => void
}

// Quản lý state + hành vi của tab "Chọn giọng": tải danh mục theo ngôn ngữ dự án khi mở modal,
// tổng hợp mẫu khóa giọng (speaker_locked) rồi gắn ngay giọng đó cho nhân vật
export function useVoiceCatalog({ open, projectId, asset, onBound, onClose, onError, addVoiceAsset }: Options) {
  /*
   * catalog danh mục giọng tải theo dự án (null = đang tải, [] = trống)
   * catalogLang ngôn ngữ nội dung dự án do backend suy ra
   * catalogError lỗi tải danh mục
   * pickingSpeaker speaker đang được tổng hợp/gắn (khóa các nút "Dùng giọng này")
   */
  const [catalog, setCatalog] = useState<CatalogVoice[] | null>(null)
  const [catalogLang, setCatalogLang] = useState('')
  const [catalogError, setCatalogError] = useState('')
  const [pickingSpeaker, setPickingSpeaker] = useState<string | null>(null)
  const { t } = useI18n()

  useEffect(() => {
    if (!open) return
    setCatalog(null)
    setCatalogError('')
    dramaApi
      .voiceCatalog(projectId)
      .then((res) => {
        setCatalog(res.voices)
        setCatalogLang(res.lang)
      })
      .catch((err) =>
        setCatalogError(
          err instanceof Error ? err.message : translate('dramaAssets.voiceBind.catalogLoadFailed'),
        ),
      )
  }, [open, projectId])

  // Chọn giọng trong danh mục: tạo tư liệu giọng khóa speaker (TTS câu mẫu) rồi gắn ngay cho nhân vật
  async function handlePickCatalog(voice: CatalogVoice) {
    if (pickingSpeaker) return
    setPickingSpeaker(voice.speaker)
    try {
      const result = await dramaApi.generateVoice({
        project_id: projectId,
        name: `${asset.name || t('dramaAssets.voiceBind.characterFallback')} · ${voice.name}`,
        voice_prompt: voice.description || voice.name,
        speaker: voice.speaker,
        speaker_locked: true,
        character_asset_id: asset.id,
      })
      const created = result.asset
      // Không có file âm thanh cũng coi như tổng hợp thất bại (giống characterVoiceGenerate)
      if (!created?.url) throw new Error(t('dramaAssets.voiceBind.synthFailed'))
      addVoiceAsset(created)
      const updated = await dramaApi.updateAsset(asset.id, { params: buildBoundParams(asset, created) })
      onBound(updated)
      onClose()
    } catch (err) {
      onError(err instanceof Error ? err.message : t('dramaAssets.step.voiceSynthFailed'))
    } finally {
      setPickingSpeaker(null)
    }
  }

  return { catalog, catalogLang, catalogError, pickingSpeaker, handlePickCatalog }
}
