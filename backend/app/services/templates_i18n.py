"""内置模板的多语言名称与描述。

`name` / `description` 字段仍保留中文作为主键与逻辑依据（风格锁、允许原名等规则按 id 判断，
不依赖名称），此处仅提供界面展示用的 en / vi 译文，由 seed 写入 `templates.i18n`，
前端按界面语言取值，缺失时回落中文。

结构：{template_id: {"en": {"name", "description"}, "vi": {...}}}
"""

TEMPLATE_I18N: dict[str, dict[str, dict[str, str]]] = {
    "opensource_showcase": {
        "en": {
            "name": "Open-source showcase",
            "description": "Planned from the project itself: people operating the system UI in real work settings. Good for open-source tools and platform intros.",
        },
        "vi": {
            "name": "Giới thiệu dự án mã nguồn mở",
            "description": "Các cảnh được lên theo nội dung của từng dự án: người thao tác trên giao diện hệ thống và bối cảnh sử dụng thật. Hợp để giới thiệu công cụ, nền tảng mã nguồn mở.",
        },
    },
    "opensource_live_work": {
        "en": {
            "name": "Live-action workstation",
            "description": "Photoreal desk work: profile or over-the-shoulder shots of someone operating the system. Good for open-source tools and product workflow explainers.",
        },
        "vi": {
            "name": "Người thật · bàn làm việc",
            "description": "Người thật ngồi làm việc, quay góc nghiêng hoặc qua vai khi đang thao tác phần mềm. Hợp với video kiến thức về công cụ mã nguồn mở và quy trình làm việc của sản phẩm.",
        },
    },
    "live_street_interview": {
        "en": {
            "name": "Street-interview talking head",
            "description": "Real people speaking to camera on the street or during a commute. Good for opinions, experiences, and light interview explainers.",
        },
        "vi": {
            "name": "Người thật · phỏng vấn đường phố",
            "description": "Người thật nói trước ống kính ngoài phố hoặc trên đường đi làm. Hợp với video nêu quan điểm, chia sẻ trải nghiệm, phỏng vấn nhanh.",
        },
    },
    "live_product_desk": {
        "en": {
            "name": "Live-action desk demo",
            "description": "Top-down or angled photoreal desk shots: real hands demonstrating a product or laptop workflow. Good for tool reviews and tutorials.",
        },
        "vi": {
            "name": "Người thật · demo trên bàn",
            "description": "Quay từ trên xuống hoặc chếch xuống mặt bàn: đôi tay thật đang dùng sản phẩm hoặc thao tác trên laptop. Hợp với video review công cụ và hướng dẫn sử dụng.",
        },
    },
    "portrait_story": {
        "en": {
            "name": "Vertical illustrated story",
            "description": "Vertical illustrated storytelling with cinematic framing. Good for history and culture shorts.",
        },
        "vi": {
            "name": "Kể chuyện bằng tranh · khung dọc",
            "description": "Kể chuyện bằng tranh minh hoạ khung dọc, bố cục như phim điện ảnh. Hợp với video ngắn về lịch sử, văn hoá.",
        },
    },
    "anim_3d": {
        "en": {
            "name": "3D animation",
            "description": "Film-grade 3D animation with rounded shapes and soft volumetric light. Good for explainers and story shorts.",
        },
        "vi": {
            "name": "Hoạt hình 3D",
            "description": "Hoạt hình 3D đẹp như phim chiếu rạp, nhân vật bo tròn, ánh sáng mềm. Hợp với video kiến thức và truyện ngắn.",
        },
    },
    "live_cinematic": {
        "en": {
            "name": "Live-action cinematic",
            "description": "Live-action film look with dramatic lighting and shallow depth of field. Good for narrative shorts.",
        },
        "vi": {
            "name": "Người thật · phong cách điện ảnh",
            "description": "Hình ảnh người thật như phim điện ảnh: ánh sáng kịch tính, hậu cảnh xoá mờ. Hợp với video ngắn kể chuyện.",
        },
    },
    "live_person": {
        "en": {
            "name": "Live-action narrative",
            "description": "Everyday on-camera realism. Good for personal stories, talking heads, and documentary shorts.",
        },
        "vi": {
            "name": "Người thật · đời thường",
            "description": "Người thật xuất hiện tự nhiên như đời thường. Hợp với chuyện về nhân vật, video nói trước ống kính và phóng sự ngắn.",
        },
    },
    "photo_realism": {
        "en": {
            "name": "Photorealistic",
            "description": "Photo-grade realism. Good for products, landscapes, and documentary explainers.",
        },
        "vi": {
            "name": "Ảnh chụp chân thực",
            "description": "Hình ảnh chân thực như ảnh chụp. Hợp với sản phẩm, phong cảnh và video kiến thức kiểu phóng sự.",
        },
    },
    "film_cinematic": {
        "en": {
            "name": "Cinematic film stock",
            "description": "Widescreen film grain with dramatic lighting. Good for narrative and mood-driven shorts.",
        },
        "vi": {
            "name": "Phim nhựa điện ảnh",
            "description": "Chất phim nhựa màn ảnh rộng, ánh sáng kịch tính. Hợp với video kể chuyện, cần nhiều cảm xúc.",
        },
    },
    "noir_thriller": {
        "en": {
            "name": "Noir thriller",
            "description": "High-contrast light and cool tones. Good for mystery, true-crime, and night-time narratives.",
        },
        "vi": {
            "name": "Film noir ly kỳ",
            "description": "Ánh sáng tương phản mạnh, tông màu lạnh. Hợp với chuyện ly kỳ bí ẩn, vụ án, câu chuyện trong đêm tối.",
        },
    },
    "vox_papercut": {
        "en": {
            "name": "Vox-style paper cut",
            "description": "Low-saturation flat paper-cut look centered on people using computers and system UIs. Good for hardcore explainers and product walkthroughs.",
        },
        "vi": {
            "name": "Video kiến thức · cắt giấy kiểu Vox",
            "description": "Tranh cắt giấy phẳng, màu ít rực, hình ảnh chính là người đang thao tác máy tính, phần mềm. Hợp với video kiến thức chuyên sâu và giới thiệu sản phẩm.",
        },
    },
    "docu_warm": {
        "en": {
            "name": "Warm documentary",
            "description": "Documentary illustration with warm tones. Good for personal stories and human-interest shorts.",
        },
        "vi": {
            "name": "Tài liệu tông ấm",
            "description": "Tranh minh hoạ kiểu phim tài liệu, tông màu ấm. Hợp với chuyện về nhân vật và phim tài liệu ngắn về con người, văn hoá.",
        },
    },
    "kids_flat": {
        "en": {
            "name": "Children's flat picture book",
            "description": "Soft colors and rounded shapes. Good for kids' explainers and stories.",
        },
        "vi": {
            "name": "Tranh truyện thiếu nhi nét phẳng",
            "description": "Màu dịu, hình vẽ bo tròn. Hợp với video kiến thức và truyện kể cho trẻ em.",
        },
    },
    "soft_anime": {
        "en": {
            "name": "Soft-light anime",
            "description": "Japanese soft-light cel shading. Good for youth stories and emotional shorts.",
        },
        "vi": {
            "name": "Anime ánh sáng dịu",
            "description": "Anime kiểu Nhật tô màu mảng phẳng (cel), ánh sáng dịu. Hợp với chuyện thanh xuân và video ngắn giàu cảm xúc.",
        },
    },
    "chalk_whiteboard": {
        "en": {
            "name": "Chalkboard sketch",
            "description": "Blackboard chalk lecture look that highlights people operating systems and drawing flowcharts. Classroom-style demos.",
        },
        "vi": {
            "name": "Vẽ tay phấn bảng · bảng trắng",
            "description": "Kiểu giảng bài bằng phấn trên bảng đen, làm nổi bật cảnh nhân vật thao tác hệ thống, vẽ sơ đồ quy trình như đang trình bày trên lớp.",
        },
    },
    "cyber_neon": {
        "en": {
            "name": "Cyber neon",
            "description": "Neon night city and futuristic feel. Good for tech, urban, and sci-fi topics.",
        },
        "vi": {
            "name": "Cyberpunk neon",
            "description": "Thành phố về đêm rực đèn neon, đậm chất tương lai. Hợp với chủ đề công nghệ, đô thị, viễn tưởng.",
        },
    },
    "epic_fantasy": {
        "en": {
            "name": "Epic fantasy",
            "description": "Grand scenery and fantasy lighting. Good for myths, adventures, and world-building shorts.",
        },
        "vi": {
            "name": "Kỳ ảo hoành tráng",
            "description": "Cảnh hoành tráng, ánh sáng kỳ ảo. Hợp với thần thoại, phiêu lưu và những thế giới giả tưởng.",
        },
    },
    "magazine_collage": {
        "en": {
            "name": "Magazine collage",
            "description": "Clipping collage with print textures. Good for culture topics and brand stories.",
        },
        "vi": {
            "name": "Cắt dán tạp chí",
            "description": "Cắt dán từ báo, tạp chí, có vân giấy in. Hợp với chủ đề văn hoá và câu chuyện thương hiệu.",
        },
    },
    "brand_clean": {
        "en": {
            "name": "Minimal brand",
            "description": "Clean color blocks and generous white space. Good for product explainers and brand shorts.",
        },
        "vi": {
            "name": "Thương hiệu tối giản",
            "description": "Mảng màu gọn gàng, nhiều khoảng trắng. Hợp với video giới thiệu sản phẩm và thương hiệu.",
        },
    },
    "pixel_retro": {
        "en": {
            "name": "Pixel retro explainer",
            "description": "8-bit / 16-bit pixel art. Good for tech history and gamified explainers.",
        },
        "vi": {
            "name": "Pixel kiểu game xưa",
            "description": "Đồ hoạ pixel 8-bit / 16-bit như game xưa. Hợp với lịch sử công nghệ và video kiến thức kiểu trò chơi.",
        },
    },
    "retro_vhs": {
        "en": {
            "name": "Retro VHS",
            "description": "Tape and scanline texture. Good for nostalgic stories and period content.",
        },
        "vi": {
            "name": "Băng VHS xưa",
            "description": "Hình ảnh như băng video cũ, có sọc nhiễu. Hợp với chuyện hoài niệm và nội dung về một thời đã qua.",
        },
    },
    "ink_guofeng": {
        "en": {
            "name": "Ink-wash Chinese style",
            "description": "Ink wash with negative space and expressive strokes. Good for history and culture short stories.",
        },
        "vi": {
            "name": "Thuỷ mặc cổ phong",
            "description": "Tranh thuỷ mặc nhiều khoảng trống, nét bút phóng khoáng. Hợp với truyện ngắn về lịch sử, văn hoá.",
        },
    },
    "huoke_douyin_hook": {
        "en": {
            "name": "Lead-gen · TikTok hook",
            "description": "Vertical talking-head rhythm: 3-second hook → scene visuals → 1–2 verifiable experiences → visit / order CTA. Built for paid lead-gen.",
        },
        "vi": {
            "name": "Bán hàng · Hook TikTok",
            "description": "Video dọc, nói trước ống kính: hook 3 giây đầu → hình ảnh bối cảnh → 1–2 trải nghiệm kiểm chứng được → mời ghé quán / đặt hàng. Hợp để chạy quảng cáo tìm khách hàng.",
        },
    },
    "huoke_xhs_recommend": {
        "en": {
            "name": "Lead-gen · Social recommendation (Facebook / Threads style)",
            "description": "Vertical friend-recommendation structure: hook title → first impression → bullet-point real experiences → who it's for. Dense cover, conversational tone.",
        },
        "vi": {
            "name": "Bán hàng · Bạn thân mách nhỏ",
            "description": "Video dọc kiểu bạn thân giới thiệu trên Facebook / Threads: tiêu đề hook → ấn tượng đầu tiên → trải nghiệm thật kể theo từng ý → nên giới thiệu cho ai. Ảnh bìa nhiều thông tin, lời lẽ như đang trò chuyện.",
        },
    },
    "huoke_review_facts": {
        "en": {
            "name": "Lead-gen · Fact-based review",
            "description": "Landscape, objective and detailed: overall verdict → space / service → picks with reasons → value for money → who it suits. Helps people decide, no gushing.",
        },
        "vi": {
            "name": "Bán hàng · Review chi tiết",
            "description": "Video ngang, khách quan và chi tiết: nhận xét chung → không gian / dịch vụ → nên chọn gì và vì sao → có đáng tiền không → hợp với ai. Giúp người xem ra quyết định, không kể lể cảm xúc.",
        },
    },
    "huoke_soft_invite": {
        "en": {
            "name": "Lead-gen · Soft word-of-mouth",
            "description": "Vertical slice-of-life short: one honest feeling → one concrete detail → one light recommendation. Restrained, not ad-like, made to forward to friends.",
        },
        "vi": {
            "name": "Bán hàng · Gợi ý nhẹ nhàng",
            "description": "Video dọc đời thường: một cảm nhận thật → một chi tiết cụ thể → một lời gợi ý nhẹ nhàng. Tiết chế, không giống quảng cáo, dễ gửi cho bạn bè.",
        },
    },
}
