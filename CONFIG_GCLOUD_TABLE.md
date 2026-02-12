# Configuration gcloud pour le projet Firebase "table"

## Si gcloud n'est pas encore installé

### Méthode la plus simple : Installation manuelle

1. **Téléchargez l'installateur** depuis votre navigateur :
   https://dl.google.com/dl/cloudsdk/channels/rapid/GoogleCloudSDKInstaller.exe

2. **Double-cliquez** sur le fichier téléchargé

3. **Suivez l'assistant** :
   - ✅ Cochez "Add gcloud to PATH"
   - ✅ Choisissez "Bundled Python"
   - Cliquez "Install"

4. **Fermez et rouvrez PowerShell**

5. **Vérifiez** :
   ```powershell
   gcloud --version
   ```

---

## Configuration du projet "table"

Une fois gcloud installé, configurez votre projet Firebase :

### 1. Connexion à votre compte Google

```powershell
gcloud auth login
```

Cette commande ouvrira votre navigateur pour vous connecter.

### 2. Configuration du projet "table"

```powershell
# Définir "table" comme projet actif
gcloud config set project table

# Vérifier la configuration
gcloud config list
```

### 3. Authentification pour Firestore

Vous avez déjà une clé de service : `firestore-key.json.json`

**Option A : Utiliser la clé de service (recommandé pour les scripts)**

```powershell
# Définir la variable d'environnement
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\USER\Downloads\sample\firestore-key.json.json"

# Vérifier
echo $env:GOOGLE_APPLICATION_CREDENTIALS
```

**Pour rendre cela permanent :**

```powershell
# Ajouter à votre profil PowerShell
Add-Content $PROFILE "`n`$env:GOOGLE_APPLICATION_CREDENTIALS = 'C:\Users\USER\Downloads\sample\firestore-key.json.json'"
```

**Option B : Authentification par défaut de l'application**

```powershell
gcloud auth application-default login
```

---

## Vérification complète

```powershell
# 1. Version de gcloud
gcloud --version

# 2. Compte connecté
gcloud auth list

# 3. Projet actif
gcloud config get-value project
# Devrait afficher : table

# 4. Tester l'accès à Firestore
gcloud firestore databases list --project=table
```

---

## Utilisation avec Python (pour votre app Streamlit)

Dans votre code Python :

```python
import firebase_admin
from firebase_admin import credentials, firestore

# Option 1 : Utiliser la clé de service
cred = credentials.Certificate("firestore-key.json.json")
firebase_admin.initialize_app(cred)

# Option 2 : Utiliser les credentials par défaut (si gcloud auth est configuré)
# firebase_admin.initialize_app()

# Accéder à Firestore
db = firestore.client()

# Test
schools = db.collection('schools').get()
for school in schools:
    print(school.to_dict())
```

---

## Commandes utiles pour le projet "table"

```powershell
# Lister les bases de données Firestore
gcloud firestore databases list --project=table

# Lister les collections (nécessite firestore-tools)
gcloud firestore operations list --project=table

# Voir les détails du projet
gcloud projects describe table

# Activer des API si nécessaire
gcloud services enable firestore.googleapis.com --project=table
```

---

## En cas de problème

**Erreur "Project not found" :**
```powershell
# Vérifier que le projet existe
gcloud projects list

# Si "table" n'apparaît pas, le vrai ID du projet pourrait être différent
# Cherchez dans la console Firebase : https://console.firebase.google.com
```

**Erreur de permissions :**
```powershell
# Assurez-vous que votre compte a les permissions nécessaires
gcloud projects get-iam-policy table
```

**Réinitialiser la configuration :**
```powershell
gcloud config unset project
gcloud config set project table
```
