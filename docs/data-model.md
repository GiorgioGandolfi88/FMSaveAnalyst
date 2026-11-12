# Modello dati del database carriera (`.fmsa`)

Ogni carriera è un file SQLite separato. Lo crea e lo aggiorna solo l'importatore, `backend/fmsa/ingest/`. Tutto il resto dell'app lo apre in sola lettura.

## Import

```bash
uv run python -m fmsa.ingest "data/careers/Mia carriera.fmsa" "Season 1.fm" "Season 2.fm"
```

- Il save viene prima copiato in una cartella temporanea, calcolandone lo SHA-256. Il file originale non viene mai toccato.
- Ogni import è **un'unica transazione**: se qualcosa va storto, il database resta com'era.
- I reader vengono letti a gruppi, riaprendo il save per ogni gruppo, perché fmsave tiene in memoria tutte le tabelle lette.
- Un reader non supportato per la build del save (es. `officials` su FM27 27.0.1) viene registrato come `unsupported` e saltato. La sua tabella resta vuota ma esiste.
- Un import viene rifiutato (`ImportRejected`) se:
  - l'edizione è diversa da quella della carriera (FM26 contro FM27);
  - quello stesso file è già stato importato (stesso SHA-256);
  - la data di gioco non è successiva a quella dell'ultimo import.

  I controlli completi di continuità arrivano con lo Step 4.

## Tabelle per ogni reader

Per ogni reader fmsave (`players`, `fixtures`, …) ci sono due oggetti:

| Oggetto | Cosa contiene |
|---|---|
| `<reader>_all` (tabella) | tutto lo storico, con le colonne tecniche `_…` |
| `<reader>` (vista) | lo stato "attuale", da usare nelle query normali |

Le liste di record diventano tabelle figlie: `players__traits`, `clubs__teams`, `league_tables__rows`, `league_tables__rows__matches`, … Si collegano al padre con `_parent_rid = <padre>._rid`, e la loro vista contiene solo i figli dei record attuali.

Regole di appiattimento:
- i record annidati diventano colonne con prefisso (`ability_current`, `attributes_finishing`, `personality_ambition`);
- i valori codificati diventano due colonne, `<campo>_label` e `<campo>_raw`;
- le liste di valori semplici sono testo JSON (`natural_positions`);
- le date sono testo ISO e i booleani 0/1;
- i campi `unknown` (dati grezzi non decodificati) vengono scartati.

### Tre tipi di memorizzazione (`backend/fmsa/ingest/readers.py`)

| Tipo | Reader | Comportamento |
|---|---|---|
| **entità** | players, contracts, staff, clubs, facilities, stadiums, nations, competitions, stages, officials, injury_types | Una versione per chiave, con `_valid_from` e `_valid_to` (id degli import). Una nuova versione si scrive solo se qualcosa è cambiato. La vista mostra le versioni con `_valid_to IS NULL`; lo storico (es. la progressione di CA e attributi) è in `_all`. |
| **evento** | fixtures, player_season_history, injuries, suspensions, finances, player_match_stats, team_match_stats | Si accumulano import dopo import e vengono deduplicati per chiave, perché ogni save conserva solo una finestra temporale. Un evento i cui valori cambiano (una partita poi giocata) viene aggiornato. `_first_seen` e `_last_seen` indicano gli import in cui l'evento compariva. |
| **snapshot** | league_tables, competition_rules, sponsorships, staff_lists, job_vacancies, … | Copia completa a ogni import (`_import_id`). La vista mostra l'ultimo import riuscito. |
| **ultimo** | player_season_stats | Resta solo l'ultimo import. Le stagioni concluse sono già in `player_season_history`, quindi altre copie le duplicherebbero (erano il 35% dello spazio). |

Chiavi delle entità/eventi principali:
- `players` e `staff`: (`uid`, `birth_date`). Così un regen che eredita l'uid di un ritirato diventa una persona nuova.
- `fixtures`: (`date`, `home_team_id`, `away_team_id`).
- `player_season_history`: (`player_uid`, `season_year`, `club_uid`, `kind`, `competition_reference`).

Se nello stesso import ci sono righe con la stessa chiave, ricevono un ordinale, così i duplicati identici restano distinti.

## Tabelle di sistema

| Tabella | Contenuto |
|---|---|
| `_meta` | edizione (`game`), data di creazione, nome del primo save, stringa di configurazione della partita |
| `_imports` | un record per import: file, SHA-256, build, data di gioco, `summary_strings`, versioni di fmsave e dell'app, durata |
| `_import_readers` | esito di ogni reader in ogni import: righe, nuove, aggiornate, invariate, chiuse, tempo, avvisi |
| `_tables`, `_columns` | catalogo di tabelle e colonne, con il percorso del campo fmsave e il suo stato (verified/unconfirmed). Servirà a query builder, mascheramento e AI. |

## Misure (FM27, 3 stagioni)

Ogni import richiede circa 2 minuti. Il file `.fmsa` occupa 180 MB dopo il primo import e 630 MB dopo il terzo.

## Accesso in sola lettura e mascheramento (Step 5)

Ogni query dell'interfaccia, delle dashboard e degli assistenti AI passa da `ReadOnlySession` (`backend/fmsa/query/session.py`), che ha tre protezioni indipendenti:

1. il file viene aperto con `mode=ro`;
2. `PRAGMA query_only = ON`;
3. un **authorizer SQLite** che permette solo la lettura (SELECT, lettura di colonne, funzioni, CTE ricorsive) e rifiuta tutto il resto prima che venga eseguito: INSERT/UPDATE/DELETE, CREATE/DROP/ALTER, ATTACH, PRAGMA, transazioni, `load_extension`.

È ammessa una sola istruzione per query. Ogni query ha inoltre un limite di tempo (30 s) e di righe (10.000 di default, 200.000 al massimo).

**Mascheramento** (`backend/fmsa/query/masking.py`): le regole sono legate ai percorsi dei campi fmsave (`_columns.source_path`), quindi valgono per ogni tabella che contiene quel campo (`players`, `staff` e i loro storici `_all`). Le colonne nascoste risultano **NULL ovunque compaiano**: in SELECT, WHERE, ORDER BY, JOIN, aggregazioni e sottoquery. Non si possono ricavare filtrando o ordinando.

| Impostazione | Campi nascosti |
|---|---|
| Potenziale (attiva di default) | `ability.potential`, `ability.potential_range_code` |
| Abilità attuale | `ability.current` |
| Attributi nascosti | `attributes.consistency`, `dirtiness`, `important_matches`, `injury_proneness`, `versatility` |
| Personalità | tutti i `personality.*` |
| Colonne extra | voci `tabella.colonna` scelte dall'utente |

Le colonne interne `_hash` e `_key` sono sempre nascoste, perché cambiano ogni volta che cambia un qualunque valore, compresi quelli nascosti.

Limite noto: nelle tabelle `_all`, un valore nascosto che cambia crea comunque una nuova versione del record. Si vede che qualcosa è cambiato, ma non cosa.

Nota: i valori che arrivano da enum testuali di fmsave sono salvati in minuscolo (es. `player_season_history.kind = 'league'`).
