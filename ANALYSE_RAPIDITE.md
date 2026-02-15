# Analyse rapidite (15/02/2026)

## Changements appliques
- UI: boutons lateraux redesign + logique action directe pour `חופשות וחגים` (plus de bouton secondaire).
- UI: bloc `כיתה + תאריכים` compacte (colonnes + CSS).
- Export: cache key robuste (`_export_cache_key`) pour eviter de regenerer PNG/HTML si le contenu n'a pas change.
- Firestore: `list_schools_for_user` cachee 20s + invalidation automatique quand permissions/ecole changent.

## Points lents detectes
1. Generation PNG (`app.py:897`, `app.py:933`)
- Lance Playwright + attend 1500ms.
- C'est le poste le plus couteux quand le cache est invalide.

2. Rendu tableau calendrier (`app.py:1592`, `app.py:1629`)
- Beaucoup de widgets Streamlit (7 colonnes x N semaines x popovers).
- Le cout augmente vite quand la plage de dates est large.

3. Lookup ecoles utilisateur (fallback Firestore) (`db_manager.py:315`, `db_manager.py:341`)
- Si `user_schools` manque, fallback peut scanner toutes les ecoles.
- Le cache ajoute reduit deja fortement l'impact sur les reruns.

## Recommandations (priorite)
1. Garder la plage date courte par defaut (deja en place) et limiter visuellement a 2-3 mois.
2. Pour PNG: rendre la generation "on-demand" (bouton explicite) au lieu de pre-generation au chargement.
3. Continuer a alimenter `user_schools` pour eviter le fallback global.
4. Si besoin de plus: ajouter memoisation par semaine visible pour reduire le cout des reruns.
