"""Backup do banco de dados (e, opcionalmente, dos PDFs das faturas) em arquivos .zip.

Aponte a pasta de destino para uma pasta sincronizada (Google Drive, OneDrive, Dropbox) e a
cópia sai do computador sozinha."""

import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from solar import config

PADRAO_NOME = "solar_*.zip"


def _destino(pasta: Path | str | None) -> Path:
    destino = Path(pasta) if pasta else config.PASTA_BACKUP
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def listar_backups(pasta: Path | str | None = None) -> list[Path]:
    return sorted(_destino(pasta).glob(PADRAO_NOME), reverse=True)


def fazer_backup(pasta: Path | str | None = None, incluir_pdfs: bool = False, agora: datetime | None = None) -> Path:
    """Copia o banco com a API de backup do SQLite (consistente mesmo com o app aberto),
    compacta e apaga os mais antigos além do limite de backups mantidos."""
    destino = _destino(pasta)
    agora = agora or datetime.now()
    arquivo = destino / f"solar_{agora:%Y%m%d_%H%M%S}.zip"

    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "solar.db"
        origem, saida = sqlite3.connect(config.CAMINHO_DB), sqlite3.connect(copia)
        try:
            origem.backup(saida)
        finally:
            origem.close()
            saida.close()
        with zipfile.ZipFile(arquivo, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(copia, "solar.db")
            if incluir_pdfs and config.PASTA_PDFS.exists():
                for pdf in config.PASTA_PDFS.glob("*.pdf"):
                    zf.write(pdf, f"pdfs/{pdf.name}")

    for antigo in listar_backups(destino)[config.BACKUPS_MANTIDOS:]:
        antigo.unlink()
    return arquivo


def backup_automatico_se_necessario(
    pasta: Path | str | None = None, dias: int = config.DIAS_ENTRE_BACKUPS_AUTOMATICOS, agora: datetime | None = None
) -> Path | None:
    """Faz backup se o último tem mais de `dias` dias (ou se não há nenhum)."""
    agora = agora or datetime.now()
    existentes = listar_backups(pasta)
    if existentes:
        ultimo = datetime.fromtimestamp(existentes[0].stat().st_mtime)
        if agora - ultimo < timedelta(days=dias):
            return None
    return fazer_backup(pasta, agora=agora)


def restaurar_backup(arquivo: Path) -> Path:
    """Troca o banco atual pelo do backup, guardando antes uma cópia do atual ao lado."""
    segurança = config.CAMINHO_DB.with_name(f"solar_antes_de_restaurar_{datetime.now():%Y%m%d_%H%M%S}.db")
    if config.CAMINHO_DB.exists():
        shutil.copy2(config.CAMINHO_DB, segurança)
    with zipfile.ZipFile(arquivo) as zf, tempfile.TemporaryDirectory() as tmp:
        zf.extract("solar.db", tmp)
        shutil.copy2(Path(tmp) / "solar.db", config.CAMINHO_DB)
    return segurança
