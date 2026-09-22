/** 英文：科普/获客短视频新建项目页与风格配置页 */

export const enStudio = {
  studioCreate: {
    untitled: 'Untitled work',
    defaultSeed: 'How AI is changing everyday life',
    aiFailed: 'AI generation failed',
    needTemplateAndTopic: 'Pick a template and enter your topic',
    createFailed: 'Could not create project',
    backCrumb: 'New project / Start creating',
    title: 'Create project',
    pickTemplate: 'Choose a template',
    searchTemplate: 'Search templates…',
    categoryTabs: 'Template categories',
    catAll: 'All',
    catHot: 'Popular',
    generic: 'General',
    inputTitle: 'Your content',
    inputTabs: {
      theme: 'One-line topic',
      script: 'Paste full script',
    },
    projectName: 'Project name',
    projectNamePlaceholder: 'Filled in automatically from your content',
    generating: 'Generating…',
    aiExpandScript: 'AI expand script',
    aiExpandTheme: 'AI write topic',
    aiHintScript: 'Expand one line into a full voiceover',
    aiHintTheme: 'Adds audience and key points',
    themePlaceholder: 'e.g. How do black holes form? Explain gravity and spacetime in plain words',
    scriptPlaceholder: 'Paste or let AI write the full voiceover script…',
    charCount: '{count} chars',
    inspireTitle: 'Inspiration',
    shuffle: 'Shuffle',
    inspireHintScript: 'Clicking an example fills in the full script and sets the project name',
    inspireHintTheme: 'Clicking an example fills in the full topic and sets the project name',
    topicHint:
      'The more specific the topic, the more accurate the storyboard and narration. Mention the audience and the key points.',
    summaryTitle: 'Summary',
    pleasePickTemplate: 'Choose a template',
    workName: 'Work name',
    outputMode: 'Output',
    outputPortrait: 'Video · 9:16',
    outputLandscape: 'Video · 16:9',
    estDuration: 'Est. length',
    estDurationValue: '~1–3 min',
    language: 'Language',
    languageValue: 'Chinese (Mandarin)',
    inputMethod: 'Input',
    creating: 'Creating…',
    nextStyle: 'Next: style settings',
    aiGenerating: 'AI generating…',
    aiHelpWrite: 'Not enough? Let AI write it',
    styleNote: 'The look comes with the template. Next, confirm the voice and output mode.',
    inspirations: [
      {
        title: 'How to shoot a store visit',
        theme: 'Local shop lead-gen voiceover: 3-second hook, scene, 1–2 real experiences, visit CTA. Facts only.',
        script:
          'I have walked past this street ten times. This time I finally went in.\n\n' +
          'Small storefront, clear sign, right by the metro exit.\n\n' +
          'I ordered their signature item. Honest take: tasted right, came out fast.\n\n' +
          'If you want to try it, check the current set menus in store and ignore any absolute promises.',
      },
      {
        title: 'A bestie’s recommendation post',
        theme: 'Lifestyle-note recommendation: hook title, first impression, real experience points, who it suits.',
        script:
          'I was only passing by, but ended up staying for a long while.\n\n' +
          'First impression: clean light, seats not cramped.\n\n' +
          'I ordered the signature dish; portions are as described. Quiet enough for a real conversation.\n\n' +
          'Best for people who want to sit and linger. In a hurry? Check the set menus first.',
      },
      {
        title: 'Review breakdown for deciders',
        theme: 'Review-style explainer: overall take, space and service, picks with reasons, value, who it suits.',
        script:
          'Overall: clean, clear process, good for first-timers.\n\n' +
          'Open, airy space; staff walk you through how to choose.\n\n' +
          'I recommend their signature item — I tried it on the spot and the steps were easy to follow.\n\n' +
          'Prices per the in-store list. Better with a friend than alone.',
      },
      {
        title: 'A light word-of-mouth nudge',
        theme: 'Friends-circle short: one honest feeling, one concrete detail, one light nudge. Not an ad.',
        script:
          'Stopped by on my way today and sat for a bit — quieter than I expected.\n\n' +
          'The table by the window gets natural light, a nice spot to rest.\n\n' +
          'If you are nearby, go take a look yourself.',
      },
      {
        title: 'How black holes form',
        theme: 'How do black holes form? Explain stellar collapse, the event horizon and curved spacetime for teens.',
        script:
          'One of the most mysterious objects in the night sky is the black hole.\n\n' +
          'When a massive star runs out of fuel, its core collapses violently under gravity, becoming so dense that even light cannot escape. That is where the event horizon is born.\n\n' +
          'It is not a cosmic vacuum cleaner — it is a region where spacetime is severely bent. Get close, and even time behaves strangely.\n\n' +
          'Remember: enough mass and a violent enough collapse, and a black hole appears. Next time you read space news, you will know legend from science.',
      },
      {
        title: 'Why the sky is blue',
        theme: 'Why is the sky blue? Use Rayleigh scattering to explain sunlight, air molecules and fiery sunsets.',
        script:
          'Look up: the daytime sky is usually blue. Is that a coincidence?\n\n' +
          'Sunlight looks white but contains many colors. Air molecules scatter blue light more strongly, bouncing it in every direction — so the sky we see leans blue.\n\n' +
          'At dawn and dusk the sun sits lower and light crosses more air; blue gets scattered away, and the remaining reds and oranges paint the horizon.\n\n' +
          'So the color of the sky is a collaboration between light and air.',
      },
      {
        title: 'How AI changes daily life',
        theme: 'How AI changes life: recommendations, voice assistants, medical imaging — the gains and the biases.',
        script:
          'Open your phone: recommended videos, navigation, voice assistants — AI has quietly moved into daily life.\n\n' +
          'It is good at finding patterns in huge amounts of data: spotting clues in medical scans, predicting machine failures, turning search into conversation.\n\n' +
          'But AI is not magic. Data carries bias, models make mistakes, and privacy needs boundaries. What is truly useful is treating AI as a tool, not an authority.\n\n' +
          'Understand what it can and cannot do, and you will use it more wisely.',
      },
      {
        title: 'A day on Mars',
        theme: 'What is a day on Mars like? Compare day length, temperature, dust and a future base with Earth.',
        script:
          'Imagine waking up on Mars: the sun is farther and smaller, the sky is creamy, and a day lasts about 24 hours 39 minutes.\n\n' +
          'Daytime may "warm up" to below freezing; nights are colder. The thin carbon-dioxide air cannot hold heat, and dust storms sometimes blot out the sky.\n\n' +
          'Scientists are still planning a base: shielding from radiation, making oxygen, growing food. Mars is not a second Earth, but it is the nearest classroom in deep space.\n\n' +
          'Understanding a Martian day is previewing humanity’s next long journey.',
      },
      {
        title: 'The power of dreams',
        theme: 'The power of dreams: sleep cycles, REM and memory sorting — how dreaming helps the brain review.',
        script:
          'After you fall asleep, your brain does not clock out.\n\n' +
          'During REM sleep it seems to replay fragments of the day, stitching them into strange dreams. Scientists think this helps organize memory and regulate mood.\n\n' +
          'Too little sleep and attention and creativity take a hit; regular sleep is like overnight maintenance for the brain.\n\n' +
          'Next time you have a weird dream, do not just call it absurd — your brain may be working overtime to learn.',
      },
      {
        title: 'A stray cat’s spring',
        theme: 'A stray cat’s spring: warm narration on urban ecology, feeding limits and living with strays.',
        script:
          'Spring is here. The orange cat at the alley mouth starts shedding and starts looking for a safer corner.\n\n' +
          'City strays survive on leftover wild instinct and the casual kindness of people. Responsible feeding, neutering and respecting distance matter more than impulse.\n\n' +
          'They are not scenery, and not a nuisance — they are part of the city’s ecology.\n\n' +
          'This spring, may every cat meet a steadier tomorrow.',
      },
      {
        title: 'The secret of photosynthesis',
        theme: 'Photosynthesis: how leaves turn sunlight into sugar — chloroplasts, energy and Earth’s oxygen.',
        script:
          'Green leaves are not decoration — they are the quietest chemical plants on Earth.\n\n' +
          'Chloroplasts capture sunlight and turn water and carbon dioxide into sugar, releasing oxygen. Without this process, most food chains would break.\n\n' +
          'The oxygen you breathe and the rice and vegetables on your table all trace back to this magic of light.\n\n' +
          'Understand photosynthesis and you understand the ledger beneath all life.',
      },
      {
        title: 'What to do in an earthquake',
        theme: 'What to do in an earthquake: preparation, safe positions and spotting rumors, taught through scenes.',
        script:
          'The ground suddenly shakes, and the first reaction is usually panic.\n\n' +
          'The right move: drop, cover and hold on nearby; stay away from windows and tall objects; do not crowd into elevators. An emergency kit packed in advance beats last-minute scrambling.\n\n' +
          'After the quake, watch for aftershocks and rumors. Official information and orderly mutual help are what real safety feels like.\n\n' +
          'A little earthquake knowledge buys a lot of calm when it counts.',
      },
      {
        title: 'How caffeine keeps you awake',
        theme: 'How caffeine keeps you awake: adenosine receptors, tolerance and the sleep cost — coffee done smart.',
        script:
          'Reaching for coffee when you are tired — does it really "wake up the brain"?\n\n' +
          'Caffeine takes the spot adenosine would sit in, so you temporarily stop feeling sleepy. But it cannot replace sleep, and too much in the afternoon means more tossing at night.\n\n' +
          'As tolerance builds, the same cup does less. The smarter approach: use it when you need focus, and leave a window for sleep.\n\n' +
          'Coffee can keep you alert, but recovery still comes from sleep.',
      },
      {
        title: 'Where does plastic go',
        theme: 'Where plastic goes: microplastics, ocean currents and alternative materials — an eco explainer.',
        script:
          'That plastic bag you threw away — did it really disappear?\n\n' +
          'Mostly it just breaks into smaller pieces. Microplastics enter rivers and oceans, then the food chain, and may end up back on our tables.\n\n' +
          'Using less single-use plastic, sorting waste and pushing better materials is far cheaper than cleaning up afterwards.\n\n' +
          'Asking "where does plastic go" is really asking what we are willing to leave for the future.',
      },
      {
        title: 'Why vaccines work',
        theme: 'Why vaccines work: antigens, antibodies and herd immunity as a "rehearsal"; clear up common myths.',
        script:
          'A vaccine is not a drug — it is more like a trailer sent to your immune system.\n\n' +
          'It lets the body learn a pathogen’s key features in advance, so antibodies mobilize faster when the real thing arrives. That is not rewriting genes; it is training memory.\n\n' +
          'When enough people are protected, transmission chains weaken. That is what herd immunity means.\n\n' +
          'Vaccinating sensibly puts you and the people around you inside a safer network.',
      },
      {
        title: 'The rise and fall of tides',
        theme: 'Why tides rise and fall: lunar gravity, centrifugal effects and spring vs neap tides, by the sea.',
        script:
          'People who live by the sea know it best: the water rises on schedule and retreats on schedule.\n\n' +
          'The main driver is the Moon’s gravity, with the Sun joining in. When Earth, Moon and Sun line up, the range grows — that is a spring tide.\n\n' +
          'Tides also shape navigation, power generation and even biological rhythms. Look up at the Moon, and the sea at your feet is answering it.\n\n' +
          'Between each rise and fall lies the visible trace of gravity between worlds.',
      },
    ],
  },
  studioStyle: {
    modes: {
      full: { label: 'AI video', desc: 'Image → video → voice → compose' },
      image_text: { label: 'Still-image film', desc: 'Stills + captions + voice, no AI video' },
    },
    previewPlayFailed: 'Could not play the sample',
    previewFailed: 'Preview failed',
    composeFailed: 'Compose failed',
    backToStudio: 'Back to studio',
    title: 'Style settings',
    projectInfo: 'Project',
    topic: 'Topic',
    duration: 'Length',
    durationValue: '~1–3 min',
    shotCount: 'Shots',
    shotCountAuto: 'Auto by AI',
    previewTemplate: 'Preview template',
    visualStyle: 'Visual style',
    visualStyleHint:
      'Locked by the template you chose. Stills and video pick up its look automatically. Whether to show characters is decided by the template rules and your topic — no need to pick a cast.',
    templateStyle: 'Template look',
    stylePromptLabel: 'Style prompt (optional override)',
    voiceTitle: 'Narration voice',
    moreVoices: 'More voices',
    female: 'Female',
    male: 'Male',
    generating: 'Generating…',
    playing: 'Playing',
    preview: 'Preview',
    currentVoice: 'Current: {name} · used for the whole film. Click “Preview” for a 5-second sample',
    outputTitle: 'Output mode',
    outputHint: 'Any template can generate AI video or not, regardless of aspect ratio.',
    imageModel: 'Image model',
    imageModelHint: 'Image models the site admin has enabled for explainer videos.',
    recommended: 'Recommended',
    videoModel: 'Video model',
    videoModelHint: 'Used for image-to-video; not called in still-image mode.',
    noImageModels: 'No image models are set up yet. Contact the site administrator.',
    noVideoModels: 'No video models are set up yet. Contact the site administrator.',
    modelAuto: 'Auto',
    modelAutoDesc: 'Rotates among the models the admin has enabled',
    ratioTitle: 'Aspect ratio',
    livePreview: 'Live preview',
    previewPlaceholder: 'Preview placeholder',
    previewNote: 'Real frames appear on the storyboard after generation. This is the template preview.',
    overviewTitle: 'Current settings',
    style: 'Style',
    character: 'Characters',
    characterAuto: 'AI decides from template and topic',
    voice: 'Voice',
    voiceDefault: 'Default',
    ratio: 'Ratio',
    output: 'Output',
    stopPreview: 'Stop preview',
    previewNamed: 'Preview “{name}”',
    starting: 'Starting…',
    saveContinue: 'Save and continue',
    generateBoard: 'Generate storyboard',
    generateNote: 'The storyboard script comes first. Review it, then start stills and voice manually.',
  },
} as const
