import os

from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, URL


def get_project_root():
    """
    Return the project root assuming the function is located
    inside src/.
    """

    return Path(__file__).resolve().parents[1]


def get_engine():
    """
    Create and return a SQLAlchemy engine using the
    PostgreSQL configuration stored in .env.
    """

    project_root = get_project_root()

    env_path = project_root / ".env"

    if not env_path.exists():
        raise FileNotFoundError(
            f".env file not found at: {env_path}"
        )

    load_dotenv(
        env_path,
        override=False
    )

    required_variables = [
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB"
    ]

    missing_variables = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing_variables:
        raise ValueError(
            "Missing environment variables: "
            f"{missing_variables}"
        )

    database_url = URL.create(
        drivername="postgresql+psycopg2",
        username=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        host=os.getenv("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT")),
        database=os.getenv("POSTGRES_DB")
    )

    return create_engine(
        database_url
    )