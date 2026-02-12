# Installation rapide de gcloud CLI - Guide

## Option 1 : Installation via l'interface graphique (En cours)

L'installateur GoogleCloudSDKInstaller.exe est en cours de téléchargement/exécution.

**Une fois la fenêtre d'installation ouverte :**
1. Cliquez sur "Next" / "Suivant"
2. **IMPORTANT : Cochez "Add gcloud to PATH"**
3. Choisissez "Bundled Python" (recommandé)
4. Terminez l'installation
5. **Fermez et rouvrez PowerShell complètement**

---

## Option 2 : Installation manuelle rapide (Alternative)

Si l'installateur ne fonctionne pas, suivez ces étapes :

### Étape 1 : Télécharger l'archive ZIP

```powershell
# Télécharger gcloud CLI (version complète)
Invoke-WebRequest -Uri "https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-windows-x86_64.zip" -OutFile "$env:USERPROFILE\Downloads\google-cloud-cli.zip"
```

### Étape 2 : Extraire l'archive

```powershell
# Extraire dans C:\gcloud
Expand-Archive -Path "$env:USERPROFILE\Downloads\google-cloud-cli.zip" -DestinationPath "C:\" -Force
```

### Étape 3 : Exécuter le script d'installation

```powershell
# Installer et configurer PATH
C:\google-cloud-sdk\install.bat
```

Répondez aux questions :
- **Create shortcuts?** → `Y` (Yes)
- **Update PATH?** → `Y` (Yes)
- **Run gcloud init?** → `N` (No, on le fera après)

### Étape 4 : Redémarrer PowerShell

Fermez COMPLÈTEMENT PowerShell et rouvrez-le.

### Étape 5 : Vérifier l'installation

```powershell
gcloud --version
```

---

## Option 3 : Ajout manuel au PATH (si gcloud est déjà installé quelque part)

Si gcloud est installé mais pas reconnu :

```powershell
# Trouver où gcloud est installé
Get-ChildItem -Path C:\ -Filter gcloud.cmd -Recurse -ErrorAction SilentlyContinue | Select-Object FullName

# Ajouter au PATH (remplacez CHEMIN par le dossier trouvé)
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";C:\CHEMIN\google-cloud-sdk\bin", [EnvironmentVariableTarget]::User)
```

Redémarrez PowerShell après.

---

## Après installation réussie

### 1. Connexion à Google Cloud

```powershell
gcloud auth login
```

### 2. Configurer le projet Firebase

```powershell
# Lister vos projets
gcloud projects list

# Définir le projet actif
gcloud config set project VOTRE-PROJECT-ID
```

### 3. Authentification pour Firestore

```powershell
# Pour les applications (utilise la clé de service)
$env:GOOGLE_APPLICATION_CREDENTIALS = "C:\Users\USER\Downloads\sample\firestore-key.json.json"

# OU connexion par défaut de l'application
gcloud auth application-default login
```

---

## Vérification complète

```powershell
# Version
gcloud --version

# Compte actif
gcloud auth list

# Projet actif
gcloud config list
```

---

## Problèmes courants

### "gcloud n'est pas reconnu"
→ Redémarrez PowerShell complètement
→ Vérifiez que le PATH contient le dossier google-cloud-sdk\bin

### "Python not found"
→ Réinstallez avec l'option "Bundled Python"

### "Permission denied"
→ Exécutez PowerShell en tant qu'administrateur
