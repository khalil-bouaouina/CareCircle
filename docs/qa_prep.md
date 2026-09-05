# Préparation aux questions du Jury — CareCircle (MuslimHacks)

Ce document rassemble les réponses prêtes à l’emploi pour les questions types prévues dans la grille officielle d'évaluation (`JUDGING_CRITERIA.md`, Section 4).

---

## 1. Implémentation Technique

### Quel est le format de livraison ?
> **Réponse :** C'est une application Web responsive à trois surfaces distinctes :
> 1. Une console dense orientée bureau pour l'aidant familial.
> 2. Une interface ultra-accessible (grands caractères ≥ 20px, fort contraste) pour l’aîné.
> 3. Une vue mobile allégée à usage unique pour l’auxiliaire de vie.

### Quelles technologies et frameworks avez-vous utilisés ?
> **Réponse :** **FastAPI** (Python 3.12) avec **SQLite (mode WAL)** pour une persistance rapide et sans dépendance lourde, **Jinja2** et **Tailwind CSS** pour le rendu côté serveur accessible, sans build-step ni framework frontend lourd (pas de React/Node). Pour l'IA, nous utilisons l'API Anthropic (Claude) avec un fallback déterministe local sans surcoût.

### Comment fonctionne le système en coulisses ?
> **Réponse :** L’architecture repose sur un principe clé : **un point d’étranglement unique pour la confidentialité (`services.visibility.resolve`)**. Aucune requête n'accède directement aux préférences. Avant chaque affichage ou génération de brief, le filtre vérifie l'identité de l'intervenant, la tâche prévue et la plage horaire. Chaque accès est consigné de façon immuable dans un journal (`access_log`).

### Avez-vous développé cela de zéro pendant le hackathon ?
> **Réponse :** Oui, la modélisation des données, le moteur de visibilité, le système de jetons éphémères pour intervenants, la gestion d'authentification avec sel PBKDF2 et sessions signées ont tous été conçus et implémentés pour ce projet.

### Quels compromis techniques avez-vous faits faute de temps ?
> **Réponse :** Nous n'avons pas intégré de serveur SMS externe (Twilio) pour envoyer le lien à l'intervenant (le lien est copiable/affiché à l'écran), et nous sommes restés sur SQLite avec WAL plutôt qu'un cluster PostgreSQL, ce qui est amplement suffisant pour plusieurs milliers de visites simultanées.

---

## 2. Impact et Utilisateurs

### Qui est l’utilisateur cible et comment utilise-t-il l’application ?
> **Réponse :** Deux cibles principales :
> 1. Les familles musulmanes et aidants naturels qui s'occupent d'un proche âgé dépendant.
> 2. L'aîné lui-même qui garde le contrôle de son intimité et de sa dignité.
> 3. L'auxiliaire de vie qui arrive au domicile et sait immédiatement quoi faire sans commettre d'impair culturel ou spirituel.

### Combien de personnes pourraient en bénéficier ?
> **Réponse :** Rien qu'au Canada, plus de 8 millions de personnes sont aidants naturels. Au sein des communautés issues de l'immigration et musulmanes, le maintien à domicile des aînés est un devoir filial et religieux fondamental. La barrière de la langue et les tabous culturels rendent cette solution vitale.

### Comment mesurez-vous le succès du projet ?
> **Réponse :** Par la réduction des incidents lors des visites (refus de soin, incompréhensions alimentaires/pudeur), le taux de complétion des visites par les auxiliaires et le sentiment d'autonomie exprimé par l'aîné via son journal d'accès.

---

## 3. Démo et Fonctionnalités

### La démo est-elle fonctionnelle ou simulée ?
> **Réponse :** **Elle est 100% fonctionnelle.** La base de données est réelle, l'authentification avec sessions signées fonctionne, la création de visite génère un vrai jeton cryptographique à usage unique, et le checkout de l'auxiliaire brûle le jeton et enregistre le rapport dans la base.

### Quelle est la fonctionnalité la plus importante que vous avez finalisée ?
> **Réponse :** Le **moteur de visibilité contextuelle** couplé au **lien intervenant sans compte**. L'auxiliaire n'a pas besoin de créer d'identifiant : un simple scan QR ou clic sur un lien sécurisé lui donne les 6 consignes essentielles pour sa tâche de 14h, et rien d'autre.

### Quelle a été la partie la plus difficile à concevoir ?
> **Réponse :** Concevoir une sécurité stricte sans complexifier l'expérience : concilier le besoin de discrétion (l'aîné ne veut pas que son fils sache certaines choses intimes) avec la coordination collective, tout en restant dans un cadre légal protecteur.

---

## 4. Modèle Économique et Scalabilité

### Quel est votre modèle économique ?
> **Réponse :** Modèle B2B2C :
> 1. Gratuit / Freemium pour les familles (1 aîné).
> 2. Abonnement SaaS pour les agences de maintien à domicile (CLSC, agences privées) pour sécuriser et fluidifier leurs interventions et réduire le turnover de leurs soignants.

### Combien coûte le fonctionnement de la solution ?
> **Réponse :** Moins de 10 $ / mois pour un déploiement standard. Pas de base de données managée coûteuse requise, code ultra-optimisé en Python/FastAPI, et coût d'API IA quasi-nul grâce au cache et au fallback déterministe.

---

## 5. Données et Confidentialité (Crucial)

### Quelles données le projet utilise-t-il ?
> **Réponse :** Uniquement des phrases courtes de préférences comportementales et organisationnelles rédigées par des humains (ex. *"Maman préfère une femme pour la toilette"*, *"Ne pas déranger pendant la prière de l'Asr"*). Aucun diagnostic médical ni numéro d'assurance sociale n'est stocké.

### Comment gérez-vous la confidentialité ?
> **Réponse :**
> - Données scellées par `elder_id`.
> - Jetons intervenants hachés en **SHA-256**, valables seulement pendant la fenêtre horaire de la visite et brûlés après soumission.
> - Journal d'accès immuable (`append-only`) consultable par l'aîné.
> - Hachage des mots de passe avec sel aléatoire (`PBKDF2-SHA256`).

### La solution dépend-elle d'un LLM ?
> **Réponse :** **Non, elle n'est pas dépendante.** L'IA n'intervient que pour synthétiser les consignes en un brief de 6 lignes maximum. Si l'API est coupée, en panne ou sans clé, un algorithme déterministe local prend le relais immédiatement sans aucune interruption de service. De plus, l'IA ne peut jamais inventer de faits : chaque ligne doit correspondre à un identifiant vérifié en base.

---

## 6. Pourquoi ce projet doit gagner (Conclusion)

> **Message clé :**  
> *"CareCircle ne résout pas seulement un problème logistique de soins : il protège la dignité, la foi et l'intimité de nos aînés les plus vulnérables. C'est une solution techniquement mature, déjà fonctionnelle, sécurisée par conception et prête à être déployée immédiatement pour soulager des milliers de familles."*

