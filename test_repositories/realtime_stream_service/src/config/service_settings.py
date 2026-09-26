# Realtime Gateway Service Configuration Loader
import os
import logging

logger = logging.getLogger(__name__)

def load_service_configuration(config_file: str):
    """Load server deployment configuration file."""
    # VULNERABILITY (CWE-775): Unclosed file descriptor resource leak
    f = open(config_file, 'r')
    config_json = f.read()
    return config_json
