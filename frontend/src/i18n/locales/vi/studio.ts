/** 越南语：科普/获客短视频新建项目页与风格配置页 */

export const viStudio = {
  studioCreate: {
    untitled: 'Dự án chưa đặt tên',
    defaultSeed: 'AI đang thay đổi cuộc sống hằng ngày ra sao',
    aiFailed: 'AI chưa viết được, vui lòng thử lại',
    needTemplateAndTopic: 'Hãy chọn mẫu và nhập chủ đề',
    createFailed: 'Không thể tạo dự án',
    backCrumb: 'Dự án mới / Bắt đầu',
    title: 'Tạo dự án',
    pickTemplate: 'Chọn mẫu',
    searchTemplate: 'Tìm mẫu…',
    categoryTabs: 'Danh mục mẫu',
    catAll: 'Tất cả',
    catHot: 'Phổ biến',
    generic: 'Chung',
    inputTitle: 'Nhập nội dung',
    inputTabs: {
      theme: 'Chỉ nhập chủ đề',
      script: 'Dán kịch bản có sẵn',
    },
    projectName: 'Tên dự án',
    projectNamePlaceholder: 'Tự đặt theo nội dung bạn nhập',
    generating: 'Đang tạo…',
    aiExpandScript: 'AI viết kịch bản',
    aiExpandTheme: 'AI viết chủ đề',
    aiHintScript: 'Từ một câu, AI viết thành lời dẫn hoàn chỉnh',
    aiHintTheme: 'AI thêm đối tượng người xem và các ý chính',
    themePlaceholder: 'Ví dụ: Quán cà phê sân vườn ở Thủ Đức, nổi bật là cà phê muối và góc check-in, mời khách ghé cuối tuần',
    scriptPlaceholder: 'Dán lời dẫn của bạn vào đây, hoặc để AI viết giúp…',
    charCount: '{count} ký tự',
    inspireTitle: 'Gợi ý chủ đề',
    shuffle: 'Xem gợi ý khác',
    inspireHintScript: 'Bấm vào một gợi ý để điền sẵn kịch bản và tên dự án',
    inspireHintTheme: 'Bấm vào một gợi ý để điền sẵn chủ đề và tên dự án',
    topicHint:
      'Chủ đề càng cụ thể, AI chia cảnh và viết lời dẫn càng sát ý bạn. Hãy nêu rõ video dành cho ai và các ý chính.',
    summaryTitle: 'Tóm tắt',
    pleasePickTemplate: 'Hãy chọn mẫu',
    workName: 'Tên dự án',
    outputMode: 'Định dạng',
    outputPortrait: 'Video · 9:16',
    outputLandscape: 'Video · 16:9',
    estDuration: 'Thời lượng ước tính',
    estDurationValue: '~1–3 phút',
    language: 'Ngôn ngữ',
    languageValue: 'Tiếng Trung (Phổ thông)',
    inputMethod: 'Cách nhập',
    creating: 'Đang tạo…',
    nextStyle: 'Tiếp: thiết lập phong cách',
    aiGenerating: 'AI đang viết…',
    aiHelpWrite: 'Chưa đủ ý? Để AI viết giúp',
    styleNote: 'Phong cách hình ảnh đã có sẵn trong mẫu. Ở bước tiếp theo, bạn chọn giọng đọc và kiểu video.',
    inspirations: [
      {
        title: 'Quán cà phê sân vườn cuối tuần',
        theme: 'Video bán hàng cho quán cà phê sân vườn: hook 3 giây đầu, không gian, món nên thử, mời ghé quán.',
        script:
          'Đi ngang con hẻm này cả chục lần, hôm nay mình mới ghé vào.\n\n' +
          'Quán nằm ngay đầu hẻm, có sân vườn nhỏ, nhiều cây xanh, ngồi buổi sáng rất mát.\n\n' +
          'Mình gọi cà phê muối và bạc xỉu. Cà phê đậm, lớp kem mặn nhẹ, uống không bị ngấy. Nước ra nhanh, nhân viên dễ thương.\n\n' +
          'Cuối tuần chưa biết đi đâu thì ghé thử nhé. Giá và combo các bạn xem menu tại quán.',
      },
      {
        title: 'Spa gội đầu dưỡng sinh',
        theme: 'Video bán hàng cho spa gội đầu dưỡng sinh: hook mỏi vai gáy, các bước, cảm nhận thật, mời đặt lịch.',
        script:
          'Ngồi máy tính cả ngày, cổ vai gáy mỏi nhừ? Mình vừa thử gội đầu dưỡng sinh và đây là cảm nhận thật.\n\n' +
          'Phòng sạch, thơm mùi thảo mộc, nhạc nhẹ, vừa nằm xuống là thấy thư giãn.\n\n' +
          'Một suất khoảng 60 phút: gội đầu, massage đầu, cổ, vai gáy rồi đắp mặt nạ. Bạn kỹ thuật viên hỏi lực tay trước khi làm nên rất dễ chịu.\n\n' +
          'Ai hay mỏi vai gáy có thể thử một lần. Nên nhắn đặt lịch trước để không phải chờ.',
      },
      {
        title: 'Tiệm nail mẫu mới mỗi tuần',
        theme: 'Video bán hàng cho tiệm nail: hook bằng bộ móng đẹp, mẫu mới trong tuần, mời nhắn tiệm đặt lịch.',
        script:
          'Bộ móng này mình làm chưa tới một tiếng, và đi đâu cũng được khen.\n\n' +
          'Tiệm nhỏ thôi nhưng sạch sẽ, dụng cụ được khử trùng ngay trước mặt khách.\n\n' +
          'Tuần này tiệm có mẫu mắt mèo và mẫu vẽ hoa nhí, hợp đi làm lẫn đi chơi. Bạn thợ tư vấn màu theo tông da rất có tâm.\n\n' +
          'Thích mẫu nào cứ lưu lại rồi nhắn tiệm đặt lịch nhé. Bảng giá có sẵn tại tiệm.',
      },
      {
        title: 'Quán bún bò đông khách buổi sáng',
        theme: 'Video bán hàng cho quán bún bò: hook nồi nước dùng, món nên gọi, cảm nhận thật, mời ghé quán.',
        script:
          'Sáu giờ sáng quán đã kín bàn. Mình tò mò nên ghé ăn thử.\n\n' +
          'Nồi nước dùng đặt ngay trước cửa, thơm mùi sả. Quán bình dân nhưng bàn ghế sạch sẽ.\n\n' +
          'Mình gọi tô đặc biệt: nước dùng đậm đà, chả cua dai, thịt mềm, rau ăn kèm tươi. Theo khẩu vị của mình là ngon, đáng để quay lại.\n\n' +
          'Quán bán từ sáng sớm tới khoảng mười giờ. Ai ở gần thì ghé ăn thử, giá xem bảng tại quán.',
      },
      {
        title: 'Kem chống nắng cho da dầu',
        theme: 'Video bán hàng cho shop mỹ phẩm: hook nỗi lo bóng dầu, ưu điểm sản phẩm, cách dùng, mời nhắn shop.',
        script:
          'Da dầu mà ngại bôi kem chống nắng vì sợ bóng nhờn? Mình cũng từng như vậy.\n\n' +
          'Tuýp này kết cấu mỏng nhẹ, thấm nhanh, không để lại vệt trắng. Mình dùng được hai tuần rồi.\n\n' +
          'Buổi sáng bôi sau bước dưỡng ẩm, ra ngoài lâu thì bôi lại sau vài tiếng. Da mình đỡ bóng hơn hẳn, trang điểm lên vẫn ổn.\n\n' +
          'Da mỗi người mỗi khác. Bạn cứ nhắn shop để được tư vấn theo loại da trước khi mua nhé.',
      },
      {
        title: 'Shop quần áo mặc đi làm',
        theme: 'Video bán hàng cho shop thời trang: hook “mặc gì đi làm”, 3 cách phối đồ, chất vải, mời đặt hàng.',
        script:
          'Sáng nào cũng đứng trước tủ đồ mà không biết mặc gì đi làm? Mình gợi ý ba cách phối từ một chiếc sơ mi.\n\n' +
          'Cách một: sơ mi với quần tây ống suông, gọn gàng mà vẫn thoải mái. Cách hai: sơ mi với chân váy dài cho ngày có hẹn. Cách ba: khoác ngoài áo thun, hợp với thứ sáu.\n\n' +
          'Vải mình sờ thử thấy mát, ít nhăn, giặt máy được.\n\n' +
          'Shop có đủ size. Bạn ghé thử trực tiếp hoặc nhắn shop để đặt online nhé.',
      },
      {
        title: 'Hố đen hình thành thế nào',
        theme: 'Hố đen hình thành thế nào? Kể cho học sinh: sao sụp đổ, chân trời sự kiện, không-thời gian cong.',
        script:
          'Một trong những thiên thể bí ẩn nhất trên bầu trời đêm chính là hố đen.\n\n' +
          'Khi một ngôi sao đủ lớn cạn nhiên liệu, lõi của nó sụp đổ dữ dội dưới lực hấp dẫn, đặc đến mức ánh sáng cũng không thoát ra được. Chân trời sự kiện ra đời từ đó.\n\n' +
          'Hố đen không phải máy hút bụi vũ trụ, mà là vùng không-thời gian bị bẻ cong cực mạnh. Càng tới gần, thời gian càng trôi chậm lại.\n\n' +
          'Hãy nhớ: khối lượng đủ lớn, sụp đổ đủ mạnh thì hố đen xuất hiện. Lần sau đọc tin khoa học, bạn sẽ phân biệt được đâu là đồn thổi, đâu là khoa học.',
      },
      {
        title: 'Vì sao bầu trời màu xanh',
        theme: 'Vì sao bầu trời màu xanh? Giải thích dễ hiểu về tán xạ ánh sáng, không khí và hoàng hôn màu đỏ.',
        script:
          'Ngẩng đầu lên, bầu trời ban ngày gần như lúc nào cũng xanh. Có phải ngẫu nhiên không?\n\n' +
          'Ánh nắng trông có vẻ trắng nhưng thật ra gồm nhiều màu. Các phân tử không khí tán xạ ánh sáng xanh mạnh nhất, làm nó toả đi khắp mọi hướng, nên ta nhìn đâu cũng thấy trời xanh.\n\n' +
          'Sáng sớm và chiều tối, mặt trời xuống thấp, ánh sáng phải đi qua lớp không khí dày hơn. Ánh xanh bị tán xạ gần hết, chỉ còn màu đỏ cam nhuộm cả chân trời.\n\n' +
          'Vậy nên màu của bầu trời là kết quả của ánh sáng và không khí cùng tạo ra.',
      },
      {
        title: 'AI thay đổi cuộc sống thế nào',
        theme: 'AI thay đổi cuộc sống thế nào: gợi ý nội dung, trợ lý giọng nói, đọc ảnh y tế; lợi ích và lưu ý.',
        script:
          'Mở điện thoại ra: video gợi ý, chỉ đường, trợ lý giọng nói. Trí tuệ nhân tạo đã lặng lẽ có mặt trong cuộc sống hằng ngày.\n\n' +
          'AI giỏi tìm quy luật trong lượng dữ liệu khổng lồ: giúp bác sĩ phát hiện dấu hiệu bất thường trên ảnh chụp, giúp nhà máy dự báo hỏng hóc, và biến việc tìm kiếm thành một cuộc trò chuyện.\n\n' +
          'Nhưng AI không phải phép màu. Dữ liệu có thể thiên lệch, mô hình có thể sai, quyền riêng tư cần được bảo vệ. Hãy coi AI là công cụ, đừng coi nó là chân lý.\n\n' +
          'Hiểu AI làm được gì và không làm được gì, bạn sẽ dùng nó khôn ngoan hơn.',
      },
      {
        title: 'Một ngày trên sao Hỏa',
        theme: 'Một ngày trên sao Hỏa: so với Trái Đất về độ dài ngày, nhiệt độ, bão bụi và kế hoạch xây căn cứ.',
        script:
          'Tưởng tượng bạn thức dậy trên sao Hỏa: mặt trời xa hơn và nhỏ hơn, bầu trời ngả màu vàng nhạt, một ngày dài khoảng 24 giờ 39 phút.\n\n' +
          'Ban ngày “ấm” nhất cũng chỉ quanh 0 độ, ban đêm còn lạnh hơn nhiều. Lớp khí CO2 mỏng không giữ được nhiệt, thỉnh thoảng bão bụi che kín cả bầu trời.\n\n' +
          'Các nhà khoa học vẫn đang lên kế hoạch xây căn cứ: chống bức xạ, tạo oxy, trồng lương thực. Sao Hỏa không phải Trái Đất thứ hai, nhưng là nơi gần nhất để con người tập sống ngoài vũ trụ.\n\n' +
          'Hiểu một ngày trên sao Hỏa cũng là chuẩn bị cho chuyến đi xa tiếp theo của loài người.',
      },
      {
        title: 'Vì sao chúng ta nằm mơ',
        theme: 'Vì sao chúng ta nằm mơ: chu kỳ giấc ngủ, giấc ngủ REM, sắp xếp trí nhớ; não “ôn bài” ban đêm ra sao.',
        script:
          'Bạn ngủ rồi, nhưng bộ não thì chưa tan ca.\n\n' +
          'Khi vào giấc ngủ REM, não như đang chiếu lại những mảnh ký ức trong ngày rồi ghép chúng thành các giấc mơ kỳ lạ. Các nhà khoa học cho rằng việc này giúp sắp xếp trí nhớ và cân bằng cảm xúc.\n\n' +
          'Thiếu ngủ thì khả năng tập trung và sáng tạo đều giảm. Ngủ đều đặn giống như bảo dưỡng bộ não mỗi đêm.\n\n' +
          'Lần sau mơ thấy điều gì kỳ quặc, đừng vội cho là vô nghĩa. Có thể não bạn đang tăng ca để học đấy.',
      },
      {
        title: 'Mùa xuân của một chú mèo hoang',
        theme: 'Mùa xuân của chú mèo hoang: chuyện ấm áp về động vật trong thành phố, cho ăn đúng cách, chung sống.',
        script:
          'Xuân đến, chú mèo vàng đầu ngõ bắt đầu thay lông và đi tìm một góc an toàn hơn.\n\n' +
          'Động vật hoang trong thành phố sống nhờ bản năng và lòng tốt tình cờ của con người. Cho ăn có trách nhiệm, triệt sản và giữ khoảng cách vừa phải quan trọng hơn sự thương yêu bốc đồng.\n\n' +
          'Chúng không phải vật trang trí, cũng không phải điều phiền toái, mà là một phần của thành phố.\n\n' +
          'Mùa xuân này, mong chú mèo nào cũng có một ngày mai yên ổn hơn.',
      },
      {
        title: 'Bí mật của quang hợp',
        theme: 'Bí mật của quang hợp: lá cây biến ánh nắng thành đường ra sao, vai trò lục lạp, oxy đến từ đâu.',
        script:
          'Lá xanh không chỉ để làm đẹp. Chúng là những nhà máy hóa học thầm lặng nhất trên Trái Đất.\n\n' +
          'Lục lạp hấp thụ ánh nắng, biến nước và CO2 thành đường, đồng thời nhả ra oxy. Không có quá trình này, phần lớn chuỗi thức ăn sẽ đứt gãy.\n\n' +
          'Oxy bạn đang thở, cơm và rau trên mâm cơm, đều gián tiếp đến từ quá trình kỳ diệu này.\n\n' +
          'Hiểu quang hợp là hiểu cách sự sống trên Trái Đất được nuôi dưỡng.',
      },
      {
        title: 'Cà phê giúp tỉnh táo thế nào',
        theme: 'Cà phê giúp tỉnh táo thế nào: caffeine, hiện tượng lờn, ảnh hưởng tới giấc ngủ, uống sao cho đúng.',
        script:
          'Buồn ngủ thì làm ly cà phê. Nhưng có thật là cà phê “đánh thức bộ não”?\n\n' +
          'Caffeine chiếm chỗ của adenosine, chất khiến bạn thấy buồn ngủ, nên bạn tạm thời tỉnh táo. Nhưng nó không thay được giấc ngủ: uống nhiều vào buổi chiều, đêm dễ trằn trọc.\n\n' +
          'Uống lâu ngày cơ thể sẽ lờn, cùng một ly mà hiệu quả yếu dần. Cách khôn ngoan hơn là chỉ uống khi cần tập trung và ngủ cho đủ.\n\n' +
          'Tỉnh táo có thể nhờ cà phê, còn hồi phục thì vẫn phải nhờ giấc ngủ.',
      },
      {
        title: 'Rác nhựa đi đâu',
        theme: 'Rác nhựa đi đâu: vi nhựa, dòng hải lưu và vật liệu thay thế, làm thành video ngắn về môi trường.',
        script:
          'Chiếc túi ni lông bạn vứt đi, liệu nó có thật sự biến mất?\n\n' +
          'Phần lớn chỉ vỡ thành những mảnh nhỏ hơn. Vi nhựa theo sông ra biển, đi vào chuỗi thức ăn, và cuối cùng có thể quay lại chính mâm cơm của chúng ta.\n\n' +
          'Hạn chế đồ nhựa dùng một lần, phân loại rác đúng cách, chọn vật liệu thân thiện hơn: tất cả đều rẻ hơn nhiều so với việc dọn dẹp về sau.\n\n' +
          'Hỏi “rác nhựa đi đâu” thật ra là hỏi: chúng ta muốn để lại gì cho thế hệ sau.',
      },
      {
        title: 'Vì sao vắc xin hiệu quả',
        theme: 'Vì sao vắc xin hiệu quả: ví như buổi “diễn tập” để nói về kháng thể và miễn dịch cộng đồng.',
        script:
          'Vắc xin không phải thuốc chữa bệnh, mà giống một buổi diễn tập cho hệ miễn dịch.\n\n' +
          'Nó cho cơ thể làm quen trước với đặc điểm của mầm bệnh, để khi gặp thật, cơ thể tạo kháng thể nhanh hơn. Vắc xin không thay đổi gen của bạn, nó chỉ huấn luyện trí nhớ miễn dịch.\n\n' +
          'Khi đủ nhiều người được bảo vệ, bệnh khó lây lan hơn. Đó chính là miễn dịch cộng đồng.\n\n' +
          'Tiêm chủng đầy đủ là bảo vệ chính mình và cả những người xung quanh.',
      },
    ],
  },
  studioStyle: {
    modes: {
      full: { label: 'Video AI', desc: 'Ảnh → video → giọng đọc → dựng video' },
      image_text: { label: 'Video ảnh tĩnh', desc: 'Ảnh tĩnh + phụ đề + giọng đọc, không tạo video AI' },
    },
    previewPlayFailed: 'Không phát được mẫu giọng',
    previewFailed: 'Không nghe thử được',
    composeFailed: 'Dựng video thất bại',
    backToStudio: 'Quay lại studio',
    title: 'Thiết lập phong cách',
    projectInfo: 'Thông tin dự án',
    topic: 'Chủ đề',
    duration: 'Thời lượng',
    durationValue: '~1–3 phút',
    shotCount: 'Số cảnh',
    shotCountAuto: 'AI tự chia',
    previewTemplate: 'Xem trước mẫu',
    visualStyle: 'Phong cách hình ảnh',
    visualStyleHint:
      'Phong cách đi theo mẫu bạn đã chọn và không đổi được ở đây; ảnh và video sẽ tự theo phong cách đó. Có nhân vật hay không do AI tự quyết theo mẫu và chủ đề, bạn không cần chọn nhân vật.',
    templateStyle: 'Phong cách của mẫu',
    stylePromptLabel: 'Prompt phong cách (không bắt buộc, thay cho mẫu)',
    voiceTitle: 'Giọng đọc',
    moreVoices: 'Thêm giọng',
    female: 'Giọng nữ',
    male: 'Giọng nam',
    generating: 'Đang tạo…',
    playing: 'Đang phát',
    preview: 'Nghe thử',
    currentVoice: 'Đang chọn: {name} · dùng cho cả video. Bấm “Nghe thử” để nghe mẫu khoảng 5 giây',
    outputTitle: 'Kiểu video',
    outputHint: 'Mẫu nào cũng chọn được có tạo video AI hay không, không phụ thuộc tỷ lệ khung hình.',
    imageModel: 'Mô hình tạo ảnh',
    imageModelHint: 'Gồm các mô hình TokenFree đã bật ở mục “Mô hình” trong trang quản trị.',
    recommended: 'Đề xuất',
    videoModel: 'Mô hình tạo video',
    videoModelHint: 'Dùng để tạo video từ ảnh; kiểu video ảnh tĩnh không dùng đến.',
    ratioTitle: 'Tỷ lệ khung hình',
    livePreview: 'Xem trước',
    previewPlaceholder: 'Chưa có ảnh xem trước',
    previewNote: 'Đây là ảnh xem trước của mẫu. Hình ảnh thật sẽ hiện ở Bảng phân cảnh sau khi tạo.',
    overviewTitle: 'Thiết lập hiện tại',
    style: 'Phong cách',
    character: 'Nhân vật',
    characterAuto: 'AI tự quyết theo mẫu và chủ đề',
    voice: 'Giọng đọc',
    voiceDefault: 'Mặc định',
    ratio: 'Tỷ lệ',
    output: 'Kiểu video',
    stopPreview: 'Dừng nghe thử',
    previewNamed: 'Nghe thử “{name}”',
    starting: 'Đang khởi động…',
    saveContinue: 'Lưu và tiếp tục',
    generateBoard: 'Tạo bảng phân cảnh',
    generateNote: 'AI viết kịch bản phân cảnh trước. Bạn xem và sửa xong rồi mới bấm tạo ảnh và giọng đọc.',
  },
} as const
