# Investigation: Missing fields in `org.ran.task` analytics event

## Problem Summary
Intermittently, the `org.ran.task` analytics event is emitted without the `task.organization_slug` and `task.id` properties. These fields are critical for downstream analytics and should never be `None`.

## Event Location
The event is triggered when storing a run in `RunsService.store_task_run_fn`:

```python
analytics_handler(lambda: RanTaskEventProperties.from_task_run(stored, trigger))
```

## Property Derivation
- `TaskProperties.build` constructs the task properties based on request path parameters and tenant data. When available, these properties are stored in the `AnalyticsService` dependency.
- For typical API routes exposing `task_id` and `task_schema_id` in the URL, the `analytics_task_properties` FastAPI dependency sets these values correctly.

## Failure Point
The `/v1/chat/completions` proxy endpoint does not include `task_id` or `task_schema_id` in its path. Consequently, the `analytics_task_properties` dependency returns `None` during `AnalyticsService` creation. Although the proxy later updates the event router with the proper task information, `RunsService` continues to use the initial `AnalyticsService` instance that lacks task properties. As a result, the `org.ran.task` event is emitted with missing `task.organization_slug` and `task.id`.

## Why only some events are affected
All API routes except the proxy expose `task_id` and `task_schema_id` in the request path. When these parameters are present, `analytics_task_properties` populates the task properties before the `AnalyticsService` is instantiated. These standard routes therefore emit analytics events with the correct fields.

Only calls hitting the OpenAI proxy omit these identifiers. When the proxy handles a request, it first creates the `AnalyticsService` without knowing the task, leading to missing fields. The event router is later updated once the proxy has located the task variant, but the already-instantiated analytics service is not updated. This mismatch explains the intermittent nature of the bug: events created through traditional endpoints are correct, while those triggered by the proxy can lack the task details.

---
This document captures the root cause for missing task data in analytics events and can be referenced when implementing the fix.
