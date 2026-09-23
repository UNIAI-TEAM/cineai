/** 剧本 / 分镜结构标签：显示 ↔ 规范往返、结构位置锚定、中文界面原样。 */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { registerHooks } from 'node:module'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// 源码里的相对 import 不带扩展名（Vite 解析）；测试里补全为 .ts / .tsx
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier.startsWith('.') && !/\.[cm]?[jt]sx?$/.test(specifier) && context.parentURL) {
      for (const ext of ['.ts', '.tsx', '/index.ts']) {
        const url = new URL(specifier + ext, context.parentURL)
        if (existsSync(fileURLToPath(url))) return nextResolve(url.href, context)
      }
    }
    return nextResolve(specifier, context)
  },
})

const { toDisplayScript, toCanonicalScript, displayScriptSpeaker } = await import('../src/lib/dramaScriptLocalize.ts')
const { messages } = await import('../src/i18n/messages.ts')

const CJK = /[一-鿿]/

// 后端 agents.py 规定格式的中文剧本（场头 / 时间内外景 / 出场人物 / △ / 台词 / 空镜）
const ZH_SCREENPLAY = [
  '### 场1-1',
  '日 内 灵山大雄宝殿',
  '出场人物：禹、鲧、行刑兵',
  '△ 刑场全景，洪水拍打山崖。',
  '禹（怒）：父亲！',
  '旁白（vo）：那一年，洪水滔天。',
  '鲧（os）：我不甘心。',
  '【空镜：江面薄雾】',
  '',
  '### 场1-2',
  '晨外 羽山刑场',
  '出场人物：无',
  '△ 众人散去。',
].join('\n')

// backend build_fragments_from_episode_body 真实产出的分镜正文
const ZH_FRAGMENT_1 =
  '【字幕：底部居中·简体中文·逐句轮换·与口播同步】\n【BGM：低沉紧张、鼓点渐强，烘托压迫与危机感；音量低于人声】\n【人物介绍·画面叠字·角色身旁】禹｜治水英雄\n【人物介绍·画面叠字·角色身旁】鲧｜治水先驱\n@duration:3\n日外 @asset:3 羽山刑场。\n@duration:3\n【画面·无配音仅环境音】△ 刑场全景，洪水拍打山崖。\n@duration:3\n【对白·慢速清晰·同步字幕】@asset:2（怒）：父亲！\n@duration:3\n【旁白·慢速清晰·同步字幕】旁白（vo）：那一年，洪水滔天。\n@duration:3\n【空镜·可仅环境音与 BGM】【空镜：江面薄雾】'
const ZH_FRAGMENT_2 =
  '【字幕：底部居中·简体中文·逐句轮换·与口播同步】\n【BGM：神秘悬疑、低频铺底，留白感强；音量低于人声】\n@duration:3\n夜 内 茅屋。\n@duration:4\n【对白·慢速清晰·同步字幕】@asset:2（os）：我一定要治好这水。'

// vi 项目：AI 仍写中文结构标签，正文为越南语
const VI_SCREENPLAY = [
  '### 场1-1',
  '夜 外 Sân trường',
  '出场人物：Minh、Lan',
  '△ Minh bước vào, mưa rơi nặng hạt.',
  'Minh（lạnh lùng）：Ai đã làm chuyện này?',
  'Lan（vo）：Tôi không biết.',
  '【空镜：Sân trường vắng lặng】',
].join('\n')
const VI_FRAGMENT = [
  '【字幕：底部居中·越南语·逐句轮换·与口播同步】',
  '【BGM：神秘悬疑、低频铺底，留白感强；音量低于人声】',
  '【片头·集号叠字】Tập 1｜Mưa',
  '【背景介绍·画面叠字】Hà Nội, 1990',
  '@duration:4',
  '【画面·无配音仅环境音】空镜：Empty classroom at dusk, rain on the windows',
  '@duration:4',
  '【画面·无配音仅环境音】特写：Minh’s trembling hands',
  '@duration:5',
  '【对白·慢速清晰·同步字幕】@asset:2（lạnh lùng）：Ai đã làm chuyện này?',
  '@duration:5',
  '【旁白·自然语速·同步字幕】旁白（VO）：Hôm đó trời mưa.',
  '【内心独白·同步字幕】Minh：Mình phải bình tĩnh.',
  '【空镜·可仅环境音与 BGM】远景：Hanoi skyline at night',
].join('\n')
// 关闭字幕后的分镜（字幕提示被去掉的前缀）
const ZH_FRAGMENT_NO_SUB = '【BGM：贴合剧情氛围的轻量配乐，情绪随画面起伏；音量低于人声】\n@duration:4\n【对白·慢速清晰】禹：走！\n【旁白·慢速清晰】旁白：天亮了。\n【内心独白】我不能输。\n【人物介绍·画面叠字】禹｜治水英雄'

const SAMPLES = [ZH_SCREENPLAY, ZH_FRAGMENT_1, ZH_FRAGMENT_2, VI_SCREENPLAY, VI_FRAGMENT, ZH_FRAGMENT_NO_SUB]

for (const locale of ['vi', 'en'] as const) {
  test(`${locale}: 真实样本往返一致`, () => {
    for (const sample of SAMPLES) {
      const display = toDisplayScript(sample, locale)
      assert.notEqual(display, sample)
      assert.equal(toCanonicalScript(display, locale), sample)
    }
  })

  test(`${locale}: 越南语项目的结构标签全部换掉，不剩中文`, () => {
    for (const sample of [VI_SCREENPLAY, VI_FRAGMENT]) {
      const display = toDisplayScript(sample, locale)
      assert.equal(CJK.test(display), false, display)
    }
  })

  test(`${locale}: CRLF、空行、首尾空白原样保留`, () => {
    const crlf = '### 场2-1\r\n\r\n日 内 教室\r\n  出场人物：A、B\r\n\r\n'
    const display = toDisplayScript(crlf, locale)
    assert.equal(display.split('\r\n').length, crlf.split('\r\n').length)
    assert.ok(display.includes('\r\n\r\n'))
    assert.equal(toCanonicalScript(display, locale), crlf)
  })

  test(`${locale}: 句中 / 台词里的标签和冒号不动`, () => {
    const text = [
      '禹：他说空镜：不要拍',
      '△ 他看着远景：山崩',
      '今天日 内 很热',
      '外面下着雨',
      '日内瓦 的街头',
      'Minh：Giờ là 10:30, đi thôi',
      '10:30 Minh tỉnh dậy',
      '禹（旁白）：这不是旁白标签',
    ].join('\n')
    assert.equal(toDisplayScript(text, locale), text)
    assert.equal(toCanonicalScript(text, locale), text)
  })

  test(`${locale}: 粘贴的中文标签保存时原样保留`, () => {
    assert.equal(toCanonicalScript(ZH_SCREENPLAY, locale), ZH_SCREENPLAY)
    assert.equal(toCanonicalScript(VI_FRAGMENT, locale), VI_FRAGMENT)
  })
}

test('vi: 显示形态与手写输入换回规范标签', () => {
  const display = toDisplayScript(ZH_SCREENPLAY, 'vi')
  const lines = display.split('\n')
  assert.equal(lines[0], '### Phân đoạn 1-1')
  assert.equal(lines[1], 'Ngày · Nội cảnh · 灵山大雄宝殿')
  assert.equal(lines[2], 'Nhân vật xuất hiện: 禹, 鲧, 行刑兵')
  assert.equal(lines[5], 'Lời dẫn (vo): 那一年，洪水滔天。')
  assert.equal(lines[7], '【Cảnh trống: 江面薄雾】')
  assert.equal(lines[10], 'Rạng sáng·Ngoại cảnh · 羽山刑场')
  assert.equal(lines[11], 'Nhân vật xuất hiện: Không có')

  // 用户手写（大小写、半角冒号、别名、无空格）
  const typed = [
    '### cảnh 3-2',
    'đêm · ngoại cảnh · Bến sông',
    'Nhân vật: Minh, Lan',
    'Cảnh trống:Bến sông trong sương',
    'cận cảnh: Đôi mắt Lan',
    'Lời dẫn: Đêm ấy không ai ngủ.',
    '【Thoại · chậm, rõ · có phụ đề】Minh：Đi thôi.',
    '【BGM: nhạc buồn】',
  ].join('\n')
  assert.equal(
    toCanonicalScript(typed, 'vi'),
    [
      '### 场3-2',
      '夜 外 Bến sông',
      '出场人物：Minh、Lan',
      '空镜：Bến sông trong sương',
      '近景：Đôi mắt Lan',
      '旁白：Đêm ấy không ai ngủ.',
      '【对白·慢速清晰·同步字幕】Minh：Đi thôi.',
      '【BGM：nhạc buồn】',
    ].join('\n'),
  )
})

test('en: 显示形态', () => {
  const display = toDisplayScript(ZH_FRAGMENT_1, 'en').split('\n')
  assert.equal(display[0], '【Subtitles: bottom center · Chinese · line by line · synced to speech】')
  assert.equal(display[1], '【BGM: low and tense, drums building, pressure and danger; quieter than voices】')
  assert.equal(display[5], 'Day·EXT. · @asset:3 羽山刑场。')
  assert.equal(display[4], '@duration:3')
  assert.equal(display[13], '【Empty shot · ambient sound and BGM only】【Empty shot: 江面薄雾】')
  assert.equal(toCanonicalScript('Wide shot: Hanoi\nINT. · Office\nScene 1-1', 'en'), '远景：Hanoi\n内 Office\nScene 1-1')
  assert.equal(toCanonicalScript('### Scene 1-1', 'en'), '### 场1-1')
})

test('非规范写法保存时规整为规范写法（语义不变）', () => {
  const loose = '### 场景1-2\n出场人物:A, B\n空镜:江面'
  const round = toCanonicalScript(toDisplayScript(loose, 'vi'), 'vi')
  assert.equal(round, '### 场1-2\n出场人物：A、B\n空镜：江面')
})

test('zh 界面：两个方向都原样返回', () => {
  for (const sample of SAMPLES) {
    assert.equal(toDisplayScript(sample, 'zh'), sample)
    assert.equal(toCanonicalScript(sample, 'zh'), sample)
  }
  assert.equal(toCanonicalScript('Cảnh trống: X', 'zh'), 'Cảnh trống: X')
  assert.equal(toDisplayScript('', 'vi'), '')
})

test('说话人：旁白按界面语言显示，角色名不动', () => {
  assert.equal(displayScriptSpeaker('旁白', 'vi'), 'Lời dẫn')
  assert.equal(displayScriptSpeaker('旁白', 'en'), 'Narrator')
  assert.equal(displayScriptSpeaker('旁白', 'zh'), '旁白')
  assert.equal(displayScriptSpeaker('禹', 'vi'), '禹')
})

test('运镜词库插入的前缀按界面语言显示并可换回', () => {
  const items = messages.vi.dramaEpisode.camera.items
  assert.equal(toDisplayScript('空镜：', 'vi'), `${items.empty.label}: `)
  assert.equal(toCanonicalScript(`${items.aerial.label}: `, 'vi'), '航拍：')
  assert.equal(toCanonicalScript(toDisplayScript('移镜：', 'en'), 'en'), '移镜：')
})

test('显示标签在各自类别内不重复，预览与编辑框的「空镜」一致', () => {
  for (const locale of ['vi', 'en'] as const) {
    const m = messages[locale]
    const sl = m.dramaEpisode.scriptLabels
    const shotLabels = [
      ...Object.values(m.dramaEpisode.camera.items).map((i) => i.label),
      ...Object.values(sl.shots),
      sl.narrator,
    ].map((s) => s.toLocaleLowerCase())
    assert.equal(new Set(shotLabels).size, shotLabels.length, `${locale} shots`)
    const markers = Object.values(sl.markers).map((s) => s.toLocaleLowerCase())
    assert.equal(new Set(markers).size, markers.length, `${locale} markers`)
    const moods = Object.values(sl.bgm.moods).map((s) => s.toLocaleLowerCase())
    assert.equal(new Set(moods).size, moods.length, `${locale} moods`)
    const times = Object.values(m.dramaProject.preview.sceneTime).map((s) => s.toLocaleLowerCase())
    assert.equal(new Set(times).size, times.length, `${locale} times`)
    assert.equal(m.dramaProject.preview.establishing, m.dramaEpisode.camera.items.empty.label)
    for (const text of [...Object.values(sl.markers), ...Object.values(sl.bgm.moods), ...shotLabels]) {
      assert.equal(CJK.test(text), false, text)
      assert.equal(text.includes('】'), false, text)
    }
  }
})
