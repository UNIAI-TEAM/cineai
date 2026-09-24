/** Danh sách giọng TTS chọn tay: lọc giới tính / nhóm, nghe thử file mẫu (không tốn phí), bấm dùng giọng */
import { useEffect, useMemo, useRef, useState } from 'react'
import type { CatalogVoice } from '../../api/drama'
import { useI18n } from '../../i18n/context'

type Props = {
  voices: CatalogVoice[]
  lang: string
  busySpeaker: string | null
  onPick: (voice: CatalogVoice) => void
}

type GenderFilter = 'all' | 'male' | 'female'

// Render danh sách giọng
export function VoiceCatalogPicker({ voices, lang, busySpeaker, onPick }: Props) {
  /*
   * gender lọc giới tính
   * scenario lọc nhóm ('' = tất cả)
   * playing speaker đang phát mẫu
   */
  const { t } = useI18n()
  const [gender, setGender] = useState<GenderFilter>('all')
  const [scenario, setScenario] = useState('')
  const [playing, setPlaying] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const scenarios = useMemo(() => [...new Set(voices.map((v) => v.scenario).filter(Boolean))], [voices])
  const shown = voices.filter(
    (v) => (gender === 'all' || v.gender === gender) && (!scenario || v.scenario === scenario),
  )

  // Dừng phát khi unmount
  useEffect(() => () => audioRef.current?.pause(), [])

  // Phát / dừng file mẫu; bấm giọng khác thì dừng giọng cũ
  function togglePlay(voice: CatalogVoice) {
    const audio = audioRef.current
    if (!audio) return
    if (playing === voice.speaker) {
      audio.pause()
      setPlaying(null)
      return
    }
    audio.src = voice.sample_url
    void audio.play().catch(() => setPlaying(null))
    setPlaying(voice.speaker)
  }

  // Nhãn nhóm đã dịch (nhóm lạ hiển thị nguyên văn)
  const scenarioLabel = (s: string) => {
    const key = `dramaAssets.voiceBind.scenario.${s}`
    const label = t(key)
    return label === key ? s : label
  }

  return (
    <div className="drama-voice-catalog">
      {lang === 'vi' ? <p className="drama-muted">{t('dramaAssets.voiceBind.viMaleNote')}</p> : null}
      <p className="drama-muted">{t('dramaAssets.voiceBind.lockedHint')}</p>
      <div className="drama-voice-catalog-filters">
        {(['all', 'male', 'female'] as const).map((g) => (
          <button
            key={g}
            type="button"
            className={`pf-btn pf-btn-sm${gender === g ? ' active' : ''}`}
            onClick={() => setGender(g)}
          >
            {t(g === 'all' ? 'dramaAssets.voiceBind.filterAll' : g === 'male' ? 'dramaAssets.voiceBind.filterMale' : 'dramaAssets.voiceBind.filterFemale')}
          </button>
        ))}
        {scenarios.length > 1 ? (
          <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
            <option value="">{t('dramaAssets.voiceBind.filterScenarioAll')}</option>
            {scenarios.map((s) => (
              <option key={s} value={s}>
                {scenarioLabel(s)}
              </option>
            ))}
          </select>
        ) : null}
      </div>
      <ul className="drama-voice-catalog-list">
        {shown.map((voice) => (
          <li key={voice.speaker} className="drama-voice-catalog-item">
            <div className="drama-voice-catalog-meta">
              <strong>{voice.name}</strong>
              <small className="drama-muted">
                {t(voice.gender === 'male' ? 'dramaAssets.voiceBind.filterMale' : 'dramaAssets.voiceBind.filterFemale')}
                {voice.scenario ? ` · ${scenarioLabel(voice.scenario)}` : ''}
              </small>
              {voice.description ? <span className="drama-muted">{voice.description}</span> : null}
            </div>
            <div className="drama-voice-catalog-actions">
              {voice.sample_url ? (
                <button type="button" className="pf-btn pf-btn-sm" onClick={() => togglePlay(voice)}>
                  {playing === voice.speaker ? t('dramaAssets.voiceBind.stop') : t('dramaAssets.voiceBind.play')}
                </button>
              ) : null}
              <button
                type="button"
                className="pf-btn pf-btn-sm pf-btn-lime"
                disabled={busySpeaker !== null}
                onClick={() => onPick(voice)}
              >
                {busySpeaker === voice.speaker ? t('dramaAssets.voiceBind.usingVoice') : t('dramaAssets.voiceBind.useVoice')}
              </button>
            </div>
          </li>
        ))}
      </ul>
      <audio ref={audioRef} onEnded={() => setPlaying(null)} hidden />
    </div>
  )
}
