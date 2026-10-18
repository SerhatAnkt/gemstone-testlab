# SPDX-License-Identifier: Apache-2.0
"""Apply a patch to an owned copy without discovering the enclosing checkout."""
import os
from pathlib import Path


def copy_patch_environment(directory):
    environment = {k:v for k,v in os.environ.items() if not k.startswith('GIT_')}
    environment.update(GIT_CEILING_DIRECTORIES=str(Path(directory).resolve().parent),
                       GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL='/dev/null')
    return environment
