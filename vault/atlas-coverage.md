# Atlas Coverage

Which atlas features have a traced diagram, and what blocks the rest.

A feature is traceable when the target repository has a test or source file named after it — see [[agents]] for who owns what. Blocked features are not a lookout defect: the unlock is a file in the target repo, named below.

## Summary

| Project | Traced | Blocked | Total | Coverage |
|---|---|---|---|---|
| asset-studio | 2 | 26 | 28 | 7% |
| commander | 6 | 32 | 38 | 16% |
| crux | 0 | 0 | 0 | — |
| perf-coach | 18 | 101 | 119 | 15% |
| viral-radar | 0 | 0 | 0 | — |
| **Fleet** | **26** | **159** | **185** | **14%** |

## Blocked features

Each row names what would give tracing a way in. Most need a feature-named test; a few already have one that imports nothing local and so cannot be followed.

### asset-studio

| Feature | Why | What would unlock it |
|---|---|---|
| AI Outline Generation | no entry point | add `tests/test_ai_outline_generation.py` |
| Batch Flow | no entry point | add `tests/test_batch_flow.py` |
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
| Template Pack v1 | no entry point | add `tests/test_template_pack_v1.py` |
| Text-to-Image Slide Backgrounds | no entry point | add `tests/test_text_to_image_slide_backgrounds.py` |
| Thai Brand Fonts | no entry point | add `tests/test_thai_brand_fonts.py` |

### commander

| Feature | Why | What would unlock it |
|---|---|---|
| Activity log linking | no entry point | add `tests/test_activity_log_linking.py` |
| Analytics tab | no entry point | add `tests/test_analytics_tab.py` |
| API | no entry point | add `tests/test_api.py` |
| Calibration cache | no entry point | add `tests/test_calibration_cache.py` |
| Concurrent multi-coder dispatch | no entry point | add `tests/test_concurrent_multi_coder_dispatch.py` |
| Cost tab | no entry point | add `tests/test_cost_tab.py` |
| Cross-run log search | no entry point | add `tests/test_cross_run_log_search.py` |
| Daily Brief | no entry point | add `tests/test_daily_brief.py` |
| Dashboard | no entry point | add `tests/test_dashboard.py` |
| Deploy tab | no entry point | add `tests/test_deploy_tab.py` |
| Editable env paths | no entry point | add `tests/test_editable_env_paths.py` |
| Env-var editor | no entry point | add `tests/test_env_var_editor.py` |
| Global Settings screen | no entry point | add `tests/test_global_settings_screen.py` |
| Hung agent redispatch | no entry point | add `tests/test_hung_agent_redispatch.py` |
| Impeccable design wiring | no entry point | add `tests/test_impeccable_design_wiring.py` |
| Live Browser UAT | no entry point | add `tests/test_live_browser_uat.py` |
| LLM provider toggle | no entry point | add `tests/test_llm_provider_toggle.py` |
| Logs-tab ticket strip | no entry point | add `tests/test_logs_tab_ticket_strip.py` |
| Nightly Hermes dev-report exporter | no entry point | add `tests/test_nightly_hermes_dev_report_exporter.py` |
| Per-area AGENTS.md | no entry point | add `tests/test_per_area_agents_md.py` |
| Per-role provider routing | no entry point | add `tests/test_per_role_provider_routing.py` |
| Pipeline mode | no entry point | add `tests/test_pipeline_mode.py` |
| Project events log | no entry point | add `tests/test_project_events_log.py` |
| Project Settings tab | no entry point | add `tests/test_project_settings_tab.py` |
| Project To-Dos | no entry point | add `tests/test_project_to_dos.py` |
| Run Browser | no entry point | add `tests/test_run_browser.py` |
| Sprint file archive | no entry point | add `tests/test_sprint_file_archive.py` |
| Sprint Manager | entry imports nothing local | make `services/sprint_manager/sprint_manager.py` import the modules it exercises |
| Sprint Workspace | no entry point | add `tests/test_sprint_workspace.py` |
| Structured Logging | no entry point | add `tests/test_structured_logging.py` |
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
| Body measurements | no entry point | add `tests/test_body_measurements.py` |
| Body-modifier guardrail | no entry point | add `tests/test_body_modifier_guardrail.py` |
| Calibration status surface | no entry point | add `tests/test_calibration_status_surface.py` |
| Coach export — paste-to-Claude loop | no entry point | add `tests/test_coach_export_paste_to_claude_loop.py` |
| Coach plan — race goal, projection, weekly message & Home card | no entry point | add `tests/test_coach_plan_race_goal_projection_weekly_message_home_card.py` |
| CTL/ATL calibration loop closed | no entry point | add `tests/test_ctl_atl_calibration_loop_closed.py` |
| Daily wellness metrics | no entry point | add `tests/test_daily_wellness_metrics.py` |
| Deterministic coach plan | no entry point | add `tests/test_deterministic_coach_plan.py` |
| Duration curves | no entry point | add `tests/test_duration_curves.py` |
| Economy backfill | no entry point | add `tests/test_economy_backfill.py` |
| Economy ceiling bonus in projection | no entry point | add `tests/test_economy_ceiling_bonus_in_projection.py` |
| Economy contribution in projection | no entry point | add `tests/test_economy_contribution_in_projection.py` |
| Economy stimulus model | no entry point | add `tests/test_economy_stimulus_model.py` |
| Endurance aborted-session guard | no entry point | add `tests/test_endurance_aborted_session_guard.py` |
| Endurance training-run recalibration | no entry point | add `tests/test_endurance_training_run_recalibration.py` |
| Fit-data collector with minimum-data gate | no entry point | add `tests/test_fit_data_collector_with_minimum_data_gate.py` |
| Fitness / fatigue / form model | entry imports nothing local | make `tests/test_fitness_fatigue_form_model__698.py` import the modules it exercises |
| Fitness projection engine | no entry point | add `tests/test_fitness_projection_engine.py` |
| Form projection | no entry point | add `tests/test_form_projection.py` |
| Gap analyzer | no entry point | add `tests/test_gap_analyzer.py` |
| Gap-finding coaching layer | no entry point | add `tests/test_gap_finding_coaching_layer.py` |
| Google Drive / Health Sync sleep import | no entry point | add `tests/test_google_drive_health_sync_sleep_import.py` |
| Habit adherence analytics | no entry point | add `tests/test_habit_adherence_analytics.py` |
| Habit tracking | no entry point | add `tests/test_habit_tracking.py` |
| Habits streaks | no entry point | add `tests/test_habits_streaks.py` |
| Habits Training / General sections | no entry point | add `tests/test_habits_training_general_sections.py` |
| Health check | no entry point | add `tests/test_health_check.py` |
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
| Per-run speed signal | no entry point | add `tests/test_per_run_speed_signal.py` |
| Per-user Banister parameter storage | no entry point | add `tests/test_per_user_banister_parameter_storage.py` |
| Performance curve | no entry point | add `tests/test_performance_curve.py` |
| Performance trends | no entry point | add `tests/test_performance_trends.py` |
| Periodic model refit with versioning & rollback | no entry point | add `tests/test_periodic_model_refit_with_versioning_rollback.py` |
| Persisted lap intensity bands | no entry point | add `tests/test_persisted_lap_intensity_bands.py` |
| Persisted performance score history + honest block deltas | no entry point | add `tests/test_persisted_performance_score_history_honest_block_deltas.py` |
| Plan projection endpoint | no entry point | add `tests/test_plan_projection_endpoint.py` |
| Plan races/checkpoints API | no entry point | add `tests/test_plan_races_checkpoints_api.py` |
| Planned-load schedule generation | no entry point | add `tests/test_planned_load_schedule_generation.py` |
| Polarized-split check | no entry point | add `tests/test_polarized_split_check.py` |
| Post-race confidence band tightening | no entry point | add `tests/test_post_race_confidence_band_tightening.py` |
| Power-to-weight trend | no entry point | add `tests/test_power_to_weight_trend.py` |
| Prediction snapshots | entry imports nothing local | make `tests/test_prediction_snapshots__1362.py` import the modules it exercises |
| Projection screen | no entry point | add `tests/test_projection_screen.py` |
| Race checkpoints | no entry point | add `tests/test_race_checkpoints.py` |
| Race readiness | no entry point | add `tests/test_race_readiness.py` |
| Race targets | no entry point | add `tests/test_race_targets.py` |
| Rate guardrail | no entry point | add `tests/test_rate_guardrail.py` |
| Rolling intensity distribution | no entry point | add `tests/test_rolling_intensity_distribution.py` |
| Run Builder | no entry point | add `tests/test_run_builder.py` |
| Run form metrics | no entry point | add `tests/test_run_form_metrics.py` |
| Run View | no entry point | add `tests/test_run_view.py` |
| Running performance scores | no entry point | add `tests/test_running_performance_scores.py` |
| Score-ceiling recalibration from B-race result | no entry point | add `tests/test_score_ceiling_recalibration_from_b_race_result.py` |
| Session intensity zones | no entry point | add `tests/test_session_intensity_zones.py` |
| Session profile detection | no entry point | add `tests/test_session_profile_detection.py` |
| Session signal panel | no entry point | add `tests/test_session_signal_panel.py` |
| Settings — Zones section | no entry point | add `tests/test_settings_zones_section.py` |
| Signal backfill | no entry point | add `tests/test_signal_backfill.py` |
| Sparse speed-signal density detection | no entry point | add `tests/test_sparse_speed_signal_density_detection.py` |
| Speed PR detection | no entry point | add `tests/test_speed_pr_detection.py` |
| Strength & plyo session logging | no entry point | add `tests/test_strength_plyo_session_logging.py` |
| Strength PR storage | no entry point | add `tests/test_strength_pr_storage.py` |
| Strength View | no entry point | add `tests/test_strength_view.py` |
| Structural dose stats | no entry point | add `tests/test_structural_dose_stats.py` |
| Stryd integration | no entry point | add `tests/test_stryd_integration.py` |
| Summary digest card | entry imports nothing local | make `tests/test_summary_digest_card__1058.py` import the modules it exercises |
| Today recommendation | entry imports nothing local | make `tests/test_today_recommendation__1352.py` import the modules it exercises |
| Training log | entry imports nothing local | make `tests/test_training_log.py` import the modules it exercises |
| Training > Performance sub-tab | no entry point | add `tests/test_training_performance_sub_tab.py` |
| Training plan model | no entry point | add `tests/test_training_plan_model.py` |
| Training Plan sub-tab | no entry point | add `tests/test_training_plan_sub_tab.py` |
| Treadmill incline → NGP normalization | no entry point | add `tests/test_treadmill_incline_ngp_normalization.py` |
| Tunable economy priors | no entry point | add `tests/test_tunable_economy_priors.py` |
| Unified daily training load series | no entry point | add `tests/test_unified_daily_training_load_series.py` |
| Unified readiness + auto-recompute | no entry point | add `tests/test_unified_readiness_auto_recompute.py` |
| Verdict history | no entry point | add `tests/test_verdict_history.py` |
| Verdict v2 — readiness & injuries modulate the verdict | no entry point | add `tests/test_verdict_v2_readiness_injuries_modulate_the_verdict.py` |
| Weekly athlete summary | no entry point | add `tests/test_weekly_athlete_summary.py` |
| Weekly habits widget | no entry point | add `tests/test_weekly_habits_widget.py` |
| Weight-trend rate with a confidence interval | no entry point | add `tests/test_weight_trend_rate_with_a_confidence_interval.py` |
| Zone 2 tracking | no entry point | add `tests/test_zone_2_tracking.py` |

