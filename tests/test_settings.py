from __future__ import annotations


def test_get_settings_reads_repo_env_even_if_cwd_changes(tmp_path, monkeypatch):
    import config.settings as settings_module

    env_path = tmp_path / ".env"
    env_path.write_text("ALPHA_VANTAGE_API_KEY=test-from-env\n", encoding="utf-8")

    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(other_dir)

    monkeypatch.setattr(settings_module, "_ENV_FILE", env_path)
    settings_module._load_settings.cache_clear()
    try:
        cfg = settings_module.get_settings()
        assert cfg.alpha_vantage_api_key == "test-from-env"
    finally:
        settings_module._load_settings.cache_clear()
