/** Tự làm mới danh sách phân cảnh khi có phân cảnh đang lồng tiếng tự động sau khi video xong.
 *
 * generate_status (dramaGenQueue) chỉ theo dõi task_type=fragment_video nên không thấy được
 * task fragment_dub được backend tự vào hàng đợi sau khi video hoàn tất; vì vậy cần vòng lặp
 * riêng, nhẹ và chỉ chạy khi thật sự có phân cảnh đang lồng tiếng (tự dừng khi hết).
 */
import { useEffect } from 'react'
import { dramaApi, type DramaFragment } from '../api/drama'
import { readFragmentDub } from '../lib/dramaFragmentDub'

const DUB_AUTO_POLL_MS = 5000

export function useFragmentDubPolling(
  episodeId: number,
  fragments: DramaFragment[],
  onFragments: (fragments: DramaFragment[]) => void,
) {
  const anyDubRunning = fragments.some((f) => readFragmentDub(f.params)?.status === 'running')

  useEffect(() => {
    if (!episodeId || !anyDubRunning) return
    let stopped = false
    const timer = setInterval(async () => {
      try {
        const ep = await dramaApi.getEpisode(episodeId)
        if (!stopped) onFragments(ep.fragments || [])
      } catch {
        /* 轮询失败下次重试 */
      }
    }, DUB_AUTO_POLL_MS)
    return () => {
      stopped = true
      clearInterval(timer)
    }
  }, [episodeId, anyDubRunning, onFragments])
}
