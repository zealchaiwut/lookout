# Atlas Coverage

Which atlas features have a traced diagram, and what blocks the rest.

A feature is traceable when the target repository has a test or source file named after it — see [[agents]] for who owns what. Blocked features are not a lookout defect: the unlock is a file in the target repo, named below.

## Summary

| Project | Traced | Blocked | Total | Coverage |
|---|---|---|---|---|
| asset-studio | 2 | 26 | 28 | 7% |
| commander | 8 | 30 | 38 | 21% |
| crux | 0 | 0 | 0 | — |
| perf-coach | 34 | 85 | 119 | 29% |
| viral-radar | 11 | 12 | 23 | 48% |
| **Fleet** | **55** | **153** | **208** | **26%** |

## Blocked features

Each row names what would give tracing a way in. Most need a feature-named test; a few already have one that imports nothing local and so cannot be followed.

### asset-studio

| Feature | Why | What would unlock it |
|---|---|---|
| AI Outline Generation | entry imports nothing local | make `tests/test_carousel_outline_generation__2.py` import the modules it exercises |
| Batch Flow | entry imports nothing local | make `tests/test_batch_flow_multi_image__46.py` import the modules it exercises |
| Brand Settings | no entry point | add `tests/test_brand_settings.py` |
| Caption + Hashtags Generation | no entry point | add `tests/test_caption_hashtags_generation.py` |
| Carousel Builder | no entry point | add `tests/test_carousel_builder.py` |
| Carousel Builder Flow v2 | no entry point | add `tests/test_carousel_builder_flow_v2.py` |
| Character Action Generation | no entry point | add `tests/test_character_action_generation.py` |
| Character Cutout Library | no entry point | add `tests/test_character_cutout_library.py` |
| Character Picker | entry imports nothing local | make `tests/test_character_picker__90.py` import the modules it exercises |
| Consistency Lock | entry imports nothing local | make `tests/test_consistency_lock__48.py` import the modules it exercises |
| Content Queue | entry imports nothing local | make `tests/test_content_queue__101.py` import the modules it exercises |
| Export to Dated Folder | no entry point | add `tests/test_export_to_dated_folder.py` |
| HTML Template Render Engine | no entry point | add `tests/test_html_template_render_engine.py` |
| Import → Draft Engine | no entry point | add `tests/test_import_draft_engine.py` |
| Job Persistence & 9:16 Export | no entry point | add `tests/test_job_persistence_9_16_export.py` |
| Legacy Carousel Removal | no entry point | add `tests/test_legacy_carousel_removal.py` |
| Multi-Ratio Rendering | no entry point | add `tests/test_multi_ratio_rendering.py` |
| Per-Account Asset Tree | no entry point | add `tests/test_per_account_asset_tree.py` |
| Per-Slide Text & Carousel Arc | no entry point | add `tests/test_per_slide_text_carousel_arc.py` |
| Single-Image Post Mode | no entry point | add `tests/test_single_image_post_mode.py` |
| Slide Compositing | entry imports nothing local | make `tests/test_slide_compositing__uat__3.py` import the modules it exercises |
| Slide Text Editing | no entry point | add `tests/test_slide_text_editing.py` |
| Stat / Data Layout with Chart Slot | no entry point | add `tests/test_stat_data_layout_with_chart_slot.py` |
| Template Pack v1 | entry imports nothing local | make `tests/test_template_pack__87.py` import the modules it exercises |
| Text-to-Image Slide Backgrounds | no entry point | add `tests/test_text_to_image_slide_backgrounds.py` |
| Thai Brand Fonts | entry imports nothing local | make `tests/test_bundle_thai_brand_fonts__85.py` import the modules it exercises |

### commander

| Feature | Why | What would unlock it |
|---|---|---|
| Activity log linking | no entry point | add `tests/test_activity_log_linking.py` |
| Analytics tab | entry imports nothing local | make `tests/test_1066__analytics_redesign.py` import the modules it exercises |
| API | no entry point | add `tests/test_api.py` |
| Calibration cache | entry imports nothing local | make `tests/test_1332__rebuild_calibration_cache.py` import the modules it exercises |
| Concurrent multi-coder dispatch | no entry point | add `tests/test_concurrent_multi_coder_dispatch.py` |
| Cost tab | entry imports nothing local | make `tests/test_689__replace_bare_except_token_cost.py` import the modules it exercises |
| Cross-run log search | no entry point | add `tests/test_cross_run_log_search.py` |
| Daily Brief | entry imports nothing local | make `tests/test_2257__delete_brief_caching_daily_report.py` import the modules it exercises |
| Dashboard | entry imports nothing local | make `tests/test_629__instrument_dashboard_routes_events.py` import the modules it exercises |
| Editable env paths | entry imports nothing local | make `tests/test_643__editable_env_paths.py` import the modules it exercises |
| Env-var editor | entry imports nothing local | make `tests/test_727__env_var_editor.py` import the modules it exercises |
| Global Settings screen | entry imports nothing local | make `tests/test_641__global_settings_screen.py` import the modules it exercises |
| Hung agent redispatch | no entry point | add `tests/test_hung_agent_redispatch.py` |
| Impeccable design wiring | no entry point | add `tests/test_impeccable_design_wiring.py` |
| Live Browser UAT | no entry point | add `tests/test_live_browser_uat.py` |
| LLM provider toggle | entry imports nothing local | make `tests/test_1667__llm_provider_toggle.py` import the modules it exercises |
| Logs-tab ticket strip | no entry point | add `tests/test_logs_tab_ticket_strip.py` |
| Nightly Hermes dev-report exporter | no entry point | add `tests/test_nightly_hermes_dev_report_exporter.py` |
| Per-area AGENTS.md | no entry point | add `tests/test_per_area_agents_md.py` |
| Per-role provider routing | no entry point | add `tests/test_per_role_provider_routing.py` |
| Project events log | no entry point | add `tests/test_project_events_log.py` |
| Project Settings tab | entry imports nothing local | make `tests/test_642__project_settings_tab.py` import the modules it exercises |
| Project To-Dos | no entry point | add `tests/test_project_to_dos.py` |
| Run Browser | entry imports nothing local | make `tests/test_783__run_browser.py` import the modules it exercises |
| Sprint file archive | no entry point | add `tests/test_sprint_file_archive.py` |
| Sprint Manager | entry imports nothing local | make `tests/test_sprint_manager_dual_write.py` import the modules it exercises |
| Sprint Workspace | no entry point | add `tests/test_sprint_workspace.py` |
| Structured Logging | entry imports nothing local | make `tests/test_unify_structured_logging__784.py` import the modules it exercises |
| Unified structured logging | no entry point | add `tests/test_unified_structured_logging.py` |
| Worktree freshness | no entry point | add `tests/test_worktree_freshness.py` |

### perf-coach

| Feature | Why | What would unlock it |
|---|---|---|
| ACWR training-load guidance | no entry point | add `tests/test_acwr_training_load_guidance.py` |
| Auto-threshold suggestions | no entry point | add `tests/test_auto_threshold_suggestions.py` |
| Banister held-out MSE validation | no entry point | add `tests/test_banister_held_out_mse_validation.py` |
| Banister parameter fitting | no entry point | add `tests/test_banister_parameter_fitting.py` |
| Body-composition modifier | no entry point | add `tests/test_body_composition_modifier.py` |
| Calibration status surface | entry imports nothing local | make `tests/test_surface_calibration_status__1165.py` import the modules it exercises |
| Coach export — paste-to-Claude loop | no entry point | add `tests/test_coach_export_paste_to_claude_loop.py` |
| Coach plan — race goal, projection, weekly message & Home card | no entry point | add `tests/test_coach_plan_race_goal_projection_weekly_message_home_card.py` |
| CTL/ATL calibration loop closed | no entry point | add `tests/test_ctl_atl_calibration_loop_closed.py` |
| Daily wellness metrics | no entry point | add `tests/test_daily_wellness_metrics.py` |
| Deterministic coach plan | no entry point | add `tests/test_deterministic_coach_plan.py` |
| Duration curves | entry imports nothing local | make `tests/test_athlete_best_effort_duration_curves__695.py` import the modules it exercises |
| Economy backfill | entry imports nothing local | make `tests/test_backfill_economy__1149.py` import the modules it exercises |
| Economy ceiling bonus in projection | no entry point | add `tests/test_economy_ceiling_bonus_in_projection.py` |
| Economy stimulus model | no entry point | add `tests/test_economy_stimulus_model.py` |
| Endurance aborted-session guard | no entry point | add `tests/test_endurance_aborted_session_guard.py` |
| Endurance training-run recalibration | no entry point | add `tests/test_endurance_training_run_recalibration.py` |
| Fit-data collector with minimum-data gate | no entry point | add `tests/test_fit_data_collector_with_minimum_data_gate.py` |
| Fitness / fatigue / form model | entry imports nothing local | make `tests/test_fitness_fatigue_form_model__698.py` import the modules it exercises |
| Fitness projection engine | no entry point | add `tests/test_fitness_projection_engine.py` |
| Gap-finding coaching layer | no entry point | add `tests/test_gap_finding_coaching_layer.py` |
| Google Drive / Health Sync sleep import | no entry point | add `tests/test_google_drive_health_sync_sleep_import.py` |
| Habit adherence analytics | no entry point | add `tests/test_habit_adherence_analytics.py` |
| Habit tracking | entry imports nothing local | make `tests/test_document_habit_tracking_type_immutability__470.py` import the modules it exercises |
| Habits streaks | no entry point | add `tests/test_habits_streaks.py` |
| Habits Training / General sections | no entry point | add `tests/test_habits_training_general_sections.py` |
| Health check | entry imports nothing local | make `tests/test_health_check_env_metadata__156.py` import the modules it exercises |
| Heat & humidity normalization | no entry point | add `tests/test_heat_humidity_normalization.py` |
| Intensity-distribution chart | no entry point | add `tests/test_intensity_distribution_chart.py` |
| Lagged ceiling lift | no entry point | add `tests/test_lagged_ceiling_lift.py` |
| Lean program — Phase 0, the persistent consult loop | no entry point | add `tests/test_lean_program_phase_0_the_persistent_consult_loop.py` |
| Lean program — Phase 1, the daily floor | no entry point | add `tests/test_lean_program_phase_1_the_daily_floor.py` |
| Lean program — Phase 2, structural deficit + guardrails | no entry point | add `tests/test_lean_program_phase_2_structural_deficit_guardrails.py` |
| Lean program — Phase 3, habits and week composition | no entry point | add `tests/test_lean_program_phase_3_habits_and_week_composition.py` |
| Lean program — Phase 4, calibration sprints and the weight hypothesis | no entry point | add `tests/test_lean_program_phase_4_calibration_sprints_and_the_weight_hypothesis.py` |
| LLM coaching layer | no entry point | add `tests/test_llm_coaching_layer.py` |
| Mobile-first daily flow | no entry point | add `tests/test_mobile_first_daily_flow.py` |
| Monthly athlete summary with supercompensation detection | no entry point | add `tests/test_monthly_athlete_summary_with_supercompensation_detection.py` |
| Multi-user | no entry point | add `tests/test_multi_user.py` |
| Muscle balance view & planning guard | no entry point | add `tests/test_muscle_balance_view_planning_guard.py` |
| Muscle-load ledger | no entry point | add `tests/test_muscle_load_ledger.py` |
| Peak tracking | entry imports nothing local | make `tests/test_peak_tracking__609.py` import the modules it exercises |
| Per-run endurance signal | no entry point | add `tests/test_per_run_endurance_signal.py` |
| Per-run speed signal | entry imports nothing local | make `tests/test_compute_store_speed_signal_per_run__1048.py` import the modules it exercises |
| Per-user Banister parameter storage | no entry point | add `tests/test_per_user_banister_parameter_storage.py` |
| Performance trends | no entry point | add `tests/test_performance_trends.py` |
| Periodic model refit with versioning & rollback | no entry point | add `tests/test_periodic_model_refit_with_versioning_rollback.py` |
| Persisted lap intensity bands | no entry point | add `tests/test_persisted_lap_intensity_bands.py` |
| Persisted performance score history + honest block deltas | no entry point | add `tests/test_persisted_performance_score_history_honest_block_deltas.py` |
| Plan projection endpoint | no entry point | add `tests/test_plan_projection_endpoint.py` |
| Planned-load schedule generation | no entry point | add `tests/test_planned_load_schedule_generation.py` |
| Polarized-split check | no entry point | add `tests/test_polarized_split_check.py` |
| Post-race confidence band tightening | no entry point | add `tests/test_post_race_confidence_band_tightening.py` |
| Power-to-weight trend | no entry point | add `tests/test_power_to_weight_trend.py` |
| Prediction snapshots | entry imports nothing local | make `tests/test_prediction_snapshots__1362.py` import the modules it exercises |
| Projection screen | entry imports nothing local | make `tests/test_projection_screen_assembly__1114.py` import the modules it exercises |
| Race readiness | entry imports nothing local | make `tests/test_race_readiness_combined_endpoint__611.py` import the modules it exercises |
| Rate guardrail | no entry point | add `tests/test_rate_guardrail.py` |
| Rolling intensity distribution | no entry point | add `tests/test_rolling_intensity_distribution.py` |
| Running performance scores | no entry point | add `tests/test_running_performance_scores.py` |
| Score-ceiling recalibration from B-race result | no entry point | add `tests/test_score_ceiling_recalibration_from_b_race_result.py` |
| Session intensity zones | no entry point | add `tests/test_session_intensity_zones.py` |
| Settings — Zones section | no entry point | add `tests/test_settings_zones_section.py` |
| Signal backfill | no entry point | add `tests/test_signal_backfill.py` |
| Sparse speed-signal density detection | no entry point | add `tests/test_sparse_speed_signal_density_detection.py` |
| Speed PR detection | no entry point | add `tests/test_speed_pr_detection.py` |
| Strength & plyo session logging | no entry point | add `tests/test_strength_plyo_session_logging.py` |
| Strength PR storage | no entry point | add `tests/test_strength_pr_storage.py` |
| Structural dose stats | no entry point | add `tests/test_structural_dose_stats.py` |
| Stryd integration | no entry point | add `tests/test_stryd_integration.py` |
| Summary digest card | entry imports nothing local | make `tests/test_summary_digest_card__1058.py` import the modules it exercises |
| Today recommendation | entry imports nothing local | make `tests/test_today_recommendation__1352.py` import the modules it exercises |
| Training log | entry imports nothing local | make `tests/test_training_log.py` import the modules it exercises |
| Training > Performance sub-tab | entry imports nothing local | make `tests/test_add_log_plan_performance_sub_tabs_to_training_page__636.py` import the modules it exercises |
| Training plan model | no entry point | add `tests/test_training_plan_model.py` |
| Training Plan sub-tab | entry imports nothing local | make `tests/test_add_log_plan_performance_sub_tabs_to_training_page__636.py` import the modules it exercises |
| Treadmill incline → NGP normalization | no entry point | add `tests/test_treadmill_incline_ngp_normalization.py` |
| Tunable economy priors | no entry point | add `tests/test_tunable_economy_priors.py` |
| Unified daily training load series | no entry point | add `tests/test_unified_daily_training_load_series.py` |
| Unified readiness + auto-recompute | no entry point | add `tests/test_unified_readiness_auto_recompute.py` |
| Verdict v2 — readiness & injuries modulate the verdict | no entry point | add `tests/test_verdict_v2_readiness_injuries_modulate_the_verdict.py` |
| Weekly athlete summary | no entry point | add `tests/test_weekly_athlete_summary.py` |
| Weekly habits widget | entry imports nothing local | make `tests/test_weekly_habits_progress_widget__391.py` import the modules it exercises |
| Weight-trend rate with a confidence interval | no entry point | add `tests/test_weight_trend_rate_with_a_confidence_interval.py` |
| Zone 2 tracking | no entry point | add `tests/test_zone_2_tracking.py` |

### viral-radar

| Feature | Why | What would unlock it |
|---|---|---|
| AI "why" layer | no entry point | add `tests/test_ai_why_layer.py` |
| Apify collector | no entry point | add `tests/test_apify_collector.py` |
| Core engine (multi-account, paste-fed) | no entry point | add `tests/test_core_engine_multi_account_paste_fed.py` |
| Discovery | entry imports nothing local | make `tests/test_discovery_queries_antimodel__b1b3.py` import the modules it exercises |
| Find the wave | no entry point | add `tests/test_find_the_wave.py` |
| Protect the voice | no entry point | add `tests/test_protect_the_voice.py` |
| Prove the recipe | no entry point | add `tests/test_prove_the_recipe.py` |
| Quarantine | no entry point | add `tests/test_quarantine.py` |
| Recipe card | no entry point | add `tests/test_recipe_card.py` |
| Self-analysis | no entry point | add `tests/test_self_analysis.py` |
| Tiers | no entry point | add `tests/test_tiers.py` |
| watchlist-analyzer | entry imports nothing local | make `tests/test_watchlist_analyzer__6.py` import the modules it exercises |

