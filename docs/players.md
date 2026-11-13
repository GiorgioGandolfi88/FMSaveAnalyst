# Giocatori: lista e scheda

La pagina **Giocatori** mostra tutti i giocatori della carriera aperta: lista a sinistra, scheda del giocatore selezionato a destra. Codice: `backend/fmsa/players.py` (API `/api/players/...`), `frontend/src/pages/PlayersPage.tsx`, `frontend/src/components/PlayerCardPanel.tsx`.

## Lista

- Colonne: età, ruoli naturali, CA, PA, club, valore, ingaggio, scadenza, presenze, gol, assist e voto medio della stagione in corso (`player_season_stats`, tipo scelto in alto: campionato, totale, coppe, ...).
- Clic sull'intestazione per ordinare. Si può filtrare per nome, ruolo e shortlist. Le righe si caricano 100 alla volta mentre scorri.
- Le celle delle statistiche sono evidenziate quando il valore supera il 60° (grigio) o l'85° percentile (scuro) dei giocatori che hanno giocato.
- **J** e **K** scorrono la lista, **S** aggiunge o toglie il giocatore dalla shortlist. La shortlist è salvata per carriera in `shortlists\` nella cartella dati.

## Scheda

- **Ruolo di confronto.** È il gruppo del primo ruolo naturale (`natural_positions`): portieri, difensori centrali, terzini, mediani, centrocampisti centrali, esterni (ML/MR/AML/AMR), trequartisti, attaccanti. Il gruppo contiene tutti i giocatori del save che hanno un ruolo naturale in quel gruppo.
- **Attributi.** Le barre e la ruota mostrano il percentile dell'attributo rispetto al gruppo. Per scorrettezza e predisposizione agli infortuni, più basso è meglio. Il numero al centro della ruota è la media dei percentili degli attributi tecnici (o da portiere), mentali e fisici.
- **Posizioni.** Mostra il valore 1-20 di ogni ruolo sul campo, i ruoli naturali, gli altri ruoli in cui gioca e il gruppo di confronto.
- **Statistiche.** Totale e per 90 minuti della stagione in corso, per tipo di competizione. Il rank è il percentile tra i giocatori dello stesso gruppo con almeno 450 minuti, calcolato sul valore per 90 (o sulla percentuale).
- **Personalità e Contratto.** Riportano personalità, caratteristiche, reputazione, contratto e clausole (le clausole che fmsave non sa decodificare non vengono mostrate).

Il mascheramento delle Impostazioni vale anche qui. Potenziale, abilità attuale, attributi nascosti e personalità, se nascosti, compaiono come "?" o con il lucchetto e non vengono usati nei confronti.
