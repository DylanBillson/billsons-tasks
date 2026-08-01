from enum import StrEnum


class GlobalRole(StrEnum):
    ADMINISTRATOR = "administrator"
    USER = "user"


class CompanyRole(StrEnum):
    MANAGER = "manager"
    EMPLOYEE = "employee"


class AuditAction(StrEnum):
    LOGIN = "login"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"

    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DEACTIVATED = "user_deactivated"
    USER_REACTIVATED = "user_reactivated"
    USER_ANONYMISED = "user_anonymised"
    PASSWORD_RESET = "password_reset"

    COMPANY_CREATED = "company_created"
    COMPANY_UPDATED = "company_updated"
    COMPANY_ARCHIVED = "company_archived"
    COMPANY_RESTORED = "company_restored"
    COMPANY_DELETED = "company_deleted"

    COMPANY_MEMBER_ADDED = "company_member_added"
    COMPANY_MEMBER_UPDATED = "company_member_updated"
    COMPANY_MEMBER_REMOVED = "company_member_removed"

    SECTION_CREATED = "section_created"
    SECTION_UPDATED = "section_updated"
    SECTION_ARCHIVED = "section_archived"
    SECTION_RESTORED = "section_restored"
    SECTION_DELETED = "section_deleted"

    SECTION_MEMBER_ADDED = "section_member_added"
    SECTION_MEMBER_REMOVED = "section_member_removed"

    LIST_CREATED = "list_created"
    LIST_UPDATED = "list_updated"
    LIST_DELETED = "list_deleted"

    TASK_DELETED = "task_deleted"
    TASK_RESTORED = "task_restored"
    TASK_PERMANENTLY_DELETED = "task_permanently_deleted"

    SETTINGS_UPDATED = "settings_updated"

    NOTIFICATION_FAILED = "notification_failed"


class SettingKey(StrEnum):
    APPLICATION_NAME = "application_name"
    DEFAULT_TIMEZONE = "default_timezone"


APPLICATION_SETTINGS: dict[SettingKey, str] = {
    SettingKey.APPLICATION_NAME: "Billson's Tasks",
    SettingKey.DEFAULT_TIMEZONE: "Europe/London",
}