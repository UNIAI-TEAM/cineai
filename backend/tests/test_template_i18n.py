"""内置模板多语言译文完整性：每个 seed 模板都有 en / vi 的名称与描述。"""

from app.services.templates_i18n import TEMPLATE_I18N
from app.services.templates_seed import TEMPLATES

LOCALES = ("en", "vi")


def test_every_seed_template_has_en_and_vi():
    missing = []
    for tpl in TEMPLATES:
        pack = TEMPLATE_I18N.get(tpl["id"]) or {}
        for locale in LOCALES:
            entry = pack.get(locale) or {}
            if not entry.get("name", "").strip() or not entry.get("description", "").strip():
                missing.append(f"{tpl['id']}:{locale}")
    assert not missing, f"缺少译文: {missing}"


def test_i18n_has_no_unknown_template_ids():
    known = {tpl["id"] for tpl in TEMPLATES}
    unknown = set(TEMPLATE_I18N) - known
    assert not unknown, f"译文引用了不存在的模板: {sorted(unknown)}"
