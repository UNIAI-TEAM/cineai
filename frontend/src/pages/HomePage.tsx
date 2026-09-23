import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowDown, ArrowRight, Check, ChevronDown, Clapperboard, Film, FolderOpen, Image as ImageIcon, Layers, Menu, Mic, MonitorPlay, ScanFace, Scissors, ShoppingBag, Sparkles, Users, Video, WandSparkles, X } from 'lucide-react'
import BrandMark from '../components/BrandMark'
import LanguageSwitch from '../components/layout/LanguageSwitch'
import HomePricing from '../components/home/HomePricing'
import { homeCopy, homeGallery, homeImage } from '../components/home/homeContent'
import { useI18n } from '../i18n'
import { HOME_CREATION_DRAFT_KEY } from '../lib/homeCreationDraft'
import '../styles/homepage.css'

const workflow = [
  { title: 'Project', image: 'valley', vi: 'Bắt đầu câu chuyện', en: 'Start your story', icon: FolderOpen },
  { title: 'Characters', image: 'filmmaker', vi: 'Tạo nhân vật của bạn', en: 'Meet your characters', icon: Users },
  { title: 'Script', image: '', vi: 'Viết nên thế giới', en: 'Write your world', icon: Film },
  { title: 'Scenes', image: 'valley', vi: 'Xây dựng bối cảnh', en: 'Set the scene', icon: Layers },
  { title: 'Shots', image: 'director', vi: 'Đạo diễn từng góc máy', en: 'Direct every shot', icon: Clapperboard },
  { title: 'Generate', image: 'astronaut', vi: 'Biến ý tưởng thành hình', en: 'Bring ideas to life', icon: Sparkles },
  { title: 'Edit', image: '', vi: 'Kết nối câu chuyện', en: 'Bring it together', icon: Scissors },
  { title: 'Film', image: 'sunset', vi: 'Sẵn sàng để chia sẻ', en: 'Ready to share', icon: MonitorPlay },
]
const capabilityIcons = [ImageIcon, WandSparkles, ShoppingBag, Video, Clapperboard, Layers]

/** Image-led marketing homepage; creation stays connected to the existing workspaces. */
export default function HomePage() {
  const { locale, m } = useI18n()
  const copy = homeCopy[locale === 'vi' ? 'vi' : 'en']
  const vi = locale === 'vi'
  const nav = useNavigate()
  const [menuOpen, setMenuOpen] = useState(false)
  const [tool, setTool] = useState<'t2v' | 't2i'>('t2v')
  const [prompt, setPrompt] = useState('')
  const [ratio, setRatio] = useState('16:9')
  const [error, setError] = useState('')
  const [category, setCategory] = useState('all')
  const promptRef = useRef<HTMLTextAreaElement>(null)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const loggedIn = Boolean(localStorage.getItem('token'))
  const tools = Object.values(m.tools.items)
  const categories = ['all', 'cinema', 'fantasy', 'animation', 'commercial'] as const
  const filtered = homeGallery.filter((item) => category === 'all' || item.category === category).slice(0, 6)

  useEffect(() => {
    if (!menuOpen) return
    const close = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setMenuOpen(false); menuButtonRef.current?.focus() }
    }
    window.addEventListener('keydown', close)
    return () => window.removeEventListener('keydown', close)
  }, [menuOpen])

  /** Preserve the destination for guests, using the application's existing auth flow. */
  function enter(path: string) {
    nav(loggedIn ? path : `/auth?next=${encodeURIComponent(path)}`)
  }

  /** Store a tab-scoped draft before opening the real image/video tool. */
  function create(event: FormEvent) {
    event.preventDefault()
    if (!prompt.trim()) { promptRef.current?.focus(); return }
    try {
      sessionStorage.setItem(HOME_CREATION_DRAFT_KEY, JSON.stringify({ toolId: tool, prompt: prompt.trim(), ratio }))
      setError('')
      enter(`/tools/${tool}`)
    } catch { setError(copy.draftError) }
  }

  /** Gallery art is a working prompt starter, not a pretend playable video. */
  function applyIdea(value: string) {
    setPrompt(value)
    document.getElementById('create')?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' })
    promptRef.current?.focus({ preventScroll: true })
  }

  const navigation = <>
    <a href="#products" onClick={() => setMenuOpen(false)}>{copy.products}<ChevronDown size={12} /></a>
    <a href="#showcase" onClick={() => setMenuOpen(false)}>{copy.showcase}</a>
    <a href="#pricing" onClick={() => setMenuOpen(false)}>{copy.pricing}</a>
    <Link to="/help">{copy.help}<ChevronDown size={12} /></Link>
    <a href="#explore" onClick={() => setMenuOpen(false)}>{copy.community}<ChevronDown size={12} /></a>
  </>

  return (
    <div className="home-page">
      <a className="home-skip" href="#home-main">{copy.skip}</a>
      <header className="home-nav">
        <div className="home-container home-nav-inner">
          <div className="home-brand"><BrandMark /><span>AI FILMMAKING STUDIO</span></div>
          <nav className="home-nav-links" aria-label={m.nav.main}>{navigation}</nav>
          <div className="home-nav-actions">
            <Link className="home-login" to={loggedIn ? '/settings' : '/auth?next=/'}>{loggedIn ? copy.account : copy.login}</Link>
            <a className="home-button home-button-small" href="#create">{copy.start}<ArrowRight size={15} /></a>
            <button ref={menuButtonRef} className="home-menu-toggle" type="button" aria-label={menuOpen ? copy.closeMenu : copy.menu} aria-expanded={menuOpen} aria-controls="home-mobile-menu" onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? <X /> : <Menu />}</button>
          </div>
        </div>
        {menuOpen && <nav id="home-mobile-menu" className="home-mobile-menu" aria-label={m.nav.mobileNav}>{navigation}<LanguageSwitch /></nav>}
      </header>

      <main id="home-main">
        <section className="home-hero home-container" aria-labelledby="home-headline">
          <div className="home-hero-art" aria-hidden="true"><img src={homeImage('filmmaker')} alt="" fetchPriority="high" /></div>
          <div className="home-hero-copy">
            <p className="home-kicker"><span /> FROM IMAGINATION TO REALITY</p>
            <h1 id="home-headline">{copy.headline[0]}<br />{copy.headline[1]}<br /><em>{copy.headline[2]}</em></h1>
            <p className="home-lead">{copy.lead}</p>
            <div className="home-actions"><button className="home-button" onClick={() => enter('/tools/t2v')}>{copy.create}<ArrowRight size={17} /></button><button className="home-button home-button-outline" onClick={() => enter('/drama')}><Clapperboard size={16} />{copy.studio}<ArrowRight size={16} /></button></div>
            <div className="home-stats"><div><strong>6<span>+</span></strong><span>{copy.toolsCount}</span></div><div><strong>2</strong><span>{copy.workflows}</span></div><div><strong className="home-lime">∞</strong><span>{copy.possibilities}</span></div></div>
          </div>
          <div className="home-hero-gallery" aria-hidden="true"><img src={homeImage('director')} alt="" /><img src={homeImage('valley')} alt="" /><img src={homeImage('astronaut')} alt="" /><span className="home-handwriting">A new world<br />awaits.</span></div>
          <span className="home-hero-note home-handwriting" aria-hidden="true">Ideas.<br />Characters.<br />Stories.<br />Films.</span>
        </section>

        <div className="home-container home-capabilities" aria-label={copy.capabilityLabel}>
          <span className="home-capability-caption">{copy.capabilityLabel}</span>
          <div>{['Image', 'Video', 'Character', 'Storyboard', 'Voice', 'Edit'].map((label, i) => { const Icon = [ImageIcon, Video, ScanFace, Layers, Mic, Scissors][i]; return <span key={label}><Icon size={21} strokeWidth={1.6} />{label}</span> })}<span className="home-capability-more">{vi ? 'và nhiều hơn nữa ↗' : 'and so much more ↗'}</span></div>
        </div>

        <section id="products" className="home-section home-products home-container">
          <p className="home-kicker">ONE CINEAI. TWO WAYS TO CREATE.</p><h2>{copy.ecosystem}</h2><p className="home-subtitle">{copy.ecosystemLead}</p>
          <div className="home-product-grid">
            {[{ name: 'Create', img: 'filmmaker', tag: copy.createTag, desc: copy.createLead, cta: copy.create, path: '/tools/t2v', features: ['Image', 'Video', 'Character', 'Product', 'Effects', 'Edit'], icons: [ImageIcon, Video, ScanFace, ShoppingBag, WandSparkles, Scissors] }, { name: 'Studio', img: 'director', tag: copy.studioTag, desc: copy.studioLead, cta: copy.studio, path: '/drama', features: ['Project', 'Characters', 'Script', 'Shots', 'Film', 'Edit'], icons: [FolderOpen, Users, Film, Clapperboard, MonitorPlay, Scissors] }].map(product => <article className={`home-product home-product-${product.name.toLowerCase()}`} key={product.name}>
              <img className="home-product-image" src={homeImage(product.img)} alt="" loading="lazy" />
              <div className="home-product-copy"><h3><img src="/logo.svg" alt="" />CineAI {product.name}</h3><h4>{product.tag}</h4><p>{product.desc}</p><div className="home-product-features">{product.features.map((label, i) => { const Icon = product.icons[i]; return <span key={label}><Icon size={19} strokeWidth={1.5} />{label}</span> })}</div><button className="home-button" onClick={() => enter(product.path)}>{product.cta}<ArrowRight size={16} /></button></div>
            </article>)}
          </div>
        </section>

        <section id="create" className="home-section home-create home-container">
          <div className="home-create-main"><p className="home-kicker">CINEAI CREATE</p><h2>{copy.createHeading[0]}<br />{copy.createHeading[1]}</h2><p className="home-subtitle">{copy.createSubtitle}</p>
            <div className="home-tool-tabs" role="group" aria-label={copy.allTools}><button type="button" aria-pressed={tool === 't2v'} className={tool === 't2v' ? 'is-active' : ''} onClick={() => setTool('t2v')}><Video size={15} />{copy.video}</button><button type="button" aria-pressed={tool === 't2i'} className={tool === 't2i' ? 'is-active' : ''} onClick={() => setTool('t2i')}><ImageIcon size={15} />{copy.image}</button><Link to="/tools/i2i">{copy.effects}</Link><Link to="/drama/assets">{copy.character}</Link><Link to="/tools">{copy.allTools}<ArrowRight size={12} /></Link></div>
            <form className="home-composer" onSubmit={create}><label className="home-sr-only" htmlFor="home-prompt">{copy.promptLabel}</label><textarea ref={promptRef} id="home-prompt" value={prompt} onChange={e => setPrompt(e.target.value)} placeholder={copy.prompt} maxLength={4000} required /><div className="home-composer-bottom"><Sparkles size={17} aria-hidden="true" /><div><label className="home-sr-only" htmlFor="home-ratio">{copy.ratio}</label><select id="home-ratio" value={ratio} onChange={e => setRatio(e.target.value)}><option>16:9</option><option>9:16</option><option>1:1</option></select><button className="home-button" type="submit">{copy.generate}<ArrowRight size={16} /></button></div></div>{error && <p role="alert" className="home-form-error">{error}</p>}</form>
          </div>
          <div className="home-create-art" aria-hidden="true"><span className="home-handwriting">{vi ? <>Biến ý tưởng<br />thành những<br />thước phim!</> : <>Bring your<br />imagination<br />to life!</>}<ArrowDown size={36} /></span><img className="home-create-space" src={homeImage('astronaut')} alt="" loading="lazy" /><img className="home-create-car" src={homeImage('car')} alt="" loading="lazy" /><img className="home-create-portrait" src={homeImage('director')} alt="" loading="lazy" /></div>
        </section>

        <section className="home-container home-tool-strip" aria-label={copy.allTools}>{tools.map((item, i) => { const Icon = capabilityIcons[i]; const id = ['t2i', 'i2i', 'i2p', 't2v', 'v2v', 'ecom'][i]; return <Link key={id} to={`/tools/${id}`}><Icon size={22} strokeWidth={1.5} /><span>{item.title}</span><ArrowRight size={13} /></Link> })}</section>

        <section id="explore" className="home-container home-explore">
          <div className="home-section-row"><p className="home-kicker">{copy.inspirationLabel}</p><Link className="home-text-link" to="/tools">{copy.allTools}<ArrowRight size={14} /></Link></div>
          <div className="home-filter-tabs" role="group" aria-label={copy.community}>{categories.map(key => <button type="button" key={key} className={category === key ? 'is-active' : ''} aria-pressed={category === key} onClick={() => setCategory(key)}>{copy[key]}</button>)}</div>
          <div className="home-gallery" aria-live="polite">{filtered.map(item => <button type="button" className="home-gallery-item" key={item.image} onClick={() => applyIdea(item.prompt)} aria-label={`${copy.useIdea}: ${item.title}`}><img src={homeImage(item.image)} alt={item.title} loading="lazy" /><span>{item.title}<ArrowRight size={15} /></span></button>)}</div><p className="home-gallery-hint">{copy.galleryHint}</p>
        </section>

        <section className="home-container home-story-banner"><img src={homeImage('valley')} alt="" loading="lazy" /><p className="home-story-before">{copy.bridgeBefore}<span>…</span></p><div><h2>{copy.bridgeTitle}</h2><p>{copy.bridgeLead}</p></div><div className="home-story-action"><span className="home-handwriting">Bigger stories.<br />Made by you.</span><button className="home-button" onClick={() => enter('/drama')}>{copy.discoverStudio}<ArrowRight size={16} /></button></div></section>

        <section id="studio" className="home-section home-container home-studio"><p className="home-kicker">CINEAI STUDIO</p><h2>{copy.studioHeading}</h2><p className="home-subtitle">{copy.studioSubtitle}</p><ol className="home-workflow">{workflow.map((step, i) => <li key={step.title}><span className="home-step-number">0{i + 1}</span><h3>{step.title}</h3><p>{vi ? step.vi : step.en}</p>{step.image ? <img src={homeImage(step.image)} alt="" loading="lazy" /> : step.title === 'Script' ? <div className="home-script-preview" aria-hidden="true"><span>EXT. CITY — NIGHT</span><i /><i /><i /><span>THE STORY BEGINS.</span><i /><i /></div> : <div className="home-timeline-preview" aria-hidden="true"><span /><span /><span /><span /><b /></div>}</li>)}</ol>
          <div className="home-continuity"><div><p className="home-kicker">{copy.continuity}</p><p className="home-subtitle">{copy.continuityLead}</p><img className="home-character-strip" src={homeImage('character')} alt={vi ? 'Bốn góc nhìn của cùng một nhân vật nữ đội mũ len xám' : 'Four views of the same woman character wearing a grey beanie'} loading="lazy" /></div><div className="home-continuity-checks"><ul>{copy.checks.map(item => <li key={item}><Check size={15} />{item}</li>)}</ul><button className="home-button home-button-outline" onClick={() => enter('/drama')}>{copy.discoverStudio}<ArrowRight size={15} /></button></div><span className="home-handwriting">Your<br />character.<br />Your story.</span></div>
        </section>

        <section id="showcase" className="home-container home-section home-showcase"><div className="home-section-row"><p className="home-kicker">{copy.showcaseTitle}</p><span className="home-small-note">{copy.showcaseNote}</span></div><div className="home-showcase-grid">{[homeGallery[5], homeGallery[3], homeGallery[2], homeGallery[6], homeGallery[7], homeGallery[1]].map(item => <button className="home-showcase-item" key={item.image} onClick={() => applyIdea(item.prompt)} aria-label={`${copy.useIdea}: ${item.title}`}><div><img src={homeImage(item.image)} alt="" loading="lazy" /><span><WandSparkles size={19} /></span></div><strong>{item.title}</strong><small>{copy[item.category]}</small></button>)}</div></section>

        <section className="home-container home-section home-audiences"><p className="home-kicker">{copy.creatorsTitle}</p><div className="home-audience-grid">{copy.audiences.map((item, i) => { const Icon = [WandSparkles, Clapperboard, ShoppingBag][i]; return <article key={item.title}><div><Icon size={24} /><div><h3>{item.title}</h3><small>{item.subtitle}</small></div></div><p>{item.desc}</p><Link to={['/tools', '/drama', '/tools/i2p'][i]}>{copy.start}<ArrowRight size={14} /></Link></article> })}<div className="home-audience-note"><span className="home-handwriting">Real ideas.<br />Amazing creations.</span><a className="home-button home-button-small" href="#create">{copy.start}<ArrowRight size={14} /></a></div></div></section>

        <div className="home-container"><HomePricing copy={copy} /></div>

        <section className="home-container home-closing"><img src={homeImage('sunset')} alt="" loading="lazy" /><div className="home-brand"><BrandMark /><span>AI FILMMAKING STUDIO</span></div><h2>{copy.close}<br />{copy.closeLine}</h2><div className="home-actions"><button className="home-button" onClick={() => enter('/tools/t2v')}>{copy.create}<ArrowRight size={16} /></button><button className="home-button home-button-outline" onClick={() => enter('/drama')}>{copy.shortStudio}<ArrowRight size={16} /></button></div></section>
      </main>

      <footer className="home-container home-footer"><div className="home-footer-top"><div className="home-brand"><BrandMark /><span>AI FILMMAKING STUDIO</span></div><nav aria-label={m.home.footNav}>{navigation}</nav><LanguageSwitch /></div><div className="home-footer-bottom"><span>© {new Date().getFullYear()} CineAI. {copy.rights}</span><nav><Link to="/terms">{copy.terms}</Link><Link to="/privacy">{copy.privacy}</Link><Link to="/contact">{copy.contact}</Link></nav></div></footer>
    </div>
  )
}
