# Rai 4 su UHF con playlist HLS aggiornata da GitHub Actions

La lista canali e la playlist HLS sono due file diversi. UHF puo aggiornare
la lista canali quotidianamente: la voce Rai 4 conserva sempre lo stesso URL.
Actions aggiorna invece il contenuto di `rai/rai4.m3u8` ogni ora, al minuto 17.
Quando il player carica quel file, trova gli URL video/audio aggiornati.
Il comportamento della cache HLS di UHF/KSPlayer va verificato sul dispositivo.

```text
Lista canali in UHF (aggiornamento quotidiano)
  -> URL stabile GitHub: rai/rai4.m3u8 (aggiornato ogni ora)
     -> playlist video/audio live Rai con token
        -> segmenti sulla CDN Rai
```

## Attivazione

1. Pubblica sul branch `main` i file preparati. Dalla cartella del repository:

   ```powershell
   git add -- .github/workflows/update-rai4.yml scripts/update_rai4.py tests/test_update_rai4.py docs/rai4-automatico.md
   git commit -m "Add hourly Rai 4 HLS refresh"
   git push origin main
   ```

   `list.m3u8` e escluso da Git nel `.gitignore` esistente; questi comandi
   non pubblicano la lista personale. Il file HLS viene creato dal workflow.

2. Nel repository GitHub apri **Actions -> Update Rai 4 HLS** e verifica
   l'esecuzione avviata dal push. Per riprovare: **Run workflow -> main**.
   Il workflow richiede `contents: write` e usa il `GITHUB_TOKEN` automatico:
   non serve creare un PAT. Eventuali regole del repository/organizzazione
   o protezioni di `main` devono consentire il push del bot.

3. Dopo un'esecuzione verde, verifica l'esistenza di questo file pubblico:

   ```text
   https://raw.githubusercontent.com/grzianod/iptv/refs/heads/main/rai/rai4.m3u8
   ```

   Il repository deve essere leggibile da UHF; questo esempio usa un URL raw
   pubblico. Mantieni il riferimento al branch `main`, non a uno specifico commit.

4. In `list.m3u8`, sostituisci solo l'URL sotto la voce Rai 4 con quello sopra,
   conservando nome, logo, EPG e `#EXTVLCOPT:http-user-agent=raiplayappletv`.
   Ricarica/reimporta una volta la lista in UHF per acquisire il nuovo indirizzo.
   Successivamente puoi lasciare l'aggiornamento della lista su **quotidianamente**.

5. Seleziona KSPlayer e prova Rai 4 subito, poi chiudi e riapri il canale il
   giorno dopo senza modificare l'URL. Questo verifica che UHF recuperi la
   playlist HLS nuova invece di riutilizzarne una copia scaduta.

## Funzionamento e verifiche

Lo script usa soltanto la libreria standard di Python (3.10 o successivo).
Scarica il master dal relinker, rende assoluti sia gli URL su righe separate
sia gli attributi `URI="..."` (audio e I-frame inclusi) e conserva tutte le
qualita e lingue. Non copia il token breve del master sugli URL figli.
Le playlist live dei segmenti continuano a essere aggiornate dalla Rai.

Prima della scrittura verifica che ogni URL abbia almeno sei ore residue
secondo `tend`, che ogni playlist referenziata sia HLS live e che un segmento
per playlist sia scaricabile. Il controllo HTTP non certifica la decodifica
o la compatibilita con UHF. Un errore interrompe il workflow conservando
il file precedente; quest'ultimo comunque scadra se i rinnovi restano bloccati.

Per una prova locale, senza pubblicare:

```powershell
python -B -m unittest discover -s tests -v
python -B scripts/update_rai4.py
```

I token indicavano circa 24 ore per gli URL figli nelle prove iniziali: non e
una garanzia del provider. GitHub Actions puo ritardare o saltare esecuzioni;
controlla gli errori nella scheda Actions. Nei repository pubblici lo schedule
puo essere disabilitato dopo 60 giorni senza attivita.

Il runner GitHub potrebbe ricevere un blocco geografico/di rete oppure token
non utilizzabili dalla connessione Apple TV: il successo locale non dimostra
il successo dal runner. In quel caso serve eseguire lo stesso aggiornamento
su un computer autorizzato nella propria rete, ad esempio con un runner
self-hosted; aumentare la frequenza non risolve il blocco.

L'aggiornamento del master non forza il rinnovo durante una visione continua:
una sessione che supera la validita dei suoi token potrebbe richiedere la
riapertura del canale. Se UHF conserva il master scaduto anche riaprendo il
canale, questa soluzione statica non e sufficiente: serve risolvere la cache
del player o usare un endpoint dinamico con gestione esplicita della cache.

Riferimenti: [schedule GitHub Actions](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
[GITHUB_TOKEN](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).
