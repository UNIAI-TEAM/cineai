"""管理端落库错误：params 错误字段 / generation 失败读取，以及 admin schema 带出 error_code / error_params。"""

from datetime import UTC, datetime
from types import SimpleNamespace

from app.api.admin.drama_assets import AdminDramaAssetDetailOut
from app.api.admin.drama_episodes import AdminDramaEpisodeDetailOut
from app.schemas import AdminProjectOut, AdminTaskBriefOut
from app.schemas_tasks import AdminTaskRunOut, TaskRunOut
from app.services.admin.stored_errors import generation_error, param_error
from app.services.drama.job_errors import set_job_error_code, with_error_code
from app.services.drama.seed import set_seed_error


def test_param_error_reads_code_and_params():
    params: dict = {}
    set_job_error_code(params, "episode_content_error", "drama.episode_gen_incomplete", {"done": 2, "total": 5})
    err = param_error(params, "episode_content_error")
    assert err is not None
    assert err.code == "drama.episode_gen_incomplete"
    assert err.params == {"done": 2, "total": 5}
    assert err.message  # 中文模板原文，供运维对照


def test_param_error_legacy_text_without_code():
    err = param_error({"summary_error": "LLM error 500: boom"}, "summary_error")
    assert err is not None
    assert err.code is None and err.params is None
    assert err.message == "LLM error 500: boom"


def test_param_error_empty_or_missing():
    assert param_error(None, "summary_error") is None
    assert param_error({}, "summary_error") is None
    assert param_error({"summary_error": None}, "summary_error") is None
    assert param_error({"summary_error": "  "}, "summary_error") is None


def test_param_error_seed_error_shape():
    params: dict = {}
    set_seed_error(params, "boom", code="drama.asset_extract_failed")
    err = param_error(params, "assets_seed_error")
    assert err is not None and err.code == "drama.asset_extract_failed" and err.message == "boom"


def test_generation_error_only_when_failed():
    failed = {"generation": with_error_code({"status": "failed", "error": "超时"}, "drama.gen_timeout")}
    err = generation_error(failed)
    assert err is not None and err.code == "drama.gen_timeout" and err.message == "超时"

    uncoded = {"generation": {"status": "failed", "error": "upstream said no"}}
    err2 = generation_error(uncoded)
    assert err2 is not None and err2.code is None and err2.message == "upstream said no"

    # 重试中 / 成功后残留的旧错误不展示
    assert generation_error({"generation": {"status": "running", "error": "old"}}) is None
    assert generation_error({"generation": "bad"}) is None
    assert generation_error(None) is None


def test_admin_project_out_includes_error_code():
    now = datetime.now(UTC)
    project = SimpleNamespace(
        id=1,
        user_id=2,
        template_id="t",
        title="x",
        status="FAILED",
        progress=40,
        error_msg="任务已取消",
        error_code="project.cancelled",
        error_params=None,
        cover_url=None,
        final_video_url=None,
        pipeline_mode="full",
        created_at=now,
        updated_at=now,
    )
    out = AdminProjectOut.model_validate(project).model_dump()
    assert out["error_code"] == "project.cancelled"
    assert out["error_msg"] == "任务已取消"
    assert "error_params" in out


def test_admin_task_outputs_include_error_code_and_params():
    brief = AdminTaskBriefOut(
        id=1,
        domain="kepu",
        task_type="x",
        status="failed",
        error_message="余额不足",
        error_code="billing.insufficient_balance",
        error_params={"need_fen": 100, "available_fen": 5},
    )
    assert brief.model_dump()["error_params"] == {"need_fen": 100, "available_fen": 5}
    assert "error_code" in AdminTaskRunOut.model_fields
    assert "error_params" in TaskRunOut.model_fields


def test_admin_drama_detail_schemas_expose_errors():
    assert {"fragment_plan_error", "episode_optimize_error"} <= set(AdminDramaEpisodeDetailOut.model_fields)
    assert "generation_error" in AdminDramaAssetDetailOut.model_fields


# --- 集成：管理端详情接口带出落库错误（需要 PostgreSQL） ---


async def test_admin_drama_details_return_stored_errors(db_session):
    import uuid

    from app.api.admin.drama_assets import get_drama_asset
    from app.api.admin.drama_episodes import get_drama_episode
    from app.api.admin.drama_fragments import get_drama_fragment
    from app.api.admin.drama_projects import get_drama_project
    from app.models_drama import DramaAsset, DramaEpisode, DramaEpisodeFragment, DramaProject, DramaScript
    from app.models_tasks import TaskRun
    from tests.conftest import make_user

    admin = await make_user(db_session)
    admin.email = f"admin-{uuid.uuid4().hex[:8]}@example.com"
    admin.role = "admin"
    user = await make_user(db_session)
    user.email = f"user-{uuid.uuid4().hex[:8]}@example.com"
    await db_session.flush()

    project_params: dict = {"assets_seed_status": "failed"}
    set_seed_error(project_params, "抽取失败", code="drama.asset_extract_failed")
    project = DramaProject(user_id=user.id, title="P", params=project_params)
    db_session.add(project)
    await db_session.flush()

    script_params: dict = {"summary_status": "failed"}
    set_job_error_code(script_params, "summary_error", "drama.llm_empty_output")
    db_session.add(DramaScript(project_id=project.id, name="s", params=script_params))

    ep_params: dict = {"fragment_plan_status": "failed"}
    set_job_error_code(ep_params, "fragment_plan_error", "drama.episode_body_empty")
    episode = DramaEpisode(project_id=project.id, name="E1", params=ep_params)
    db_session.add(episode)
    await db_session.flush()

    gen_failed = {"generation": with_error_code({"status": "failed", "error": "超时"}, "drama.gen_timeout")}
    fragment = DramaEpisodeFragment(episode_id=episode.id, sort_order=1, content="x", params=gen_failed)
    asset = DramaAsset(project_id=project.id, type="character", name="Hero", params=gen_failed)
    db_session.add_all([fragment, asset])
    db_session.add(
        TaskRun(
            domain="drama",
            task_type="fragment_video",
            status="failed",
            requested_by=user.id,
            drama_project_id=project.id,
            error_code="drama.gen_timeout",
            error_message="超时",
            error_params={"k": 1},
        )
    )
    await db_session.commit()

    detail = await get_drama_project(project_id=project.id, _admin=admin, db=db_session)
    assert detail.summary_error and detail.summary_error.code == "drama.llm_empty_output"
    assert detail.assets_seed_error and detail.assets_seed_error.code == "drama.asset_extract_failed"
    assert detail.episode_content_error is None
    assert detail.episodes[0].fragment_plan_error.code == "drama.episode_body_empty"
    assert detail.assets[0].generation_error.code == "drama.gen_timeout"
    assert detail.recent_tasks[0].error_code == "drama.gen_timeout"
    assert detail.recent_tasks[0].error_params == {"k": 1}

    ep_detail = await get_drama_episode(episode_id=episode.id, _admin=admin, db=db_session)
    assert ep_detail.fragment_plan_error.code == "drama.episode_body_empty"
    assert ep_detail.episode_optimize_error is None
    assert ep_detail.fragments[0].generation_error.message == "超时"

    frag_detail = await get_drama_fragment(fragment_id=fragment.id, _admin=admin, db=db_session)
    assert frag_detail.generation_error.code == "drama.gen_timeout"
    asset_detail = await get_drama_asset(asset_id=asset.id, _admin=admin, db=db_session)
    assert asset_detail.generation_error.code == "drama.gen_timeout"
