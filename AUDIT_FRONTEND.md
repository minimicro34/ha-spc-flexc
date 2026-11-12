# Audit du frontend SPC FlexC

Date : 12 novembre 2026.

L’audit confirme plusieurs défauts que le scanner ne détecte pas : **perte du focus clavier, styles non encapsulés et nettoyage incomplet du cycle de vie**. Aucun fichier du dépôt n’a été modifié pendant l’audit ; aucun commit ni PR n’a été créé. Ce document consigne le rapport à la demande du propriétaire du dépôt.

## Périmètre et méthode

Dépôt analysé au commit [`f0bec0c6b24de6eb2ea26a35c80920da3e7a356e`](https://github.com/minimicro34/ha-spc-flexc/tree/f0bec0c6b24de6eb2ea26a35c80920da3e7a356e), principalement `frontend/src/` et le bundle distribué dans `custom_components/spc_flexc/www/`.

Les deux dépôts GitHub étaient accessibles :

- Projet : <https://github.com/minimicro34/ha-spc-flexc>.
- Compétence officielle : <https://github.com/GoogleChrome/modern-web-guidance>, consultée au commit `4dd968349e54ca45a05dd5c818fb035c9054b022`.

La commande officielle `npx -y modern-web-guidance@latest install` a installé **Modern Web Guidance 1.0.0**, hors du dépôt, dans `/workspace/mwg-tooling`. La première tentative dans `/tmp` avait échoué parce que son répertoire `.agents` était en lecture seule. La télémétrie a été désactivée avec `DISABLE_TELEMETRY=1`.

Vérifications effectuées :

- Scanner officiel sur les deux répertoires.
- Lecture du code et consultation des guides officiels.
- `npm run check` dans `frontend/` : syntaxe valide et bundle conforme aux sources, version 1.0.19.
- Essais avec le bundle distribué dans **Chromium 156.0.8078.79**, via Playwright, avec données Home Assistant simulées, sans connexion ni commande vers une centrale.

Ces essais ne constituent pas une validation complète dans Lovelace. Les composants Home Assistant et une installation réelle n’étaient pas chargés dans la page de test.

## Résultats du scanner Modern Web Guidance

Commandes exécutées, avec la version 1.0.0 résolue au moment de l’audit :

```sh
npx -y modern-web-guidance@latest legacy-scan /workspace/ha-spc-flexc/frontend/src --json
npx -y modern-web-guidance@latest legacy-scan /workspace/ha-spc-flexc/custom_components/spc_flexc/www --json
```

| Périmètre | Résultat |
| --- | --- |
| `frontend/src/` | **0 détection** |
| `custom_components/spc_flexc/www/` | **0 détection** |

Pour chacun des scans, le résultat JSON indique `totalFindings: 0`, `guides: []`, `activeRuleCount: 35` et `activeGuideCount: 33`.

Le scanner annonce **35 règles, couvrant 33 guides**, soit environ 20 % du corpus. Ce résultat signifie uniquement qu’aucun motif couvert n’a été reconnu. Il ne certifie ni l’accessibilité, ni les performances, ni la compatibilité navigateur.

Les constats suivants proviennent de l’analyse du code et des essais réalisés pendant l’audit, **pas du scanner**.

## Problèmes confirmés

Les références de lignes correspondent au commit audité. Les lignes du bundle désignent le fichier `custom_components/spc_flexc/www/ha-spc-flexc-card.js`.

### 1. Perte du focus lors des mises à jour

**Gravité : élevée. Confirmation : code et essai Chromium avec données simulées.**

Même avec un état inchangé, `.content` est remplacé. Dans Chromium, un bouton de secteur focalisé est détruit et `document.activeElement` devient `BODY`. Le changement d’onglet détruit également le bouton focalisé.

**Localisation :** [frontend/src/ha-spc-flexc-card.js](frontend/src/ha-spc-flexc-card.js), lignes 3259–3285 ; bundle : mêmes lignes.

**Recommandation :** conserver les éléments interactifs et mettre à jour leurs propriétés ou leur texte. Un rendu Lit avec identités stables convient à Lovelace, mais une mise à jour DOM ciblée suffit. Préserver explicitement le focus lorsque le remplacement est nécessaire.

### 2. Nettoyage du scheduler non enregistré comme callback de cycle de vie

**Gravité : moyenne. Confirmation : code, guide officiel et essai Chromium.**

`disconnectedCallback` est remplacé après `customElements.define()`. Le navigateur conserve le callback enregistré initialement. Lors de l’essai, une frame reste planifiée après retrait, puis la carte construit son DOM alors qu’elle est déconnectée. Le désabonnement initial reste, lui, enregistré.

**Localisation :**

- [frontend/src/ha-spc-flexc-card.js](frontend/src/ha-spc-flexc-card.js), ligne 3511.
- [frontend/src/spc-flexc-render-scheduler.js](frontend/src/spc-flexc-render-scheduler.js), lignes 161–194.
- Bundle : lignes 3511 et 5840–5873.

**Recommandation :** définir tous les callbacks avant l’enregistrement du Custom Element, ou faire appeler un auxiliaire de nettoyage par le callback initial. Annuler les frames au retrait et prévoir la réinsertion.

### 3. Styles débordant de la carte

**Gravité : moyenne. Confirmation : code et essai Chromium.**

Les composants utilisent le Light DOM avec des sélecteurs génériques : `.title`, `.card`, `ha-card`, mais aussi `label`, `input` et `select` dans l’éditeur. Dans Chromium, un `.title` extérieur prend la taille de 24 px définie par la carte. Le sélecteur `:host` n’a pas l’effet d’encapsulation attendu sans Shadow DOM.

**Localisation :** [frontend/src/ha-spc-flexc-card.js](frontend/src/ha-spc-flexc-card.js), lignes 2409–2459, notamment 2412–2459, et 3424–3456 ; bundle : mêmes lignes.

**Recommandation :** utiliser un Shadow DOM ouvert pour la carte et l’éditeur, en conservant les variables CSS Home Assistant héritées. À défaut, préfixer systématiquement les sélecteurs par les noms des composants.

### 4. Secteurs impossibles à développer si le stockage refuse les écritures

**Gravité : moyenne. Confirmation : code et essai Chromium avec erreur de stockage simulée.**

Le commentaire annonce une conservation en mémoire, mais aucun état mémoire n’est conservé : chaque rendu relit le stockage. Lors de l’essai avec `Storage.prototype.setItem()` levant `SecurityError`, après clic, `aria-expanded` reste `false`.

**Localisation :** [frontend/src/spc-flexc-area-cards.js](frontend/src/spc-flexc-area-cards.js), lignes 14–55 ; bundle : lignes 4809–4850.

**Recommandation :** garder l’état développé/replié en mémoire et utiliser `localStorage` comme persistance facultative. La navigation doit fonctionner lorsque le stockage est indisponible.

### 5. Onglet actif non indiqué programmatiquement

**Gravité : moyenne. Confirmation : balisage et DOM Chromium.**

L’état actif repose uniquement sur `.active`. Les boutons restent activables au clavier, mais aucune sélection ARIA ni relation avec le panneau n’est exposée par ce balisage.

**Localisation :** [frontend/src/spc-flexc-outputs.js](frontend/src/spc-flexc-outputs.js), lignes 287–291 ; bundle : lignes 3822–3826.

**Recommandation :** implémenter le modèle complet `tablist` / `tab` / `tabpanel`, avec `aria-selected`, relations et navigation clavier. Une solution plus simple peut conserver des boutons et exposer explicitement leur état, sans ajouter des rôles de tabs incomplets.

### 6. Travail répété sur chaque affectation de hass

**Gravité : moyenne — coût confirmé, impact à mesurer.**

Aucun filtre ne vérifie si les données utiles ont changé. Un essai avec état inchangé déclenche trois appels à `_getZones()`. Cette méthode copie et parcourt tous les états Home Assistant ; le rendu reconstruit aussi le markup et les styles. Le scheduler regroupe les appels dans une frame, sans supprimer ce travail.

**Localisation :**

- [frontend/src/ha-spc-flexc-card.js](frontend/src/ha-spc-flexc-card.js), lignes 59–65 et 438–452.
- [frontend/src/spc-flexc-render-scheduler.js](frontend/src/spc-flexc-render-scheduler.js), à partir de la ligne 92.
- Bundle : lignes 59, 438 et 5771.

**Recommandation :** invalider le rendu sur les entités réellement utilisées, la configuration et la langue. Parcourir directement les identifiants du panneau ; calculer les zones une fois par rendu et réutiliser le résultat.

### 7. Libellés des onglets conservés dans l’ancienne langue

**Gravité : faible. Confirmation : code et essai Chromium.**

La conservation du bandeau compare les identifiants et l’onglet actif, sans actualiser les libellés. Lors de l’essai `hass.locale.language` anglais → français, l’onglet reste « General », alors que la traduction courante retourne « Général ».

**Localisation :** [frontend/src/ha-spc-flexc-card.js](frontend/src/ha-spc-flexc-card.js), lignes 3264–3283 ; bundle : mêmes lignes.

**Recommandation :** actualiser les textes des onglets conservés lors d’un changement de langue. Appliquer aussi cette invalidation à l’éditeur, dont le setter `hass` ne rend qu’à la première affectation.

### 8. Titres visuels sans sémantique de titre

**Gravité : faible. Confirmation : code et DOM Chromium.**

Le titre principal et les titres techniques sont des `div`. Le rendu général testé ne contient aucun élément de titre.

**Localisation :** [frontend/src/ha-spc-flexc-card.js](frontend/src/ha-spc-flexc-card.js), lignes 3243 et 1556 ; bundle : mêmes lignes.

**Recommandation :** employer des titres HTML adaptés à la hiérarchie du dashboard. Ne pas ajouter un nouveau `<main>` ou un `<h1>` à chaque carte.

## Points nécessitant des tests supplémentaires

Ces points ne sont pas des défauts d’usage confirmés par le scanner ou par les essais effectués.

| Point | Évidence disponible | Validation recommandée |
| --- | --- | --- |
| **Annonces d’alarme répétées** | La région `role="alert"` / `aria-live="assertive"` est remplacée même lorsque l’alarme reste identique : `frontend/src/ha-spc-flexc-card.js`, lignes 2377 et 3277 ; bundle : mêmes lignes. | Tester NVDA/Firefox et VoiceOver/Safari. Conserver une région stable et annoncer les changements utiles ; une alarme justifie l’urgence, ses répétitions inchangées peuvent devenir gênantes. |
| **Recalculs de layout et à-coups** | Le scheduler lit les dimensions, écrit `minHeight`, remplace le contenu puis restaure les positions de défilement : `frontend/src/spc-flexc-render-scheduler.js`, lignes 100–149. | Profiler dans Lovelace avec plusieurs cartes et beaucoup de zones. Aucune valeur INP, CLS ou durée de tâche n’a été mesurée ici ; aucun dépassement ne peut être affirmé. |
| **Contrastes et zoom** | Plusieurs couleurs dépendent du thème Home Assistant ; certains états utilisent des couleurs de repli. | Tester thèmes clair/sombre, couleurs forcées, zoom et affichage mobile. Aucun échec de contraste n’est confirmé par cet audit. |

## Compatibilité navigateur et limites des outils

Aucune incompatibilité bloquante n’a été reproduite dans Chromium. **Firefox, Safari, les WebViews Companion et les lecteurs d’écran n’ont pas été testés** ; il ne s’agit pas d’outils ayant échoué pendant l’audit. Aucun résultat Lighthouse ou axe-core n’a été produit.

Les fonctions modernes demandent une appréciation nuancée :

- Les **container queries** de [frontend/src/spc-flexc-responsive.js](frontend/src/spc-flexc-responsive.js), à partir de la ligne 76, disposent d’une présentation de base en une colonne : leur absence dégrade surtout la mise en page.
- `:has()` et `color-mix()` dans [frontend/src/spc-flexc-outputs.js](frontend/src/spc-flexc-outputs.js), autour de la ligne 344, nécessitent des essais si des WebViews anciennes font partie des cibles. Leur présence seule ne prouve pas un défaut.
- `moveBefore()` ne corrigerait pas le remplacement par de nouveaux nœuds. Si cette API est retenue pour de vrais déplacements, le guide officiel impose une détection de capacité et un repli, notamment pour Safari.

Il faut définir les versions navigateur et Companion effectivement prises en charge avant de recommander des polyfills.

Modern Web Guidance et son scanner étaient disponibles et ont fonctionné. Le seul échec d’installation rencontré était lié au répertoire `.agents` en lecture seule sous `/tmp` ; il a été contourné en installant la compétence dans un répertoire distinct hors du projet.

## Guides Modern Web Guidance consultés

Les guides suivants ont été consultés :

- `accessibility`.
- `shadow-dom`.
- `move-dom-element-without-losing-state`.
- `custom-elements`.
- `performance`.
- `interactions-in-complex-layouts`.

Ils étayent les recommandations, notamment la règle selon laquelle les callbacks de cycle de vie sont mémorisés à l’enregistrement du composant. **Aucune correction n’a été appliquée.** Les problèmes confirmés restent des conclusions de l’audit manuel ou des essais Chromium, distinctes du résultat nul du scanner.

Les priorités sont la conservation du focus, l’encapsulation CSS et l’enregistrement correct du nettoyage du scheduler. Le dépôt est resté propre après l’audit initial ; le présent document constitue uniquement la restitution demandée.
