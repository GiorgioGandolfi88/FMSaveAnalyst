# FMSaveAnalyst

Analisi in sola lettura, tutta in locale, dei salvataggi di Football Manager 26 e 27, basata sulla libreria [fmsave](https://github.com/rhiever/fmsave).
*Local, read-only analysis of Football Manager 26 and 27 saves.*

> Stato: in sviluppo (Step 1 – scheletro e packaging). Il piano completo è in `docs/`.

## Uso

Scarica `FMSaveAnalyst-<versione>-win64.zip` dalle [release](https://github.com/GiorgioGandolfi88/FMSaveAnalyst/releases), estrai la cartella e avvia `FMSaveAnalyst.exe`. Non serve installare nulla (Windows 10/11, 64 bit). Le istruzioni sono anche in `LEGGIMI.txt` dentro lo zip.

## Sviluppo

Requisiti: Python 3.13, [uv](https://docs.astral.sh/uv/) e Node.js 24.

```bash
uv sync                      # crea .venv con tutte le dipendenze
cd frontend && npm install && npm run build && cd ..
uv run python -m fmsa        # avvia l'app con la finestra nativa
```

Sviluppo dell'interfaccia con ricaricamento automatico:

```bash
uv run python -m fmsa --dev  # API su 127.0.0.1:8765 (token "dev")
cd frontend && npm run dev   # apri http://localhost:5173
```

Il file `portable.flag` nella radice del repository fa sì che, in sviluppo, impostazioni e database finiscano in `data/` (ignorata da git) invece che in `%APPDATA%`.

Controlli:

```bash
uv run pytest
uv run ruff check backend spikes scripts
uv run pyright
```

### Build dell'eseguibile portabile

```bash
uv run python scripts/build.py
```

Produce `dist/FMSaveAnalyst/` e `dist/FMSaveAnalyst-<versione>-win64.zip`, con il relativo `.sha256`. Per verificare il pacchetto:
`dist/FMSaveAnalyst/FMSaveAnalyst.exe --self-test [percorso\di\un\save.fm]`. Il risultato finisce nel log `data/logs/fmsa.log`.

### Release

1. Aggiorna `__version__` in `backend/fmsa/__init__.py` e la `version` in `frontend/package.json`.
2. Crea e pubblica il tag corrispondente:

```bash
git tag v0.2.0
```

```bash
git push origin v0.2.0
```

Il workflow `release.yml` compila, esegue i test e pubblica lo zip come GitHub Release.

## Struttura

| Percorso | Contenuto |
|---|---|
| `backend/fmsa/` | Backend Python: server FastAPI locale, configurazione, avvio con pywebview |
| `frontend/` | Interfaccia React + TypeScript + Mantine (IT/EN) |
| `reference/` | Database anagrafiche per versione di gioco (Step 3) |
| `packaging/` | Spec di PyInstaller e file distribuiti nello zip |
| `scripts/build.py` | Build della release portabile |
| `spikes/`, `docs/` | Analisi della libreria fmsave (Step 0) e documentazione |

## Privacy

Tutti i dati restano sul PC. Le uniche connessioni a internet sono il controllo aggiornamenti su GitHub (disattivabile) e gli assistenti AI configurati con la propria chiave API.
