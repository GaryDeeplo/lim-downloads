# Downloads Manager

Trie le dossier Téléchargements par lots : doublons, zips déjà extraits, installeurs, rangement par type. Rien n'est supprimé directement (quarantaine 30 jours, chaque action s'annule).

- Lancer : `start.bat` ou l'exe. L'appli s'ouvre dans sa propre fenêtre (WebView2, le moteur web de Windows) ; la croix la range près de l'horloge, le tri auto continue. Sans WebView2, elle s'ouvre dans le navigateur (http://127.0.0.1:8765). Journaux : `%LOCALAPPDATA%\DownloadsManager\downloads-manager.log`
- Démarrage avec Windows : `python -m dm.autostart` crée le raccourci du menu Démarrer et le lancement discret à l'ouverture de session (icône seule). Désactivable depuis le menu de l'icône.
- Tri automatique : éteint par défaut. La pastille « Régler le tri auto » (ou Lim, le robot guide) ouvre son panneau : délai, actions autorisées, fichiers en attente, derniers rangements, passe immédiate. Il ne touche qu'aux téléchargements arrivés après son activation, une fois le délai passé. Un fichier dont le déplacement a été annulé n'est plus jamais trié automatiquement.
- Exe : `dist\Downloads Manager.exe` (un seul fichier, sans console). Reconstruire : `cd web && npm run build` puis `.venv\Scripts\python tools\build_exe.py`. Au lancement, l'exe repointe les raccourcis (menu Démarrer, démarrage) vers lui. Réglages : `config.json` à côté de l'exe.
- Quarantaine : visible dans l'appli (dock ou colonne de gauche), restauration fichier par fichier, suppression par lot ou vidage complet.
- Guide : Lim se présente au premier lancement ; sa tête en haut à droite le rappelle.
- Front (React + Vite + Motion) : `cd web && npm run dev` pendant le dev, `npm run build` pour régénérer `dm/static`
- Démo sans toucher aux vrais fichiers : `python tools/make_demo.py` puis `set DM_CONFIG=%TEMP%\dm-demo\config.json` avant `python -m dm`
- Tests : `.venv\Scripts\python -m pytest`
- Réglages (dossiers cibles, seuils, mots sensibles) : `config.json` à la racine
