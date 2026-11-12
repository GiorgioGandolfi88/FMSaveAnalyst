# Rilascio

## Pubblicare una versione

1. Aggiorna la versione in due punti: `__version__` in `backend/fmsa/__init__.py` e `version` in `frontend/package.json`.
2. Se serve, aggiorna i CSV in `reference/src/`.
3. Fai commit e push su `main`, e verifica che il workflow **CI** sia verde.
4. Crea il tag e pubblicalo:

```bash
git tag v0.2.0
```

```bash
git push origin v0.2.0
```

Il workflow **Release**:
- verifica che il tag corrisponda a `__version__`;
- esegue i test;
- compila il frontend, il database delle anagrafiche e l'exe;
- esegue `--self-test`;
- pubblica `FMSaveAnalyst-<versione>-win64.zip` e il relativo `.sha256` come release su GitHub, con le note generate dai commit.

Da quel momento il controllo aggiornamenti delle app installate propone la nuova versione.

Il controllo funziona solo se il repository è **pubblico**: con un repository privato GitHub risponde "non trovato" e l'app non segnala aggiornamenti.

## Checklist di prova manuale (Windows 10 e Windows 11, senza Python installato)

- [ ] Estrai lo zip in una cartella con spazi e lettere accentate nel nome e avvia `FMSaveAnalyst.exe`.
- [ ] La finestra si apre. Con SmartScreen, "Ulteriori informazioni" → "Esegui comunque" funziona.
- [ ] Impostazioni: lingua IT/EN, cartella dei salvataggi, salvataggio delle impostazioni.
- [ ] Nuova carriera da un salvataggio FM26 e da uno FM27: l'import termina.
- [ ] Aggiorna una carriera con la stagione successiva: la verifica dice "stessa carriera" e l'import termina.
- [ ] Aggiorna una carriera con il salvataggio di un'altra carriera: la verifica avvisa.
- [ ] Esplora dati: filtri, ordinamento, export in CSV per Excel (si apre correttamente in Excel).
- [ ] Query builder: due tabelle collegate, esecuzione, salvataggio della query, modifica come SQL.
- [ ] Dashboard: filtri club/competizione/stagione, passaggio grafico/tabella, export ZIP.
- [ ] Mascheramento: con "Potenziale" attivo, il potenziale non compare da nessuna parte (griglia, SQL, dashboard).
- [ ] Assistenti AI: salvataggio della chiave, "Test connessione", una domanda, approvazione e rifiuto dell'invio dei dati.
- [ ] Aggiornamenti: "Controlla ora".
- [ ] Modalità portabile: con `portable.flag` accanto all'exe, i dati finiscono in `data\`.
- [ ] Senza WebView2 (o con `--browser`): l'app si apre nel browser.
- [ ] `FMSaveAnalyst.exe --self-test` → `data\logs\fmsa.log` (oppure `%APPDATA%\FMSaveAnalyst\logs`) termina con `PASSED`.

## Limiti noti

- **Firma del codice:** l'exe non è firmato, quindi SmartScreen mostra un avviso al primo avvio. Un certificato di firma si può valutare in futuro.
- **Conversazioni AI:** si perdono alla chiusura dell'app.
- **Anagrafiche:** i nomi di competizioni, nazioni e città restano vuoti finché i CSV in `reference/src/` non vengono compilati.
- **FM27 27.0.1:** alcuni dati (arbitri, statistiche di squadra per partita, pianificazione della rosa) dipendono dal supporto di fmsave per quella build.
- **Carriere grandi:** una carriera FM26 di 10 stagioni occupa circa 2 GB, e ogni import usa fino a circa 3 GB di RAM.
