# FMSaveAnalyst

Analisi in sola lettura, tutta in locale, dei salvataggi di Football Manager 26 e 27, basata sulla libreria [fmsave](https://github.com/rhiever/fmsave).
*Local, read-only analysis of Football Manager 26 and 27 saves.*

## Cosa fa

- **Carriere:** ogni carriera ha un database separato. Lo crei da un salvataggio di FM e lo aggiorni con i salvataggi successivi. L'app controlla che ogni salvataggio prosegua la stessa carriera, e partite, infortuni e storico si accumulano anche quando il gioco li scarta.
- **Esplora dati:** tutte le tabelle, con filtri per colonna, ordinamento e paginazione.
- **Query builder:** colleghi le tabelle in modo visuale oppure scrivi SQL in un editor con suggerimenti. Le query si salvano per carriera e si esportano in CSV o JSON.
- **Dashboard:** 10 dashboard pronte (rosa, progressione, giovani, contratti, finanze, classifiche, statistiche stagionali, infortuni, mercato, partite). Si possono esportare e puoi aggiungerne di tue.
- **Assistenti AI:** Claude, OpenAI o Gemini con la tua chiave API. Gli assistenti interrogano i dati in sola lettura e ti chiedono conferma prima di inviare qualcosa.
- **Anti-spoiler:** potenziale, abilità attuale, attributi nascosti e personalità si possono nascondere ovunque, anche all'AI.
- **Aggiornamenti:** all'avvio l'app controlla le release su GitHub e ti indica il download.

I database delle carriere vengono solo letti: né le query né l'interfaccia possono modificarli. Le uniche connessioni a internet sono il controllo aggiornamenti (disattivabile) e gli assistenti AI che configuri tu.

## Installazione

1. Scarica `FMSaveAnalyst-<versione>-win64.zip` dalle [release](https://github.com/GiorgioGandolfi88/FMSaveAnalyst/releases).
2. Estrai la cartella dove vuoi, anche su una chiavetta USB.
3. Avvia `FMSaveAnalyst.exe`.

Non serve installare nulla (Windows 10/11, 64 bit). Le istruzioni sono anche in `LEGGIMI.txt` dentro lo zip.

## Documentazione

| Documento | Contenuto |
|---|---|
| [docs/data-model.md](docs/data-model.md) | Struttura dei database, import, sola lettura e mascheramento |
| [docs/dashboards.md](docs/dashboards.md) | Dashboard incluse e come crearne di tue |
| [docs/ai.md](docs/ai.md) | Assistenti AI: configurazione, cosa viene inviato, privacy |
| [reference/README.md](reference/README.md) | Database delle anagrafiche di gioco (nomi di competizioni, nazioni, città) |
| [docs/fmsave-schema.md](docs/fmsave-schema.md) | Analisi della libreria fmsave sui salvataggi reali (Step 0) |
| [docs/release.md](docs/release.md) | Come pubblicare una release e checklist di prova manuale |

## Sviluppo

Requisiti: Python 3.13, [uv](https://docs.astral.sh/uv/) e Node.js 24.

```bash
uv sync
```

```bash
cd frontend && npm install && npm run build
```

```bash
uv run python -m fmsa
```

Per lavorare sull'interfaccia con il ricaricamento automatico (due terminali):

```bash
uv run python -m fmsa --dev
```

```bash
cd frontend && npm run dev
```

Poi apri http://localhost:5173. Il file `portable.flag` nella radice del repository fa finire i dati di sviluppo in `data/`, che git ignora.

Import da riga di comando:

```bash
uv run python -m fmsa.ingest "data/careers/Mia carriera.fmsa" "Season 1.fm" "Season 2.fm"
```

Controlli:

```bash
uv run pytest
```

```bash
uv run ruff check backend spikes scripts reference
```

```bash
uv run pyright
```

Test facoltativi su salvataggi o carriere reali: imposta `FMSA_TEST_SAVE` / `FMSA_TEST_SAVE_2` (percorsi di file `.fm`) oppure `FMSA_TEST_CAREER` (percorso di un file `.fmsa`).

### Build portabile

```bash
uv run python scripts/build.py
```

Produce `dist/FMSaveAnalyst/` e `dist/FMSaveAnalyst-<versione>-win64.zip`, con il relativo `.sha256`. Per verificare il pacchetto, avvia `dist/FMSaveAnalyst/FMSaveAnalyst.exe --self-test [percorso\di\un\save.fm]` e leggi il risultato nel log.

## Struttura

| Percorso | Contenuto |
|---|---|
| `backend/fmsa/` | Server locale FastAPI, finestra desktop, impostazioni |
| `backend/fmsa/ingest/` | Import dei salvataggi nei database delle carriere, controllo di continuità |
| `backend/fmsa/query/` | Sessione in sola lettura, mascheramento, relazioni, paginazione, export |
| `backend/fmsa/dashboards/` | Motore delle dashboard e definizioni JSON |
| `backend/fmsa/ai/` | Provider, assistenti, strumenti, approvazione dei dati inviati |
| `frontend/` | Interfaccia React + TypeScript + Mantine (IT/EN), AG Grid, React Flow, Monaco, ECharts |
| `reference/` | Sorgenti CSV e script del database delle anagrafiche |
| `packaging/`, `scripts/` | PyInstaller e build della release |
| `spikes/`, `docs/` | Analisi di fmsave e documentazione |
