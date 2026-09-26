# Transaction Receipt Archiver & File Manager
import os
import logging

logger = logging.getLogger(__name__)

def archive_transaction_receipt(receipt_path: str):
    """Read and archive customer transaction receipt to disk."""
    logger.info(f"Archiving transaction receipt from {receipt_path}")
    
    # VULNERABILITY (CWE-775): Unclosed file descriptor resource leak
    f = open(receipt_path, 'r')
    receipt_data = f.read()
    return receipt_data
