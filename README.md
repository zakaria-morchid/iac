# Infra to GitLab

Décrivez vos étapes d’infrastructure dans `infra.yml`, puis générez les jobs GitLab CI correspondants. Le même manifeste permet aussi d’exécuter une étape localement avec la commande `infra`.

Le projet propose des actions pour déclencher un pipeline GitLab, lancer un job template AWX et afficher un message de démonstration. Les manifests sont validés avec Pydantic et les résultats des actions sont conservés au format JSON pour les étapes suivantes.

## Installation

Python **3.12 ou supérieur** est requis. Depuis la racine du dépôt, créez un environnement virtuel.

```bash
python -m venv .venv
```

Activez-le sous PowerShell.

```powershell
.\.venv\Scripts\Activate.ps1
```

Ou sous Linux et macOS.

```bash
source .venv/bin/activate
```

Installez ensuite le projet.

```bash
python -m pip install -e .
```

Les commandes `infra` et `python -m infra_to_gitlab` donnent accès à la même interface.

## Démarrage rapide

Validez le manifeste et générez le fichier CI.

```bash
python -m infra_to_gitlab validate infra.yml
python -m infra_to_gitlab generate infra.yml --output .gitlab-ci-generated.yml
```

Pour générer une CI dont chaque job simule son action, ajoutez `--dry-run`.

```bash
python -m infra_to_gitlab generate infra.yml --output .gitlab-ci-generated.yml --dry-run
```

Cette commande écrit bien `.gitlab-ci-generated.yml`. Les scripts des jobs contiennent alors l’option `--dry-run`.

```yaml
message_1:
  stage: test
  when: on_success
  allow_failure: false
  script:
    - infra run infra.yml --step message_1 --dry-run
  artifacts:
    paths:
      - .infra-outputs/message_1.json
    expire_in: 1 day
```

Pour exécuter uniquement une étape locale en simulation, utilisez directement `run`.

```bash
infra run infra.yml --step message_1 --dry-run
```

## Afficher le schéma du manifeste

Le schéma JSON est généré directement depuis les modèles Pydantic du projet. Aucun fichier `infra.yml` n’est nécessaire pour cette commande.

```bash
infra schema
python -m infra_to_gitlab schema
```

Pour l’enregistrer dans un fichier, redirigez la sortie.

```bash
python -m infra_to_gitlab schema > infra.schema.json
```

Pour afficher ou enregistrer le schéma au format YAML, utilisez `--format yaml`. L’alias `--format yml` est aussi accepté.

```bash
python -m infra_to_gitlab schema --format yaml
python -m infra_to_gitlab schema --format yaml > infra.schema.yml
```

Le contenu suit la spécification JSON Schema, avec une représentation en YAML.

Le schéma décrit les champs, les types, les valeurs par défaut et les contraintes déclarées dans les modèles. Les validations personnalisées, comme l’unicité des `id` et l’existence d’une action enregistrée, restent vérifiées par `infra validate`. Les `inputs` des actions sont représentés par un dictionnaire libre.

## Écrire un manifeste

```yaml
global:
  env: dev

steps:
  - id: prepare
    name: preparation
    action: example:echo
    inputs:
      message: "Environnement ${{ global.env }}"

  - id: deploy_api
    name: deployment
    action: example:echo
    inputs:
      message: "Déploiement API sur ${{ global.env }}"

  - id: deploy_worker
    name: deployment
    action: example:echo
    inputs:
      message: "Déploiement worker sur ${{ global.env }}"

  - id: report
    name: verification
    action: example:echo
    inputs:
      message: "Résultat API — ${{ steps.deploy_api.outputs.message }}"
```

### Jobs, stages et parallélisme

- `id` est l’identifiant unique de l’étape et le nom du job GitLab. Il accepte les lettres ASCII, chiffres, tirets et underscores.
- `name` est le nom du stage GitLab. S’il est absent ou vaut `null`, le stage prend la valeur de `id`.
- Plusieurs étapes peuvent partager le même `name`. Elles appartiennent alors au même stage et peuvent s’exécuter en parallèle, selon la disponibilité des runners.
- La liste des stages contient chaque nom une seule fois, dans l’ordre de sa première apparition dans le manifeste.
- Deux étapes ayant le même `id` sont refusées à la validation, même si leurs noms de stage diffèrent.

L’exemple produit les stages `preparation`, `deployment`, puis `verification`. Les jobs `deploy_api` et `deploy_worker` partagent le stage `deployment`.

### Champs d’une étape

- `id` est obligatoire.
- `action` est obligatoire et doit correspondre à une action enregistrée.
- `name` est facultatif et doit contenir au moins un caractère lorsqu’il est renseigné.
- `manual` vaut `false` par défaut. Avec `true`, le job généré attend un déclenchement manuel.
- `allow_failure` vaut `false` par défaut. Ce champ est transmis au job GitLab.
- `enabled` vaut `true` par défaut. Avec `false`, le job reçoit une règle `when: never` et l’exécution locale est refusée.
- `inputs` est un dictionnaire libre, vide par défaut. Chaque action détermine les valeurs qu’elle utilise.

Le manifeste contient au moins une étape. Les champs inconnus sont refusés au niveau du manifeste et des étapes. La validation vérifie leur structure et l’existence des actions. Les paramètres propres à chaque action sont utilisés lors de son exécution.

Les options `manual` et `allow_failure` contrôlent le comportement GitLab CI. Une commande locale `infra run` lance directement l’étape sélectionnée.

Pour qu’une étape manuelle bloque les stages suivants jusqu’à son lancement et sa réussite, utilisez `manual: true` avec `allow_failure: false`. Avec `manual: true` et `allow_failure: true`, le job est optionnel et les stages suivants peuvent démarrer sans son exécution. Le manifeste fourni configure les deux étapes manuelles comme bloquantes.

## Variables et outputs

Les expressions peuvent utiliser les variables de `global`, les variables d’environnement via `env` et les outputs d’une étape, identifiée par son `id`.

```yaml
inputs:
  environment: ${{ global.env }}
  branch: ${{ env.CI_COMMIT_REF_NAME }}
  pipeline: ${{ steps.trigger.outputs.pipeline_id }}
  message: "Pipeline ${{ steps.trigger.outputs.pipeline_id }} sur ${{ global.env }}"
```

Les syntaxes `${{ global.env }}` et `{{ global.env }}` sont toutes deux acceptées. La résolution parcourt aussi les listes et les dictionnaires imbriqués.

Utilisez `${{ env.NOM_VARIABLE }}` ou `{{ env.NOM_VARIABLE }}` pour lire une variable du processus qui exécute l’étape, en local ou dans le job GitLab. Les valeurs d’environnement sont des chaînes de caractères. Une variable absente provoque une erreur explicite. Une variable définie avec une valeur vide est acceptée.

Exemple sous PowerShell avec une variable d’environnement et une variable globale dans le même message.

```powershell
$env:DEPLOY_REGION = "eu-west-1"
```

```yaml
global:
  env: dev
steps:
  - id: show_environment
    name: preparation
    action: example:echo
    inputs:
      message: "Environnement ${{ global.env }} en ${{ env.DEPLOY_REGION }}"
```

Les références `env` sont résolues à l’exécution de `run`, y compris en dry run. La génération de CI conserve les expressions dans le manifeste et utilise les variables disponibles dans chaque job lors de son exécution.

Une expression occupant toute la valeur conserve le type de la donnée résolue. Une expression insérée dans un texte est convertie en chaîne.

Après une exécution réussie, les résultats sont écrits dans `.infra-outputs/<id>.json`, relativement au répertoire courant. Une nouvelle exécution de la même étape remplace son fichier. En local, exécutez les étapes dépendantes depuis le même répertoire.

```bash
infra run infra.yml --step trigger
infra run infra.yml --step consume
```

Dans la CI générée, chaque job publie son fichier d’outputs comme artifact avec une expiration d’un jour. Placez une étape qui consomme des outputs dans un stage ultérieur à celui qui les produit. Deux jobs du même stage ne disposent pas d’un ordre d’exécution garanti.

## Actions disponibles

### `example:echo`

Retourne le message fourni dans l’output `message`.

```yaml
- id: greeting
  name: test
  action: example:echo
  inputs:
    message: Bonjour
```

### `gitlab:pipeline:trigger`

Déclenche un pipeline pour un projet GitLab et retourne `project_id` et `pipeline_id`.

```yaml
- id: trigger
  name: deployment
  action: gitlab:pipeline:trigger
  inputs:
    projectId: 456
    branch: main
    variables:
      ENV: ${{ global.env }}
```

`projectId` est requis et peut contenir un identifiant ou un chemin de projet. `branch` vaut `main` par défaut. Les valeurs de `variables` sont transmises comme chaînes de caractères.

L’action utilise `GITLAB_TOKEN` pour l’authentification. L’URL d’API vient de `CI_API_V4_URL` si cette variable est renseignée. Sinon, elle est construite à partir de `GITLAB_URL`, par exemple `https://gitlab.example.com`.

### `awx:job-template:launch`

Lance un job template AWX et retourne `job_id`.

```yaml
- id: launch_awx
  name: deployment
  action: awx:job-template:launch
  inputs:
    job_template: vault-job-template
    inventory: vault-inventory
    extra_vars:
      env: ${{ global.env }}
      vault: test
```

`job_template` et `inventory` sont requis. Chacun accepte un identifiant numérique ou un nom. Une recherche par nom doit retourner exactement une ressource. `extra_vars` est facultatif et vaut un dictionnaire vide par défaut.

Configurez `AWX_URL`, par exemple `https://awx.example.com`, et `AWX_TOKEN`. Le template doit autoriser les paramètres transmis via ses réglages *Prompt on Launch*. Si AWX signale des champs ignorés, l’action retourne une erreur.

Les actions GitLab et AWX retournent dès que le lancement distant est accepté. Elles ne suivent pas la fin du pipeline ou du job distant.

## Configurer les accès

Pour une exécution locale sous PowerShell, renseignez les variables correspondant aux actions utilisées.

```powershell
$env:GITLAB_URL = "https://gitlab.example.com"
$env:GITLAB_TOKEN = "<token>"
$env:AWX_URL = "https://awx.example.com"
$env:AWX_TOKEN = "<token>"
```

Sous Linux et macOS, utilisez `export`.

```bash
export GITLAB_URL="https://gitlab.example.com"
export GITLAB_TOKEN="<token>"
export AWX_URL="https://awx.example.com"
export AWX_TOKEN="<token>"
```

En CI, configurez les tokens dans les variables CI/CD du projet, avec le masquage et la protection adaptés à vos branches. Les variables sont lues dans l’environnement du processus. Un fichier `.env` n’est pas chargé automatiquement.

## Utiliser la CI générée

Le fichier généré définit l’image `python:3.12-slim` et installe le projet avec `python -m pip install --disable-pip-version-check .` avant les jobs. Le dépôt exécuté par le runner doit donc contenir le package Python et le manifeste.

Le fichier `.gitlab-ci.yml` du dépôt exécute les contrôles Ruff, Pylint et mypy, puis valide `infra.yml`. Il génère ensuite `.gitlab-ci-generated.yml`, le publie comme artifact et le lance comme pipeline enfant dynamique. Le job de déclenchement attend le résultat du pipeline enfant avec `strategy: mirror`, disponible à partir de GitLab 18.2.

`INFRA_DRY_RUN` vaut `true` par défaut. Pour exécuter les actions réelles, définissez cette variable à `false` au lancement du pipeline. Les étapes marquées `manual: true` restent à déclencher manuellement dans le pipeline enfant, y compris en dry run.

Le manifeste fourni utilise `DEPLOY_REGION`. Définissez cette variable dans les paramètres CI/CD du projet. Pour les actions réelles, configurez également les accès GitLab et AWX décrits plus haut. Les variables fournies au lancement du pipeline parent sont transmises au pipeline enfant.

Le fichier généré est recréé à chaque pipeline et peut être conservé uniquement comme artifact. Pour une intégration statique dans un autre projet, versionnez le fichier généré et utilisez cet include dans son `.gitlab-ci.yml`.

```yaml
include:
  - local: .gitlab-ci-generated.yml
```

Vous pouvez aussi générer directement le fichier principal.

```bash
python -m infra_to_gitlab generate infra.yml --output .gitlab-ci.yml
```

La génération remplace le fichier indiqué par `--output`. Sans cette option, la sortie est `.gitlab-ci-generated.yml`.

### Fonctionnement du dry run

```bash
python -m infra_to_gitlab generate infra.yml --output .gitlab-ci-generated.yml --dry-run
```

Le fichier CI est créé normalement et chaque commande `infra run` reçoit `--dry-run`. Les réglages de déclenchement manuel et d’activation des étapes continuent de s’appliquer.

Lors de l’exécution d’un job en dry run, la commande affiche l’identifiant, le stage, l’action et les inputs résolus. Elle n’appelle pas le handler de l’action et ne crée aucun fichier d’outputs. Les accès GitLab et AWX ne sont donc pas nécessaires pour cette simulation.

Les références à des outputs nécessitent cependant les fichiers JSON correspondants déjà présents dans `.infra-outputs/`. Une simulation ne produit pas les résultats des actions distantes. Une chaîne de jobs en dry run qui dépend de ces résultats échouera si les fichiers manquent. Les déclarations d’artifacts restent présentes dans le YAML généré, même si le dry run ne produit aucun artifact.

Les inputs résolus sont affichés dans les logs du dry run. Évitez d’y placer des secrets.

## Développement

Installez les outils de développement, puis lancez les contrôles.

```bash
python -m pip install -r requirements-dev.txt -e .
python -m ruff check .
python -m ruff format --check .
python -m pylint infra_to_gitlab.py infra_actions
python -m mypy
python -m infra_to_gitlab validate infra.yml
```

Si `make` est disponible, les raccourcis suivants regroupent les commandes courantes.

```bash
make install-dev
make check
make generate
make generate INFRA=infra.yml OUTPUT=.gitlab-ci-generated.yml
make help
```

La commande `make` seule installe le projet et génère la CI. Pour générer des jobs en dry run, utilisez la commande Python avec `--dry-run`.

### Ajouter une action

Créez un module dans `infra_actions/` et enregistrez une fonction qui reçoit un dictionnaire d’inputs et retourne un dictionnaire d’outputs sérialisable en JSON.

```python
from typing import Any

from infra_actions import register


@register("custom:hello")
def execute(inputs: dict[str, Any]) -> dict[str, Any]:
    return {"message": f"Bonjour {inputs['name']}"}
```

Les modules du package sont découverts automatiquement. Utilisez ensuite `action: custom:hello` dans le manifeste et transmettez `name` dans `inputs`.

## Résoudre les erreurs courantes

- **`Invalid manifest`** — vérifiez les champs obligatoires, les types YAML, les champs inconnus et l’unicité des `id`.
- **`Unsupported action`** — utilisez une action enregistrée. Le message liste les actions disponibles.
- **`Missing environment variable`** — renseignez la variable indiquée dans le shell ou dans les variables CI/CD.
- **`Missing outputs for step`** — vérifiez que l’étape productrice a réussi et que son fichier JSON est disponible dans le répertoire courant. En CI, utilisez un stage ultérieur et vérifiez les artifacts.
- **`Step is disabled`** — passez `enabled` à `true` pour exécuter l’étape.
- **`Expected one ... named ...`** — utilisez un nom AWX unique ou son identifiant numérique.
- **`AWX ignored launch fields`** — vérifiez les paramètres *Prompt on Launch* du template.

Pour consulter les options depuis le terminal, utilisez `infra --help`, `infra generate --help` ou `infra run --help`.
