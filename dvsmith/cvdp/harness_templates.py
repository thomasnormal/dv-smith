"""Harness templates for CVDP tasks."""

from typing import Dict


def harness_for_xcelium(run_cmd: str, hash_tag: str = "dvsmith") -> Dict[str, str]:
    """Generate CVDP harness files for Xcelium simulator.
    
    Args:
        run_cmd: Command to run simulation
        hash_tag: Unique hash for this task
        
    Returns:
        Dictionary of harness files (path -> content)
    """
    return {
        "docker-compose.yml": (
            "services:\n"
            "  direct:\n"
            "    image: ${VERIF_EDA_IMAGE:?set VERIF_EDA_IMAGE}\n"
            "    network_mode: host\n"
            "    shm_size: 2g\n"
            "    volumes:\n"
            "      - ./src/:/src/:ro\n"
            "      - ../code/:/code/:ro\n"
            "    working_dir: /code/rundir\n"
            "    env_file: ./src/.env\n"
            "    command: /bin/bash -lc \"/src/run_xcelium.sh\"\n"
        ),
        "src/.env": f"HASH={hash_tag}\n",
        "src/run_xcelium.sh": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "echo \"Running Xcelium harness...\"\n"
            f"{run_cmd}\n"
        ),
    }


def harness_for_questa(run_cmd: str, hash_tag: str = "dvsmith") -> Dict[str, str]:
    """Generate CVDP harness files for Questa simulator.
    
    Args:
        run_cmd: Command to run simulation
        hash_tag: Unique hash for this task
        
    Returns:
        Dictionary of harness files (path -> content)
    """
    return {
        "docker-compose.yml": (
            "services:\n"
            "  direct:\n"
            "    image: ${VERIF_EDA_IMAGE:?set VERIF_EDA_IMAGE}\n"
            "    network_mode: host\n"
            "    shm_size: 2g\n"
            "    volumes:\n"
            "      - ./src/:/src/:ro\n"
            "      - ../code/:/code/:ro\n"
            "    working_dir: /code/rundir\n"
            "    env_file: ./src/.env\n"
            "    command: /bin/bash -lc \"/src/run_questa.sh\"\n"
        ),
        "src/.env": f"HASH={hash_tag}\n",
        "src/run_questa.sh": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "echo \"Running Questa harness...\"\n"
            f"{run_cmd}\n"
        ),
    }


def harness_for_vcs(run_cmd: str, hash_tag: str = "dvsmith") -> Dict[str, str]:
    """Generate CVDP harness files for VCS simulator.
    
    Args:
        run_cmd: Command to run simulation
        hash_tag: Unique hash for this task
        
    Returns:
        Dictionary of harness files (path -> content)
    """
    return {
        "docker-compose.yml": (
            "services:\n"
            "  direct:\n"
            "    image: ${VERIF_EDA_IMAGE:?set VERIF_EDA_IMAGE}\n"
            "    network_mode: host\n"
            "    shm_size: 2g\n"
            "    volumes:\n"
            "      - ./src/:/src/:ro\n"
            "      - ../code/:/code/:ro\n"
            "    working_dir: /code/rundir\n"
            "    env_file: ./src/.env\n"
            "    command: /bin/bash -lc \"/src/run_vcs.sh\"\n"
        ),
        "src/.env": f"HASH={hash_tag}\n",
        "src/run_vcs.sh": (
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "echo \"Running VCS harness...\"\n"
            f"{run_cmd}\n"
        ),
    }
