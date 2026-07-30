# Settings Registry

Application settings are stored in the `application_settings` table rather than
being hard-coded throughout the application.

The registry provides a single source of truth for configurable values while
allowing administrators to change application behaviour without modifying code.

---

## Principles

- Every setting has a unique key.
- Every setting stores its value as text.
- The application converts values into the correct type when reading them.
- Settings are never referenced using hard-coded strings.
- New settings should be added to:
  - `app/core/constants.py`
  - `scripts/seed_settings.py`
  - this document

---

## Value Types

The following value types are currently supported.

| Type | Description | Example |
|------|-------------|---------|
| `string` | Plain text | `Billson's Tasks` |
| `integer` | Whole number | `30` |
| `boolean` | True/False value | `true` |
| `timezone` | IANA timezone identifier | `Europe/London` |

---

# Registry

## application_name

| Property | Value |
|----------|-------|
| Key | `application_name` |
| Type | `string` |
| Public | Yes |
| Default | `Billson's Tasks` |

Displayed throughout the user interface.

---

## default_timezone

| Property | Value |
|----------|-------|
| Key | `default_timezone` |
| Type | `timezone` |
| Public | Yes |
| Default | `Europe/London` |

Used for:

- displaying dates and times
- interpreting deadlines
- formatting audit timestamps

Internally, all timestamps remain stored in UTC.

---

# Adding a New Setting

When introducing a new application setting:

1. Add the key to `SettingKey` in `app/core/constants.py`.
2. Add the default value to `APPLICATION_SETTINGS`.
3. Add the setting to `SettingService.seed_registry()`.
4. Document the setting in this file.
5. Use `SettingService` when reading the value.

Do **not** reference settings using literal strings throughout the codebase.

---

# Changing Default Values

Changing a default value in the registry does **not** update existing
installations.

The seed process only creates missing settings.

Existing administrator-configured values are always preserved.

---

# Administrator Settings

Version 1 currently exposes the following configurable settings:

| Setting | Description |
|----------|-------------|
| Application Name | Display name shown throughout the application |
| Default Timezone | Default timezone used for displaying dates and times |

Additional settings will be added in future versions as new features are
introduced.