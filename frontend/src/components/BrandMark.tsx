import { Link } from 'react-router-dom'

type Props = {
  to?: string
}

/** Logo CineAI: biểu tượng dải băng gấp + wordmark "Cine" + "AI" (AI màu lime) */
export default function BrandMark({ to = '/' }: Props) {
  return (
    <Link to={to} className="brand-mark" aria-label="CineAI">
      <img src="/logo.svg" alt="" className="brand-logo" width={28} height={28} />
      <span className="brand-word" aria-hidden="true">
        Cine<span className="brand-word-ai">AI</span>
      </span>
    </Link>
  )
}
