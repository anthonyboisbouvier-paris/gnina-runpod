# GNINA GPU - RunPod Serverless

Docking moleculaire GPU via GNINA sur RunPod serverless.
Standalone, pas integre a BindX pour l'instant.

## Architecture

```
Client (BindX ou test_client.py)
  |
  | POST JSON (receptor PDB + ligands SDF + pocket center)
  v
RunPod Serverless Endpoint
  |
  | Cold start ~60s (pull image si premier appel)
  v
Docker Container (CUDA 12.1 + GNINA 1.1)
  |
  | gnina --receptor X --ligand Y --cnn_scoring rescore
  v
Resultat JSON (3 scores par molecule + SDF des poses)
```

## Fichiers

```
Dockerfile       Image Docker GNINA GPU (~2 GB)
handler.py       RunPod serverless handler
test_client.py   Script de test client
README.md        Ce fichier
```

## Deploiement

### 1. Builder l'image Docker

```bash
# Sur une machine avec Docker
cd gnina-runpod
docker build -t gnina-serverless .

# Tag pour Docker Hub (remplacer YOUR_USERNAME)
docker tag gnina-serverless YOUR_USERNAME/gnina-serverless:latest
docker push YOUR_USERNAME/gnina-serverless:latest
```

### 2. Creer l'endpoint RunPod

1. Aller sur https://www.runpod.io/console/serverless
2. "New Endpoint"
3. Container Image: YOUR_USERNAME/gnina-serverless:latest
4. GPU: RTX 3090 ou RTX 4090 (GNINA tourne sur n'importe quel GPU CUDA)
5. Min Workers: 0 (cold start ~60s mais gratuit en idle)
6. Max Workers: 1 (suffisant pour du test)
7. Idle Timeout: 5s (libere le GPU vite)
8. Flash Boot: ON (cache l'image pour cold start plus rapide)
9. Creer l'endpoint, noter l'ENDPOINT_ID

### 3. Tester

```bash
export RUNPOD_API_KEY="votre_cle"
export GNINA_ENDPOINT_ID="votre_endpoint_id"

# Test avec donnees minimales
python test_client.py

# Test avec vrais fichiers
python test_client.py \
  --receptor /path/to/protein.pdb \
  --ligand /path/to/ligands.sdf \
  --cx 10.5 --cy 20.3 --cz 15.7
```

## Cout estime

- Image pull (cold start): ~60s, gratuit
- RTX 3090: ~$0.30/heure
- Docking 50 molecules: ~2-5 min = ~$0.03
- Docking 500 molecules: ~20-30 min = ~$0.15
- Idle: $0 (min workers = 0)

## Input JSON

```json
{
  "input": {
    "receptor_pdb": "HEADER...\nATOM...\nEND\n",
    "ligand_sdf": "mol1\n...\n$$$$\nmol2\n...\n$$$$\n",
    "center_x": 10.5,
    "center_y": 20.3,
    "center_z": 15.7,
    "size_x": 25,
    "size_y": 25,
    "size_z": 25,
    "exhaustiveness": 8,
    "num_modes": 9,
    "cnn_scoring": "rescore"
  }
}
```

## Output JSON

```json
{
  "results": [
    {
      "rank": 1,
      "minimizedAffinity": -9.2,
      "CNNscore": 0.91,
      "CNNaffinity": 8.1
    }
  ],
  "docked_sdf": "...(full SDF with poses)...",
  "n_molecules": 50,
  "elapsed_seconds": 142.5,
  "gpu_used": true
}
```

## Limites

- GNINA v1.1 binaire statique : supporte CUDA mais pas de controle 
  fin sur quel GPU utiliser (prend le premier disponible)
- Timeout serverless : 600s par defaut RunPod. Pour >500 molecules,
  augmenter le timeout dans les settings de l'endpoint.
- Taille payload : RunPod limite a ~10MB. Pour >1000 molecules,
  splitter en batches cote client.
