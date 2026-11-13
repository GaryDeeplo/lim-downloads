/* Anglais des textes de l'interface (clé : le texte français exact passé à tr()). */
const en: Record<string, string> = {
  /* Mots passés à plural() */
  'élément': 'item',
  'éléments': 'items',

  /* App : toasts */
  'Tri auto : {n} élément rangé': 'Auto-sort: {n} item sorted',
  'Tri auto : {n} éléments rangés': 'Auto-sort: {n} items sorted',
  'Rien à ranger pour l\'instant': 'Nothing to sort yet',
  'Les fichiers en attente n\'ont pas encore atteint le délai.': 'The waiting files haven’t reached their delay yet.',
  'Scan impossible': 'Couldn’t scan',
  'Action impossible': 'Couldn’t do that',
  'aucun élément déplacé': 'nothing was moved',
  '{n} ignoré(s) : {error}': '{n} skipped: {error}',
  'Transfert vers {label} lancé': 'Transfer to {label} started',
  '{size} · tu peux continuer à trier': '{size} · you can keep sorting',
  '{label} indisponible': '{label} unavailable',
  '{items} remis dans Téléchargements': '{items} moved back to Downloads',
  '{n} erreur(s)': '{n} error(s)',
  '{size} supprimés définitivement': '{size} permanently deleted',
  'Rien d\'assez ancien à purger': 'Nothing old enough to purge',
  'Quarantaine vidée : {size} libérés': 'Quarantine emptied: {size} freed',
  '{n} lot supprimé définitivement (le reçu garde noms et liens).': '{n} batch permanently deleted (the receipt keeps names and links).',
  '{n} lots supprimés définitivement (le reçu garde noms et liens).': '{n} batches permanently deleted (the receipt keeps names and links).',
  '{size} libérés': '{size} freed',
  'Supprimé définitivement de la quarantaine (le reçu garde nom et lien).': 'Permanently deleted from quarantine (the receipt keeps its name and link).',
  '« {name} » remis dans Téléchargements': '“{name}” moved back to Downloads',
  'Relance un scan pour le retrouver dans les lots.': 'Rescan to see it in the batches again.',
  '{name} : {error}': '{name}: {error}',
  'Exemplaire gardé déjà rangé': 'The kept copy is already sorted',
  'Relance un scan pour le retrouver.': 'Rescan to find it again.',

  /* ScanState */
  'Fais le tri.': 'Sort it out.',
  'Le dossier est analysé en quelques secondes. Rien ne bouge tant que tu ne l\'as pas confirmé.':
    'Your folder is scanned in seconds. Nothing moves until you confirm.',
  'Scanner Téléchargements': 'Scan Downloads',
  'scan en cours · {s} s': 'scanning · {s} s',
  'Démarrage': 'Starting',
  'Indexation': 'Indexing',
  'Fichiers incomplets': 'Incomplete files',
  'Recherche des doublons': 'Looking for duplicates',
  'Vérification des zips': 'Checking zips',
  'Recherche de copies sauvegardées': 'Looking for backed-up copies',
  'Classement': 'Sorting',

  /* Thumb */
  'fichier': 'file',

  /* lib : provenance */
  'Retéléchargeable depuis {label}': 'Re-downloadable from {label}',
  'Lien de transfert qui expire : pas de deuxième chance': 'Transfer link that expires: no second chance',
  'Téléchargé depuis {label}': 'Downloaded from {label}',
}

export default en
