"""
Datasource persistence module.

Saves and loads datasources to/from a JSON file to persist across restarts.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Store datasources in a JSON file in the app directory
DATASOURCES_FILE = Path(__file__).parent.parent / "datasources.json"


def save_datasources(datasources: Dict[str, Any]) -> None:
    """
    Save datasources to JSON file.

    Args:
        datasources: Dictionary of datasources to save
    """
    try:
        with open(DATASOURCES_FILE, 'w') as f:
            json.dump(datasources, f, indent=2)
        logger.info(f"Saved {len(datasources)} datasources to {DATASOURCES_FILE}")
    except Exception as e:
        logger.error(f"Failed to save datasources: {e}", exc_info=True)


def load_datasources() -> Dict[str, Any]:
    """
    Load datasources from JSON file.

    Returns:
        Dictionary of datasources, or empty dict if file doesn't exist
    """
    try:
        if not DATASOURCES_FILE.exists():
            logger.info("No datasources file found - starting with empty datasources")
            return {}

        with open(DATASOURCES_FILE, 'r') as f:
            datasources = json.load(f)

        logger.info(f"Loaded {len(datasources)} datasources from {DATASOURCES_FILE}")
        return datasources

    except Exception as e:
        logger.error(f"Failed to load datasources: {e}", exc_info=True)
        return {}


def delete_datasource(datasource_id: str, datasources: Dict[str, Any]) -> None:
    """
    Delete a datasource and update the persistence file.

    Args:
        datasource_id: ID of datasource to delete
        datasources: Current datasources dictionary
    """
    if datasource_id in datasources:
        del datasources[datasource_id]
        save_datasources(datasources)
        logger.info(f"Deleted datasource {datasource_id} from persistence")
