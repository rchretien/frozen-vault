"""Utilities for the API."""

import os
from pathlib import Path

from dotenv import dotenv_values

from frozen_vault_backend.exceptions import EnvironmentVariableNotFoundError


# TODO(Renaud): rely on same function from toolbox, once it accepts a defaut path for .env file.
def get_env_var(varname: str, default: str | None = None) -> str:
    """Get the provided environment variable.

    It will check the sources below in the following order (and raise an exception if not able
    to find it):
    1. as an environment variable
    2. as an environment variable with `-` replaced by `_`
    3. in `~/.env-local`
    4. in `./.env-local`
    5. from default value, if provided

    Parameters
    ----------
    varname
        Name of the environment variable to retrieve.
    default
        Default value to return if the environment variable could not be found.

    Returns
    -------
    str
        The value of the requested environment variable.
    """
    # try loading it from environment variables
    envvar = os.environ.get(varname, None)
    if envvar:
        return envvar

    # try loading it from environment variables with `-` replaced by `_`
    envvar = os.environ.get(varname.replace("-", "_"), None)
    if envvar:
        return envvar

    # try loading it from ~/.env-local file
    envvar = dotenv_values(dotenv_path=Path("~").expanduser() / ".env-local").get(varname, None)
    if envvar:
        return envvar

    # try fetching it from ./.env-local file
    envvar = dotenv_values(dotenv_path="./.env-local").get(varname, None)
    if envvar:
        return envvar

    # Couldn't retrieve it, returning default if set
    if default:
        return default

    raise EnvironmentVariableNotFoundError(varname)
