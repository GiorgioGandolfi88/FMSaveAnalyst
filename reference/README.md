# Database anagrafiche di gioco

Nei save mancano i nomi di competizioni, nazioni e città. Si trovano nel database del gioco, e FMSaveAnalyst li legge da `fm_reference.sqlite`. Quel file si genera dai CSV di questa cartella ed è incluso nello zip di release.

## Struttura

```
reference/src/<versione>/competitions.csv   database_id,name,short_name,nation_database_id
reference/src/<versione>/nations.csv        database_id,name,short_name,code
reference/src/<versione>/cities.csv         database_id,name,nation_database_id
reference/src/<versione>/<altro>.csv        qualsiasi tabella con una colonna database_id
```

- `<versione>` è la versione del gioco nella forma `major.minor.patch` (es. `26.3.2`, `27.0.1`). È la prima parte della build scritta nel save (`26.3.2+2329565`).
- I file sono UTF-8 con riga di intestazione. `database_id` è obbligatorio e deve essere univoco nel file.
- Le colonne che si chiamano `database_id` o finiscono in `_id` sono numeri interi; tutte le altre sono testo. Una cella vuota significa "nessun valore".
- Una tabella deve avere le stesse colonne in tutte le versioni.
- Puoi aggiungere nuovi CSV quando vuoi: ognuno diventa una tabella `ref_<nome>` nei database delle carriere.

## Quali id usare

| File | Id da usare | Dove compare nei dati del save |
|---|---|---|
| `competitions.csv` | id della competizione nel database di gioco | `competitions.database_id` (fmsave lo usa anche per riempire `name` e `competition_name`) |
| `nations.csv` | id della nazione nel database di gioco | `nations.database_id` (la vista `nation_names` lo collega al `nation_id` del save) |
| `cities.csv` | id della città | `clubs.city_id`: resta da verificare che sia l'id del database di gioco |

## Aggiornamento

```bash
python reference/build_reference.py
```

Il comando rigenera `reference/fm_reference.sqlite`, che non è versionato in git. La build della release (`scripts/build.py`) lo esegue da sola.

Ogni import di una carriera usa la versione più adatta alla build del save:
1. la stessa versione;
2. altrimenti la più vicina precedente della stessa edizione;
3. altrimenti la più vicina successiva.

I nomi vengono copiati nelle tabelle `ref_*` della carriera e aggiornati a ogni import, quindi le correzioni che fai vengono riprese dall'import successivo.
