---
feature: Plan races/checkpoints API
files_read:
  - auth.py
  - db.py
  - models.py
traced: 2026-08-13
stale: false
---


## What

Plan races/checkpoints API — traced from `tests/test_races_checkpoints_crud_api_in_plan_router__1100.py` through 3 source file(s).

## Entry Points

- `tests/test_races_checkpoints_crud_api_in_plan_router__1100.py` (tracing origin)

## Related Issues

- #1676 — [follow-up] Add committed regression test for auto_periodize in PUT /api/fuel/settings response
- #1666 — [follow-up] Orphaned plan-modal-type select is exposed to screen readers but wired to nothing

## Flowchart

```mermaid
flowchart LR
  auth_py[auth.py]
  db_py[db.py]
  models_py[models.py]
  users[(users)]
  weight_entries[(weight_entries)]
  weight_targets[(weight_targets)]
  habits[(habits)]
  habit_logs[(habit_logs)]
  workouts[(workouts)]
  workout_exercises[(workout_exercises)]
  workout_splits[(workout_splits)]
  daily_metrics[(daily_metrics)]
  fuel_settings[(fuel_settings)]
  fuel_entries[(fuel_entries)]
  personal_records[(personal_records)]
  strength_personal_records[(strength_personal_records)]
  strength_record_achievements[(strength_record_achievements)]
  strava_tokens[(strava_tokens)]
  google_oauth_credentials[(google_oauth_credentials)]
  drive_sleep_connections[(drive_sleep_connections)]
  stryd_credentials[(stryd_credentials)]
  strava_activities[(strava_activities)]
  daily_readiness[(daily_readiness)]
  stryd_activities[(stryd_activities)]
  removed_activities[(removed_activities)]
  workout_feel[(workout_feel)]
  sleep_imports[(sleep_imports)]
  app_config[(app_config)]
  workout_templates[(workout_templates)]
  user_preferences[(user_preferences)]
  training_load_snapshots[(training_load_snapshots)]
  sync_jobs[(sync_jobs)]
  worker_job_runs[(worker_job_runs)]
  job_queue[(job_queue)]
  activity_streams[(activity_streams)]
  races[(races)]
  race_checkpoints[(race_checkpoints)]
  race_calibrations[(race_calibrations)]
  race_predictions[(race_predictions)]
  athlete_duration_curves[(athlete_duration_curves)]
  sleep_records[(sleep_records)]
  training_plans[(training_plans)]
  planned_load[(planned_load)]
  strength_sessions[(strength_sessions)]
  plyo_sessions[(plyo_sessions)]
  economy_ceiling_snapshots[(economy_ceiling_snapshots)]
  user_banister_params[(user_banister_params)]
  summary_cache[(summary_cache)]
  planned_sessions[(planned_sessions)]
  exercise_catalog[(exercise_catalog)]
  injury_log[(injury_log)]
  llm_generations[(llm_generations)]
  verdict_history[(verdict_history)]
  body_measurements[(body_measurements)]
  performance_score_history[(performance_score_history)]
  run_form_metrics[(run_form_metrics)]
  prediction_snapshots[(prediction_snapshots)]
  muscle_load_daily[(muscle_load_daily)]
  gap_findings[(gap_findings)]
  performance_goals[(performance_goals)]
  decisions[(decisions)]
  calibration_sprints[(calibration_sprints)]
  weekly_coach_messages[(weekly_coach_messages)]
  daily_briefs[(daily_briefs)]
  plan_drafts[(plan_drafts)]
  training_preferences[(training_preferences)]
  preference_proposals[(preference_proposals)]
  user_custom_presets[(user_custom_presets)]
  plan_patterns[(plan_patterns)]
  plan_exercises[(plan_exercises)]
  preference_import_audits[(preference_import_audits)]
  auth_py --> db_py
  db_py --> models_py
  models_py --> users
  models_py --> weight_entries
  models_py --> weight_targets
  models_py --> habits
  models_py --> habit_logs
  models_py --> workouts
  models_py --> workout_exercises
  models_py --> workout_splits
  models_py --> daily_metrics
  models_py --> fuel_settings
  models_py --> fuel_entries
  models_py --> personal_records
  models_py --> strength_personal_records
  models_py --> strength_record_achievements
  models_py --> strava_tokens
  models_py --> google_oauth_credentials
  models_py --> drive_sleep_connections
  models_py --> stryd_credentials
  models_py --> strava_activities
  models_py --> daily_readiness
  models_py --> stryd_activities
  models_py --> removed_activities
  models_py --> workout_feel
  models_py --> sleep_imports
  models_py --> app_config
  models_py --> workout_templates
  models_py --> user_preferences
  models_py --> training_load_snapshots
  models_py --> sync_jobs
  models_py --> worker_job_runs
  models_py --> job_queue
  models_py --> activity_streams
  models_py --> races
  models_py --> race_checkpoints
  models_py --> race_calibrations
  models_py --> race_predictions
  models_py --> athlete_duration_curves
  models_py --> sleep_records
  models_py --> training_plans
  models_py --> planned_load
  models_py --> strength_sessions
  models_py --> plyo_sessions
  models_py --> economy_ceiling_snapshots
  models_py --> user_banister_params
  models_py --> summary_cache
  models_py --> planned_sessions
  models_py --> exercise_catalog
  models_py --> injury_log
  models_py --> llm_generations
  models_py --> verdict_history
  models_py --> body_measurements
  models_py --> performance_score_history
  models_py --> run_form_metrics
  models_py --> prediction_snapshots
  models_py --> muscle_load_daily
  models_py --> gap_findings
  models_py --> performance_goals
  models_py --> decisions
  models_py --> calibration_sprints
  models_py --> weekly_coach_messages
  models_py --> daily_briefs
  models_py --> plan_drafts
  models_py --> training_preferences
  models_py --> preference_proposals
  models_py --> user_custom_presets
  models_py --> plan_patterns
  models_py --> plan_exercises
  models_py --> preference_import_audits
```

## Key Files

- `auth.py` — traced during import walk
- `db.py` — traced during import walk
- `models.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `httpx` imported in `test_races_checkpoints_crud_api_in_plan_router__1100.py` but `httpx.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `pytest` imported in `test_races_checkpoints_crud_api_in_plan_router__1100.py` but `pytest.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `fastapi` imported in `auth.py` but `fastapi.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `sqlalchemy` imported in `db.py` but `sqlalchemy.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `dotenv` imported in `db.py` but `dotenv.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `sqlalchemy` imported in `models.py` but `sqlalchemy.py` not found in source — handler unresolved -->
