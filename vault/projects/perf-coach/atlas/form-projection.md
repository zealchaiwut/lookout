---
feature: Form projection
files_read:
  - training_load.py
  - db.py
  - models.py
  - acwr.py
  - time.py
traced: 2026-08-13
stale: false
---


## What

Form projection — traced from `tests/test_add_forward_form_projection_to_target_date__710.py` through 5 source file(s).

## Entry Points

- `tests/test_add_forward_form_projection_to_target_date__710.py` (tracing origin)

## Related Issues

- #1672 — [follow-up] Log instead of silently swallowing malformed sets_json in get_strength_tss_per_set_for_workout
- #1545 — [follow-up] Remove out-of-sprint test file test_race_time_projection__1503.py

## Flowchart

```mermaid
flowchart LR
  training_load_py[training_load.py]
  db_py[db.py]
  models_py[models.py]
  acwr_py[acwr.py]
  time_py[time.py]
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
  training_load_py --> db_py
  db_py --> models_py
  models_py --> acwr_py
  acwr_py --> time_py
  time_py --> users
  time_py --> weight_entries
  time_py --> weight_targets
  time_py --> habits
  time_py --> habit_logs
  time_py --> workouts
  time_py --> workout_exercises
  time_py --> workout_splits
  time_py --> daily_metrics
  time_py --> fuel_settings
  time_py --> fuel_entries
  time_py --> personal_records
  time_py --> strength_personal_records
  time_py --> strength_record_achievements
  time_py --> strava_tokens
  time_py --> google_oauth_credentials
  time_py --> drive_sleep_connections
  time_py --> stryd_credentials
  time_py --> strava_activities
  time_py --> daily_readiness
  time_py --> stryd_activities
  time_py --> removed_activities
  time_py --> workout_feel
  time_py --> sleep_imports
  time_py --> app_config
  time_py --> workout_templates
  time_py --> user_preferences
  time_py --> training_load_snapshots
  time_py --> sync_jobs
  time_py --> worker_job_runs
  time_py --> job_queue
  time_py --> activity_streams
  time_py --> races
  time_py --> race_checkpoints
  time_py --> race_calibrations
  time_py --> race_predictions
  time_py --> athlete_duration_curves
  time_py --> sleep_records
  time_py --> training_plans
  time_py --> planned_load
  time_py --> strength_sessions
  time_py --> plyo_sessions
  time_py --> economy_ceiling_snapshots
  time_py --> user_banister_params
  time_py --> summary_cache
  time_py --> planned_sessions
  time_py --> exercise_catalog
  time_py --> injury_log
  time_py --> llm_generations
  time_py --> verdict_history
  time_py --> body_measurements
  time_py --> performance_score_history
  time_py --> run_form_metrics
  time_py --> prediction_snapshots
  time_py --> muscle_load_daily
  time_py --> gap_findings
  time_py --> performance_goals
  time_py --> decisions
  time_py --> calibration_sprints
  time_py --> weekly_coach_messages
  time_py --> daily_briefs
  time_py --> plan_drafts
  time_py --> training_preferences
  time_py --> preference_proposals
  time_py --> user_custom_presets
  time_py --> plan_patterns
  time_py --> plan_exercises
  time_py --> preference_import_audits
```

## Key Files

- `training_load.py` — traced during import walk
- `db.py` — traced during import walk
- `models.py` — traced during import walk
- `acwr.py` — traced during import walk
- `time.py` — traced during import walk


## Open Questions

<!-- OPEN QUESTION: `pytest` imported in `test_add_forward_form_projection_to_target_date__710.py` but `pytest.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `sqlalchemy` imported in `training_load.py` but `sqlalchemy.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `sqlalchemy` imported in `db.py` but `sqlalchemy.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `dotenv` imported in `db.py` but `dotenv.py` not found in source — handler unresolved -->
<!-- OPEN QUESTION: `sqlalchemy` imported in `models.py` but `sqlalchemy.py` not found in source — handler unresolved -->
