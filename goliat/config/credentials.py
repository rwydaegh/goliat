"""Environment variable and credentials management."""

import os


def get_download_email() -> str:
    """Returns the download email from environment variables.

    Raises:
        ValueError: If DOWNLOAD_EMAIL is not set in the environment.
    """
    email = os.getenv("DOWNLOAD_EMAIL")
    if not email:
        raise ValueError("Missing DOWNLOAD_EMAIL. Please set this in your .env file.")
    return email


def get_osparc_credentials() -> dict:
    """Gets oSPARC credentials from environment variables.

    Raises:
        ValueError: If required oSPARC credentials are not set.

    Returns:
        A dictionary containing oSPARC API credentials.
    """
    credentials = {
        "api_key": os.getenv("OSPARC_API_KEY"),
        "api_secret": os.getenv("OSPARC_API_SECRET"),
        "api_server": "https://api.sim4life.science",
        "api_version": "v0",
    }

    missing = [key for key, value in credentials.items() if value is None and key != "api_version"]
    if missing:
        raise ValueError(
            f"Missing oSPARC credentials: {', '.join(missing)}. "
            "Please create a .env file in the project root with your oSPARC API credentials. "
            "See README.md for setup instructions."
        )

    return credentials
