import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config import DATA_DIR

LOG_DIR=DATA_DIR/"logs"
LOG_DIR.mkdir(parents=True,exist_ok=True)
LOG_FILE=LOG_DIR/"strategy_e.log"

def configure_logging():
    root=logging.getLogger()
    if getattr(root,"_strategy_e_configured",False): return
    root.setLevel(logging.INFO)
    fmt=logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    sh=logging.StreamHandler(); sh.setFormatter(fmt); sh.setLevel(logging.INFO)
    fh=RotatingFileHandler(LOG_FILE,maxBytes=5_000_000,backupCount=5,encoding="utf-8"); fh.setFormatter(fmt); fh.setLevel(logging.INFO)
    root.addHandler(sh); root.addHandler(fh)
    root._strategy_e_configured=True

logger=logging.getLogger("strategy_e")
