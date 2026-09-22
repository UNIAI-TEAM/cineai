/** Mục "Tự động" dùng chung trong các danh sách chọn model (thanh tạo ảnh/video, đầu trang tập phim). */
import type { MouseEvent } from 'react'

type ModelAutoOptionProps = {
  selected: boolean
  label: string
  desc?: string
  onSelect: () => void
  onMouseDown?: (e: MouseEvent) => void
}

export function ModelAutoOption({ selected, label, desc, onSelect, onMouseDown }: ModelAutoOptionProps) {
  return (
    <button
      type="button"
      className={`fc-gen-model-item${selected ? ' selected' : ''}`}
      onMouseDown={onMouseDown}
      onClick={onSelect}
    >
      {desc ? (
        <>
          <strong>{label}</strong>
          <span>{desc}</span>
        </>
      ) : (
        label
      )}
    </button>
  )
}
