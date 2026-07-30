from sqlalchemy import text
from sqlalchemy.orm import Session


def test_database_fixture_connects_to_test_database(
    db: Session,
) -> None:
    database_name = db.execute(
        text(
            "SELECT current_database()",
        ),
    ).scalar_one()

    assert database_name == "billsons_tasks_test"


def test_database_fixture_supports_service_commits(
    db: Session,
) -> None:
    db.execute(
        text(
            """
            CREATE TEMPORARY TABLE pytest_commit_check (
                id integer
            )
            """
        ),
    )

    db.execute(
        text(
            """
            INSERT INTO pytest_commit_check (id)
            VALUES (1)
            """
        ),
    )

    db.commit()

    result = db.execute(
        text(
            """
            SELECT id
            FROM pytest_commit_check
            """
        ),
    ).scalar_one()

    assert result == 1